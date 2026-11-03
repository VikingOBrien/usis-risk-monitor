"""One LTF division's risk report."""

from __future__ import annotations

import streamlit as st

import data
import ui
from views import common, report


def render(key: str):
    meta = data.DIVISIONS[key]
    name, color = meta["name"], meta["color"]
    raw = common.division_raw(key)

    pills = [ui.pill(f"Source: {meta['source']}"), ui.pill(f"As of {ui.date_str(meta['as_of'])}"),
             ui.pill(f"Risk contact: {meta['risk_contact']}"), ui.pill(meta["lead"])]
    side = (f'<div class="lbl">Division value</div><div class="big">{ui.gbp(float(raw["Value invested"].sum()))}</div>'
            f'<div class="sub">{ui.esc(common.benchmark_name(key))} benchmark</div>')
    ui.hero(f"LTF division · {name}", name, meta["tagline"], pills, side)

    with st.expander("✏️  What-if: edit this division's holdings", expanded=False):
        st.caption("Change a value, add a row or delete one, and every number on this page updates. Nothing is saved: "
                   "reload the page to go back to the report figures.")
        edited = st.data_editor(raw, num_rows="dynamic", width="stretch", hide_index=True, key=f"edit-{key}")

    try:
        holdings = data.clean_holdings(edited)
    except ValueError as e:
        st.error(f"The edited table can't be used: {e}")
        holdings = data.clean_holdings(raw)
    if not edited.equals(raw):
        st.info("You're looking at an edited what-if version of this division, not the reported holdings.")

    prices, info = common.market_data(holdings)
    a = common.analyse(holdings, prices, info, common.benchmark_name(key))
    tiers = common.tier_table(holdings, lookup=st.session_state.get(f"caps-{key}", False))

    report.kpi_row(a, key, color)

    flags = common.division_flags(key, a, name, color, tiers, include_notes=False)
    ui.section("Watchlist", "Risk flags", "Concentration, mandate and data checks for this division. Data notes are in the last tab.")
    ui.flags(flags[:8], empty=f"Nothing stands out for {name}.")
    if len(flags) > 8:
        with st.expander(f"{len(flags) - 8} more flags"):
            ui.flags(flags[8:])

    ui.section("Risk report", name)
    report.render_tabs(a, key, color, tiers, key)
    ui.footer(f"USIS · Twikker Fund LTF · {name} division · prices from Yahoo Finance, converted to GBP")
