---
name: daewoo-daily-analysis
description: Daily Daewoo x ShootOrder Meta Ads deep-analysis agent. Use when the user (or a scheduled task) says to run the daily analysis, or when a new Campaign Performance Report appears in inbox/<date>/. Produces the Deep Analysis workbook, a digest and a history snapshot.
---

# Daewoo × ShootOrder — Daily Deep-Analysis Agent

## Inputs
The finished daily **Campaign Performance Report** workbook (sheets `Campaign Report`, `Data_CRM`, …) placed at
`inbox/<YYYY-MM-DD>/Campaign_Performance_Report.xlsx` (any `.xlsx` name works; use the newest folder).

## Steps
1. Find the newest folder in `inbox/` that has no matching `outputs/<same-date>/digest.md`. If none exists, say "no new report" and stop. If the folder holds no `.xlsx`, tell the user which file is missing — never guess.
2. Run: `python3 pipeline/analyze_report.py inbox/<date>/<file>.xlsx`
   (writes `outputs/<date>/Deep_Analysis_Report-<end date>.xlsx`, `digest.md`, `facts.json`, and appends `history/daily_snapshot.csv`).
3. **Check QA.** If the script exits non-zero or the digest starts with "QA FAILED", report the failing checks and stop — do not send the report.
4. Read `outputs/<date>/digest.md` and `facts.json`. Add 2–3 sentences of judgement the script cannot make (why a trend likely happened, what to test first). Keep every number exactly as in the digest.
5. Deliver: send the Excel file and the digest to the user (SendUserFile / email or Slack connector if connected). Commit `outputs/` and `history/` to the working branch and push. **Never commit `inbox/`** (contains lead e-mails; it is git-ignored).

## Rules
- Targets live in `config/targets.json` (optional; defaults in the script). Do not invent targets.
- Never change numbers by hand; fix the script or the input instead.
- Judge lead quality only on mature leads (≥3 days old). Do not call the last 2 days a crash.
- Cost per meeting is the headline KPI; CPL is secondary.

## Not yet automated (next phase)
Building the Campaign Performance Report itself from the 5 raw exports (Meta ×3, LeadChain, CRM LeadModule 1/2, MeetingLeads, MeetingDetails). Needs one sample set of raw files.
