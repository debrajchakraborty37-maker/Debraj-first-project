# Debraj-first-project
Automated daily reporting powered by Claude: Meta Ads performance at Campaign, Ad Set and Ad level, plus Lead and Sales reports, for faster insights and better decisions.

## Daily reporting agent (two reports from raw exports)
1. Put the 8 raw files in `inbox/<YYYY-MM-DD>/raw/` (git-ignored; contains lead e-mails): Meta Campaigns/Ad sets/Ads CSVs, LeadChain CSV(s), LeadModule1, LeadModule2, MeetingLeads, MeetingDetails.
2. Run `python3 pipeline/run_daily.py inbox/<date>/raw` (or ask Claude: "run the daily report").
3. Get in `outputs/<date>/`: **Report 1** Campaign Performance Report (same layout as the manual report), **Report 2** Deep Analysis Report, `digest.md`, `facts.json`. `history/` grows daily so true day-over-day spend/CTR appear on the `Daily_Delta` tab from day 2.
- Agent instructions: `.claude/skills/daewoo-daily-analysis/SKILL.md` · targets: `config/targets.json` · report structure: `config/structure.json`
- Needs: python3 with pandas, numpy, openpyxl, and LibreOffice (`soffice`) for recalculation.

## Brand FinalReport agent (7 brands)
- Agent: `.claude/agents/brand-report-builder.md` · reference format: `templates/FinalReport_TEMPLATE.xlsx` · spec: `config/final_report_spec.md` · brand mapping (draft): `config/brands.json`
- Brands: Adhira & Appa Coffee, Chhota Bheem, Acer Chhota Bheem, Bonum Cha, Carlton, Natuf, Shayreen -> one workbook each in `outputs/<date>/`.
- Usage: put the shared raw export in `inbox/<date>/raw/`, then ask Claude to use the `brand-report-builder` agent.
