# Debraj-first-project
Automated daily reporting powered by Claude: Meta Ads performance at Campaign, Ad Set and Ad level, plus Lead and Sales reports, for faster insights and better decisions.

## Daily reporting agent (two reports from raw exports)
1. Put the 8 raw files in `inbox/<YYYY-MM-DD>/raw/` (git-ignored; contains lead e-mails): Meta Campaigns/Ad sets/Ads CSVs, LeadChain CSV(s), LeadModule1, LeadModule2, MeetingLeads, MeetingDetails.
2. Run `python3 pipeline/run_daily.py inbox/<date>/raw` (or ask Claude: "run the daily report").
3. Get in `outputs/<date>/`: **Report 1** Campaign Performance Report (same layout as the manual report), **Report 2** Deep Analysis Report, `digest.md`, `facts.json`. `history/` grows daily so true day-over-day spend/CTR appear on the `Daily_Delta` tab from day 2.
- Agent instructions: `.claude/skills/daewoo-daily-analysis/SKILL.md` · targets: `config/targets.json` · report structure: `config/structure.json`
- Needs: python3 with pandas, numpy, openpyxl, and LibreOffice (`soffice`) for recalculation.

## Expert agent (Business Analytics, JavaScript, jQuery, Python, C, C++, Data Structures & Algorithms)
- Definition: `.claude/agents/analytics-dev-expert.md` (name: `analytics-dev-expert`).
- Use it by asking Claude, for example: "Use the analytics-dev-expert agent to ..." or by typing `@agent-analytics-dev-expert` in Claude Code. It writes and runs the code it gives you, checks its numbers, and explains the result in plain English.
