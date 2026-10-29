#!/usr/bin/env python3
"""Daily runner: raw exports -> Report 1 (Campaign Performance Report) -> Report 2 (Deep Analysis Report) + digest.

Usage: python3 pipeline/run_daily.py inbox/<YYYY-MM-DD>/raw      (outputs go to outputs/<YYYY-MM-DD>/)
"""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import clean_raw, build_report, analyze_report

raw = sys.argv[1].rstrip("/")
date_dir = os.path.basename(os.path.dirname(os.path.abspath(raw)))
out = os.path.join(ROOT, "outputs", date_dir)
try:
    clean_raw.find_files(raw)
except clean_raw.MissingFiles as e:
    print("STOP:", e); sys.exit(4)
rep = build_report.build(raw, out, os.path.join(ROOT, "history"))
code = analyze_report.build(rep, out, os.path.join(ROOT, "history", "daily_snapshot.csv"), os.path.join(ROOT, "config", "targets.json"))
print("\nREPORT 1:", rep); print("REPORT 2:", glob.glob(os.path.join(out, "*Deep_Analysis_Report*.xlsx"))[0]); print("DIGEST  :", os.path.join(out, "digest.md"))
sys.exit(code)
