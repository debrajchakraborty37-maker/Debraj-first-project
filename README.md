# Debraj-first-project
Automated daily reporting powered by Claude: Meta Ads performance at Campaign, Ad Set and Ad level, plus Lead and Sales reports, for faster insights and better decisions.

## Usage

```
pip install pandas openpyxl
python meta_ads_report.py --campaigns campaigns.csv --adsets adsets.csv --ads ads.csv \
    --crm crm.csv --meetings meetings.csv --client "Client Name" --currency INR \
    --mtd-start 2026-10-01 --mtd-end 2026-10-18 --ftd-start 2026-10-17 --ftd-end 2026-10-18 \
    --out Campaign_Performance_Report.xlsx
```

Produces an Excel workbook: KPI snapshot, MTD and FTD campaign tables, ad set and ad tables
with subtotals, key insights, a Daily Trend sheet and the source data sheets.
