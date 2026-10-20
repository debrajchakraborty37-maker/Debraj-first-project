#!/usr/bin/env python3
"""Generate daily Meta Ads reports from a CSV export.

Outputs (CSV files in --out-dir):
  daily_campaign.csv, daily_adset.csv, daily_ad.csv, leads_report.csv, sales_report.csv

Usage:
  python meta_ads_report.py export.csv --out-dir reports
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

# Canonical name -> accepted header variants (compared case-insensitively,
# with any "(currency)" suffix stripped).
ALIASES = {
    "date": ["day", "date", "reporting starts", "reporting_starts"],
    "campaign": ["campaign name", "campaign"],
    "adset": ["ad set name", "adset name", "ad set"],
    "ad": ["ad name", "ad"],
    "spend": ["amount spent", "spend", "cost"],
    "impressions": ["impressions"],
    "reach": ["reach"],
    "clicks": ["link clicks", "clicks (all)", "clicks"],
    "leads": ["leads", "results (leads)", "website leads", "on-facebook leads"],
    "purchases": ["purchases", "website purchases", "results (purchases)"],
    "revenue": ["purchase conversion value", "website purchases conversion value",
                "purchases conversion value", "revenue"],
}
COUNT_COLS = ["spend", "impressions", "reach", "clicks", "leads", "purchases", "revenue"]
LEVELS = {
    "campaign": ["date", "campaign"],
    "adset": ["date", "campaign", "adset"],
    "ad": ["date", "campaign", "adset", "ad"],
}


def normalize(header: str) -> str:
    h = header.strip().lower()
    if "(" in h:  # "Amount spent (USD)" -> "amount spent"
        h = h.split("(")[0].strip()
    return h


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    lookup = {normalize(c): c for c in df.columns}
    rename = {}
    for canon, names in ALIASES.items():
        for n in names:
            if n in lookup:
                rename[lookup[n]] = canon
                break
    df = df.rename(columns=rename)
    if "date" not in df.columns:
        sys.exit("error: no date column found (expected 'Day' or 'Reporting starts')")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])
    for c in ("campaign", "adset", "ad"):
        if c in df.columns:
            df[c] = df[c].fillna("(none)")
    for c in COUNT_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce"
            ).fillna(0)
        else:
            df[c] = 0.0
    return df


def safe_div(a, b):
    return (a / b.where(b != 0)).round(4)


def add_ratios(g: pd.DataFrame) -> pd.DataFrame:
    g["ctr_%"] = (safe_div(g["clicks"], g["impressions"]) * 100).round(2)
    g["cpc"] = safe_div(g["spend"], g["clicks"]).round(2)
    g["cpm"] = (safe_div(g["spend"], g["impressions"]) * 1000).round(2)
    g["cpl"] = safe_div(g["spend"], g["leads"]).round(2)
    g["cpa"] = safe_div(g["spend"], g["purchases"]).round(2)
    g["roas"] = safe_div(g["revenue"], g["spend"]).round(2)
    return g


def summarize(df: pd.DataFrame, keys: list) -> pd.DataFrame:
    keys = [k for k in keys if k in df.columns]
    g = df.groupby(keys, as_index=False)[COUNT_COLS].sum()
    g["spend"] = g["spend"].round(2)
    return add_ratios(g).sort_values(keys)


def lead_report(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["date", "campaign"], as_index=False)[["spend", "clicks", "leads"]].sum()
    g = g[g["leads"] > 0].copy()
    g["cpl"] = safe_div(g["spend"], g["leads"]).round(2)
    g["lead_conv_rate_%"] = (safe_div(g["leads"], g["clicks"]) * 100).round(2)
    return g.sort_values(["date", "campaign"])


def sales_report(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["date", "campaign"], as_index=False)[["spend", "purchases", "revenue"]].sum()
    g = g[g["purchases"] > 0].copy()
    g["aov"] = safe_div(g["revenue"], g["purchases"]).round(2)
    g["cpa"] = safe_div(g["spend"], g["purchases"]).round(2)
    g["roas"] = safe_div(g["revenue"], g["spend"]).round(2)
    return g.sort_values(["date", "campaign"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", help="Meta Ads export CSV")
    p.add_argument("--out-dir", default="reports")
    args = p.parse_args()

    df = load(args.csv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    reports = {}
    for level, keys in LEVELS.items():
        if all(k in df.columns for k in keys):
            reports[f"daily_{level}"] = summarize(df, keys)
        else:
            print(f"skipping {level} report: missing column(s) {[k for k in keys if k not in df.columns]}")
    reports["leads_report"] = lead_report(df)
    reports["sales_report"] = sales_report(df)

    for name, r in reports.items():
        r.to_csv(out / f"{name}.csv", index=False)
        print(f"\n== {name} ({len(r)} rows) -> {out / (name + '.csv')}")
        print(r.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
