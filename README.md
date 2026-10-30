# Debraj-first-project
Automated daily reporting powered by Claude: Meta Ads performance at Campaign, Ad Set and Ad level, plus Lead and Sales reports, for faster insights and better decisions.

## Daily reporting agent (two reports from raw exports)
1. Put the 8 raw files in `inbox/<YYYY-MM-DD>/raw/` (git-ignored; contains lead e-mails): Meta Campaigns/Ad sets/Ads CSVs, LeadChain CSV(s), LeadModule1, LeadModule2, MeetingLeads, MeetingDetails.
2. Run `python3 pipeline/run_daily.py inbox/<date>/raw` (or ask Claude: "run the daily report").
3. Get in `outputs/<date>/`: **Report 1** Campaign Performance Report (same layout as the manual report), **Report 2** Deep Analysis Report, `digest.md`, `facts.json`. `history/` grows daily so true day-over-day spend/CTR appear on the `Daily_Delta` tab from day 2.
- Agent instructions: `.claude/skills/daewoo-daily-analysis/SKILL.md` · targets: `config/targets.json` · report structure: `config/structure.json`
- Needs: python3 with pandas, numpy, openpyxl, and LibreOffice (`soffice`) for recalculation.

## Brand month-to-month reports (reusable)
- **Start here:** skill `.claude/skills/brand-month-report/SKILL.md` · architecture `docs/ARCHITECTURE.md` · decision log `docs/DECISIONS.md` · config `config/report_config.json` (months, brands, rules — edit this, not the code) · agent `.claude/agents/brio.md`.
- **Run:** `pipeline/run_report.sh <lead_dir> <meta_dir> <out_dir> [brand ...]` — build → LibreOffice recalc → real PivotTable + slicers → four independent verifiers → `Brand_Reports.zip`. Needs python3 (pandas, numpy, openpyxl) and LibreOffice. Exits non-zero if any check fails.
- Each brand workbook: Master Dashboard (Month dropdown, tiles, charts), All Reports (One Tab), Month-on-Month, Master Pivot (open in desktop Excel for slicers), Brand-Wise, Campaign-Wise, KPI Definitions, Data Quality Log, Validation, and data tabs.
- Raw data (PII), generated workbooks and the reference workbook are git-ignored; supply them again for each run.
