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
- **FW:** Kustard-FW Meta spend ÷ Facebook form leads in FW_LeadData ('face book' source) — bulk Excel uploads (82 %) not counted. FW lead file ends 27 Oct because the FW lead campaign was STOPPED (user confirmed 2026-10-31) — so FW's Oct CPL is correct, not overstated.
- **Cost basis (important):** leads on campaigns whose spend is NOT in the supplied Meta files ("outside Meta export", e.g. Natuf's in-house campaigns: 86 % of Sep, 39 % of Oct) are excluded from CPL / Quality % / CPQL and listed separately; undetermined-campaign leads stay in. The 7 brand reports' brand-total CPL still uses all Facebook leads (not changed — offer to align).
- **TK = Tamil Nadu–Kerala:** 'Adhira & Appa Tk UF/MF' and 'Acer TK' are Coffee / Acer leads (campaign names 'AAC … TN-Kerala'). Adhira & Appa here includes TK; the earlier 7 reports excluded Adhira TK (~226 Sep leads). Adhira & Appa Toys = brand 'Adhira & Appa Toys' only; no Meta export supplied → cost shows a dash.
- **Cut-offs differ:** Meta (Rahul set) to 30 Oct, new Meta files to 31 Oct, LeadDetails to 30 Oct 13:15, FW leads to 27 Oct (campaign stopped), Daewoo to 30 Oct; Oct is partial. Counts (Quality Leads) are not like-for-like with a full month.
- **Month label:** in the Brand Comparison report the October column/month reads "Oct 2026" (no "(partial)"); the partial-month caveat stays in the notes. Config key `partial_in_label: false` (default true keeps the 7 brand reports' labels).
- **Dashboard graphics:** Master Dashboard also has a 'Graphical interpretation' section: CPL change %, CPQL change %, Quality Lead % change (pp) per brand as green (improved) / red (worse) bars, and Oct share of Meta spend vs share of quality leads per brand. Chart data lives in Dashboard_Data (formulas, NA() gaps).
- **Adhira & Appa Toys Meta data received (2026-10-31):** one campaign 'E_Adhira & Appa Toys_23092026' (Sep ₹23,215.85 / Oct ₹103,272.73); ad-set and ad exports reconcile exactly. Toys now has CPL/CPQL. Rule: Meta exports can carry a first SUMMARY row with a blank Campaign name (the period total) — `load_meta` ignores blank-name rows so spend is never double counted (none of the other 11 exports had one).
- **Slicers:** user confirmed (2026-10-31) the Master Pivot slicers work in desktop Excel.

## 2026-11-01 — New data pack analysed (no report built yet)
- Data.zip = 12 Meta accounts × 3 levels (Sep–Oct, all to 31 Oct), LeadData1 (all Sep), LeadData2 (all Oct to 31 Oct), FWLeads (same as before, to 27 Oct). Full findings in `docs/DATA_INVENTORY_2026-11-01.md`. User asked Brio to analyse and remember it, then wait for instructions.

## 2026-11-01 — Brand Comparison report rebuilt on the new data pack (Oct 1–31)
- **User answers:** add `Carlton_Salon_MF` to Carlton (yes); data must be **1 Oct – 31 Oct**; do NOT align the 7 brand reports now (they stay as delivered); **include WhatsApp leads**.
- **Data:** Meta = new exports (all to 31 Oct); CRM = `LeadData1.csv` (all Sep) + `LeadData2.csv` (all Oct to 31 Oct 23:59); FW = `FWLeads.csv`. Config: `lead_files`, `lead_sources` = [Facebook, Whatsapp Cloud API], `fw_lead_file`, Toys prefix `A-&-A-Toys`; Oct no longer flagged partial.
- **WhatsApp leads** (Lead Source 'Whatsapp Cloud API', click-to-WhatsApp ads) are counted with Facebook leads in CPL / Quality Leads / Quality % / CPQL. They match Meta's 'messaging conversations' (Adhira & Appa Sep 3,668 vs 3,609). Most have no campaign name → 'campaign not determinable' (kept in cost basis). Comparison tab shows WhatsApp leads per brand (green block, right). Brand reports unaffected (their `lead_sources` default = Facebook).
- **Daewoo stays on its own CRM reports** for both months: only 391 of the Oct report's 1,853 leads exist in LeadData (it holds a fraction of Daewoo's leads), so LeadData cannot replace it. Consequence: Daewoo October = 1–30 Oct (report) because Daewoo's 31 Oct leads were not supplied, even though the new Daewoo Meta export runs to 31 Oct (₹1,415,611). Ask the user for the Daewoo report/leads to 31 Oct to extend it.
- **Cut-offs now:** both months complete, except FW leads (campaign stopped 27 Oct) and Daewoo Oct (to 30 Oct).

## 2026-11-02 — Website leads added; lead sources made visible
- **User:** include 'Website' and 'WhatsApp Cloud API' leads. WhatsApp was already included (6,189 leads) but only visible in a far-right column; **Website added** (151 leads: Carlton Oct 91 net, Adhira & Appa 16, Natuf 5, FW 1). Config `lead_sources` = [Facebook, Whatsapp Cloud API, Website].
- **Visibility:** Master Dashboard has a 'Where the leads come from' section (stacked charts by brand for Sep and Oct); Comparison tab green block lists WhatsApp and Website leads per brand. Verifier checks both. Other CRM sources (Google Ads 52, Organic Dm 38, Manual 1, Excel uploads, GOOGLE_SHEETS) are still NOT counted.

## 2026-11-02 — EVERY lead in the lead data is counted (Brand Comparison)
- **User:** "add each & every lead from the lead data, otherwise the CPL will go high." Choices: the 10 LeadData brands take the lead count from the CRM lead data (all Lead Sources); **FW = count ALL FW leads** (incl. bulk Excel uploads); **Daewoo stays on its two reports**.
- Config `lead_sources` = `["*"]` (= all sources; `report_config.src_mask`). 7 brand reports keep their default (Facebook only).
- Effect: for the 10 brands only ~180 extra leads (Google Ads 52, Organic Dm 38, Manual 1, small Excel) → CPL moves ≤ ₹3. **FW** counts 10,142 Sep / 1,263 Oct leads (was 1,074 / 947) → FW CPL Sep ₹123 (was ≈₹1,160; ~9.1k Excel uploads carry no ad spend), Oct ₹723. Disclosed on the report.
- Comparison tab: source split Facebook / WhatsApp / Website / Other (cols AL–AO); dashboard charts E/F have 4 series. Verifier: 6,156 checks, 0 mismatches.

## 2026-11-02 — Daewoo October now 1–31 Oct (1,950 leads)
- **User:** Daewoo lead count is 1,950 → supplied `Daewoo x ShootOrder … MTD-1-31Oct-FTD-31-Oct2026.xlsx` (Data_CRM 1,950 rows, spend ₹1,415,611.46, qualified flag 466). Config `daewoo_reports.Oct` points to it; Daewoo Oct CPL ₹726, CPQL ₹3,038. Daewoo is no longer an exception to the 1–31 Oct period (only FW ends 27 Oct).

## 2026-11-02 — Leads on campaigns outside the Meta export now INCLUDED in CPL
- **User:** "Include those leads in CPL also." Reverses the 2026-10-31 cost-basis rule. Config `outside_in_cpl: true` (builder + verifier honour it; false restores the old rule). Lead counts now = every lead in LeadData1/2 (10 brands, minus FW-campaign leads) and FWLeads.
- Effect: Natuf Sep CPL ₹1,475 → ₹207 (8,010 leads; 6,884 sit on in-house campaigns whose spend is NOT in the Meta files, so CPL is understated), Oct ₹712 → ₹447; FW Sep ₹123 → ₹120; Carlton Sep ₹1,579 → ₹1,478; Adhira & Appa Sep ₹220 → ₹213. Quality Lead % for Natuf falls (225 / 8,010 in Sep) for the same reason. The orange columns still list these leads and the notes warn about the understatement.

## Open items / known data limits (as of 2026-10-30)
- Reach: Adhira export daily; brand-level unique reach not in any file. Landing page views: missing for most brands.
- 17–70 % of Facebook leads per brand cannot be tied to a campaign (blank name, ad set not uniquely mapped); some leads sit on campaigns outside the supplied Meta export (e.g. in-house campaigns from another ad account) — spend for those not available.
- Slicers: confirmed working in desktop Excel by the user (cannot be click-tested in this environment).
