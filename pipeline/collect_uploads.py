#!/usr/bin/env python3
"""Collect the newest set of raw daily files that the user uploaded in chat into inbox/<date>/raw/.

Usage: python3 pipeline/collect_uploads.py [--uploads DIR] [--dry-run] [--force]
Picks, per file type, the newest upload (all LeadChain files uploaded within 3 h of the newest one), reads the report date
from the Meta Campaigns CSV ('Reporting ends'), and copies the set to inbox/<YYYY-MM-DD>/raw/.
Exit codes: 0 ready to run, 4 files missing, 5 this date was already built (use --force to rebuild).
"""
import argparse, glob, os, shutil, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
KINDS = {
    "campaigns": lambda n: "campaigns" in n and n.endswith(".csv"),
    "adsets": lambda n: ("ad-sets" in n or "ad sets" in n or "ad_sets" in n) and n.endswith(".csv"),
    "ads": lambda n: any(t in n for t in ("-ads-", "_ads_", " ads ")) and "ad-sets" not in n and n.endswith(".csv"),
    "leadchain": lambda n: "leadchain" in n and n.endswith(".csv"),
    "lm1": lambda n: "leadmodule1" in n and n.endswith((".xlsx", ".xls")),
    "lm2": lambda n: "leadmodule2" in n and n.endswith((".xlsx", ".xls")),
    "ml": lambda n: "meetingleads" in n and n.endswith((".xlsx", ".xls")),
    "md": lambda n: "meetingdetails" in n and n.endswith((".xlsx", ".xls")),
}


def default_uploads():
    c = sorted(glob.glob("/root/.claude/uploads/*"), key=os.path.getmtime)
    return c[-1] if c else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--uploads", default=default_uploads()); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not a.uploads or not os.path.isdir(a.uploads):
        print("STOP: no uploads folder found — please upload the 8 raw files in chat."); return 4
    files = [f for f in glob.glob(os.path.join(a.uploads, "*")) if os.path.isfile(f)]
    picked, missing = {}, []
    for kind, pred in KINDS.items():
        c = sorted((f for f in files if pred(os.path.basename(f).lower())), key=os.path.getmtime)
        if not c: missing.append(kind); continue
        newest = os.path.getmtime(c[-1])
        picked[kind] = [f for f in c if newest - os.path.getmtime(f) <= 3 * 3600] if kind == "leadchain" else [c[-1]]
    if missing:
        print("STOP: missing raw file type(s): " + ", ".join(missing)); return 4
    camp = pd.read_csv(picked["campaigns"][0]); date = pd.to_datetime(camp["Reporting ends"].iloc[0]).strftime("%Y-%m-%d")
    start = pd.to_datetime(camp["Reporting starts"].iloc[0]).strftime("%d %b"); end = pd.to_datetime(camp["Reporting ends"].iloc[0]).strftime("%d %b %Y")
    dest = os.path.join(ROOT, "inbox", date, "raw")
    print(f"Report period: {start} – {end}  (FTD {end})\nFiles selected:")
    for k, v in picked.items():
        for f in v: print(f"  {k:10s} {os.path.basename(f)}")
    built = glob.glob(os.path.join(ROOT, "outputs", date, "*Deep_Analysis*.xlsx"))
    if built and not a.force:
        print(f"ALREADY BUILT for {date}: {built[0]} (use --force to rebuild)"); return 5
    if a.dry_run: print("dry run — nothing copied"); return 0
    shutil.rmtree(dest, ignore_errors=True); os.makedirs(dest)
    for v in picked.values():
        for f in v: shutil.copy2(f, dest)
    print(f"Copied to {dest}\nNext: python3 pipeline/run_daily.py inbox/{date}/raw"); return 0


if __name__ == "__main__":
    sys.exit(main())
