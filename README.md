# USIS Risk Monitor: Twikker Fund LTF

A risk website for the Twikker Fund's Long Term Fund. It covers the Defensive, Growth, Income and Yorkshire divisions, together and one at a time, all in sterling.

| Page | What it shows |
|---|---|
| **LTF overview** | Total value, volatility, VaR, beta, drawdown, yield and diversification benefit. Also: each division's share of money and of risk, exposure by sector, region, asset class, currency and market (split by division), a watchlist of risk flags, and the biggest positions and risk contributors |
| **Compare divisions** | A scorecard, growth of £100, risk vs return, how the divisions move together, drawdowns and side-by-side exposure heatmaps |
| **Defensive / Growth / Income / Yorkshire** | The full report for one division in five tabs: Exposure, Market risk, Holdings, Stress tests, and Mandate & data. Each page also has a what-if editor for testing a change before trading |
| **Analyse a portfolio** | Upload any CSV or Excel holdings file and get the same report |
| **Methodology** | What each number means, in plain English |

## Running it on your PC

Double-click **`run.bat`**, or from PowerShell:

```powershell
cd "E:\4th year twikker\twikker-risk"
.\run.bat
```

The first run installs the packages into a `.venv` folder next to the app. That takes a few minutes, and after that the app starts in seconds at http://localhost:8501. Press Ctrl+C in the window to stop it.

The app needs its own `.venv` because it uses Streamlit 1.64, and the Python on the C: drive has 1.36, which can't open pages from a link or a refresh. The C: drive is also almost full, which is why `.venv` lives on E:.

**Avast note:** Avast's HTTPS scanning re-signs every website's certificate. Python doesn't trust Avast's certificate by default, so the app adds the Windows certificate store when it downloads prices (see `market.py`). Without that, every price download fails with "unable to get local issuer certificate".

## Updating a division

Each division's holdings are in `data/funds/<division>.csv`, taken from its latest report. To update one, edit the file in Excel and save it as CSV. Changes show up when the app restarts (or within 10 minutes). Online, pushing to GitHub restarts it. Division details (who runs it, report date, mandate rules, data notes) are in `data/funds.json`.

| Column | Needed? | Notes |
|---|---|---|
| Company name, Ticker, Value invested | required | Tickers use Yahoo Finance format: `AV.L`, `ACA.PA`, `BFSA.DE`, `MSFT`. Leave the ticker blank for cash |
| Sector, Region, Market | required | Region like `Europe (UK)` or `North America (USA)`. The app groups these into broad regions |
| Industry | optional | A finer split, e.g. Banking or Insurance |
| Asset class | optional | Equity, Equity fund, Government bond, Corporate bond, Credit, Commodity, Cash |
| FX exposure | optional | Currency of the underlying assets (e.g. USD for a GBP-quoted Nasdaq tracker) |
| Yield, Duration, Cost, Tier | optional | Yield in %, duration in years (bonds), cost in £, and market-cap tier 1-4 |
| Notes | optional | Shown in the Mandate & data tab |

Check the **Ticker check** table in the Mandate & data tab after any change. It shows the name Yahoo returned for each ticker.

## Putting it online for the fund

1. Create a GitHub repository (private is fine) and push this folder to it. `.venv` is excluded by `.gitignore`.
2. Go to https://share.streamlit.io, sign in with GitHub and click **Create app**.
3. Pick the repository, set the main file to `app.py`, and under **Advanced settings** choose Python 3.13. Then deploy.
4. To limit who can open it, add people's email addresses under **Settings → Sharing**.
5. Pin the link in the Risk folder.

Every push to GitHub updates the live site.

## Files

| File | Purpose |
|---|---|
| `app.py` | Page setup, navigation and the settings toolbar |
| `views/` | One file per page, plus `report.py` (the shared report) and `common.py` (downloads, analysis, flags) |
| `risk.py` | All the risk maths: volatility, VaR, beta, risk contributions, stress tests and tier checks |
| `market.py` | Yahoo Finance downloads, GBP conversion and repair of bad Yahoo prices |
| `data.py` | Loading and tidying the holdings files |
| `ui.py` | USIS colours, CSS, cards, tables and chart styling |
