"""The four divisions side by side."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data
import risk
import ui
from views import common, overview, report


def render():
    ltf = common.ltf_holdings()
    prices, info = common.market_data()
    bench = common.benchmark_name()
    a = common.analyse(ltf, prices, info, bench)
    by_div = {k: common.analyse(ltf[ltf["Division key"] == k].assign(Weight=lambda d: d["Division weight"]), prices, info, bench)
              for k in data.DIVISIONS}
    period = common.PERIOD_LABELS.get(common.settings()["period"])

    ui.hero("Twikker Fund · Long Term Fund", "Division comparison",
            f"The four divisions measured the same way, against the {bench} and over {period}, so they can be compared like for like.",
            [ui.pill(m["name"], m["color"]) for m in data.DIVISIONS.values()])

    # ---------- scorecard ----------
    ui.section("Scorecard", "Side by side", f"Every division is measured against the {bench} here, so that betas line up. "
               "Each division's own page uses its default benchmark.")
    metrics = [
        ("Value", lambda x: ui.gbp(x.total)),
        ("% of LTF", lambda x: ui.pct(x.total / a.total)),
        ("Names", lambda x: str(x.conc["Holdings"])),
        ("Cash", lambda x: ui.pct(x.conc["Cash"])),
        ("Return", lambda x: ui.pct(x.stats.get("Total return"), 1, True)),
        ("Volatility", lambda x: ui.pct(x.stats.get("Volatility"))),
        ("Beta", lambda x: ui.num(x.stats.get("Beta", np.nan))),
        ("VaR 95%", lambda x: ui.pct(x.stats.get("VaR 95%"), 2)),
        ("Max DD", lambda x: ui.pct(x.stats.get("Max drawdown"))),
        ("Sharpe", lambda x: ui.num(x.stats.get("Sharpe ratio", np.nan))),
        ("Yield", lambda x: ui.pct(x.yield_, 2) if not np.isnan(x.yield_) else "–"),
        ("Top 5", lambda x: ui.pct(x.conc["Top 5 weight"])),
    ]
    headers = [("Division", "l")] + [(m, "r") for m, _ in metrics]
    rows = [[ui.chip(data.DIVISIONS[k]["name"], data.DIVISIONS[k]["color"])] + [f(x) for _, f in metrics] for k, x in by_div.items()]
    total = ["Whole LTF"] + [f(a) for _, f in metrics]
    ui.table(headers, rows, total, compact=True)

    if not a.priced:
        st.warning("No price data was downloaded, so only the exposure comparisons below are available.")
    else:
        # ---------- performance ----------
        ui.section("Performance and risk", "Over time")
        with st.container(border=True):
            ui.card_title("Growth of £100", f"Today's holdings in each division, held for the whole period, in GBP, against the {bench}. "
                          "This isn't the divisions' actual track record.")
            series = {bench: (a.bench.reindex(a.port.index), ui.BENCH, "dot")}
            for k, x in by_div.items():
                if len(x.port):
                    series[data.DIVISIONS[k]["name"]] = (x.port, data.DIVISIONS[k]["color"], "solid")
            series["Whole LTF"] = (a.port, ui.NAVY, "dash")
            ui.show(report.growth_chart(series, height=380), key="cmp-growth")

        c1, c2 = st.columns(2, gap="medium")
        with c1:
            with st.container(border=True):
                ui.card_title("Risk vs return", "Further right = bumpier ride, higher up = better return. Bubble size = value.")
                fig = go.Figure()
                for k, x in by_div.items():
                    if not x.stats:
                        continue
                    m = data.DIVISIONS[k]
                    fig.add_trace(go.Scatter(
                        x=[x.stats["Volatility"]], y=[x.stats["Annualised return"]], mode="markers+text", name=m["name"],
                        text=[m["name"]], textposition="top center", textfont=dict(color=ui.INK, size=12.5),
                        marker=dict(color=m["color"], size=18 + 40 * np.sqrt(x.total / a.total), line=dict(color="#fff", width=2), opacity=.92),
                        hovertemplate=f"<b>{m['name']}</b><br>Volatility %{{x:.1%}}<br>Annualised return %{{y:.1%}}<extra></extra>"))
                fig.add_trace(go.Scatter(x=[a.stats["Volatility"]], y=[a.stats["Annualised return"]], mode="markers+text", name="Whole LTF",
                                         text=["Whole LTF"], textposition="bottom center", textfont=dict(color=ui.NAVY, size=12.5),
                                         marker=dict(color=ui.NAVY, size=14, symbol="diamond", line=dict(color="#fff", width=2)),
                                         hovertemplate="<b>Whole LTF</b><br>Volatility %{x:.1%}<br>Annualised return %{y:.1%}<extra></extra>"))
                fig = ui.style(fig, 360)
                fig.update_xaxes(tickformat=".0%", showgrid=True, title_text="Volatility (annualised)", rangemode="tozero")
                fig.update_yaxes(tickformat=".0%", showgrid=True, title_text="Annualised return", zeroline=True)
                ui.show(fig, key="cmp-scatter")
        with c2:
            with st.container(border=True):
                ui.card_title("How the divisions move together", "Correlation of returns. Lower numbers mean more diversification.")
                series = risk.group_series(ltf, a.returns, "Division", a.priced)
                names = pd.Series({c: c for c in series.columns})
                ui.show(report.corr_heatmap(series, names, height=360), key="cmp-corr")

        with st.container(border=True):
            ui.card_title("Drawdowns", "How far each division fell below its previous high")
            fig = go.Figure()
            for k, x in by_div.items():
                if len(x.port):
                    dd = risk.drawdown_series(x.port)
                    fig.add_trace(go.Scatter(x=dd.index, y=dd, name=data.DIVISIONS[k]["name"], mode="lines",
                                             line=dict(color=data.DIVISIONS[k]["color"], width=2), hovertemplate="%{y:.1%}"))
            fig = ui.style(fig, 300, unified=True)
            fig.update_yaxes(tickformat=".0%", showgrid=True)
            ui.show(fig, key="cmp-dd")

    # ---------- exposure ----------
    ui.section("Exposure side by side", "Exposure", "Each column adds up to 100% of that division.")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Sector")
            ui.show(overview.heat_by_division(ltf, "Sector"), key="cmp-heat-sector")
    with c2:
        with st.container(border=True):
            ui.card_title("Region")
            ui.show(overview.heat_by_division(ltf, "Broad region"), key="cmp-heat-region")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True):
            ui.card_title("Asset class")
            ui.show(overview.heat_by_division(ltf, "Asset class"), key="cmp-heat-asset")
    with c2:
        with st.container(border=True):
            ui.card_title("Currency")
            ui.show(overview.heat_by_division(ltf, "FX exposure"), key="cmp-heat-fx")

    overlap = ltf[ltf["Ticker"] != ""].groupby("Ticker")["Division"].nunique()
    shared = overlap[overlap > 1]
    if len(shared):
        ui.section("Held by more than one division", "Overlap")
        rows = []
        for t in shared.index:
            g = ltf[ltf["Ticker"] == t]
            rows.append([f'<div class="name">{ui.esc(g["Company name"].iloc[0])}</div><div class="muted">{ui.esc(t)}</div>',
                         " ".join(ui.chip(d, ui.color_for("Division", d)) for d in g["Division"]), ui.gbp(g["Value invested"].sum())])
        ui.table([("Holding", "l"), ("Divisions", "l"), ("Combined value", "r")], rows)

    ui.footer("USIS · Twikker Fund Long Term Fund · prices from Yahoo Finance, converted to GBP")
