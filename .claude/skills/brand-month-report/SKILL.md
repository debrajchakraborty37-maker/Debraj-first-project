---
name: brand-month-report
description: Month-to-month Brand + Campaign Meta Ads × CRM lead-quality reports (one Excel workbook per brand) with Master Dashboard, Master Pivot (real PivotTable + slicers), Month-on-Month, Brand-Wise, Campaign-Wise, Data Quality Log and Validation tabs. Use when the user asks for the brand reports / "FinalReport" for several brands over several months (e.g. Jul–Oct), or uploads Meta campaign exports + monthly LeadDetails CSVs (a zip like Rahul_Report / Meta_Experts).
---

# Brand month-to-month report (FinalReport format)

Everything needed is in this repo: `config/report_config.json` (months, brands, rules) → `pipeline/` (build, inject pivot, verify) → `docs/ARCHITECTURE.md` (how it works) → `docs/DECISIONS.md` (what the user decided and why). **Read DECISIONS.md first** — the user's preferences below come from there.

## 1. Inputs to ask for (never invent anything)
| What | Where it goes | Notes |
|---|---|---|
| Meta Ads Manager **campaign-level** CSV per brand, **monthly rows** (Breakdown → Time → Month), with columns Reach and Landing page views | `<meta_dir>/<prefix>…Campaigns….csv` | Prefix per brand is in `config/report_config.json`. Daily rows are accepted but then campaign Reach cannot be summed (shows "–"). Ad-set / Ad exports are NOT used. |
| CRM Lead Module export, one CSV per month: `LeadDetails_<MonthName><Year>.csv` | `<lead_dir>/` | Needs columns Lead id, Created On, Modified On, Status, Lead Source, Brand, Facebook Campaign Name, Facebook Ad Set ID. Contains PII — never commit, never copy names/phones/emails into outputs. |
| Brand list + which CRM `Brand` values belong to each brand | `config/report_config.json` → `brands` | Confirm with the user when a new brand/variant appears (e.g. In House, MF, FOFO, TK variants). |
| Reference format `FinalReport.xlsx` | not stored in git (real data) | Only needed again if the layout must change; `config/final_report_spec.md` + `docs/ARCHITECTURE.md` encode it. |

## 2. Do this first on every new run (checklist, then WAIT for the user's go-ahead)
1. Unzip each upload into its own empty scratch dir (untrusted); run Python with `-I`.
2. Inventory: files per month, rows, columns, period covered, last lead date (last month is usually partial), Meta export granularity (monthly vs daily), missing columns (Reach, Landing page views).
3. Brand mapping: CRM `Brand` values per brand, unmapped values, **FW brands/campaigns (excluded)**, blank brand `-` (excluded), campaigns outside each brand's Meta export.
4. Report what is missing and what will show "–"; ask only what changes the outcome. Do not build until the user says go.

## 3. Run
```bash
# edit config/report_config.json first if the period or brands changed (months list, partial flag, brands)
pipeline/run_report.sh <lead_dir> <meta_dir> <out_dir>            # all brands: build → recalc → inject pivot → verify → zip
pipeline/run_report.sh <lead_dir> <meta_dir> <out_dir> "Natuf"    # one brand
REPORT_CONFIG=/path/other.json pipeline/run_report.sh …            # alternative config (tests, other periods)
```
Needs python3 with pandas, numpy, openpyxl, and LibreOffice (`soffice`). ~2 min for 7 brands. The script exits non-zero if any verifier finds a mismatch — **never send files that did not pass all four stages.**

## 4. Rules that must hold (user decisions — see DECISIONS.md)
- One workbook per brand; levels **Brand + Campaign only** (no ad-set / ad level, no FTD, no Meta-vs-CRM lead match unless a Meta Leads Center export is supplied).
- Month blocks side by side + a period-total block; the last month is **partial** (label it, never compare like-for-like silently).
- **FW is a separate brand → always excluded** (CRM brands starting FW / Franchise World, leads on `FW_*` campaigns, and leads whose Ad Set ID belongs to an FW campaign). Out-of-scope brands (Adhira Toys / Tk UF / Tk MF, etc.) stay out unless the user adds them.
- Cost metrics = Meta spend ÷ **Facebook-sourced** CRM leads. Other sources are shown in Brand-Wise section C without cost.
- Facebook leads with no campaign name are placed on a campaign **only through a unique Ad Set ID** (all leads carrying that ID name the same campaign). **Never** by ad-set name (89 % accurate on test = not acceptable). The rest stay on a "not determinable" line; campaigns outside the Meta export stay on "outside Meta export".
- Undefined ratios (0 ÷ 0, missing source data) show a dash "–" — never "N/A" text, never a fake 0. Real zero counts stay 0. Keep every campaign row, including inactive ones.
- Each workbook has: Master Dashboard (first tab; Month dropdown, tiles, charts, highlights), All Reports (One Tab), Month-on-Month, Master Pivot, Brand-Wise, Campaign-Wise, KPI Definitions, Data Quality Log, Validation, Dashboard_Data, Pivot_Data, Data_Meta, Data_CRM.
- Quality bar: **100 % correct**. State honestly what source data is missing (Reach / Landing page views / leads without campaign) and what export would fill it.

## 5. Pitfalls already hit (don't repeat)
- openpyxl cannot write PivotTables/slicers and the LibreOffice recalculation drops them → `inject_pivot.py` runs **last**, on the recalculated file.
- The Master Pivot range must contain **plain values only — no formulas, no merged cells** (Excel refuses to refresh), and the tab must have **no frozen panes** (16 frozen header rows made it impossible to scroll). `inject_pivot.py` and `verify_masterpivot.py` enforce this.
- Meta exports may contain months outside the configured period → they are ignored (counted in the Data Quality Log).
- Landing page views are missing/blank in several exports → "–"; check the export before promising numbers.
- Slicers only work in **desktop Excel** (not LibreOffice / Google Sheets / most previews). We cannot click-test them in this environment — say so, and ask the user to confirm after opening one file. If Excel shows a repair message, get its text.
- Brand names in CRM have variants/typos (e.g. "Carlon Spa") — map via config, don't pattern-match campaign names.

## 6. Deliver
Zip of the workbooks (`Brand_Reports.zip`, made by run_report.sh) via SendUserFile; short summary: what changed, checks passed (counts), what is "–" and why, anything for the user to confirm. Outputs, raw data and the reference workbook stay out of git (`.gitignore`); code, config, docs and this skill are committed and pushed.


## 7. Brand Comparison report (second report type)
When the user asks to **compare two months across many brands** (CPL, Quality Leads, Quality Lead %, CPQL) in ONE workbook with a Master Pivot + Master Dashboard: use `pipeline/run_comparison.sh` (config `config/comparison_config.json`, decisions in `docs/DECISIONS.md` → "Brand Comparison report"). Inputs: monthly LeadDetails CSVs, Meta campaign CSVs (per account), the Daewoo reports and the FW lead file when those brands are included. Rules: cost basis excludes leads on campaigns outside the supplied Meta files; Daewoo from its reports; FW = Facebook form leads only; FW and Adhira & Appa Toys are separate brands; Tk = Tamil Nadu–Kerala (belongs to Coffee / Acer). Always run `verify_comparison.py` (exit 0) before sending, and tell the user about cut-off differences and brands without Meta spend.
