"""Analyse any portfolio from a CSV or Excel file."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

import data
import ui
from views import common, report


def read_upload(file) -> pd.DataFrame:
    if file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(file, keep_default_na=False, na_values=[""])
    raw = file.getvalue()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc, keep_default_na=False, na_values=[""])
        except UnicodeDecodeError:
            continue
    raise ValueError("Couldn't read the file. Save it as CSV (UTF-8) and try again.")


def render():
    ui.hero("Tools · Analyse a portfolio", "Analyse a portfolio",
            "Upload any list of holdings (a new division, a pitch, or a what-if rebalance) and get the same risk report as the LTF divisions.",
            [ui.pill("CSV or Excel"), ui.pill("Yahoo Finance tickers"), ui.pill("Nothing is stored")])

    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        upload = st.file_uploader("Holdings file", type=["csv", "xlsx", "xls"], label_visibility="collapsed")
    with c2:
        ui.html(
            '<div class="card"><div class="card-title">What the file needs</div>'
            '<div class="card-sub">One row per holding. Six columns are required, and the rest are optional.</div>'
            '<div class="mg-row"><span>Company name, Ticker, Value invested</span><span>required</span></div>'
            '<div class="mg-row"><span>Sector, Region, Market</span><span>required</span></div>'
            '<div class="mg-row"><span>Industry, Asset class, FX exposure, Yield, Duration, Cost, Tier, Notes</span><span>optional</span></div>'
            '<div class="mg-row"><span>Tickers use Yahoo format: AV.L, ACA.PA, BFSA.DE, MSFT. Leave Ticker blank for cash.</span><span></span></div>'
            "</div>"
        )
        st.download_button("Download the template", data.template_csv(), "usis_portfolio_template.csv", "text/csv",
                           width="stretch")

    if upload is None:
        ui.section("Waiting for a file", "", "The template is the Income division's holdings, so you can see a filled-in example.")
        return

    try:
        holdings = data.clean_holdings(read_upload(upload))
    except Exception as e:  # bad file: show the reason instead of a traceback
        st.error(str(e))
        return
    if holdings.empty:
        st.warning("No holdings with a value above zero.")
        return

    name = upload.name.rsplit(".", 1)[0]
    prices, info = common.market_data(holdings)
    a = common.analyse(holdings, prices, info, common.benchmark_name())
    tiers = common.tier_table(holdings, lookup=st.session_state.get("caps-upload", False))

    ui.section(name, "Your portfolio")
    report.kpi_row(a, None, ui.BLUE)
    ui.section("Watchlist", "Risk flags")
    ui.flags(common.division_flags(None, a, name, None, tiers))
    ui.section("Risk report", name)
    report.render_tabs(a, "upload", ui.BLUE, tiers, None)
