# Debraj-first-project
Automated daily reporting powered by Claude: Meta Ads performance at Campaign, Ad Set and Ad level, plus Lead and Sales reports, for faster insights and better decisions.

## Daily deep-analysis agent
1. Drop your finished daily report in `inbox/<YYYY-MM-DD>/Campaign_Performance_Report.xlsx` (git-ignored: contains lead e-mails).
2. Run `python3 pipeline/analyze_report.py inbox/<date>/Campaign_Performance_Report.xlsx` (or ask Claude: "run the daily analysis").
3. Get `outputs/<date>/Deep_Analysis_Report-<date>.xlsx`, `digest.md`, `facts.json`; `history/daily_snapshot.csv` grows daily so true day-over-day spend/CTR appear on the `Daily_Delta` tab.
- Agent instructions: `.claude/skills/daewoo-daily-analysis/SKILL.md` · targets: `config/targets.json`
- Needs: python3 with pandas, numpy, openpyxl.
