"""Shared pieces for every page: settings, cached downloads, analysis and flags."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import streamlit as st

import data
import market
import risk
import ui

DEFAULTS = {"period": "1y", "freq": "Daily", "benchmark": "Division default", "rf": 0.04}
PERIOD_LABELS = {"6mo": "6 months", "1y": "1 year", "2y": "2 years", "3y": "3 years", "5y": "5 years"}


def settings() -> dict:
    return {**DEFAULTS, **st.session_state.get("settings", {})}


def benchmark_name(division_key: str | None = None) -> str:
    choice = settings()["benchmark"]
    if choice != "Division default":
        return choice
    if division_key and division_key in data.DIVISIONS:
        return data.DIVISIONS[division_key]["benchmark"]
    return "FTSE All-Share"


# ---------- cached data ----------

@st.cache_data(ttl=600, show_spinner=False)
def ltf_holdings() -> pd.DataFrame:
    return data.load_ltf()


@st.cache_data(ttl=600, show_spinner=False)
def division_raw(key: str) -> pd.DataFrame:
    return data.read_division(key)


@st.cache_data(ttl=3600, show_spinner=False)
def _prices(symbols: tuple, period: str, hints: tuple):
    return market.fetch_prices(list(symbols), period, dict(hints))


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def market_caps(symbols: tuple) -> pd.Series:
    return market.fetch_market_caps(list(symbols))


def _hints(h: pd.DataFrame) -> dict:
    d = h[(h["Ticker"] != "") & (h["Currency"] != "")]
    return dict(zip(d["Ticker"], d["Currency"]))


def market_data(holdings: pd.DataFrame | None = None):
    """GBP prices for every LTF holding and benchmark, plus any extra tickers in `holdings`.

    The LTF download is shared by every page (one cache entry), and extra tickers
    from an upload or a what-if edit are fetched on their own.
    """
    period = settings()["period"]
    ltf = ltf_holdings()
    base = sorted(set(ltf["Ticker"]) - {""} | set(market.BENCHMARKS.values()))
    with st.spinner(f"Downloading {PERIOD_LABELS.get(period, period)} of prices for {len(base)} tickers…"):
        prices, info = _prices(tuple(base), period, tuple(sorted(_hints(ltf).items())))
    if holdings is not None:
        extra = sorted(set(holdings["Ticker"]) - set(base) - {""})
        if extra:
            with st.spinner(f"Downloading prices for {len(extra)} more tickers…"):
                p2, i2 = _prices(tuple(extra), period, tuple(sorted(_hints(holdings).items())))
            prices = prices.join(p2, how="outer") if not prices.empty else p2
            info = pd.concat([info, i2])
    return prices, info


# ---------- analysis ----------

def analyse(holdings: pd.DataFrame, prices: pd.DataFrame, info: pd.DataFrame, bench_name: str) -> SimpleNamespace:
    s = settings()
    freq = s["freq"]
    total = float(holdings["Value invested"].sum())
    bench_symbol = market.BENCHMARKS[bench_name]
    tickers = [t for t in holdings["Ticker"].unique() if t and t in prices.columns]
    cols = tickers + ([bench_symbol] if bench_symbol in prices.columns else [])
    rets = risk.to_returns(prices[cols], freq) if cols else pd.DataFrame()

    out = SimpleNamespace(holdings=holdings, total=total, freq=freq, bench_name=bench_name, priced=[],
                          stats={}, contrib=pd.DataFrame(), betas=pd.Series(dtype=float), port=pd.Series(dtype=float),
                          asset=pd.DataFrame(), bench=pd.Series(dtype=float), weights=pd.Series(dtype=float),
                          info=info, unpriced=pd.DataFrame(), returns=rets)
    out.conc = risk.concentration(holdings)
    out.yield_, out.yield_cover = risk.weighted_yield(holdings)
    out.pnl, out.pnl_pct, out.pnl_cover = risk.unrealised_pnl(holdings)

    if not rets.empty:
        bench = rets[bench_symbol] if bench_symbol in rets else pd.Series(dtype=float)
        asset, weights, port, usable = risk.portfolio_returns(holdings, rets.drop(columns=[bench_symbol], errors="ignore"), freq)
        out.asset, out.weights, out.port, out.priced, out.bench = asset, weights, port, usable, bench
        if usable:
            out.stats = risk.summary_stats(port, bench, total, s["rf"], freq)
            out.contrib = risk.risk_contributions(asset, weights, freq) if len(usable) > 1 else pd.DataFrame(
                {"Weight": weights, "Volatility": asset.std() * np.sqrt(risk.PERIODS_PER_YEAR[freq]), "Risk share": 1.0})
            out.betas = risk.asset_betas(asset, bench)

    has_ticker = holdings[holdings["Ticker"] != ""]
    missing = has_ticker[~has_ticker["Ticker"].isin(out.priced)].copy()
    if not missing.empty:
        missing["Reason"] = [
            (info.loc[t, "Status"] if t in info.index and info.loc[t, "Status"] != "OK" else "Not enough price history")
            for t in missing["Ticker"]
        ]
    out.unpriced = missing
    return out


def horizon_label() -> str:
    return risk.HORIZON[settings()["freq"]]


# ---------- flags ----------

GUIDES = {"holding": 0.10, "holding_high": 0.15, "sector": 0.40, "sector_high": 0.50, "region": 0.60, "cash_high": 0.15, "tier4": 0.30}


def division_flags(key: str | None, a: SimpleNamespace, name: str, color: str | None = None, tiers: pd.DataFrame | None = None,
                   include_notes: bool = True) -> list[dict]:
    """Watchlist items for one division (or an uploaded portfolio when key is None)."""
    h = a.holdings
    meta = data.DIVISIONS.get(key, {}) if key else {}
    mandate = meta.get("mandate", {})
    out = []

    def add(level, title, detail=""):
        out.append({"level": level, "title": title, "detail": detail, "division": name, "color": color})

    invested = h[h["Sector"] != "Cash"]
    for _, r in invested.sort_values("Weight", ascending=False).iterrows():
        # a fund, bond or ETF is already diversified, so it gets twice the room of a single company
        scale = 1 if r["Asset class"] == "Equity" else 2
        kind = "single company" if scale == 1 else "single fund or bond"
        if r["Weight"] > GUIDES["holding_high"] * scale:
            add("serious", f"{r['Company name']} is {ui.pct(r['Weight'])} of {name}",
                f"That's more than {GUIDES['holding_high'] * scale:.0%} in a {kind}.")
        elif r["Weight"] > GUIDES["holding"] * scale:
            add("warning", f"{r['Company name']} is {ui.pct(r['Weight'])} of {name}",
                f"That's above the {GUIDES['holding'] * scale:.0%} guide for a {kind}.")

    total = h["Value invested"].sum()
    equity_like = invested[~invested["Sector"].isin(["Fixed Income", "Commodities", "Diversified"])]
    for sec, w in (equity_like.groupby("Sector")["Value invested"].sum() / total).sort_values(ascending=False).items():
        if w > GUIDES["sector_high"]:
            add("serious", f"{sec} is {ui.pct(w)} of {name}", "More than half the division is in one sector.")
        elif w > GUIDES["sector"]:
            add("warning", f"{sec} is {ui.pct(w)} of {name}", "That's above the 40% sector guide.")

    if not meta.get("regional"):  # a regional mandate (Yorkshire) is meant to be concentrated
        regions = h[h["Broad region"] != "Cash"].groupby("Broad region")["Value invested"].sum() / total
        for reg, w in regions.items():
            if w > GUIDES["region"]:
                add("warning", f"{reg} is {ui.pct(w)} of {name}", "That's above the 60% single-region guide, so the division leans heavily on one economy.")

    cash = a.conc["Cash"]
    if cash > GUIDES["cash_high"]:
        add("info", f"{ui.pct(cash)} of {name} is in cash", "A large cash balance holds back returns but cushions falls.")

    beta = a.stats.get("Beta")
    if "beta_range" in mandate and beta is not None and not np.isnan(beta):
        lo, hi = mandate["beta_range"]
        if not lo <= beta <= hi:
            add("serious", f"Beta is {ui.num(beta)}, outside the {lo:.2f}-{hi:.2f} target",
                f"Measured against the {a.bench_name} over the chosen period.")
    if "yield_range" in mandate and not np.isnan(a.yield_):
        lo, hi = mandate["yield_range"]
        y = a.yield_ * 100
        if not lo <= y <= hi:
            add("warning", f"Yield is {y:.2f}%, outside the {lo:.0f}-{hi:.0f}% target",
                f"Weighted over the {ui.pct(a.yield_cover, 0)} of holdings that report a yield.")

    if tiers is not None and not tiers.empty:
        over = tiers[tiers["Over guide"]]
        if len(over):
            names = ", ".join(f"{r['Company name']} ({ui.pct(r['Weight'])})" for _, r in over.head(5).iterrows())
            more = f" and {len(over) - 5} more" if len(over) > 5 else ""
            bought_ok = over["Cost"].notna().all() and not over["Cost over max buy"].any()
            note = " Each was bought within its £ max-buy limit, so the guide is being passed through growth or a small division size." if bought_ok else ""
            add("warning", f"{len(over)} position{'s' if len(over) > 1 else ''} above the tier size guide", f"{names}{more}.{note}")
        t4 = tiers.loc[tiers["Tier"] == 4, "Value invested"].sum() / h["Value invested"].sum()
        if t4 > GUIDES["tier4"]:
            add("warning", f"Tier 4 (< £250m) companies are {ui.pct(t4)} of {name}", "Microcaps are less liquid and can fall hard in a sell-off.")

    if not a.contrib.empty:
        hot = a.contrib[(a.contrib["Risk share"] > 2 * a.contrib["Weight"]) & (a.contrib["Risk share"] > 0.08)]
        names = h.drop_duplicates("Ticker").set_index("Ticker")["Company name"]
        for t, r in hot.iterrows():
            add("info", f"{names.get(t, t)} drives {ui.pct(r['Risk share'])} of {name}'s risk",
                f"That's from only {ui.pct(r['Weight'])} of the money, because it's volatile or moves with the rest of the division.")

    if len(a.unpriced):
        add("warning", f"{len(a.unpriced)} holding{'s' if len(a.unpriced) > 1 else ''} without usable prices",
            ", ".join(f"{r['Company name']} ({r['Ticker']})" for _, r in a.unpriced.iterrows()) + ". They count as zero-risk until fixed.")

    if include_notes:
        for note in meta.get("data_notes", []):
            add("info", "Data note", note)

    order = {"critical": 0, "serious": 1, "warning": 2, "info": 3}
    return sorted(out, key=lambda f: order[f["level"]])


def tier_table(holdings: pd.DataFrame, lookup: bool) -> pd.DataFrame:
    caps = None
    if lookup:
        need = tuple(sorted(holdings.loc[(holdings["Asset class"] == "Equity") & holdings["Tier"].isna() & (holdings["Ticker"] != ""), "Ticker"]))
        if need:
            with st.spinner(f"Looking up market caps for {len(need)} companies…"):
                caps = market_caps(need)
    return risk.tier_check(holdings, data.TIER_LIMITS, caps)
