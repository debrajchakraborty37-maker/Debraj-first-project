# Architecture — month-to-month brand reports

## Pipeline
```
raw files ──► build_brand_report.py ──► LibreOffice recalc ──► inject_pivot.py ──► verify_* ──► zip
(Meta CSV,     openpyxl workbook,        (cached values for     (PivotTable +        (independent    (Brand_Reports
 LeadDetails)  live formulas             every formula)          slicers into the     recompute from   .zip)
               + Master Dashboard,                               recalculated file)   raw files)
               Pivot_Data, Master Pivot grid
```
Driver: `pipeline/run_report.sh` → `run_all_brands.py` (per brand: build → `soffice --headless --calc --convert-to xlsx` → `inject_pivot.inject`) → four verifier stages. Any mismatch → non-zero exit.

## Modules (`pipeline/`)
| File | Responsibility |
|---|---|
| `report_config.py` + `config/report_config.json` | Single source of truth: months (key, name, partial flag), year, lead-file pattern, qualified / meeting status lists, FW regex, per-brand Meta file prefix + CRM brand values. All label text for the period derives from it. `REPORT_CONFIG` env var swaps the file. |
| `build_brand_report.py` | Loads CRM + Meta, attributes leads to campaigns, writes all tabs with **live formulas** (COUNTIFS/SUMIFS on `Data_CRM`/`Data_Meta`; median TAT as array formula). `main(brand, lead_dir, meta_dir, out_dir)`. |
| `pivot_dashboard.py` | `Pivot_Data` (one row per campaign line × month, formulas linked to Campaign-Wise), `Master Pivot` grid (plain values), `Master Dashboard` + `Dashboard_Data` helper (SUMIFS driven by the Month dropdown; charts; highlight sentences), extra Validation rows. Supports 1–7 months. |
| `inject_pivot.py` | Edits the xlsx zip: pivotCacheDefinition/Records (from `Pivot_Data` values), pivotTable1.xml (rows Brand›Campaign, columns Month × 12 measures, calculated fields for ratios), 4 slicers (Month, Lead attribution, Delivery, Campaign) + drawing, content types, rels, workbook.xml `pivotCaches`, x14 slicerCaches. Modelled on an Excel-produced exemplar; `refreshOnLoad="1"`. Guard: refuses merged cells / formulas inside the pivot range. |
| `run_all_brands.py`, `run_report.sh` | Orchestration. |
| `verify_reports.py` | From the RAW files only, recomputes every Campaign-Wise / Brand-Wise / Pivot_Data / Month-on-Month cell (all months + total) and compares. |
| `verify_masterpivot.py` | Master Pivot body vs `Pivot_Data`; structure (no merges/formulas in pivot range, no panes, zoom 85). |
| `verify_dashboard.py` | Dashboard tiles, change lines, month table, top-10 lists, attribution split for a chosen dropdown value. |
| (legacy) `run_daily.py`, `build_report.py`, … | The separate Daewoo daily-report agent; untouched. |

## Inputs (data contracts)
- **Meta campaign CSV** (per brand): `Reporting starts/ends`, `Campaign name`, `Campaign delivery`, `Amount spent (INR)`, `Impressions`, `Reach`, `Link clicks`, `Clicks (all)`, `Landing page views` (optional), `Results`, `Result indicator`. Month = month of `Reporting starts`. Daily rows are summed (Reach then unavailable). Rows outside the configured months are ignored. Meta leads = `Results` where `Result indicator = actions:leadgen.other`.
- **LeadDetails_<Month><Year>.csv**: `Lead id`, `Created On` (dd/mm/yyyy hh:mm:ss), `Modified On`, `Status`, `Lead Source`, `Brand`, `Facebook Campaign Name`, `Facebook Ad Set ID`, `Facebook Ad Set Name`, `Facebook Ad`. Only these are read; PII columns are never loaded.

