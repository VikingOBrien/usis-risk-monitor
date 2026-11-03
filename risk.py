"""Risk maths for a table of holdings.

Plain pandas/numpy, no Streamlit, so everything here can be tested on its own.
Prices are expected in GBP, so currency moves are part of every number.
Cash, and anything without a usable price history, earns 0% with no volatility.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = {"Daily": 252, "Weekly": 52}
HORIZON = {"Daily": "1-day", "Weekly": "1-week"}
MIN_HISTORY = {"Daily": 60, "Weekly": 12}


def to_returns(prices: pd.DataFrame | pd.Series, freq: str = "Daily"):
    if prices is None or len(prices) == 0:
        return prices
    p = prices.ffill()
    if freq == "Weekly":
        p = p.resample("W-FRI").last()
    return p.pct_change(fill_method=None).iloc[1:]


def portfolio_returns(holdings: pd.DataFrame, returns: pd.DataFrame, freq: str = "Daily"):
    """Returns for each priced holding and for the whole portfolio.

    Returns (asset_returns, weights, portfolio, priced) where `weights` are each
    ticker's share of the whole portfolio and `priced` lists the tickers with
    enough history to use.
    """
    weights = holdings[holdings["Ticker"] != ""].groupby("Ticker")["Weight"].sum()
    usable = [t for t in weights.index if t in returns.columns and returns[t].notna().sum() >= MIN_HISTORY[freq]]
    weights = weights[usable]
    asset = returns[usable].fillna(0.0)
    port = asset.mul(weights, axis=1).sum(axis=1)
    return asset, weights, port, usable


def max_drawdown(r: pd.Series) -> float:
    wealth = (1 + r).cumprod()
    return float((wealth / wealth.cummax() - 1).min()) if len(r) else np.nan


def drawdown_series(r: pd.Series) -> pd.Series:
    wealth = (1 + r).cumprod()
    return wealth / wealth.cummax() - 1


def summary_stats(port: pd.Series, bench: pd.Series | None, total_value: float, risk_free: float, freq: str = "Daily") -> dict:
    ppy = PERIODS_PER_YEAR[freq]
    if port is None or len(port) < 2:
        return {}
    vol = float(port.std() * np.sqrt(ppy))
    growth = float((1 + port).prod())
    ann_ret = growth ** (ppy / len(port)) - 1
    var_hist = float(-np.percentile(port, 5))
    var_99 = float(-np.percentile(port, 1))
    tail = port[port <= -var_hist]
    cvar = float(-tail.mean()) if len(tail) else var_hist
    downside = port[port < 0].std() * np.sqrt(ppy)
    month = np.sqrt(ppy / 12)

    s = {
        "Total return": growth - 1,
        "Annualised return": ann_ret,
        "Volatility": vol,
        "Downside volatility": float(downside) if pd.notna(downside) else np.nan,
        "Sharpe ratio": (ann_ret - risk_free) / vol if vol else np.nan,
        "Sortino ratio": (ann_ret - risk_free) / downside if downside else np.nan,
        "Max drawdown": max_drawdown(port),
        "VaR 95%": var_hist,
        "VaR 99%": var_99,
        "CVaR 95%": cvar,
        "VaR 95% (£)": var_hist * total_value,
        "1-month VaR 95% (£)": var_hist * month * total_value,
        "Worst period": float(port.min()),
        "Best period": float(port.max()),
        "Positive periods": float((port > 0).mean()),
    }
    if bench is not None and len(bench) > 0:
        joined = pd.concat([port.rename("p"), bench.rename("b")], axis=1, join="inner").dropna()
        if len(joined) > MIN_HISTORY[freq] // 2:
            cov = np.cov(joined["p"], joined["b"])
            beta = cov[0, 1] / cov[1, 1]
            b_growth = float((1 + joined["b"]).prod())
            b_ann = b_growth ** (ppy / len(joined)) - 1
            s.update({
                "Beta": float(beta),
                "Correlation": float(joined["p"].corr(joined["b"])),
                "Tracking error": float((joined["p"] - joined["b"]).std() * np.sqrt(ppy)),
                "Benchmark return": b_growth - 1,
                "Benchmark volatility": float(joined["b"].std() * np.sqrt(ppy)),
                "Alpha (annual)": float(ann_ret - (risk_free + beta * (b_ann - risk_free))),
            })
    return s


def risk_contributions(asset: pd.DataFrame, weights: pd.Series, freq: str = "Daily") -> pd.DataFrame:
    """Each holding's share of the portfolio's variance (the shares add up to 100%)."""
    ppy = PERIODS_PER_YEAR[freq]
    cov = asset.cov() * ppy
    w = weights.reindex(cov.index).values
    port_var = float(w @ cov.values @ w)
    contrib = w * (cov.values @ w) / port_var if port_var > 0 else np.zeros_like(w)
    return pd.DataFrame(
        {"Weight": w, "Volatility": np.sqrt(np.diag(cov.values)), "Risk share": contrib},
        index=cov.index,
    )


def asset_betas(asset: pd.DataFrame, bench: pd.Series) -> pd.Series:
    if bench is None or len(bench) == 0 or asset.empty:
        return pd.Series(dtype=float)
    joined = asset.join(bench.rename("__b"), how="inner").dropna(subset=["__b"])
    if len(joined) < 20:
        return pd.Series(dtype=float)
    var_b = joined["__b"].var()
    return joined.drop(columns="__b").apply(lambda c: c.cov(joined["__b"]) / var_b)


def group_series(holdings: pd.DataFrame, returns: pd.DataFrame, by: str, usable) -> pd.DataFrame:
    """Return series for each group (e.g. each division), weighted by share of the whole."""
    rows = holdings[holdings["Ticker"].isin(usable)]
    out = {}
    for name, g in rows.groupby(by):
        w = g.groupby("Ticker")["Weight"].sum()
        out[name] = returns[w.index].fillna(0.0).mul(w, axis=1).sum(axis=1)
    return pd.DataFrame(out)


def group_risk(holdings: pd.DataFrame, returns: pd.DataFrame, port: pd.Series, by: str, usable) -> pd.DataFrame:
    """Each group's share of the total portfolio's variance."""
    series = group_series(holdings, returns, by, usable)
    var = port.var()
    weight = holdings.groupby(by)["Weight"].sum()
    share = series.apply(lambda c: c.cov(port) / var if var else 0.0)
    out = pd.DataFrame({"Weight": weight}).join(share.rename("Risk share")).fillna(0.0)
    return out.sort_values("Weight", ascending=False)


def standalone(series: pd.Series, total: float, weight: float, freq: str = "Daily") -> dict:
    """Stats for one group's own return series, rescaled as if it were a portfolio on its own."""
    if weight <= 0:
        return {}
    r = series / weight
    return summary_stats(r, None, total, 0.0, freq)


