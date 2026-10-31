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

- **Agent name:** the report agent is called **Brio** (`.claude/agents/brio.md`); user asked for a small name.

## 2026-10-31 — Brand Comparison report (Sep vs Oct 2026, 12 brands, ONE workbook)
- **Ask:** one report comparing Sep vs Oct for CPL, Quality Leads, Quality Lead %, CPQL for 12 brands (Adhira & Appa, Acer, Chhota Bheem, Bonum Cha, Natuf by Shayreen, Natuf, Carlton, Daewoo, FW, Adhira & Appa Toys, Nonstop Physio, Govintham); one Master Pivot (slicers, clickable, scrollable) + one Master Dashboard for management. FW and Adhira & Appa Toys are separate brands.
- **Quality Lead:** same status list as the 7 brand reports (Qualified, Follow-Up, Details Shared, Meeting Scheduled, Meeting Conducted).
- **Daewoo:** taken from the two Daewoo x ShootOrder reports (Daewoo CRM; spend + leads on campaigns with spend; qualified = the report's own flag, which also counts Interested/Negotiation/Token Received/Won). The Daewoo Meta CSV (to 31 Oct) is not used for spend (reports end 30 Oct).
- **FW:** Kustard-FW Meta spend ÷ Facebook form leads in FW_LeadData ('face book' source) — bulk Excel uploads (82 %) not counted. FW lead file ends 27 Oct, so FW's Oct CPL is overstated.
- **Cost basis (important):** leads on campaigns whose spend is NOT in the supplied Meta files ("outside Meta export", e.g. Natuf's in-house campaigns: 86 % of Sep, 39 % of Oct) are excluded from CPL / Quality % / CPQL and listed separately; undetermined-campaign leads stay in. The 7 brand reports' brand-total CPL still uses all Facebook leads (not changed — offer to align).
- **TK = Tamil Nadu–Kerala:** 'Adhira & Appa Tk UF/MF' and 'Acer TK' are Coffee / Acer leads (campaign names 'AAC … TN-Kerala'). Adhira & Appa here includes TK; the earlier 7 reports excluded Adhira TK (~226 Sep leads). Adhira & Appa Toys = brand 'Adhira & Appa Toys' only; no Meta export supplied → cost shows a dash.
- **Cut-offs differ:** Meta (Rahul set) to 30 Oct, new Meta files to 31 Oct, LeadDetails to 30 Oct 13:15, FW leads to 27 Oct, Daewoo to 30 Oct; Oct is partial. Counts (Quality Leads) are not like-for-like with a full month.
- **Month label:** in the Brand Comparison report the October column/month reads "Oct 2026" (no "(partial)"); the partial-month caveat stays in the notes. Config key `partial_in_label: false` (default true keeps the 7 brand reports' labels).
- **Dashboard graphics:** Master Dashboard also has a 'Graphical interpretation' section: CPL change %, CPQL change %, Quality Lead % change (pp) per brand as green (improved) / red (worse) bars, and Oct share of Meta spend vs share of quality leads per brand. Chart data lives in Dashboard_Data (formulas, NA() gaps).

## Open items / known data limits (as of 2026-10-30)
- Reach: Adhira export daily; brand-level unique reach not in any file. Landing page views: missing for most brands.
- 17–70 % of Facebook leads per brand cannot be tied to a campaign (blank name, ad set not uniquely mapped); some leads sit on campaigns outside the supplied Meta export (e.g. in-house campaigns from another ad account) — spend for those not available.
- Slicers could not be click-tested outside desktop Excel.