## Lead → campaign attribution (Facebook-sourced leads)
1. Campaign named on the lead → that campaign.
2. Blank / `_` → look up `Facebook Ad Set ID` in the evidence table built from **all** named Facebook leads of all brands; use it only if exactly one campaign name is seen for that ID (a Meta ad set belongs to one campaign). Leave-one-out accuracy 99.5–100 %.
3. If the resolved campaign starts with FW → lead excluded (FW is a separate brand).
4. Resolved name in the brand's Meta export → that campaign; resolved but not in export → line "campaign outside Meta export"; unresolved → "campaign not determinable".
Non-Facebook leads never get a campaign (shown in Brand-Wise section C).

## KPI definitions (also in each workbook's KPI Definitions tab)
Qualified = status in `qualified_statuses`; Meetings = `meeting_statuses`; Contacted = status ≠ New Lead; TAT = Modified − Created (hours, eligible if both valid and ≥ 0). CPL/CPQL/cost per meeting = Meta spend ÷ Facebook-sourced CRM leads / qualified / meetings. Reach not additive → only on campaign rows within a month, never in brand/total blocks. Undefined → "–".

## Workbook map
Master Dashboard · All Reports (One Tab) [live mirror of Brand-Wise + Campaign-Wise] · Month-on-Month · Master Pivot · Brand-Wise · Campaign-Wise · KPI Definitions · Data Quality Log · Validation (24 live tie-outs) · Dashboard_Data · Pivot_Data · Data_Meta · Data_CRM. Column grid: 3 hierarchy columns + (N months + total) blocks × 30 KPI columns (Meta 14, CRM 8, Contacted 5, TAT 3).

## Excel constraints learned
- PivotTable body = plain values; no merged cells or formulas in `location ref`; Excel refreshes it on open.
- No frozen panes on the Master Pivot (reference format has none); zoom 85.
- Slicers need desktop Excel; they are defined by slicerCache/slicer/drawing parts + workbook/sheet extLst.
- openpyxl drops charts/pivots/slicers it did not create → never re-save the final file with openpyxl; always inject last.

## Verification suite (gate before delivery)
`verify_reports` (≈78 k cells for 7 brands × 4 months) · `verify_masterpivot` (≈17.8 k cells + structure) · `verify_dashboard` (per dropdown value) · workbook Validation tab (24 ✔) · scan for `#` errors and any "N/A". A 3-month alternative config (`REPORT_CONFIG`) was run end-to-end as a generality test.

## Brand Comparison report (separate pipeline, one workbook)
`pipeline/run_comparison.sh <leads_dir> <meta_experts_dir> <comp_dir> <out_dir>` → `build_comparison_report.py` → `verify_comparison.py`.
- Config: `config/comparison_config.json` (months, qualified statuses, FW rule, per-brand `source` = leaddetails | daewoo_reports | fw_leads, `meta_dir`, Meta file prefix, CRM brand values). It reuses `build_brand_report.load_crm / load_meta` and the Ad-Set-ID attribution by pointing `REPORT_CONFIG` at this config.
- Tabs: Master Dashboard (portfolio tiles, scorecard with verdict colours, formula-driven insights, 4 Sep-vs-Oct charts, notes) · Comparison (per brand: spend, leads, CPL, Quality Leads, Quality %, CPQL with change + verdict; orange columns = leads outside the Meta export / not determinable) · Master Pivot (real PivotTable Brand › Campaign × Month × 6 measures; slicers Brand, Month, Lead attribution, Campaign; plain-value body, no panes) · Data Quality Log · KPI Definitions · Validation (12 live checks) · Dashboard_Data (chart helper, intentional #N/A gaps) · Pivot_Data / Data_Meta / Data_Leads (formula-linked, lead-level rows).
- `inject_pivot.inject(src, dst, spec)` is spec-driven (fields, measures, slicers, hierarchy); `spec=None` keeps the per-brand report layout byte-identical (tested).
- Verification: `verify_comparison.py` recomputes every brand/month/campaign line from the raw files (own code), compares Comparison, Pivot_Data, Data_Leads, Master Pivot body, dashboard tiles + scorecard, and pivot structure (≈5.3 k checks); negative-tested with a wrong qualified list (169 mismatches flagged).