def concentration(holdings: pd.DataFrame) -> dict:
    w = holdings["Weight"]
    invested = holdings[holdings["Sector"] != "Cash"]["Weight"]
    hhi = float((w ** 2).sum())
    return {
        "Holdings": int((holdings["Sector"] != "Cash").sum()),
        "Largest holding": float(invested.max()) if len(invested) else 0.0,
        "Largest name": holdings.loc[invested.idxmax(), "Company name"] if len(invested) else "",
        "Top 5 weight": float(invested.nlargest(5).sum()),
        "HHI": hhi,
        "Effective holdings": 1 / hhi if hhi else np.nan,
        "Cash": float(w[holdings["Sector"] == "Cash"].sum()),
    }


def split(holdings: pd.DataFrame, by: str) -> pd.DataFrame:
    out = holdings.groupby(by)["Value invested"].sum().sort_values(ascending=False).to_frame("Value")
    out["Weight"] = out["Value"] / holdings["Value invested"].sum()
    out.index.name = by
    return out


def weighted_yield(holdings: pd.DataFrame):
    """Value-weighted yield over the holdings that have one, and how much of the fund that covers.

    Cash counts as covered with a 0% yield.
    """
    inv = holdings[holdings["Sector"] != "Cash"]
    has = inv[inv["Yield"].notna()]
    if has.empty:
        return np.nan, 0.0
    covered = has["Value invested"].sum() / inv["Value invested"].sum()
    y = float((has["Yield"] * has["Value invested"]).sum() / has["Value invested"].sum())
    return y, float(covered)


def unrealised_pnl(holdings: pd.DataFrame):
    inv = holdings[(holdings["Sector"] != "Cash") & holdings["Cost"].notna()]
    if inv.empty:
        return np.nan, np.nan, 0.0
    pnl = float((inv["Value invested"] - inv["Cost"]).sum())
    pct = pnl / float(inv["Cost"].sum())
    covered = inv["Value invested"].sum() / holdings.loc[holdings["Sector"] != "Cash", "Value invested"].sum()
    return pnl, pct, float(covered)


