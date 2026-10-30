# FinalReport spec (distilled from templates/FinalReport_TEMPLATE.xlsx, Natuf x Gen Y, MTD 1-16 Oct 2026)

## Workbook tabs (23, in order)
All Reports (One Tab) · MTD Report · FTD Report · Master Pivot · Brand-Wise · Campaign-Wise · AdSet-Wise · Ad-Wise · Meta vs CRM Recon · Meta Lead Match · Lead Status & TAT · Data Quality Log · KPI Definitions · Validation · Data_Campaigns · Data_AdSets · Data_Ads · Data_CRM · Data_MetaLeads · Data_MeetingScheduled · Data_UnmappedMeetings · Data_MeetingConducted · Pivot_Data

## "All Reports (One Tab)" layout (A:CE, header row 5, band row 4)
- A-E Hierarchy: Brand/class, Campaign, Ad Set, Ad, Delivery
- F-U Meta MTD: Spend, Impr, Reach, Freq, Clicks, Link Clicks, CTR, Link CTR, CPC, Link CPC, CPM, LPV, Results, Result Rate, Meta Leads, CPL(Meta)
- V-AC CRM MTD: CRM Leads, Qualified, Qual %, Meetings, Meeting %, CPL(CRM), CPQL, Cost/Meeting
- AD-AI Recon: Matched, Unmatched Meta, Unattributed CRM, Match %, CRM/Meta, Lead Variance
- AJ-AN Contacted: Contacted, %, Not Contacted, %, Blank/Invalid
- AO-AY TAT: Avg/Median/Min/Max hrs, Avg/Median d-h-m, Eligible, Missing Created, Missing Modified, Invalid, Negative
- AZ-CE FTD mirror (Meta, CRM, quality, contacted, TAT, cost, match)
- Rows: 6 account total, 9 brand-wise, 20 campaign-wise (+TOTAL), 48 ad-set-wise (+TOTAL), 121 ad-wise (+TOTAL, orange balance rows), 191+ "How to read" notes
- Every cell is a live link (=IF(src="","",src)) to the detail tab named in the section band.

## KPI rules
- Frequency = Impr/Reach; CTR = Clicks/Impr; Link CTR = LinkClicks/Impr; CPC = Spend/Clicks; Link CPC = Spend/LinkClicks; CPM = Spend/Impr*1000; Result Rate = Results/Impr
- Meta Leads = Results where indicator = actions:leadgen.other; CPL(Meta) = Spend/Meta Leads
- CRM Leads = distinct Lead IDs created in period; Qualified = {Qualified, Follow-Up, Details Shared, Meeting Scheduled, Meeting Conducted}; Meetings = {Follow-Up, Meeting Scheduled, Meeting Conducted}
- Qual % and Meeting % = / CRM Leads; CPL(CRM)=Spend/CRM Leads; CPQL=Spend/Qualified; Cost/Meeting=Spend/Meetings
- Contacted = Status != New Lead; Not Contacted = New Lead; TAT = Modified On - Created On (hours; not first-response)
- Match: Meta Leads Center lead <-> CRM lead 1:1 on phone (last 10) or e-mail, CRM Created On within 10 min of Meta time; Meta time Pacific -> IST = +12h30. Variance = Meta - Matched.
- FTD = single latest day; Meta FTD metrics come from day-only exports, never by subtraction.

## Non-negotiables
- N/A (never fake 0) when denominator is 0 or input missing. Campaign/Ad-set/Ad totals are alternative views - never added. Reach is not additive (total rows show range / N/A).
- Ads export lacks ad-set column: place ads by continuity/balance; unlisted spend = orange balance rows (Ad-set total - listed ads). Zero-activity entities shown grey.
- Anything unresolved goes to Data Quality Log with PASS/INFO/WARN/FAIL; Validation tab holds live-formula tie-outs (spend, impressions, clicks, leads, qualified, meetings, contacted+not=total, no duplicate Lead IDs).

## Period change (user request)
Reports are month-to-month: Jul, Aug, Sep, Oct 2026 (Oct partial/MTD). The template's MTD/FTD blocks are the pattern; the month blocks replace/extend them. Open: whether FTD stays.

## Scope change (user request): Brand + Campaign level only
Drop AdSet-Wise, Ad-Wise, Data_AdSets, Data_Ads, ad-set/ad sections and the Ad Set / Ad columns (C, D) in the front tab, orange balance rows, and ad-level Validation/Data-Quality checks. Keep Brand-Wise, Campaign-Wise and all KPI blocks. Notes/Data Quality Log rewritten accordingly.
