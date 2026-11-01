# Data inventory — Data.zip received 2026-11-01 (analysed, not yet used for a report)

Raw files stay out of git (PII). This note is the durable memory of what they contain and how they differ from earlier data.

## What is in it (36 files, 1 Sep – 31 Oct 2026)
| Group | Files | Notes |
|---|---|---|
| Meta exports, 12 accounts × 3 levels (Campaigns / Ad-sets / Ads) | A&A Toys, Daewoo x ShootOrder, Govintham, Bonum Cha (in-house), Shayreen by Natuf, Adhira & Appa (in-house), Acer, Carlton (Kustard), FW (Kustard), Nonstop Physio (Kustard), Natuf x Gen Y, Chhota Bheem (Shoot Order) | All rows **monthly** (Sep, Oct), `Reporting ends` = **31 Oct** for every account. No blank-name summary rows in these files. Report uses Campaign level only. |
| CRM | `LeadData1.csv` (31,331 rows) = **all of September** (Created On 1–30 Sep); `LeadData2.csv` (29,410 rows) = **all of October** (1 Oct 00:00 → 31 Oct 23:59) | Same 139-column LeadDetails layout; `Lead id` unique in each; the two files share no lead ids. Extracted ~2 Nov (Modified On up to 2 Nov). |
| FW | `FWLeads.csv` (11,668 rows) | Identical rows to the earlier `FW_LeadData.csv` (same keys, order, 118 columns); only 25 statuses updated. Created On 2 Sep → **27 Oct** (FW lead campaign was stopped — user confirmed). 82 % Excel uploads; 2,011 'face book' leads. |

## Meta spend (named campaign rows, ₹)
| Account | Sep | Oct | Ad-set = Campaign? | Ads = Campaign? |
|---|---|---|---|---|
| A&A Toys | 23,215.85 | 103,272.73 | yes | yes |
| Daewoo x ShootOrder | 832,599.27 | 1,415,611.46 | yes | yes |
| Govintham | 15,479.82 | 113,323.00 | yes | no (−1,865 / −2,190) |
| Bonum Cha | 480,100.02 | 68,665.42 | yes | yes |
| Shayreen by Natuf | 141,016.09 | 0.00 | yes | yes |
| Adhira & Appa | 1,289,483.49 | 950,981.55 | yes | no (−94,422 / −17,898) |
| Acer | 510,669.52 | 268,729.10 | yes | yes |
| Carlton | 1,476,179.43 | 2,489,871.77 | yes | no (−2,117 / −11,668) |
| FW | 1,246,366.25 | 913,087.16 | yes | no (−295,365 / −194,712) |
| Nonstop Physio | 522,738.02 | 334,157.32 | yes | yes |
| Natuf | 1,661,019.83 | 1,659,440.85 | yes | no (−78,933 / −5,579) |
| Chhota Bheem | 268,451.97 | 565,794.73 | yes | yes (±₹1) |
| **Total** | **8,467,319.56** | **8,882,935.09** | | |
- **September spend is identical to the earlier exports.** October spend is higher for 7 accounts because the new exports include 31 Oct (e.g. Natuf +₹36.5k, Daewoo +₹37.3k vs the old CSV and +₹66.6k vs the Daewoo report which ended 30 Oct, Adhira +₹79.0k, Chhota Bheem +₹47.0k, Acer +₹10.5k, Carlton +₹25.3k, Nonstop +₹4.8k, Govintham +₹3.0k, FW +₹0.2k). Toys, Bonum, Shayreen unchanged.
- Ads-level exports omit spend for several accounts → never use Ads level for totals (Campaign = Ad-set exactly).
- Result indicators: Meta leads = `actions:leadgen.other`; Chhota Bheem and Daewoo also carry `conversion_leads:conversion_lead`; Bonum/Adhira/Carlton/FW/Natuf/Nonstop carry messaging / landing-page-view indicators (not leads).

## Reach and Landing page views
- **Reach is present for every row of every account, monthly** (Adhira & Appa is now monthly, not daily → campaign reach is usable; brand-level unique reach is still not additive).
- **Landing page views** (few campaigns only): Daewoo (Sep 5 / Oct 4 rows), Govintham, Adhira & Appa (3 / 2), Carlton (2 / 3), FW (Sep 1 / Oct 0), Natuf (1 / 1). None for Toys, Bonum, Shayreen, Acer, Nonstop; Chhota Bheem has no column.

## CRM facts
- September file vs earlier `LeadDetails_September2026`: same 31,331 lead ids; 98 statuses updated, 4 brand changes, 18 campaign-name changes, created times identical.
- October file vs earlier `LeadDetails_October2026` (28,100 rows, to 30 Oct 13:15): all 28,100 ids still present; **1,310 new leads** (30 Oct 13:21 → 31 Oct 23:59: 502 on 30 Oct, 808 on 31 Oct); 1,187 statuses updated; 3 brand and 18 campaign-name changes.
- Facebook-source leads for the 12 configured brands (CRM Brand values per `config/comparison_config.json`): Sep / Oct — Acer 7,277 / 3,378 · Adhira & Appa 2,315 / 1,856 · Toys 103 / 325 · Bonum Cha 1,408 / 239 · Carlton 964 / 3,096 · Chhota Bheem 455 / 989 · Govintham 38 / 277 · Natuf 8,014 / 3,621 · Natuf by Shayreen 482 / 0 · Nonstop 1,186 / 1,045. (Daewoo and FW are sourced separately.)
- Unmapped brand values worth a decision: **`Carlton_Salon_MF`** (15 Sep / 65 Oct Facebook leads) looks like a Carlton variant not yet in the config; **`Daewoo`, `SO Daewoo`, `Daewoo_MF`** (Sep 311 / Oct 912 Facebook leads) — far fewer than the Daewoo reports' 1,396 / 1,853, so Daewoo is still better served by its own CRM reports; FW-prefixed Facebook leads inside LeadData (`FW_Stocklist` 399, `FW_All_FICO` 115, `FW_Chhota_bheem` 69, `FW Expansion` 24 …) overlap FW territory (earlier check: ~260 phone overlaps with FW_LeadData) — keep FW = FWLeads.csv only unless told otherwise. Out of scope: Tarzan, NativeTouch, EBG Rental, AGEON, Fractro, Realty*, Kabego Rental.

## What changes if the comparison / brand reports are rebuilt from this data
1. **October is now a COMPLETE month** for Meta (to 31 Oct) and CRM (to 31 Oct 23:59) — except FW leads (stopped 27 Oct) and the Daewoo reports (to 30 Oct). The "(partial)" caveat and `partial` flag in the configs would no longer apply; Oct counts become like-for-like with September.
2. October spend/leads move (see table); September is essentially unchanged (98 status updates).
3. Adhira & Appa campaign Reach becomes available; Landing page views remain mostly dashes.
4. Decisions to confirm before rebuilding: add `Carlton_Salon_MF` to Carlton? keep Daewoo on its reports (Oct report ends 30 Oct while Meta now ends 31 Oct)? align the 7 brand reports' brand-total CPL with the comparison's cost basis?
