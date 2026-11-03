"""Price downloads from Yahoo Finance, converted to GBP.

Every ticker is downloaded on its own (in parallel) because Yahoo reports each
one's quote currency alongside its history. That currency, not a guess from the
ticker, decides how prices are converted to GBP.
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import ssl
import sys
import tempfile
import threading

import numpy as np
import pandas as pd
import yfinance as yf

BENCHMARKS = {
    "FTSE All-Share": "^FTAS",
    "FTSE 100": "^FTSE",
    "FTSE 250": "^FTMC",
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "MSCI World (URTH)": "URTH",
}

# Yahoo FX pairs that turn one unit of a currency into GBP.
FX_PAIRS = {
    c: f"{c}GBP=X"
    for c in ("USD", "EUR", "CHF", "JPY", "HKD", "TWD", "CAD", "AUD", "SEK", "DKK", "NOK", "KRW", "INR", "SGD", "CNY", "ZAR")
}

SUFFIX_CURRENCY = {
    ".L": "GBp", ".DE": "EUR", ".PA": "EUR", ".AS": "EUR", ".MI": "EUR", ".MC": "EUR", ".BR": "EUR",
    ".IR": "EUR", ".SW": "CHF", ".T": "JPY", ".HK": "HKD", ".TW": "TWD", ".TO": "CAD", ".AX": "AUD",
}

_local = threading.local()
_bundle_path = None
_bundle_lock = threading.Lock()


def _ca_bundle():
    """Python's own certificates plus the Windows certificate store.

    Antivirus HTTPS scanning (Avast, AVG, ESET...) re-signs every certificate
    with its own root. Windows trusts that root but Python's bundle doesn't, so
    downloads fail with "unable to get local issuer certificate" unless the
    Windows store is included.
    """
    global _bundle_path
    with _bundle_lock:
        if _bundle_path is None:
            import certifi

            pems = [open(certifi.where(), encoding="utf-8").read()]
            for store in ("ROOT", "CA"):
                for der, encoding, _trust in ssl.enum_certificates(store):
                    if encoding == "x509_asn":
                        pems.append(ssl.DER_cert_to_PEM_cert(der))
            path = os.path.join(tempfile.gettempdir(), "usis_risk_ca_bundle.pem")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(pems))
            _bundle_path = path
    return _bundle_path


def _session():
    """One curl_cffi session per thread (sessions are not shared across threads)."""
    if getattr(_local, "session", None) is None:
        from curl_cffi import requests as creq

        verify = _ca_bundle() if sys.platform == "win32" else True
        _local.session = creq.Session(impersonate="chrome", verify=verify)
    return _local.session


def guess_currency(ticker: str) -> str:
    for suffix, ccy in SUFFIX_CURRENCY.items():
        if ticker.upper().endswith(suffix):
            return ccy
    return "USD"


def _history(symbol: str, period: str):
    try:
        t = yf.Ticker(symbol, session=_session())
        hist = t.history(period=period, auto_adjust=True)
        meta = t.history_metadata or {}
    except Exception as e:  # network errors, delisted tickers, rate limits
        return symbol, None, {"error": str(e)[:200]}
    if hist is None or hist.empty or "Close" not in hist:
        return symbol, None, meta
    close = hist["Close"].astype(float)
    idx = close.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    close.index = idx.normalize()
    close = close[~close.index.duplicated(keep="last")].dropna()
    return symbol, close, meta


def clean_glitches(close: pd.Series) -> tuple[pd.Series, int]:
    """Repair the two kinds of bad data Yahoo serves for small UK stocks.

    1. Pence/pound flips: a run of prices 100x too small or too large (a one-day
       move of roughly x100 or /100 that later flips back).
    2. One-day bad prints: a spike of more than 3x (or below a third) that
       reverses the next day.
    Returns the cleaned series and how many fixes were made.
    """
    p = close.astype(float).copy()
    fixes = 0
    vals = p.values
    factor = 1.0
    out = np.empty_like(vals)
    out[0] = vals[0]
    for i in range(1, len(vals)):
        ratio = vals[i] / vals[i - 1] if vals[i - 1] else 1.0
        if 50 <= ratio <= 200:
            factor /= 100
            fixes += 1
        elif 1 / 200 <= ratio <= 1 / 50:
            factor *= 100
            fixes += 1
        out[i] = vals[i] * factor
    # the run that was wrongly scaled is whichever side disagrees with the latest price
    if factor != 1.0:
        out = out / factor
    p = pd.Series(out, index=p.index)

    ratio = p / p.shift(1)
    nxt = p.shift(-1) / p
    spike = ((ratio > 3) & (nxt < 1 / 3)) | ((ratio < 1 / 3) & (nxt > 3))
    if spike.any():
        fixes += int(spike.sum())
        p[spike] = np.nan
        p = p.ffill()
    return p, fixes


def _download(symbols, period):
    if not symbols:
        return []
    with cf.ThreadPoolExecutor(max_workers=min(8, len(symbols))) as pool:
        return list(pool.map(lambda s: _history(s, period), symbols))


def fetch_prices(symbols, period: str = "1y", currency_hints: dict | None = None):
    """Download daily closes and convert each to GBP.

    Returns (prices, info). `prices` has one GBP column per ticker that loaded.
    `info` has one row per requested ticker: Yahoo's name, quote currency,
    number of days of history and a status message.
    """
    hints = {k: v for k, v in (currency_hints or {}).items() if v}
    symbols = sorted({s.strip().upper() for s in symbols if s and str(s).strip()})
    results = _download(symbols, period)

    closes, info = {}, {}
    for sym, close, meta in results:
        ccy = meta.get("currency") or hints.get(sym) or guess_currency(sym)
        row = {
            "Yahoo name": meta.get("longName") or meta.get("shortName") or "",
            "Quote currency": ccy,
            "Type": (meta.get("instrumentType") or "").title(),
            "Days": 0,
            "Status": "OK",
        }
        if close is None or close.empty:
            row["Status"] = "No data - check the ticker" if "error" not in meta else f"Download failed: {meta['error']}"
        else:
            close, fixes = clean_glitches(close)
            closes[sym] = close
            row["Days"] = int(close.size)
            row["Fixes"] = fixes
            if fixes:
                row["Status"] = f"OK, {fixes} bad price{'s' if fixes > 1 else ''} repaired"
        info[sym] = row

    # FX needed for the currencies that turned up
    def norm(c):
        return "GBP" if c in ("GBp", "GBX", "GBP") else c.upper()

    needed = sorted({norm(info[s]["Quote currency"]) for s in closes} - {"GBP"})
    fx = {}
    for sym, close, _meta in _download([FX_PAIRS[c] for c in needed if c in FX_PAIRS], period):
        if close is not None:
            fx[sym] = close

    if not closes:
        return pd.DataFrame(), pd.DataFrame.from_dict(info, orient="index")

    raw = pd.DataFrame(closes).sort_index().ffill()
    prices = {}
    for sym in raw.columns:
        ccy = info[sym]["Quote currency"]
        series = raw[sym]
        if ccy in ("GBp", "GBX"):
            series = series / 100.0
        elif norm(ccy) != "GBP":
            pair = FX_PAIRS.get(norm(ccy))
            if pair not in fx:
                info[sym]["Status"] = f"No {norm(ccy)}->GBP rate, left out"
                continue
            rate = fx[pair].reindex(raw.index.union(fx[pair].index)).ffill().reindex(raw.index)
            series = series * rate
        prices[sym] = series

    prices = pd.DataFrame(prices)
    # A price is only valid from the first day the ticker actually traded.
    for sym in prices.columns:
        first = closes[sym].index.min()
        prices.loc[prices.index < first, sym] = np.nan
    return prices, pd.DataFrame.from_dict(info, orient="index")


def fetch_market_caps(symbols, fx_period: str = "5d") -> pd.Series:
    """Latest market capitalisation in GBP, or NaN when Yahoo doesn't have one."""
    symbols = sorted({s for s in symbols if s})

    def one(sym):
        try:
            fi = yf.Ticker(sym, session=_session()).fast_info
            return sym, fi.get("marketCap"), fi.get("currency")
        except Exception:
            return sym, None, None

    with cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(symbols)))) as pool:
        raw = list(pool.map(one, symbols))

    rates = {"GBP": 1.0}
    for ccy in sorted({c.upper() for _, _, c in raw if c and c not in ("GBp", "GBX")} - {"GBP"}):
        pair = FX_PAIRS.get(ccy)
        if pair:
            _, close, _ = _history(pair, fx_period)
            if close is not None and not close.empty:
                rates[ccy] = float(close.iloc[-1])

    out = {}
    for sym, cap, ccy in raw:
        if not cap or not ccy:
            out[sym] = np.nan
        elif ccy in ("GBp", "GBX"):
            out[sym] = cap / 100.0
        else:
            out[sym] = cap * rates[ccy.upper()] if ccy.upper() in rates else np.nan
    return pd.Series(out, dtype=float)
