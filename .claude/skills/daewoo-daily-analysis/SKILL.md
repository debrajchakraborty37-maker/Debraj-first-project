---
name: daewoo-daily-analysis
description: Daily Daewoo x ShootOrder Meta Ads reporting agent. Use when the user (or a scheduled task) says "run the daily report/analysis", or when raw exports appear in inbox/<date>/raw/. Cleans and maps the raw exports, builds Report 1 (Campaign Performance Report) and Report 2 (Deep Analysis Report) plus a digest.
---

# Daewoo × ShootOrder — Daily Reporting Agent

## Inputs (8 raw files in `inbox/<YYYY-MM-DD>/raw/`)
Meta Ads Manager CSVs (Campaigns, Ad sets, Ads) · LeadChain CSV(s) · CRM LeadModule1 and LeadModule2 (.xlsx) · MeetingLeads (.xlsx) · MeetingDetails (.xlsx).
File names are matched by keyword (`campaigns`, `ad-sets`, `-ads-`, `leadchain`, `leadmodule1/2`, `meetingleads`, `meetingdetails`), so hash prefixes are fine.

## Daily flow (files uploaded in chat)
1. `python3 pipeline/collect_uploads.py` → picks the newest 8 uploaded files, reads the period from the Meta CSV, copies them to `inbox/<date>/raw/`.
   - exit 4 (files missing) → tell the user exactly which file types are missing and stop.
   - exit 5 (already built) → say today's report was already produced and give the existing files; rebuild only if the user asks (`--force`).
2. Run the pipeline (below), then send **Report 1, Report 2 and the digest** in chat (SendUserFile). If an email connector is connected, also email debraj.c@theebg.com; otherwise say email is not connected.

## Run
`python3 pipeline/run_daily.py inbox/<date>/raw`
1. `clean_raw.py` repairs LeadChain (padded columns, repeated headers, duplicate IDs), canonicalises names by persistent ID, joins LeadModule1 on Social Lead ID and LeadModule2 on the first 15 digits, adds MeetingLeads leads, maps MeetingDetails (Social Lead ID → e-mail/phone), applies the Qualified/Meeting rules.
2. `build_report.py` writes **Report 1** (identical layout/formulas to the manual report; verified cell-for-cell on 28 Oct) from `templates/` + `config/structure.json`.
3. `analyze_report.py` reads Report 1 and writes **Report 2** (Deep Analysis), `digest.md`, `facts.json`, and appends `history/daily_snapshot.csv` (enables the Daily_Delta tab from day 2).

## Stop conditions (never send a report if any applies)
- `STOP: Missing raw file(s)` → tell the user exactly which files are missing.
- QA FAILED in the digest (spend mismatch, lead counts, duplicate IDs, unmapped leads) → report the failing checks.
- New campaign / ad set shown as "(untracked ad set — no parent on record)" → ask the user where it belongs, then add it to `config/structure.json`.

## Deliver
Send the user both workbooks and the digest text (email/Slack when connected, otherwise SendUserFile). Add 2–3 sentences of judgement, keeping every number exactly as in the digest. Commit `outputs/<date>/` (Report 2, digest, facts), `history/` and any `config/` change, push to the working branch. Report 1 and `inbox/` are git-ignored because they contain lead e-mail addresses.

## Rules
- Cost per meeting is the headline KPI; CPL is secondary. Judge lead quality only on leads ≥3 days old.
- Targets live in `config/targets.json` (placeholders until the client agrees them). Do not invent targets.
- Never edit numbers by hand; fix the input or the code.
