"""USIS · Twikker Fund LTF risk monitor.

Run locally with:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

import data
import market
import ui
from views import common, compare, division, method, overview, registry, upload

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(page_title="USIS Risk Monitor", page_icon=str(ASSETS / "usis-icon.png"), layout="wide",
                   initial_sidebar_state="auto")
ui.inject_css()
ui.register_colors("Division", {m["name"]: m["color"] for m in data.DIVISIONS.values()})
st.logo(str(ASSETS / "usis-logo.png"), size="large", icon_image=str(ASSETS / "usis-icon.png"))


def _division_page(key: str):
    def page():
        division.render(key)
    page.__name__ = f"division_{key}"
    return page


ICONS = {"defensive": ":material/shield:", "growth": ":material/trending_up:", "income": ":material/payments:",
         "yorkshire": ":material/location_on:"}

pages = {
    "Long Term Fund": [
        st.Page(overview.render, title="LTF overview", icon=":material/dashboard:", url_path="overview", default=True),
        st.Page(compare.render, title="Compare divisions", icon=":material/compare_arrows:", url_path="compare"),
    ],
    "Divisions": [
        st.Page(_division_page(k), title=m["name"], icon=ICONS.get(k, ":material/folder:"), url_path=k)
        for k, m in data.DIVISIONS.items()
    ],
    "Tools": [
        st.Page(upload.render, title="Analyse a portfolio", icon=":material/upload_file:", url_path="analyse"),
        st.Page(method.render, title="Methodology", icon=":material/menu_book:", url_path="methodology"),
    ],
}
for p in pages["Divisions"]:
    registry.PAGES[p.url_path] = p

nav = st.navigation(pages)

# Settings sit in a toolbar rather than the sidebar: with nothing else in the
# sidebar, Streamlit lists every page instead of hiding some behind "View more".
left, right = st.columns([3.2, 1], vertical_alignment="center")
with left:
    ui.html('<div class="topbar"><b>USIS</b> · Twikker Fund · Long Term Fund risk monitor</div>')
with right:
    label_period = common.PERIOD_LABELS[st.session_state.get("set-period", common.DEFAULTS["period"])]
    label_freq = st.session_state.get("set-freq", common.DEFAULTS["freq"])
    with st.popover(f"⚙  {label_period} · {label_freq} returns", width="stretch"):
        period = st.selectbox("Price history", list(common.PERIOD_LABELS), index=1, format_func=common.PERIOD_LABELS.get, key="set-period")
        freq = st.radio("Returns", ["Daily", "Weekly"], horizontal=True, key="set-freq",
                        help="Weekly returns are steadier across time zones. Daily returns give more data points.")
        bench = st.selectbox("Benchmark", ["Division default"] + list(market.BENCHMARKS), key="set-bench",
                             help="'Division default' means the FTSE All-Share for Defensive, Income and the LTF, "
                                  "the FTSE 250 for Yorkshire and MSCI World for Growth.")
        rf = st.number_input("Risk-free rate (%)", value=common.DEFAULTS["rf"] * 100, step=0.25, min_value=0.0, max_value=15.0, key="set-rf")
        st.caption("Prices refresh every hour. Holdings come from each division's latest report.")
st.session_state["settings"] = {"period": period, "freq": freq, "benchmark": bench, "rf": rf / 100}

nav.run()