# ---------- stress tests ----------

def exposures(holdings: pd.DataFrame, betas: pd.Series) -> dict:
    """The three £ sensitivities the stress tests use."""
    by_ticker = holdings[holdings["Ticker"] != ""].groupby("Ticker")["Value invested"].sum()
    return {
        # £ that moves one-for-one with the benchmark (value x beta)
        "beta_value": float((by_ticker * betas.reindex(by_ticker.index).fillna(0.0)).sum()),
        # £ held in assets whose underlying currency isn't sterling
        "foreign_value": float(holdings.loc[holdings["FX exposure"] != "GBP", "Value invested"].sum()),
        # £ x years of duration: the loss for each 1% rise in bond yields is 1% of this
        "rate_value": float((holdings["Value invested"] * holdings["Duration"].fillna(0.0)).sum()),
    }


def scenario_pnl(exp: dict, market: float = 0.0, gbp: float = 0.0, rate_bp: float = 0.0) -> float:
    """£ P&L for a benchmark move, a sterling move (+ = GBP stronger) and a change in yields."""
    return exp["beta_value"] * market + exp["foreign_value"] * (1 / (1 + gbp) - 1) - exp["rate_value"] * rate_bp / 10000


SCENARIOS = [
    ("Market correction", "Benchmark -10%", dict(market=-0.10)),
    ("Bear market", "Benchmark -20%", dict(market=-0.20)),
    ("2008-style crash", "Benchmark -40%", dict(market=-0.40)),
    ("Rally", "Benchmark +10%", dict(market=0.10)),
    ("Sterling strengthens", "GBP +10% against other currencies", dict(gbp=0.10)),
    ("Sterling weakens", "GBP -10% against other currencies", dict(gbp=-0.10)),
    ("Rates up", "Bond yields +1%", dict(rate_bp=100)),
    ("Rates down", "Bond yields -1%", dict(rate_bp=-100)),
    ("Stagflation", "Benchmark -15%, yields +1%, GBP -5%", dict(market=-0.15, rate_bp=100, gbp=-0.05)),
]


def stress_table(holdings: pd.DataFrame, betas: pd.Series) -> pd.DataFrame:
    """Rough £ impact of simple scenarios on the holdings."""
    exp = exposures(holdings, betas)
    total = holdings["Value invested"].sum()
    rows = [(name, desc, scenario_pnl(exp, **kw)) for name, desc, kw in SCENARIOS]
    out = pd.DataFrame(rows, columns=["Scenario", "Assumption", "P&L"])
    out["P&L %"] = out["P&L"] / total
    return out


def tier_check(holdings: pd.DataFrame, limits: dict, caps: pd.Series | None = None) -> pd.DataFrame:
    """Position size against the market-cap tier guide.

    Uses the Tier column when the file has one, otherwise looks the market cap up.
    """
    h = holdings[(holdings["Asset class"] == "Equity") & (holdings["Sector"] != "Cash")].copy()
    if h.empty:
        return pd.DataFrame()
    tiers = h["Tier"].copy()
    if caps is not None and len(caps):
        cap = h["Ticker"].map(caps)
        looked_up = pd.cut(cap, [-np.inf, 250e6, 500e6, 1e9, np.inf], labels=[4, 3, 2, 1]).astype(float)
        tiers = tiers.fillna(looked_up)
        h["Market cap"] = cap
    else:
        h["Market cap"] = np.nan
    h["Tier"] = tiers
    h = h[h["Tier"].notna()].copy()
    if h.empty:
        return pd.DataFrame()
    h["Tier"] = h["Tier"].astype(int)
    h["Guide max"] = h["Tier"].astype(str).map({k: float(v) for k, v in limits["max_weight"].items()})
    h["Max buy"] = h["Tier"].astype(str).map({k: float(v) for k, v in limits["max_buy"].items()})
    h["Over guide"] = h["Weight"] > h["Guide max"]
    h["Cost over max buy"] = h["Cost"] > h["Max buy"]
    cols = ["Company name", "Ticker", "Tier", "Market cap", "Value invested", "Weight", "Guide max", "Over guide", "Cost", "Max buy", "Cost over max buy"]
    return h[cols].sort_values(["Over guide", "Weight"], ascending=[False, False])
