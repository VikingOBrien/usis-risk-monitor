"""How every number is worked out, in plain English."""

from __future__ import annotations

import streamlit as st

import data
import ui


def card(title: str, body: str):
    ui.html(f'<div class="card method"><h4>{ui.esc(title)}</h4>{body}</div>')


def render():
    ui.hero("Tools · Methodology", "How the numbers work",
            "What each measure means, where the data comes from, and what the model can and can't tell you.",
            [ui.pill("Plain English"), ui.pill("Yahoo Finance prices"), ui.pill("All figures in GBP")])

    ui.section("The data", "Inputs")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        card("Holdings", (
            "<p>Each division's holdings live in a CSV file in <code>data/funds/</code>, taken from that division's latest report. "
            "To update a division, edit its file (or ask its risk contact for a new one) and push it to GitHub: the website updates itself.</p>"
            "<p>Every page can be checked against the reports: the <b>Mandate &amp; data</b> tab lists anything that didn't add up, "
            "and the <b>Ticker check</b> shows the name Yahoo returned for each ticker.</p>"))
    with c2:
        card("Prices", (
            "<p>Daily closing prices come from Yahoo Finance, adjusted for dividends and splits, and are refreshed every hour. "
            "Each price is converted to sterling using that day's exchange rate, so currency moves are included in the risk.</p>"
            "<p>Bonds and funds without a Yahoo price use a similar ETF as a stand-in (noted on the holding). Cash, and anything "
            "without at least three months of prices, is treated as having no volatility.</p>"))

    ui.section("The measures", "Definitions")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        card("Volatility", "<p>How much returns bounce around: the standard deviation of daily (or weekly) returns, scaled to a year. "
                           "15% means that in a typical year the portfolio ends within about ±15% of its average path two times out of three.</p>")
        card("Value at Risk (VaR 95%)", "<p>The loss you'd expect to beat on 19 days out of 20. It's taken straight from the history: the worst 5% "
                                         "of days set the line. <b>CVaR</b> is the average loss on those worst 5% of days, so it describes how bad "
                                         "the bad days are. The 1-month figure scales the daily VaR by the square root of time.</p>")
        card("Beta", "<p>How much the portfolio tends to move when the benchmark moves 1%. A beta of 0.6 means about 0.6% on average. "
                     "The Defensive mandate targets 0.50 to 0.80.</p>")
        card("Max drawdown", "<p>The largest fall from a high point to a later low within the period. It's the number that hurts most in practice.</p>")
    with c2:
        card("Share of risk", "<p>Each holding's contribution to the portfolio's total variance, which allows for how holdings move together. "
                              "The shares add up to 100%. A holding with 5% of the money but 12% of the risk is either very volatile or "
                              "moves in step with the rest of the portfolio.</p>")
        card("Diversification benefit", "<p>How much lower the LTF's volatility is than the four divisions' volatilities added together. "
                                        "It's high when the divisions don't move in lockstep.</p>")
        card("Concentration", "<p><b>HHI</b> is the sum of squared weights. <b>Effective holdings</b> = 1 ÷ HHI: a portfolio of 20 holdings "
                              "with an effective count of 8 behaves like 8 equal-sized positions.</p>")
        card("Sharpe and Sortino", "<p>Return above the risk-free rate (set in the sidebar) per unit of volatility. Sortino only counts "
                                   "downside volatility.</p>")

    ui.section("Checks and stress tests", "Rules")
    c1, c2 = st.columns(2, gap="medium")
    tl = data.TIER_LIMITS
    tiers = "".join(f"<li>{ui.esc(data.TIER_NAMES[int(k)])}: up to {float(v) * 100:.2f}% of the division, max buy £{tl['max_buy'][k]:,}</li>"
                    for k, v in tl["max_weight"].items())
    with c1:
        card("Watchlist flags", (
            "<ul><li>A single position above 10% of a division (above 15% counts as high)</li>"
            "<li>A sector above 40% (above 50% counts as high)</li><li>A region above 60%, except for the Yorkshire regional mandate</li>"
            "<li>Beta or yield outside a division's mandate</li><li>Positions above the market-cap tier guide, and Tier 4 above 30%</li>"
            "<li>Holdings carrying at least twice their weight in risk</li><li>Tickers without usable prices</li></ul>"))
        card("Market-cap tier guide", f"<p>{ui.esc(tl['source'])}.</p><ul>{tiers}</ul>")
    with c2:
        card("Stress tests", (
            "<p>Rough, first-order estimates:</p><ul>"
            "<li><b>Market moves</b> use each holding's beta to the benchmark</li>"
            "<li><b>Sterling moves</b> hit every non-sterling asset in full (a stronger pound lowers their sterling value)</li>"
            "<li><b>Rate moves</b> use the Duration column: a 1% rise in yields costs about duration × 1% of a bond's value</li></ul>"
            "<p>Real crises also change correlations, so treat these as a floor rather than a ceiling.</p>"))
        card("Limits", (
            "<p>History isn't a forecast. One year of prices covers one market regime, so try two or three years in the sidebar. "
            "Daily returns across time zones (London and New York close hours apart) understate correlation, and weekly returns fix that. "
            "Reported values come from the division reports, not live positions.</p>"))
    ui.footer("USIS · Twikker Fund Long Term Fund risk model")
