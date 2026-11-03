"""The whole Long Term Fund on one page."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data
import risk
import ui
from views import common, registry, report


def heat_by_division(h: pd.DataFrame, dim: str, height: int | None = None) -> go.Figure:
    """Rows = categories, columns = divisions, cells = share of that division."""
    tab = h.pivot_table(index=dim, columns="Division", values="Value invested", aggfunc="sum", fill_value=0)
    tab = tab / tab.sum()
    tab = tab.loc[ui.slot_order(dim, list(tab.index))]
    divisions = [m["name"] for m in data.DIVISIONS.values() if m["name"] in tab.columns]
    tab = tab[divisions]
    z = tab.values
    zmax = max(0.5, float(z.max()))
    fig = go.Figure(go.Heatmap(
        z=z, x=divisions, y=list(tab.index), zmin=0, zmax=zmax,
        colorscale=[[i / (len(ui.SEQ_BLUE) - 1), c] for i, c in enumerate(ui.SEQ_BLUE)],
        xgap=3, ygap=3, showscale=False, hovertemplate="<b>%{y}</b> in %{x}: %{z:.1%}<extra></extra>",
    ))
    for i, label in enumerate(tab.index):  # one label per cell, light text on the darker cells
        for j, div in enumerate(divisions):
            v = z[i, j]
            if v > 0:
                fig.add_annotation(x=div, y=label, text=f"{v * 100:.0f}%", showarrow=False,
                                   font=dict(size=12, color="#ffffff" if v / zmax > 0.55 else ui.INK))
    fig = ui.style(fig, height or max(240, 34 * len(tab) + 60), legend=False)
    fig.update_xaxes(side="top", tickfont=dict(color=ui.INK, size=12.5), showgrid=False)
    fig.update_yaxes(autorange="reversed", tickfont=dict(color=ui.INK, size=12.5), ticksuffix="  ", showgrid=False)
    return fig


def division_card(key: str, a, ltf_total: float):
    meta = data.DIVISIONS[key]
    h = a.holdings
    top_sector = risk.split(h[h["Sector"] != "Cash"], "Sector")
    sector_txt = f"{top_sector.index[0]} {ui.pct(top_sector['Value'].iloc[0] / a.total)}" if len(top_sector) else "–"
    s = a.stats
    rows = [("Share of LTF", ui.pct(a.total / ltf_total)), ("Volatility", ui.pct(s.get("Volatility"))),
            (f"{common.horizon_label()} VaR 95%", ui.gbp(s.get("VaR 95% (£)"))), ("Beta", ui.num(s.get("Beta", np.nan))),
            ("Largest sector", sector_txt), ("Holdings", str(a.conc["Holdings"]))]
    body = "".join(f'<div class="mg-row"><span>{ui.esc(k)}</span><span>{ui.esc(v)}</span></div>' for k, v in rows)
    ui.html(
        f'<div class="kpi" style="--accent:{meta["color"]};padding-bottom:6px">'
        f'<div class="kpi-label"><span class="chip"><span class="dot" style="background:{meta["color"]}"></span>{ui.esc(meta["name"])}</span></div>'
        f'<div class="kpi-value">{ui.gbp(a.total)}</div><div class="kpi-sub" style="min-height:52px">{ui.esc(meta["tagline"])}</div>'
        f'<div style="margin-top:10px">{body}</div></div>'
    )
    if key in registry.PAGES:
        st.page_link(registry.PAGES[key], label=f"Open the {meta['name']} report", icon=":material/arrow_forward:")


def render():
    ltf = common.ltf_holdings()
    prices, info = common.market_data()
    bench = common.benchmark_name()
    a = common.analyse(ltf, prices, info, bench)
    by_div = {k: common.analyse(ltf[ltf["Division key"] == k].assign(Weight=lambda d: d["Division weight"]), prices, info,
                                common.benchmark_name(k)) for k in data.DIVISIONS}
    total = a.total
    s = a.stats
    n_hold = int((ltf["Sector"] != "Cash").sum())
    period = common.PERIOD_LABELS.get(common.settings()["period"])

    pills = [ui.pill(m["name"], m["color"]) + f" · {ui.gbp(by_div[k].total)}" for k, m in data.DIVISIONS.items()]
    side = (f'<div class="lbl">Long Term Fund value</div><div class="big">{ui.gbp(total)}</div>'
            f'<div class="sub">{n_hold} holdings across 4 divisions</div>')
    ui.hero("Twikker Fund · Long Term Fund", "Risk Monitor",
            "Exposure, volatility, value at risk, stress tests and mandate checks for the Defensive, Growth, Income and "
            "Yorkshire divisions, all in sterling and all in one place.", pills, side)

    # diversification: how much lower LTF volatility is than the divisions' volatilities added up
    div_risk = pd.DataFrame()
    benefit = np.nan
    if a.priced:
        series = risk.group_series(ltf, a.returns, "Division", a.priced)
        ppy = risk.PERIODS_PER_YEAR[a.freq]
        standalone_sum = float((series.std() * np.sqrt(ppy)).sum())
        benefit = 1 - s["Volatility"] / standalone_sum if standalone_sum else np.nan
        div_risk = risk.group_risk(ltf, a.returns, a.port, "Division", a.priced)

    report.kpi_row(a, None, ui.NAVY)
    second = [
        {"label": "Diversification benefit", "value": ui.pct(benefit),
         "sub": "lower volatility than the four divisions added up"},
        {"label": "Largest position", "value": ui.pct(a.conc["Largest holding"]), "sub": ui.esc(a.conc["Largest name"])},
        {"label": "Top 5 positions", "value": ui.pct(a.conc["Top 5 weight"]), "sub": f"effective holdings: {a.conc['Effective holdings']:.0f}"},
        {"label": "Non-sterling assets", "value": ui.pct(ltf.loc[ltf["FX exposure"] != "GBP", "Weight"].sum()),
         "sub": "value exposed to currency moves"},
        {"label": "Sharpe ratio", "value": ui.num(s.get("Sharpe ratio", np.nan)), "sub": f"over {period}"},
    ]
    pnl = report.pnl_kpi(a)
    if pnl:
        second.append(pnl)
    ui.kpis(second, ui.NAVY_700, cols=6)

    # ---------- divisions ----------
    ui.section("The four divisions", "Allocation", "How the LTF is split, and how much of its risk each division carries.")
    c1, c2 = st.columns([1, 1.25], gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Value by division")
            df = risk.split(ltf, "Division")
            d1, d2 = st.columns([0.95, 1.35], gap="small")
            with d1:
                ui.show(ui.donut(df, "Division", ui.gbp(total / 1000, 0) + "k", "total value"), key="ov-div-donut")
            with d2:
                ui.legend(df, "Division")
    with c2:
        with st.container(border=True):
            ui.card_title("Share of money vs share of risk", "A division whose diamond sits right of its dot carries more risk than its size")
            if not div_risk.empty:
                names = pd.Series({n: n for n in div_risk.index})
                ui.show(report.dumbbell(div_risk, names, height=250), key="ov-div-dumbbell")
            else:
                st.caption("Needs price data.")

    cols = st.columns(4, gap="small")
    for col, key in zip(cols, data.DIVISIONS):
        with col:
            division_card(key, by_div[key], total)

    # ---------- exposure ----------
    ui.section("Exposure across the LTF", "Exposure",
               "Left: the whole fund. Right: each division's split, so you can see who is driving each exposure.")
    tabs = st.tabs(["Sector", "Region", "Asset class", "Currency", "Market"])
    for tab, (dim, title) in zip(tabs, [("Sector", "Sector"), ("Broad region", "Region"), ("Asset class", "Asset class"),
                                        ("FX exposure", "Currency"), ("Market", "Market")]):
        with tab:
            df = risk.split(ltf, dim)
            c1, c2 = st.columns([1, 1.1], gap="medium")
            with c1:
                with st.container(border=True):
                    ui.card_title(f"{title}: whole LTF")
                    d1, d2 = st.columns([0.95, 1.35], gap="small")
                    with d1:
                        ui.show(ui.donut(df, dim, ui.pct(df["Weight"].iloc[0]), str(df.index[0])), key=f"ov-donut-{dim}")
                    with d2:
                        ui.legend(df, dim)
            with c2:
                with st.container(border=True):
                    ui.card_title(f"{title} by division", "Each column adds up to 100% of that division")
                    ui.show(heat_by_division(ltf, dim), key=f"ov-heat-{dim}")

    # ---------- watchlist ----------
    ui.section("Watchlist", "Risk flags", "Everything the checks picked up across the four divisions, most serious first.")
    all_flags, notes = [], []
    for key, m in data.DIVISIONS.items():
        tiers = common.tier_table(by_div[key].holdings, lookup=False)
        f = common.division_flags(key, by_div[key], m["name"], m["color"], tiers, include_notes=True)
        all_flags += [x for x in f if x["title"] != "Data note"]
        notes += [x for x in f if x["title"] == "Data note"]
    order = {"critical": 0, "serious": 1, "warning": 2, "info": 3}
    all_flags.sort(key=lambda f: order[f["level"]])
    ui.flags(all_flags[:10])
    if len(all_flags) > 10:
        with st.expander(f"{len(all_flags) - 10} more flags"):
            ui.flags(all_flags[10:])
    with st.expander(f"Data notes from the division reports ({len(notes)})"):
        ui.flags(notes)

    # ---------- positions ----------
    ui.section("Positions", "Holdings", "The biggest positions in the LTF, and the ones that add the most risk.")
    c1, c2 = st.columns(2, gap="medium")
    inv = ltf[ltf["Sector"] != "Cash"].sort_values("Value invested", ascending=False)
    with c1:
        rows = [[f'<div class="name">{ui.esc(r["Company name"])}</div><div class="muted">{ui.esc(r["Ticker"])}</div>',
                 ui.chip(r["Division"], ui.color_for("Division", r["Division"])), ui.gbp(r["Value invested"]),
                 ui.bar_cell(r["Weight"], inv["Weight"].max(), report.WEIGHT_COLOR, ui.pct(r["Weight"]))]
                for _, r in inv.head(10).iterrows()]
        ui.card_title("Largest positions", "Share of the whole LTF")
        ui.table([("Holding", "l"), ("Division", "l"), ("Value", "r"), ("Weight", "l")], rows)
    with c2:
        ui.card_title("Biggest risk contributors", "Share of the LTF's volatility")
        if not a.contrib.empty:
            top = a.contrib.sort_values("Risk share", ascending=False).head(10)
            first = ltf.drop_duplicates("Ticker").set_index("Ticker")
            rows = [[f'<div class="name">{ui.esc(first.loc[t, "Company name"])}</div><div class="muted">{ui.esc(t)}</div>',
                     ui.chip(first.loc[t, "Division"], ui.color_for("Division", first.loc[t, "Division"])), ui.pct(r["Weight"]),
                     ui.bar_cell(r["Risk share"], top["Risk share"].max(), report.RISK_COLOR, ui.pct(r["Risk share"]))]
                    for t, r in top.iterrows()]
            ui.table([("Holding", "l"), ("Division", "l"), ("Weight", "r"), ("Share of risk", "l")], rows)
        else:
            st.caption("Needs price data.")

    with st.expander("Every LTF holding"):
        report.holdings_table(a, show_division=True)

    ui.footer("USIS · Twikker Fund Long Term Fund · prices from Yahoo Finance, converted to GBP · refreshed hourly")
