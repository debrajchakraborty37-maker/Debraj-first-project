# Decisions & user preferences (dated log)

Newest last. Each line: what the user said / chose → what we do → why.

- **2026-10-30 — Seven brands, one workbook each.** Adhira & Appa Coffee, Chhota Bheem, Acer Chhota Bheem, Bonum Cha, Carlton, Natuf, Shayreen. → separate report per brand.
- **Format reference** = `FinalReport.xlsx` (Natuf × Gen Y: front "All Reports (One Tab)", Master Pivot, KPI blocks). User re-shares it when needed; not stored in git (real data).
- **Periods:** month-to-month Jul, Aug, Sep, Oct 2026; October partial (data to 30 Oct). FTD **dropped**.
- **FW is a separate brand → excluded** from everything (CRM brands FW_* / Franchise World, `FW_*` campaign leads, leads on FW ad sets).
- **Levels:** Brand + Campaign only. No Ad-set / Ad tabs or rows.
- **Meta-vs-CRM lead match:** not built (no Meta Leads Center export supplied).
- **Brand mapping:** include In House / MF / FOFO / TK variants (e.g. Natuf + In House Natuf + Natuf_MF; Acer = Acer Electric Bikes + Acer TK). Adhira Toys / Tk UF / Tk MF excluded. "Acer Chhota Bheem" = Acer Electric Bikes + Acer TK (user choice).
- **Monthly Meta exports** replaced the single 4-month export (monthly spend needed). Adhira's came daily.
- **Lead attribution:** use Ad Set ID (not ad-set name) to place unnamed Facebook leads on campaigns; keep a "not determinable" line.
- **Quality bar:** every number must be 100 % correct; independent verification before sending; zip of all reports.
- **Extra tabs:** Master Pivot (real PivotTable with slicers, like the reference) and Master Dashboard (management view), inside each brand workbook; dashboard dropdown is **Month** (single-brand files).
- **Master Pivot fixes:** pivot range must be plain values (no merges/formulas); no frozen panes.
- **"N/A" removed:** undefined cells show "–" (never a fake 0); keep every campaign row; fill Reach / Landing page views only with real Meta data — ask for monthly campaign export with those columns + account-level reach.
- **Reusability:** user will request this report repeatedly → skill `brand-month-report`, docs, config-driven months/brands (`config/report_config.json`), one-command `pipeline/run_report.sh`.

## Open items / known data limits (as of 2026-10-30)
- Reach: Adhira export daily; brand-level unique reach not in any file. Landing page views: missing for most brands.
- 17–70 % of Facebook leads per brand cannot be tied to a campaign (blank name, ad set not uniquely mapped); some leads sit on campaigns outside the supplied Meta export (e.g. in-house campaigns from another ad account) — spend for those not available.
- Slicers could not be click-tested outside desktop Excel.
