"""The full risk report for one portfolio: a division or an uploaded file."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data
import risk
import ui
from views import common

LOSS = "#c94f4f"   # diverging poles for P&L (red = loss, blue = gain)
GAIN = "#1c5cab"
WEIGHT_COLOR = ui.SERIES[0]
RISK_COLOR = ui.SERIES[1]


# ---------- headline ----------

def pnl_kpi(a: SimpleNamespace) -> dict | None:
    if np.isnan(a.pnl) or a.pnl_cover < 0.5:
        return None
    sign = "good" if a.pnl >= 0 else "serious"
    return {"label": "Unrealised P&L", "value": ui.gbp(a.pnl, signed=True),
            "sub": ui.status(sign, ui.pct(a.pnl_pct, 1, signed=True)) + f" · {ui.pct(a.pnl_cover, 0)} has a cost"}


def kpi_items(a: SimpleNamespace, key: str | None) -> list[dict]:
    """The six headline numbers: value, volatility, beta, VaR, drawdown and yield (or Sharpe)."""
    s = common.settings()
    period = common.PERIOD_LABELS.get(s["period"], s["period"])
    st_ = a.stats
    mandate = data.DIVISIONS.get(key, {}).get("mandate", {}) if key else {}
    conc = a.conc

    beta = st_.get("Beta", np.nan)
    if "beta_range" in mandate and not np.isnan(beta):
        lo, hi = mandate["beta_range"]
        beta_sub = ui.status("good" if lo <= beta <= hi else "serious", f"Target {lo:.2f}-{hi:.2f}")
    else:
        beta_sub = f"vs {ui.esc(a.bench_name)}"

    value_sub = f"{conc['Holdings']} holdings · {ui.pct(conc['Cash'])} cash"
    pnl = pnl_kpi(a)
    if pnl and key:
        value_sub += " · P&L " + ui.status("good" if a.pnl >= 0 else "serious", ui.pct(a.pnl_pct, 1, signed=True))

    items = [
        {"label": "Value", "value": ui.gbp(a.total), "sub": value_sub},
        {"label": "Volatility", "value": ui.pct(st_.get("Volatility")), "sub": f"annualised · {period}"},
        {"label": "Beta", "value": ui.num(beta), "sub": beta_sub},
        {"label": f"{common.horizon_label()} VaR 95%", "value": ui.gbp(st_.get("VaR 95% (£)")),
         "sub": f"{ui.pct(st_.get('VaR 95%'), 2)} of value"},
        {"label": "Max drawdown", "value": ui.pct(st_.get("Max drawdown")), "sub": f"worst fall from a peak · {period}"},
    ]
    if not np.isnan(a.yield_):
        sub = f"covers {ui.pct(a.yield_cover, 0)} of holdings"
        if "yield_range" in mandate:
            lo, hi = mandate["yield_range"]
            ok = lo <= a.yield_ * 100 <= hi
            sub = ui.status("good" if ok else "warning", f"Target {lo:.0f}-{hi:.0f}%") + f" · {sub}"
        items.append({"label": "Yield", "value": ui.pct(a.yield_, 2), "sub": sub})
    else:
        items.append({"label": "Sharpe ratio", "value": ui.num(st_.get("Sharpe ratio", np.nan)),
                      "sub": f"return per unit of risk · {period}"})
    return items


def kpi_row(a: SimpleNamespace, key: str | None, accent: str | None):
    ui.kpis(kpi_items(a, key), accent)


# ---------- exposure ----------

EXPOSURES = [
    ("Sector", "Sector", "Share of value in each sector"),
    ("Broad region", "Region", "Where the businesses are based"),
    ("Asset class", "Asset class", "Shares, funds, bonds, commodities and cash"),
    ("FX exposure", "Currency", "Currency of the underlying assets"),
]


def exposure_card(h: pd.DataFrame, dim: str, title: str, sub: str, key: str):
    df = risk.split(h, dim)
    with st.container(border=True):
        ui.card_title(title, sub)
        c1, c2 = st.columns([0.95, 1.35], gap="small")
        with c1:
            ui.show(ui.donut(df, dim, ui.pct(df["Weight"].iloc[0]), str(df.index[0])), key=f"{key}-donut-{dim}")
        with c2:
            ui.legend(df, dim)


def exposure_tab(a: SimpleNamespace, key: str):
    h = a.holdings
    for row in (EXPOSURES[:2], EXPOSURES[2:]):
        cols = st.columns(2, gap="medium")
        for col, (dim, title, sub) in zip(cols, row):
            with col:
                exposure_card(h, dim, title, sub, key)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Industry", "A finer split than sector, using the division's own labels")
            ind = risk.split(h[h["Sector"] != "Cash"], "Industry")
            ind["Weight"] = ind["Value"] / a.total
            ui.show(ui.hbar(ind, "Weight", color=ui.BLUE), key=f"{key}-industry")
    with c2:
        with st.container(border=True):
            ui.card_title("Market", "Where each holding mainly trades")
            exposure_inner = risk.split(h, "Market")
            ui.show(ui.hbar(exposure_inner, "Weight", color=ui.NAVY_700), key=f"{key}-market")


# ---------- market risk ----------

def growth_chart(series: dict[str, tuple[pd.Series, str, str]], height: int = 330) -> go.Figure:
    """series: name -> (returns, colour, dash)."""
    fig = go.Figure()
    ends = []
    for name, (r, color, dash) in series.items():
        if r is None or len(r) == 0:
            continue
        g = 100 * (1 + r.fillna(0)).cumprod()
        fig.add_trace(go.Scatter(x=g.index, y=g, name=name, mode="lines",
                                 line=dict(color=color, width=2.6 if dash == "solid" else 1.8, dash=dash),
                                 hovertemplate=f"{ui.esc(name)}: %{{y:.1f}}<extra></extra>"))
        ends.append((g.index[-1], float(g.iloc[-1]), name, color))
    for x, y, name, color in ends:
        fig.add_annotation(x=x, y=y, text=f"  {y:.0f}", showarrow=False, xanchor="left", font=dict(color=ui.INK_2, size=11.5))
    fig = ui.style(fig, height, unified=True)
    fig.update_yaxes(showgrid=True, title_text="Growth of £100")
    fig.update_layout(margin=dict(l=8, r=40, t=30, b=8))
    return fig


def drawdown_chart(r: pd.Series, color: str = ui.NAVY, height: int = 250) -> go.Figure:
    dd = risk.drawdown_series(r)
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", mode="lines", line=dict(color=color, width=1.6),
                               fillcolor="rgba(1,46,88,0.12)", hovertemplate="%{y:.1%}<extra></extra>"))
    fig = ui.style(fig, height, legend=False, unified=True)
    fig.update_yaxes(tickformat=".0%", showgrid=True)
    return fig


def rolling_vol_chart(r: pd.Series, freq: str, color: str = ui.NAVY, height: int = 250) -> go.Figure:
    window = 63 if freq == "Daily" else 13
    rv = r.rolling(window).std() * np.sqrt(risk.PERIODS_PER_YEAR[freq])
    fig = go.Figure(go.Scatter(x=rv.index, y=rv, mode="lines", line=dict(color=color, width=2), hovertemplate="%{y:.1%}<extra></extra>"))
    fig = ui.style(fig, height, legend=False, unified=True)
    fig.update_yaxes(tickformat=".0%", showgrid=True, rangemode="tozero")
    return fig


def distribution_chart(r: pd.Series, var: float, height: int = 280) -> go.Figure:
    fig = go.Figure(go.Histogram(x=r, nbinsx=50, marker=dict(color=ui.BLUE_200, line=dict(color="#fff", width=1)),
                                 hovertemplate="%{x:.2%}: %{y} periods<extra></extra>"))
    fig.add_vline(x=-var, line=dict(color=LOSS, width=2, dash="dash"))
    fig.add_annotation(x=-var, y=1, yref="paper", text=f"VaR 95%: −{var:.2%}", showarrow=False, xanchor="right",
                       yanchor="top", font=dict(color=LOSS, size=12))
    fig = ui.style(fig, height, legend=False)
    fig.update_xaxes(tickformat=".1%")
    fig.update_yaxes(showgrid=True, title_text="Number of periods")
    fig.update_layout(bargap=0.05)
    return fig


def risk_tab(a: SimpleNamespace, key: str, color: str):
    if not a.stats:
        st.warning("No price history could be downloaded, so market risk can't be measured. Check the tickers in the Mandate & data tab.")
        return
    s = a.stats
    h = common.horizon_label()
    ui.metric_cards({
        "Return": [("Total return", ui.pct(s["Total return"], 1, True)), ("Annualised return", ui.pct(s["Annualised return"], 1, True)),
                   ("Sharpe ratio", ui.num(s["Sharpe ratio"])), ("Sortino ratio", ui.num(s["Sortino ratio"]))],
        "Volatility": [("Volatility (annual)", ui.pct(s["Volatility"])), ("Downside volatility", ui.pct(s["Downside volatility"])),
                       (f"Best {h.split('-')[1]}", ui.pct(s["Best period"], 2, True)), (f"Worst {h.split('-')[1]}", ui.pct(s["Worst period"], 2, True))],
        "Tail risk": [(f"{h} VaR 95%", f"{ui.gbp(s['VaR 95% (£)'])} · {ui.pct(s['VaR 95%'], 2)}"),
                      (f"{h} VaR 99%", ui.pct(s["VaR 99%"], 2)), ("CVaR 95% (average bad day)", ui.pct(s["CVaR 95%"], 2)),
                      ("1-month VaR 95%", ui.gbp(s["1-month VaR 95% (£)"])), ("Max drawdown", ui.pct(s["Max drawdown"]))],
        f"Against the {a.bench_name}": [("Beta", ui.num(s.get("Beta", np.nan))), ("Correlation", ui.num(s.get("Correlation", np.nan))),
                                         ("Tracking error", ui.pct(s.get("Tracking error", np.nan))),
                                         ("Alpha (annual)", ui.pct(s.get("Alpha (annual)", np.nan), 1, True)),
                                         ("Benchmark return", ui.pct(s.get("Benchmark return", np.nan), 1, True))],
    })
    with st.container(border=True):
        ui.card_title("Growth of £100", f"Today's holdings held for the whole period, in GBP, against the {a.bench_name}. "
                      "This isn't the division's actual track record.")
        ui.show(growth_chart({a.bench_name: (a.bench.reindex(a.port.index), ui.BENCH, "dot"), "Portfolio": (a.port, color, "solid")}), key=f"{key}-growth")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Drawdown", "How far the portfolio sat below its previous high")
            ui.show(drawdown_chart(a.port, color), key=f"{key}-dd")
    with c2:
        with st.container(border=True):
            win = "3-month" if a.freq == "Daily" else "13-week"
            ui.card_title("Rolling volatility", f"{win} window, annualised")
            ui.show(rolling_vol_chart(a.port, a.freq, color), key=f"{key}-rv")
    with st.container(border=True):
        ui.card_title("Distribution of returns", f"Each bar counts how many {h.split('-')[1]}s landed in that range. VaR marks the worst 5%.")
        ui.show(distribution_chart(a.port, s["VaR 95%"]), key=f"{key}-hist")
    ui.html('<div class="section-caption">Cash, and holdings without price history, count as zero-volatility. '
            'Past volatility is a guide, not a forecast. Holdings in different time zones close at different times, '
            'which can understate daily correlation, so try weekly returns in the sidebar to check.</div>')


# ---------- holdings ----------

def holdings_table(a: SimpleNamespace, show_division: bool = False):
    h = a.holdings.sort_values("Value invested", ascending=False)
    contrib = a.contrib
    max_w = h["Weight"].max()
    max_rs = contrib["Risk share"].clip(lower=0).max() if len(contrib) else 0
    headers = [("Holding", "l")] + ([("Division", "l")] if show_division else []) + [
        ("Sector", "l"), ("Region", "l"), ("Value", "r"), ("Weight", "l"), ("Volatility", "r"), ("Beta", "r"),
        ("Share of risk", "l"), ("P&L", "r"), ("Yield", "r")]
    rows = []
    for _, r in h.iterrows():
        t = r["Ticker"]
        vol = contrib["Volatility"].get(t, np.nan) if len(contrib) else np.nan
        rs = contrib["Risk share"].get(t, np.nan) if len(contrib) else np.nan
        if len(contrib) and t in contrib.index:
            # a ticker can appear in more than one row (e.g. two divisions): split its share by value
            same = h.loc[h["Ticker"] == t, "Weight"].sum()
            rs = rs * r["Weight"] / same if same else rs
        beta = a.betas.get(t, np.nan) if len(a.betas) else np.nan
        if pd.notna(r["Cost"]) and r["Cost"] > 0:
            p = r["Value invested"] / r["Cost"] - 1
            ink = ui.STATUS["good"][1] if p >= 0 else ui.STATUS["critical"][1]
            pnl = f'<span style="color:{ink};font-weight:600">{ui.pct(p, 1, True)}</span>'
        else:
            pnl = '<span class="muted">–</span>'
        name = f'<div class="name">{ui.esc(r["Company name"])}</div><div class="muted">{ui.esc(t) if t else "Cash"}</div>'
        cells = [name]
        if show_division:
            cells.append(ui.chip(r["Division"], ui.color_for("Division", r["Division"])))
        cells += [
            ui.esc(r["Sector"]), f'<span class="muted">{ui.esc(r["Region"])}</span>', ui.gbp(r["Value invested"]),
            ui.bar_cell(r["Weight"], max_w, WEIGHT_COLOR, ui.pct(r["Weight"])),
            ui.pct(vol) if pd.notna(vol) else '<span class="muted">–</span>',
            ui.num(beta) if pd.notna(beta) else '<span class="muted">–</span>',
            ui.bar_cell(max(rs, 0), max_rs, RISK_COLOR, ui.pct(rs)) if pd.notna(rs) else '<span class="muted">–</span>',
            pnl,
            ui.pct(r["Yield"], 2) if pd.notna(r["Yield"]) else '<span class="muted">–</span>',
        ]
        rows.append(cells)
    total = ["Total"] + ([""] if show_division else []) + ["", "", ui.gbp(a.total), ui.pct(1.0, 0), ui.pct(a.stats.get("Volatility")),
                                                         ui.num(a.stats.get("Beta", np.nan)), ui.pct(1.0, 0) if len(contrib) else "–",
                                                         ui.pct(a.pnl_pct, 1, True) if not np.isnan(a.pnl) else "–",
                                                         ui.pct(a.yield_, 2) if not np.isnan(a.yield_) else "–"]
    ui.table(headers, rows, total)


def dumbbell(contrib: pd.DataFrame, names: pd.Series, top: int = 18, height: int | None = None) -> go.Figure:
    d = contrib.sort_values("Risk share", ascending=False).head(top).iloc[::-1]
    labels = [names.get(t, t) for t in d.index]
    fig = go.Figure()
    for lab, (_, r) in zip(labels, d.iterrows()):
        fig.add_trace(go.Scatter(x=[r["Weight"], r["Risk share"]], y=[lab, lab], mode="lines",
                                 line=dict(color=ui.AXIS, width=2), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d["Weight"], y=labels, mode="markers", name="Share of money",
                             marker=dict(color=WEIGHT_COLOR, size=11, line=dict(color="#fff", width=2)),
                             hovertemplate="<b>%{y}</b><br>Share of money: %{x:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d["Risk share"], y=labels, mode="markers", name="Share of risk",
                             marker=dict(color=RISK_COLOR, size=11, symbol="diamond", line=dict(color="#fff", width=2)),
                             hovertemplate="<b>%{y}</b><br>Share of risk: %{x:.1%}<extra></extra>"))
    fig = ui.style(fig, height or max(260, 28 * len(d) + 70))
    fig.update_xaxes(tickformat=".0%", showgrid=True, zeroline=True)
    fig.update_yaxes(tickfont=dict(color=ui.INK, size=12.5), ticksuffix="  ")
    return fig


def corr_heatmap(asset: pd.DataFrame, names: pd.Series, height: int | None = None) -> go.Figure:
    corr = asset.corr()
    labels = [names.get(t, t) for t in corr.columns]
    fig = go.Figure(go.Heatmap(z=corr.values, x=labels, y=labels, zmin=-1, zmax=1, colorscale=ui.DIVERGING,
                               text=np.round(corr.values, 2), texttemplate="%{text:.2f}", textfont=dict(size=10.5),
                               hovertemplate="%{y} & %{x}: %{z:.2f}<extra></extra>", xgap=2, ygap=2,
                               colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(color=ui.INK_3))))
    fig = ui.style(fig, height or max(360, 30 * len(labels) + 120), legend=False)
    fig.update_xaxes(tickangle=-40, showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def holdings_tab(a: SimpleNamespace, key: str, show_division: bool = False):
    holdings_table(a, show_division)
    if a.contrib.empty:
        return
    names = a.holdings.drop_duplicates("Ticker").set_index("Ticker")["Company name"]
    with st.container(border=True):
        ui.card_title("Share of money vs share of risk",
                      "A diamond to the right of its dot means the holding adds more risk than its size suggests")
        ui.show(dumbbell(a.contrib, names), key=f"{key}-dumbbell")
    if len(a.asset.columns) > 1:
        with st.container(border=True):
            ui.card_title("Correlation", "How closely each pair of holdings moved together (1 = in lockstep, 0 = unrelated)")
            ui.show(corr_heatmap(a.asset, names), key=f"{key}-corr")


# ---------- stress tests ----------

def stress_tab(a: SimpleNamespace, key: str):
    if a.betas.empty:
        st.warning("Stress tests need price history for the holdings and the benchmark.")
        return
    h = a.holdings
    exp = risk.exposures(h, a.betas)
    ui.kpis([
        {"label": "Moves with the market", "value": ui.gbp(exp["beta_value"]),
         "sub": f"value × beta, or {ui.pct(exp['beta_value'] / a.total)} of the portfolio"},
        {"label": "Non-sterling assets", "value": ui.gbp(exp["foreign_value"]), "sub": f"{ui.pct(exp['foreign_value'] / a.total)} exposed to currency moves"},
        {"label": "Bond rate sensitivity", "value": ui.gbp(exp["rate_value"] / 100), "sub": "lost for every 1% rise in bond yields"},
    ])
    table = risk.stress_table(h, a.betas)
    c1, c2 = st.columns([1.15, 1], gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Scenarios", f"Estimated P&L (red = loss). Market moves use each holding's beta to the {a.bench_name}")
            d = table.iloc[::-1]
            fig = go.Figure(go.Bar(x=d["P&L"], y=d["Scenario"], orientation="h",
                                   marker=dict(color=[LOSS if v < 0 else GAIN for v in d["P&L"]], cornerradius=4),
                                   customdata=[f"{ui.gbp(v, signed=True)} ({ui.pct(p, 1, True)})" for v, p in zip(d["P&L"], d["P&L %"])],
                                   hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>"))
            fig = ui.style(fig, 380, legend=False)
            span = float(d["P&L"].abs().max()) or 1
            # the exact figures are in the table alongside, so the bars carry no labels
            fig.update_xaxes(range=[-span * 1.1, span * 1.1], zeroline=True, zerolinecolor=ui.AXIS, showticklabels=False)
            fig.update_yaxes(tickfont=dict(color=ui.INK, size=12.5), ticksuffix="  ")
            ui.show(fig, key=f"{key}-stress")
    with c2:
        rows = [[f'<span class="name">{ui.esc(r["Scenario"])}</span>', f'<span class="muted">{ui.esc(r["Assumption"])}</span>',
                 ui.gbp(r["P&L"], signed=True), ui.pct(r["P&L %"], 1, True)] for _, r in table.iterrows()]
        ui.table([("Scenario", "l"), ("Assumption", "l"), ("P&L", "r"), ("%", "r")], rows)

    ui.section("Build your own scenario", "Custom", "Move the sliders to combine a market move, a change in sterling and a change in bond yields.")
    with st.container(border=True):
        s1, s2, s3 = st.columns(3, gap="large")
        m = s1.slider("Benchmark move", -50, 30, -15, step=1, format="%d%%", key=f"{key}-m") / 100
        g = s2.slider("Sterling move (+ = stronger)", -25, 25, 0, step=1, format="%d%%", key=f"{key}-g") / 100
        y = s3.slider("Bond yields change", -300, 300, 0, step=25, format="%d bp", key=f"{key}-y")
        pnl = risk.scenario_pnl(exp, market=m, gbp=g, rate_bp=y)
        level = "good" if pnl >= 0 else ("serious" if pnl / a.total < -0.1 else "warning")
        ui.kpis([{"label": "Estimated P&L", "value": ui.gbp(pnl, signed=True),
                  "sub": ui.status(level, ui.pct(pnl / a.total, 1, True) + " of the portfolio")}])
    ui.html('<div class="section-caption">These are first-order estimates: market moves scale with beta, currency moves hit '
            'non-sterling assets in full, and rate moves use the Duration column (bonds only). Real crises also change correlations.</div>')


# ---------- mandate & data ----------

def mandate_tab(a: SimpleNamespace, key: str | None, tiers: pd.DataFrame, show_division: bool = False):
    meta = data.DIVISIONS.get(key, {}) if key else {}
    mandate = meta.get("mandate", {})
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Mandate", meta.get("source", "Rules from the division's report"))
            rows = []
            for rule in mandate.get("rules", []) or ["No mandate rules recorded."]:
                mark = ""
                if rule.lower().startswith("target beta") and "Beta" in a.stats:
                    lo, hi = mandate["beta_range"]
                    b = a.stats["Beta"]
                    mark = ui.status("good" if lo <= b <= hi else "serious", f"Now {b:.2f}")
                elif rule.lower().startswith("target dividend yield") and not np.isnan(a.yield_):
                    lo, hi = mandate["yield_range"]
                    mark = ui.status("good" if lo <= a.yield_ * 100 <= hi else "warning", f"Now {a.yield_ * 100:.2f}%")
                rows.append(f'<div class="mg-row"><span>{ui.esc(rule)}</span><span>{mark}</span></div>')
            ui.html("".join(rows))
    with c2:
        with st.container(border=True):
            ui.card_title("Data notes", "Things to know about where these numbers came from")
            notes = meta.get("data_notes", [])
            per_row = [f"{r['Company name']}: {r['Notes']}" for _, r in a.holdings.iterrows() if r["Notes"]]
            items = notes + per_row
            ui.html("".join(f'<div class="mg-row"><span>{ui.esc(n)}</span><span></span></div>' for n in items)
                    or '<div class="mg-row"><span>No notes.</span><span></span></div>')

    ui.section("Position size by market-cap tier", "Size guide", data.TIER_LIMITS["source"] + ".")
    # the page reads this toggle from st.session_state before building `tiers`
    st.toggle("Look up market caps on Yahoo for holdings without a tier", key=f"caps-{key or 'upload'}",
              help="Takes a few seconds. The Yorkshire file already has tiers from its report.")
    if tiers is None or tiers.empty:
        st.caption("No tiers yet. Turn on the market-cap lookup, or add a Tier column (1-4) to the file.")
    else:
        rows = []
        for _, r in tiers.iterrows():
            over = r["Over guide"]
            rows.append([
                f'<div class="name">{ui.esc(r["Company name"])}</div><div class="muted">{ui.esc(r["Ticker"])}</div>',
                ui.esc(data.TIER_NAMES.get(int(r["Tier"]), r["Tier"])),
                ui.gbp(r["Market cap"] / 1e6) + "m" if pd.notna(r["Market cap"]) else '<span class="muted">from report</span>',
                ui.gbp(r["Value invested"]), ui.pct(r["Weight"]), ui.pct(r["Guide max"], 2),
                ui.status("warning" if over else "good", "Above guide" if over else "Within"),
                (ui.status("warning" if r["Cost over max buy"] else "good", f"{ui.gbp(r['Cost'])} of {ui.gbp(r['Max buy'])}")
                 if pd.notna(r["Cost"]) else '<span class="muted">no cost</span>'),
            ])
        ui.table([("Holding", "l"), ("Tier", "l"), ("Market cap", "r"), ("Value", "r"), ("Weight", "r"), ("Guide max", "r"),
                  ("Weight check", "l"), ("Bought for vs max buy", "l")], rows)

    ui.section("Ticker check", "Data quality", "What Yahoo Finance returned for each ticker. A wrong name here means a wrong ticker in the file.")
    info = a.info
    rows = []
    for _, r in a.holdings[a.holdings["Ticker"] != ""].iterrows():
        t = r["Ticker"]
        i = info.loc[t] if t in info.index else None
        ok = t in a.priced
        rows.append([
            f'<div class="name">{ui.esc(r["Company name"])}</div>', ui.esc(t),
            ui.esc(i["Yahoo name"]) if i is not None else "–", ui.esc(i["Quote currency"]) if i is not None else "–",
            str(int(i["Days"])) if i is not None else "0",
            ui.status("good", "Priced") if ok else ui.status("serious", (i["Status"] if i is not None and i["Status"] != "OK" else "Too little history")),
        ])
    ui.table([("Holding", "l"), ("Ticker", "l"), ("Yahoo name", "l"), ("Currency", "l"), ("Days", "r"), ("Status", "l")], rows)


def render_tabs(a: SimpleNamespace, key: str, color: str, tiers: pd.DataFrame, division_key: str | None, show_division: bool = False):
    t1, t2, t3, t4, t5 = st.tabs(["Exposure", "Market risk", "Holdings", "Stress tests", "Mandate & data"])
    with t1:
        exposure_tab(a, key)
    with t2:
        risk_tab(a, key, color)
    with t3:
        holdings_tab(a, key, show_division)
    with t4:
        stress_tab(a, key)
    with t5:
        mandate_tab(a, division_key, tiers, show_division)
