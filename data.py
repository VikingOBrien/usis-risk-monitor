"""Loading and tidying holdings: the four LTF divisions or an uploaded file."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
FUND_DIR = ROOT / "data" / "funds"
META = json.loads((ROOT / "data" / "funds.json").read_text(encoding="utf-8"))
DIVISIONS = META["divisions"]
TIER_LIMITS = META["tier_limits"]

REQUIRED_COLUMNS = ["Company name", "Ticker", "Value invested", "Sector", "Region", "Market"]
OPTIONAL_TEXT = ["Industry", "Asset class", "Currency", "FX exposure", "Notes"]
OPTIONAL_NUMBERS = ["Yield", "Duration", "Cost", "Tier"]

TIER_NAMES = {1: "Tier 1 (> £1bn)", 2: "Tier 2 (£500m-£1bn)", 3: "Tier 3 (£250m-£500m)", 4: "Tier 4 (< £250m)"}


def _number(series: pd.Series) -> pd.Series:
    # anything that isn't a number after stripping symbols (blank, "nan", "-") becomes NaN
    return pd.to_numeric(series.astype(str).str.replace(r"[£$€,%\s]", "", regex=True), errors="coerce")


def broad_region(region: str, sector: str = "") -> str:
    """Map a detailed label like 'Europe (UK)' to one of a few broad regions."""
    r = str(region).lower()
    if str(sector).lower() == "cash" or "gbp" in r:
        return "Cash"
    if re.search(r"emerging|africa|latam|latin", r):
        return "Emerging markets"
    if re.search(r"global|world|international", r):
        return "Global"
    if re.search(r"asia|taiwan|china|japan|korea|india|hong kong|singapore|vietnam", r):
        return "Asia"
    if re.search(r"north america|\busa?\b|united states|canada", r):
        return "North America"
    if re.search(r"\buk\b|united kingdom|britain|england|scotland", r):
        return "United Kingdom"
    if re.search(r"europe|euro|german|france|french|luxembourg|netherlands|ireland|spain|italy|swiss", r):
        return "Europe ex-UK"
    return "Other"


def _default_asset_class(sector: str) -> str:
    s = str(sector).lower()
    if s == "cash":
        return "Cash"
    if "fixed income" in s or "bond" in s:
        return "Government bond" if "gov" in s else "Corporate bond"
    if "commodit" in s:
        return "Commodity"
    return "Equity"


def clean_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy a holdings table and add weights and derived columns.

    Needs the six template columns. Every other column is optional and filled
    with a sensible default when missing.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}. Download the template to see the layout.")

    keep = REQUIRED_COLUMNS + [c for c in OPTIONAL_TEXT + OPTIONAL_NUMBERS + ["Division"] if c in df.columns]
    df = df[keep]
    df = df[df["Company name"].notna() & df["Company name"].astype(str).str.strip().ne("")]
    df = df[~df["Company name"].astype(str).str.strip().str.lower().isin(["total", "totals", "grand total"])]

    df["Company name"] = df["Company name"].astype(str).str.strip()
    df["Value invested"] = _number(df["Value invested"])
    df = df[df["Value invested"].fillna(0) > 0]
    df["Ticker"] = df["Ticker"].fillna("").astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": ""})
    for col in ["Sector", "Region", "Market"]:
        df[col] = df[col].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown"})

    for col in OPTIONAL_TEXT:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip().replace({"nan": ""})
    for col in OPTIONAL_NUMBERS:
        df[col] = _number(df[col]) if col in df.columns else np.nan

    is_cash = df["Sector"].str.lower().eq("cash") | df["Company name"].str.lower().eq("cash")
    df.loc[is_cash, ["Sector", "Asset class", "Market"]] = "Cash"
    df.loc[is_cash, "Ticker"] = ""

    df["Industry"] = df["Industry"].where(df["Industry"] != "", df["Sector"])
    df["Asset class"] = df["Asset class"].where(df["Asset class"] != "", df["Sector"].map(_default_asset_class))
    df["Currency"] = df["Currency"].str.upper()
    df["FX exposure"] = df["FX exposure"].where(df["FX exposure"] != "", df["Currency"]).replace({"": "GBP"}).str.upper()
    df.loc[df["FX exposure"].isin(["GBX", "GBP"]), "FX exposure"] = "GBP"
    df.loc[is_cash, "FX exposure"] = "GBP"
    df["Broad region"] = [broad_region(r, s) for r, s in zip(df["Region"], df["Sector"])]
    df["Yield"] = df["Yield"] / 100.0  # stored as % in the files

    df["Weight"] = df["Value invested"] / df["Value invested"].sum()
    return df.reset_index(drop=True)


def read_division(key: str) -> pd.DataFrame:
    # keep_default_na=False so "N/A" stays text (pandas would otherwise read it as missing)
    return pd.read_csv(FUND_DIR / f"{key}.csv", encoding="utf-8", keep_default_na=False, na_values=[""])


def load_division(key: str) -> pd.DataFrame:
    return clean_holdings(read_division(key))


def load_ltf() -> pd.DataFrame:
    """All four divisions in one table. Weight is the share of the whole LTF."""
    frames = []
    for key, meta in DIVISIONS.items():
        h = load_division(key)
        h["Division"] = meta["name"]
        h["Division key"] = key
        h["Division weight"] = h["Weight"]
        frames.append(h)
    ltf = pd.concat(frames, ignore_index=True)
    ltf["Weight"] = ltf["Value invested"] / ltf["Value invested"].sum()
    return ltf


def template_csv() -> bytes:
    return (ROOT / "sample_portfolio.csv").read_bytes()
