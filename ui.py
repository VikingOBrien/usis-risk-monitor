"""USIS look and feel: colours, CSS, page furniture and chart styling."""

from __future__ import annotations

import html as _html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------- colour tokens ----------

NAVY_950 = "#00142b"
NAVY_900 = "#011e3c"
NAVY = "#012e58"          # sampled from the USIS logo
NAVY_700 = "#0b3c70"
BLUE = "#1f5fbf"
BLUE_200 = "#b9cfee"
BLUE_100 = "#dce7f6"
BLUE_50 = "#eef3fa"
PAGE = "#f4f7fb"
LINE = "#e3e9f2"
GRID = "#e8edf4"
AXIS = "#c5cfdc"
INK = "#0b1b33"
INK_2 = "#44546c"
INK_3 = "#7d8aa0"

# Categorical slots, validated in this order for adjacent pairs (stacks, donuts).
SERIES = ["#1f5fbf", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#a7b1c2"
CASH = "#d3dae5"
BENCH = "#8a96a8"

STATUS = {  # reserved for state, always shown with an icon and a label
    "good": ("#0ca30c", "#0a6e0a", "✓"),
    "info": ("#1f5fbf", "#1f5fbf", "i"),
    "warning": ("#fab219", "#8a5a00", "!"),
    "serious": ("#ec835a", "#a3431c", "▲"),
    "critical": ("#d03b3b", "#a12424", "✕"),
}

SLOTS = {
    "Sector": ["Financials", "Technology", "Industrials", "Healthcare", "Consumer", "Communication Services", "Utilities", "Fixed Income"],
    "Broad region": ["United Kingdom", "North America", "Europe ex-UK", "Asia", "Emerging markets", "Global", "Other"],
    "Asset class": ["Equity", "Equity fund", "Government bond", "Corporate bond", "Credit", "Commodity"],
    "FX exposure": ["GBP", "USD", "EUR", "EM", "Mixed"],
    "Market": ["LSE", "LSE AIM", "NYSE", "NASDAQ", "XETRA", "Euronext Paris"],
}
CASH_LABELS = {"Cash", "N/A", "UK (GBP)"}

# Sequential (magnitude) and diverging (polarity) scales
SEQ_BLUE = ["#f4f8fd", "#dce7f6", "#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
# poles kept mid-dark so the dark cell labels stay readable at both ends
DIVERGING = [[0.0, "#d65a5a"], [0.25, "#f0aaa5"], [0.5, "#f0efec"], [0.75, "#a9c9f2"], [1.0, "#4f8fe0"]]

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"


CUSTOM_COLORS: dict[str, dict[str, str]] = {}


def register_colors(dimension: str, mapping: dict[str, str]):
    """Fixed colours for a dimension that isn't in SLOTS (e.g. the four divisions)."""
    CUSTOM_COLORS[dimension] = dict(mapping)
    SLOTS[dimension] = list(mapping)


def color_for(dimension: str, label: str) -> str:
    if dimension in CUSTOM_COLORS and label in CUSTOM_COLORS[dimension]:
        return CUSTOM_COLORS[dimension][label]
    if label in CASH_LABELS:
        return CASH
    slots = SLOTS.get(dimension, [])
    if label in slots:
        return SERIES[slots.index(label) % len(SERIES)]
    return OTHER


def slot_order(dimension: str, labels) -> list:
    slots = SLOTS.get(dimension, [])
    rank = {lab: i for i, lab in enumerate(slots)}
    return sorted(labels, key=lambda lab: (lab in CASH_LABELS, lab not in rank, rank.get(lab, 0), lab))


# ---------- formatting ----------

def esc(x) -> str:
    return _html.escape(str(x), quote=True)


def gbp(x, dp: int = 0, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    sign = "−" if x < 0 else ("+" if signed and x > 0 else "")
    return f"{sign}£{abs(x):,.{dp}f}"


def pct(x, dp: int = 1, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    v = round(float(x) * 100, dp)  # round first so a tiny negative never shows as "−0.0%"
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    return f"{sign}{abs(v):.{dp}f}%"


def num(x, dp: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:.{dp}f}".replace("-", "−")


def date_str(iso: str) -> str:
    try:
        return pd.Timestamp(iso).strftime("%-d %b %Y")
    except ValueError:
        return pd.Timestamp(iso).strftime("%d %b %Y").lstrip("0")


# ---------- CSS ----------

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Jost:wght@400;500;600;700&display=swap');

:root {{
  --navy-950:{NAVY_950}; --navy-900:{NAVY_900}; --navy:{NAVY}; --navy-700:{NAVY_700};
  --blue:{BLUE}; --blue-200:{BLUE_200}; --blue-100:{BLUE_100}; --blue-50:{BLUE_50};
  --page:{PAGE}; --line:{LINE}; --ink:{INK}; --ink-2:{INK_2}; --ink-3:{INK_3};
  --radius: 14px;
  --shadow: 0 1px 2px rgba(1,30,60,.05), 0 6px 24px -12px rgba(1,30,60,.18);
}}

/* fonts come from .streamlit/config.toml; these cover our own HTML */
.hero, .kpis, .section, .legend, .flags, .tbl-wrap, .metric-grid, .card, .topbar, .foot {{ font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }}

.stApp {{ background: var(--page); color: var(--ink); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"], footer, #MainMenu {{ display: none !important; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 5rem; max-width: 1440px; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--navy-950) 0%, var(--navy-900) 45%, var(--navy) 100%);
  border-right: 0;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius: 10px; margin: 1px 0; padding: 6px 10px; }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] > span:last-child {{ color: rgba(255,255,255,.78); font-size: 14px; }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{ background: rgba(255,255,255,.07); }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(255,255,255,.13); box-shadow: inset 3px 0 0 #86b6ef; }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] > span:last-child {{ color: #fff; font-weight: 600; }}
[data-testid="stSidebarNavViewButton"] {{ color: rgba(185,207,238,.8) !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {{ color: rgba(255,255,255,.6); }}
[data-testid="stSidebar"] header, [data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {{
  color: rgba(185,207,238,.75) !important; font-family: 'Jost', sans-serif; text-transform: uppercase;
  letter-spacing: .14em; font-size: 11px; font-weight: 600;
}}
[data-testid="stSidebarNavSeparator"] {{ border-color: rgba(255,255,255,.12); }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
  color: rgba(185,207,238,.85); font-family: 'Jost', sans-serif; text-transform: uppercase;
  letter-spacing: .12em; font-size: 11px; font-weight: 600;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-testid="stNumberInput"] > div > div,
[data-testid="stSidebar"] [data-baseweb="input"] {{
  background: rgba(255,255,255,.07) !important; border-color: rgba(255,255,255,.16) !important; border-radius: 10px;
}}
[data-testid="stSidebar"] [data-baseweb="base-input"], [data-testid="stSidebar"] input {{ background: transparent !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] input {{ color: #fff !important; -webkit-text-fill-color: #fff; }}
[data-testid="stSidebar"] [data-baseweb="select"] svg {{ fill: rgba(255,255,255,.8); }}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {{ background: transparent; color: #fff; border-color: rgba(255,255,255,.12); }}
[data-testid="stSidebar"] [role="radiogroup"] label p {{ color: rgba(255,255,255,.9); }}
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small {{ color: rgba(220,231,246,.72); }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}
[data-testid="stSidebarCollapseButton"] svg, [data-testid="stSidebarCollapsedControl"] svg {{ color: #fff; }}
img[data-testid="stLogo"] {{ height: 34px; }}

/* ---------- native widgets on the page ---------- */
[data-testid="stTab"] {{ padding: 10px 16px; }}
[data-testid="stTab"] p {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .1em; font-size: 13px;
  font-weight: 600; color: var(--ink-3); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--navy); }}
[data-testid="stTab"]:hover p {{ color: var(--blue); }}
[data-testid="stExpander"] details {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
[data-testid="stExpander"] summary p {{ font-weight: 600; color: var(--navy); }}
.stButton button, .stDownloadButton button {{ border-radius: 10px; border: 1px solid var(--line); font-weight: 600; color: var(--navy); background: #fff; }}
.stButton button:hover, .stDownloadButton button:hover {{ border-color: var(--blue); color: var(--blue); }}
[data-testid="stFileUploaderDropzone"] {{ background: #fff; border: 1.5px dashed var(--blue-200); border-radius: var(--radius); }}
[data-testid="stPlotlyChart"] {{ background: transparent; }}
/* any block whose own first elements include a card title becomes a white card */
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stHtml"] > .card-title) {{
  background: #fff; border: 1px solid var(--line) !important; border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px 10px;
}}
/* the settings toolbar */
.topbar {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .18em; font-size: 11.5px; font-weight: 600;
  color: var(--ink-3); padding-top: 10px; }}
.topbar b {{ color: var(--navy); }}
[data-testid="stPopover"] button {{ border-radius: 999px; border: 1px solid var(--line); background: #fff; color: var(--navy); font-weight: 600;
  box-shadow: var(--shadow); }}
[data-testid="stAlert"] {{ border-radius: 12px; }}

/* ---------- page furniture ---------- */
.hero {{
  position: relative; overflow: hidden; border-radius: 20px; padding: 34px 38px 30px;
  background: radial-gradient(120% 140% at 85% -10%, #0f4f93 0%, rgba(15,79,147,0) 55%),
              linear-gradient(135deg, var(--navy-950) 0%, var(--navy) 60%, #0a447f 100%);
  color: #fff; box-shadow: 0 18px 40px -24px rgba(1,30,60,.65); margin-bottom: 6px;
  display: flex; justify-content: space-between; gap: 28px; align-items: flex-end; min-height: 188px;
}}
.hero-grid {{
  position: absolute; inset: 0; opacity: .5; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
  background-size: 36px 36px; mask-image: linear-gradient(90deg, transparent 0%, #000 55%);
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 55%);
}}
.hero-skyline {{ position: absolute; right: 0; bottom: 0; width: 62%; max-width: 760px; height: auto; opacity: .16; pointer-events: none; }}
.hero-body {{ position: relative; z-index: 1; max-width: 760px; }}
.hero-eyebrow {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .22em; font-size: 12px; font-weight: 600; color: #b9cfee; }}
.hero-title {{ font-family: 'Jost', sans-serif; font-weight: 600; font-size: 44px; line-height: 1.05; letter-spacing: .02em; margin: 10px 0 10px; color: #fff; }}
.hero-sub {{ font-size: 16px; line-height: 1.5; color: rgba(232,240,250,.86); max-width: 680px; }}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }}
.hero-pill {{ display: inline-flex; align-items: center; gap: 7px; padding: 5px 11px; border-radius: 999px;
  background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.16); font-size: 12.5px; color: #eaf1fb; }}
.hero-pill .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.hero-side {{ position: relative; z-index: 1; text-align: right; min-width: 200px; }}
.hero-side .big {{ font-family: 'Jost', sans-serif; font-size: 40px; font-weight: 600; line-height: 1; color: #fff; }}
.hero-side .lbl {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .18em; font-size: 11px; color: #b9cfee; margin-bottom: 6px; }}
.hero-side .sub {{ font-size: 13px; color: rgba(232,240,250,.8); margin-top: 6px; }}

.kpis {{ display: grid; gap: 14px; grid-template-columns: repeat(var(--cols, 6), minmax(0, 1fr)); margin: 4px 0 2px; }}
@media (max-width: 1100px) {{ .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 640px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .hero {{ flex-direction: column; align-items: flex-start; padding: 26px 22px; }}
  .hero-side {{ text-align: left; }} .hero-title {{ font-size: 34px; }} }}
.kpi {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 16px 18px 14px;
  box-shadow: var(--shadow); position: relative; overflow: hidden; }}
.kpi::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent, var(--navy)); }}
.kpi-label {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .12em; font-size: 11px; font-weight: 600; color: var(--ink-3); }}
.kpi-value {{ font-size: clamp(20px, 1.9vw, 27px); font-weight: 700; color: var(--ink); margin-top: 6px; letter-spacing: -.01em;
  font-variant-numeric: tabular-nums; white-space: nowrap; }}
.kpi-sub {{ font-size: 12.5px; color: var(--ink-2); margin-top: 4px; min-height: 18px; }}

.section {{ margin: 26px 0 10px; }}
.section-eyebrow {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .2em; font-size: 11px; font-weight: 600; color: var(--blue); }}
.section-title {{ font-family: 'Jost', sans-serif; font-size: 24px; font-weight: 600; color: var(--navy); margin-top: 2px; }}
.section-caption {{ font-size: 14px; color: var(--ink-2); margin-top: 4px; max-width: 900px; line-height: 1.5; }}

.card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); padding: 18px 20px; }}
.card-title {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; font-weight: 600; color: var(--navy); margin-bottom: 2px; }}
.card-sub {{ font-size: 12.5px; color: var(--ink-3); margin-bottom: 8px; }}

.chip {{ display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
  background: var(--blue-50); color: var(--navy); border: 1px solid var(--blue-100); white-space: nowrap; }}
.chip .dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.status {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.status .ico {{ width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  font-size: 10px; color: #fff; font-weight: 700; }}

.legend {{ display: flex; flex-direction: column; gap: 9px; padding-top: 4px; }}
.lg-row {{ display: grid; grid-template-columns: 12px minmax(0, 1fr) auto 50px; align-items: center; column-gap: 9px; row-gap: 6px; font-size: 13px; }}
.lg-row .sw {{ width: 11px; height: 11px; border-radius: 3px; }}
.lg-name {{ color: var(--ink); line-height: 1.25; }}
.lg-val {{ color: var(--ink-3); font-variant-numeric: tabular-nums; font-size: 12.5px; }}
.lg-pct {{ color: var(--ink); font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }}
.lg-bar {{ grid-column: 2 / 5; height: 4px; background: var(--blue-50); border-radius: 4px; margin-top: -5px; }}
.lg-bar span {{ display: block; height: 4px; border-radius: 4px; }}

.flags {{ display: flex; flex-direction: column; gap: 10px; }}
.flag {{ display: grid; grid-template-columns: 26px 1fr auto; gap: 12px; align-items: start; background: #fff;
  border: 1px solid var(--line); border-left: 4px solid var(--flag); border-radius: 12px; padding: 12px 14px; }}
.flag-ico {{ width: 22px; height: 22px; border-radius: 50%; background: var(--flag); color: #fff; display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 700; margin-top: 1px; }}
.flag-ico.dark {{ color: var(--ink); }}
.flag-title {{ font-weight: 600; color: var(--ink); font-size: 14px; }}
.flag-detail {{ color: var(--ink-2); font-size: 13px; margin-top: 2px; line-height: 1.45; }}
.flag-level {{ font-size: 11px; text-transform: uppercase; letter-spacing: .1em; font-weight: 700; color: var(--flag-ink); }}

.tbl-wrap {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); overflow-x: auto; }}
table.tbl {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.tbl thead th {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .1em; font-size: 11px; font-weight: 600;
  color: var(--ink-3); text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); background: #fbfcfe; white-space: nowrap; }}
table.tbl td {{ padding: 10px 14px; border-bottom: 1px solid #eef2f7; color: var(--ink); vertical-align: middle; }}
table.tbl tbody tr:last-child td {{ border-bottom: 0; }}
table.tbl tbody tr:hover td {{ background: #f8fafd; }}
table.tbl .r {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
table.tbl .muted {{ color: var(--ink-3); font-size: 12px; }}
table.tbl tr.total td {{ font-weight: 700; background: #fbfcfe; border-top: 1px solid var(--line); }}
table.tbl .name {{ font-weight: 600; }}
.bar {{ position: relative; height: 6px; background: var(--blue-50); border-radius: 6px; min-width: 44px; }}
.bar span {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 6px; }}
table.tbl.compact td, table.tbl.compact thead th {{ padding: 10px 9px; }}
table.tbl.compact thead th {{ letter-spacing: .06em; font-size: 10.5px; }}
.barcell {{ display: grid; grid-template-columns: 44px minmax(44px, 1fr); gap: 8px; align-items: center; }}
table.tbl td .name + .muted {{ margin-top: 1px; }}

.metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }}
.mg-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); padding: 14px 18px; }}
.mg-title {{ font-family: 'Jost', sans-serif; text-transform: uppercase; letter-spacing: .12em; font-size: 11px; font-weight: 600; color: var(--blue); margin-bottom: 8px; }}
.mg-row {{ display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px dashed #edf1f6; font-size: 13.5px; }}
.mg-row:last-child {{ border-bottom: 0; }}
.mg-row span:first-child {{ color: var(--ink-2); }}
.mg-row span:last-child {{ font-weight: 600; font-variant-numeric: tabular-nums; color: var(--ink); }}

.method h4 {{ font-family: 'Jost', sans-serif; color: var(--navy); margin: 0 0 6px; font-size: 17px; }}
.method p, .method li {{ color: var(--ink-2); font-size: 14px; line-height: 1.6; }}
.method code {{ background: var(--blue-50); color: var(--navy); padding: 1px 6px; border-radius: 6px; font-size: 12.5px; }}
.foot {{ color: var(--ink-3); font-size: 12px; margin-top: 28px; text-align: center; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str):
    """Render a block of HTML without Markdown processing."""
    st.html(markup)


# ---------- page furniture ----------

def _skyline_svg() -> str:
    # an abstract night skyline - a nod to the city photo on usis.co.uk
    blocks = [(0, 38, 54), (40, 26, 86), (68, 32, 64), (102, 22, 118), (126, 38, 78), (166, 18, 104), (186, 44, 96),
              (232, 28, 128), (262, 20, 92), (284, 48, 72), (334, 26, 146), (362, 34, 108), (398, 22, 84),
              (422, 42, 122), (466, 28, 70), (496, 38, 102), (536, 30, 132), (568, 44, 76), (614, 26, 98),
              (642, 40, 114), (684, 36, 66), (722, 38, 90)]
    rects = "".join(f'<rect x="{x}" y="{170 - h}" width="{w}" height="{h}" rx="1"/>' for x, w, h in blocks)
    shard = '<path d="M196 170 L214 18 L232 170 Z"/>'
    gherkin = '<path d="M455 170 C 438 120, 440 70, 460 44 C 480 70, 482 120, 465 170 Z"/>'
    windows = "".join(
        f'<rect x="{x + 5 + (i % 3) * 8}" y="{170 - h + 10 + (i // 3) * 12}" width="3" height="5" fill="#fff" opacity=".55"/>'
        for x, w, h in blocks[::3] for i in range(0, min(9, int(h / 14) * 3))
    )
    return (f'<svg class="hero-skyline" viewBox="0 0 760 170" preserveAspectRatio="xMaxYMax meet" '
            f'xmlns="http://www.w3.org/2000/svg" fill="#ffffff">{rects}{shard}{gherkin}{windows}</svg>')


def hero(eyebrow: str, title: str, subtitle: str, pills: list[str] | None = None, side: str = ""):
    pill_html = "".join(f'<span class="hero-pill">{p}</span>' for p in (pills or []))
    side_html = f'<div class="hero-side">{side}</div>' if side else ""
    html(
        f'<div class="hero"><div class="hero-grid"></div>{_skyline_svg()}'
        f'<div class="hero-body"><div class="hero-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="hero-title">{esc(title)}</div><div class="hero-sub">{esc(subtitle)}</div>'
        f'<div class="hero-meta">{pill_html}</div></div>{side_html}</div>'
    )


def pill(text: str, dot: str | None = None) -> str:
    d = f'<span class="dot" style="background:{dot}"></span>' if dot else ""
    return f"{d}{esc(text)}"


def section(title: str, eyebrow: str = "", caption: str = ""):
    eb = f'<div class="section-eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    cap = f'<div class="section-caption">{esc(caption)}</div>' if caption else ""
    html(f'<div class="section">{eb}<div class="section-title">{esc(title)}</div>{cap}</div>')


def kpis(items: list[dict], accent: str | None = None, cols: int | None = None):
    style = f' style="--cols:{cols or min(6, max(1, len(items)))};{f"--accent:{accent}" if accent else ""}"'
    cards = "".join(
        f'<div class="kpi"><div class="kpi-label">{esc(i["label"])}</div>'
        f'<div class="kpi-value">{esc(i["value"])}</div><div class="kpi-sub">{i.get("sub", "")}</div></div>'
        for i in items
    )
    html(f'<div class="kpis"{style}>{cards}</div>')


def status(level: str, text: str) -> str:
    fill, ink, icon = STATUS[level]
    icon_color = INK if level == "warning" else "#fff"
    return (f'<span class="status" style="color:{ink}"><span class="ico" style="background:{fill};color:{icon_color}">{icon}</span>'
            f'{esc(text)}</span>')


def chip(text: str, dot: str | None = None) -> str:
    d = f'<span class="dot" style="background:{dot}"></span>' if dot else ""
    return f'<span class="chip">{d}{esc(text)}</span>'


LEVEL_NAMES = {"critical": "Breach", "serious": "High", "warning": "Watch", "info": "Note", "good": "OK"}


def flags(items: list[dict], empty: str = "Nothing to flag."):
    if not items:
        html(f'<div class="flags"><div class="flag" style="--flag:{STATUS["good"][0]};--flag-ink:{STATUS["good"][1]}">'
             f'<div class="flag-ico">✓</div><div><div class="flag-title">{esc(empty)}</div></div><div></div></div></div>')
        return
    rows = []
    for f in items:
        fill, ink, icon = STATUS[f["level"]]
        dark = " dark" if f["level"] == "warning" else ""
        tag = chip(f["division"], f.get("color")) if f.get("division") else ""
        rows.append(
            f'<div class="flag" style="--flag:{fill};--flag-ink:{ink}"><div class="flag-ico{dark}">{icon}</div>'
            f'<div><div class="flag-level">{LEVEL_NAMES[f["level"]]}</div><div class="flag-title">{esc(f["title"])}</div>'
            f'<div class="flag-detail">{esc(f.get("detail", ""))}</div></div><div>{tag}</div></div>'
        )
    html(f'<div class="flags">{"".join(rows)}</div>')


def legend(df: pd.DataFrame, dimension: str, label_col: str | None = None):
    rows = []
    for label, r in df.iterrows():
        c = color_for(dimension, label)
        rows.append(
            f'<div class="lg-row"><span class="sw" style="background:{c}"></span><span class="lg-name" title="{esc(label)}">{esc(label)}</span>'
            f'<span class="lg-val">{gbp(r["Value"])}</span><span class="lg-pct">{pct(r["Weight"])}</span>'
            f'<div class="lg-bar"><span style="width:{min(100, r["Weight"] * 100):.1f}%;background:{c}"></span></div></div>'
        )
    html(f'<div class="legend">{"".join(rows)}</div>')


def card_title(title: str, sub: str = ""):
    s = f'<div class="card-sub">{esc(sub)}</div>' if sub else ""
    html(f'<div class="card-title">{esc(title)}</div>{s}')


def metric_cards(groups: dict[str, list[tuple[str, str]]]):
    cards = []
    for title, rows in groups.items():
        body = "".join(f'<div class="mg-row"><span>{esc(k)}</span><span>{v}</span></div>' for k, v in rows)
        cards.append(f'<div class="mg-card"><div class="mg-title">{esc(title)}</div>{body}</div>')
    html(f'<div class="metric-grid">{"".join(cards)}</div>')


def bar_cell(value: float, max_value: float, color: str, text: str) -> str:
    width = 0 if not max_value else max(0.0, min(100.0, value / max_value * 100))
    return (f'<div class="barcell"><span class="r">{text}</span><div class="bar"><span style="width:{width:.1f}%;'
            f'background:{color}"></span></div></div>')


def table(headers: list[tuple[str, str]], rows: list[list[str]], total: list[str] | None = None, compact: bool = False):
    """headers: (label, 'l' or 'r'); rows: lists of ready-made cell HTML."""
    th = "".join(f'<th class="{a}">{esc(h)}</th>' for h, a in headers)
    body = "".join("<tr>" + "".join(f'<td class="{headers[i][1]}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    if total:
        body += '<tr class="total">' + "".join(f'<td class="{headers[i][1]}">{c}</td>' for i, c in enumerate(total)) + "</tr>"
    cls = "tbl compact" if compact else "tbl"
    html(f'<div class="tbl-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')


def footer(text: str):
    html(f'<div class="foot">{esc(text)}</div>')


# ---------- charts ----------

def style(fig: go.Figure, height: int = 320, legend: bool = True, **layout) -> go.Figure:
    fig.update_layout(
        height=height,
        font=dict(family=FONT, size=12, color=INK_2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=12, t=14, b=8),
        hoverlabel=dict(bgcolor="#fff", bordercolor=LINE, font=dict(family=FONT, color=INK, size=12)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12, color=INK_2), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified" if layout.pop("unified", False) else "closest",
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS, tickfont=dict(color=INK_3), showgrid=False,
                     title_font=dict(color=INK_3), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS, tickfont=dict(color=INK_3), title_font=dict(color=INK_3),
                     automargin=True)
    fig.update_layout(**layout)
    return fig


def show(fig: go.Figure, key: str | None = None):
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True}, key=key)


def donut(df: pd.DataFrame, dimension: str, center_top: str, center_bottom: str, height: int = 250) -> go.Figure:
    """Slices in fixed slot order so neighbouring colours are always a validated pair."""
    labels = slot_order(dimension, list(df.index))
    d = df.loc[labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=d["Value"], hole=0.7, sort=False, direction="clockwise", rotation=0,
        marker=dict(colors=[color_for(dimension, lab) for lab in labels], line=dict(color="#ffffff", width=2)),
        textinfo="none",
        customdata=np.stack([d["Weight"] * 100], axis=-1),
        hovertemplate="<b>%{label}</b><br>£%{value:,.0f} · %{customdata[0]:.1f}%<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{esc(center_top)}</b>", x=0.5, y=0.56, showarrow=False, font=dict(family=FONT, size=19, color=INK))
    fig.add_annotation(text=esc(center_bottom), x=0.5, y=0.41, showarrow=False, font=dict(family=FONT, size=11.5, color=INK_3))
    return style(fig, height=height, legend=False, margin=dict(l=4, r=4, t=4, b=4))


def hbar(df: pd.DataFrame, value_col: str, color: str = BLUE, height: int | None = None, fmt=pct, max_rows: int = 14) -> go.Figure:
    d = df.head(max_rows).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d[value_col], y=[str(i) for i in d.index], orientation="h", marker=dict(color=color, cornerradius=4),
        text=[fmt(v) for v in d[value_col]], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=12), hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
    ))
    fig = style(fig, height=height or max(160, 30 * len(d) + 30), legend=False)
    fig.update_xaxes(visible=False, range=[0, float(d[value_col].max()) * 1.22 if len(d) else 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK, size=12.5), ticksuffix="  ")
    fig.update_layout(bargap=0.38)
    return fig
