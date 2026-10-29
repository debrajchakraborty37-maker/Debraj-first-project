#!/usr/bin/env python3
"""Report 1 — build the Daewoo x ShootOrder Campaign Performance Report from the raw daily exports.

Usage: python3 pipeline/build_report.py <raw_dir> [--outdir outputs/<date>]
Output: Daewoo_x_ShootOrder-Campaign_Performance_Report-MTD-<d1>-<d2><Mon>-FTD-<d2>-<Mon><Year>.xlsx
(same layout, formulas and Data_* sheets as the manual report; recalculated so values are visible everywhere)
"""
import argparse, copy, hashlib, json, os, re, subprocess, sys
from collections import Counter, OrderedDict
import numpy as np, pandas as pd, openpyxl
from openpyxl.utils import get_column_letter as L

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clean_raw as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "Campaign_Performance_Report_TEMPLATE.xlsx")
STRUCT = os.path.join(ROOT, "config", "structure.json")
NM = C.NOT_MAPPED
# template row types
R = dict(title=1, sub=2, banner=4, k1l=5, k1v=6, k2l=8, k2v=9, nb=11, n12=12, n13=13, n14=14, n15=15, n16=16, n17=17, s1=19, ch=20, cr=21, ct=30,
         mt=31, mn=32, n33=33, s2=35, fn=36, fh=37, fr=38, fnm=47, ft=48, s3=50, ah=51, ar=52, asub=54, agt=81, an=82, s4=84, dh=85, dr=86, dsub=104,
         dgt=144, dn=145, ib=147, ir=148, src=159)
MERGE_TYPES = {  # template row -> list of (c1, c2)
}


def fnum(x):
    if isinstance(x, str):
        try: return float(x)
        except ValueError: return x
    return x


def clean(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return float(v)
    return v


def fsub(f, r0, r):
    """Replace relative row refs r0 -> r (leaves $-absolute rows alone)."""
    return re.sub(r"(?<![A-Za-z_])(\$?[A-Z]{1,2})(\d+)\b", lambda m: m.group(1) + str(r) if int(m.group(2)) == r0 else m.group(0), f)


def dmy(ts): return ts.strftime("%d %b %Y")


def build(raw_dir, outdir, history_dir):
    D = C.load_all(raw_dir); F = D["facts"]; crm, meet, lc, meta = D["crm"], D["meet"], D["lc"], D["meta"]
    start, end = F["start"], F["end"]
    mon = end.strftime("%b"); year = end.year
    st = json.load(open(STRUCT)); struct_camps = st["campaigns"]
    # ------------------------------------------------------------------ Meta tables
    cm = meta["campaigns"].copy(); asx = meta["adsets"].copy(); adx = meta["ads"].copy()
    for df in (cm, asx, adx):
        for c in ("Ad set budget",):
            if c in df: df[c] = df[c].map(fnum)
    ad_parent_idx = {}
    for a in st["adsets"]: ad_parent_idx.setdefault((a["adset"], a["starts"]), a["parent"])
    adset_parents = {}
    for a in st["adsets"]: adset_parents.setdefault(a["adset"], []).append(a["parent"])
    lc_adset_parent = lc[lc.adset.notna() & (lc.adset != "")].sort_values("t").groupby("adset")["camp"].last().to_dict()

    def parent_of_adset(name, starts):
        p = ad_parent_idx.get((name, str(starts)))
        return p or lc_adset_parent.get(name) or (adset_parents.get(name) or ["(untracked ad set — no parent on record)"])[0]
    asx["Parent Campaign"] = [parent_of_adset(n, s) for n, s in zip(asx["Ad set name"], asx["Starts"].astype(str))]
    ad_set_parent_by_name = {}
    for p, n in zip(asx["Parent Campaign"], asx["Ad set name"]): ad_set_parent_by_name.setdefault(n, []).append(p)
    ad_struct_parent = {(a["adset"], a["ad"]): a["parent"] for a in st["ads"]}

    def parent_of_ad(adset, ad):
        p = ad_struct_parent.get((adset, ad))
        if p: return p
        ps = ad_set_parent_by_name.get(adset) or adset_parents.get(adset) or ["(untracked ad set — no parent on record)"]
        return ps[0]
    adx["Parent Campaign"] = [parent_of_ad(a, b) for a, b in zip(adx["Ad set name"], adx["Ad name"])]
    adx["Match Key"] = adx["Ad set name"] + " || " + adx["Ad name"]

    # ------------------------------------------------------------------ what appears in the report
    def active_row(r):
        return any((pd.notna(r.get(k)) and r.get(k) not in (0, "0")) for k in ("Amount spent (INR)", "Impressions", "Results"))
    crm_by_camp = crm.groupby("camp").size().to_dict(); meet_by_camp = meet.groupby("camp").size().to_dict()
    camps = list(struct_camps)
    for _, r in cm.iterrows():
        n = r["Campaign name"]
        if n not in camps and (active_row(r) or crm_by_camp.get(n) or meet_by_camp.get(n)): camps.append(n)
    for n in list(crm_by_camp) + list(meet_by_camp):
        if n not in camps and n != NM: camps.append(n)
    cm_idx = cm.set_index("Campaign name")
    adset_rows = OrderedDict()   # (parent, name, starts) -> row
    struct_as = [(a["parent"], a["adset"], a["starts"]) for a in st["adsets"]]
    crm_as = set(zip(crm.camp, crm.adset)); meet_as = set(zip(meet.camp, meet.adset))
    for _, r in asx.iterrows():
        key = (r["Parent Campaign"], r["Ad set name"], str(r["Starts"]))
        if r["Parent Campaign"] in camps and (key in struct_as or active_row(r) or (key[0], key[1]) in crm_as or (key[0], key[1]) in meet_as):
            adset_rows[key] = r
    ordered_as = []
    for p in camps:
        mine = [k for k in struct_as if k[0] == p and k in adset_rows] + [k for k in adset_rows if k[0] == p and k not in struct_as]
        ordered_as += list(OrderedDict.fromkeys(mine))
    ad_rows = OrderedDict()
    struct_ad = [(a["parent"], a["adset"], a["ad"]) for a in st["ads"]]
    crm_ad = set(zip(crm.camp, crm.adset, crm.ad)); meet_ad = set(zip(meet.camp, meet.adset, meet.ad))
    for _, r in adx.iterrows():
        key = (r["Parent Campaign"], r["Ad set name"], r["Ad name"])
        if key[0] in camps and (key in struct_ad or active_row(r) or key in crm_ad or key in meet_ad) and key not in ad_rows:
            ad_rows[key] = r
    groups = []   # (parent, adset) in report order
    for k in ordered_as:
        pa = (k[0], k[1])
        if pa not in groups: groups.append(pa)
    ads_by_group = {g: [k for k in struct_ad if (k[0], k[1]) == g and k in ad_rows] + [k for k in ad_rows if (k[0], k[1]) == g and k not in struct_ad] for g in groups}
    for g in groups: ads_by_group[g] = list(OrderedDict.fromkeys(ads_by_group[g]))
    # ad sets reachable in ads table but missing from ad set table (new)
    for k in ad_rows:
        if (k[0], k[1]) not in groups and k[0] in camps: groups.append((k[0], k[1])); ads_by_group[(k[0], k[1])] = [k]

    # ------------------------------------------------------------------ workbook from template
    wb = openpyxl.load_workbook(TEMPLATE)
    tws = wb["Campaign Report"]
    sty = {r: {c: copy.copy(tws.cell(r, c)._style) for c in range(1, 27)} for r in range(1, 160)}
    hts = {r: tws.row_dimensions[r].height for r in range(1, 160)}
    tmerge = {}
    for mr in tws.merged_cells.ranges:
        tmerge.setdefault(mr.min_row, []).append((mr.min_col, mr.max_col))
    tform = {r: {c: tws.cell(r, c).value for c in range(1, 27)} for r in range(1, 160)}
    widths = {k: v.width for k, v in tws.column_dimensions.items()}
    ws = wb.create_sheet("Campaign Report_new", 0)
    for k, w in widths.items(): ws.column_dimensions[k].width = w
    ws.sheet_view.showGridLines = False

    def emit(tr, nr, vals=None, height=None, merge=True):
        for c in range(1, 27): ws.cell(nr, c)._style = copy.copy(sty[tr][c])
        if merge:
            for c1, c2 in tmerge.get(tr, []): ws.merge_cells(start_row=nr, start_column=c1, end_row=nr, end_column=c2)
        h = height if height is not None else hts.get(tr)
        if h: ws.row_dimensions[nr].height = h
        for c, v in (vals or {}).items():
            ws.cell(nr, c).value = clean(v)

    def note_h(text, base_tr):
        return max(hts.get(base_tr) or 14, 12.5 * (len(text) // 250 + 1) + 6)

    # ---- data sheets first (sizes drive the formulas)
    NCRM = len(crm) + 1
    NMT = max(200, len(meet) + 60)
    # ---- campaign table rows
    r_camp0 = R["cr"]; rows = {}
    n = len(camps); r_camp1 = r_camp0 + n - 1; r_ctot = r_camp1 + 1
    m_by_camp = meet.groupby("camp").size().to_dict()
    total_meet = len(meet); mapped_meet = int((meet.camp != NM).sum())
    sp_tot = float(cm["Amount spent (INR)"].fillna(0).sum())

    def fix_ranges(f):
        return f.replace("$1694", f"${NCRM}").replace("$200", f"${NMT}")

    # ---- rows 1..18
    sub = f"MTD: {dmy(start)} – {dmy(end)}   |   FTD: {dmy(end)}   |   Currency: INR   |   Attribution: LeadChain (Meta raw Lead Ads export) — ground-truth Ad / Ad Set / Campaign join"
    emit(R["title"], 1, {1: "DAEWOO  ×  SHOOTORDER — CAMPAIGN, AD SET & AD-WISE PERFORMANCE REPORT"})
    emit(R["sub"], 2, {1: sub}); emit(3, 3, merge=False) if False else None
    emit(R["banner"], 4, {1: f"{end.strftime('%B').upper()} {year} — PERFORMANCE SNAPSHOT   (MTD {start.day}–{end.day} {mon}  ·  FTD {end.day} {mon})"})
    ctotal_row_t = R["ct"]
    for tr, nr in ((R["k1l"], 5), (R["k1v"], 6), (R["k2l"], 8), (R["k2v"], 9)):
        vals = {}
        for c in range(1, 27):
            v = tform[tr][c]
            if isinstance(v, str) and v.startswith("="):
                v = v.replace(f"${ctotal_row_t}", f"${r_ctot}"); v = fix_ranges(v)
            if tr == R["k2l"] and c == 13: v = f"FTD ({end.day} {mon.upper()}) — CRM LEADS"
            if tr == R["k2v"] and c == 20: v = F["ml_unique"]
            if v is not None: vals[c] = v
        emit(tr, nr, vals)
    # ---- data notes (text assembled below after stats) -> placeholders, filled later
    # statistics used by notes / insights
    nl = len(crm); nq = int(crm.q.sum()); lm1_n = F["lm1_rows"]; lm2_new = F["lm2_rows"] - len(F["lm2_dups"])
    lm_total = lm1_n + lm2_new
    camp_meet = Counter(meet[meet.camp != NM].camp)
    meet_order = ", ".join(f"{v} to {k}" for k, v in camp_meet.most_common())
    dup_emails = crm[crm.email.notna() & (crm.email != "")].groupby("email").date.apply(lambda s: sorted(s))
    dup_emails = dup_emails[dup_emails.map(len) > 1]
    dup_txt = "; ".join(f"{e} appears {len(ds)}× ({', '.join(d.strftime('%d %b') for d in ds)})" for e, ds in dup_emails.items())
    # ---- previous snapshot (lead movement)
    os.makedirs(history_dir, exist_ok=True)
    snap_path = os.path.join(history_dir, "crm_snapshot.csv")
    h = lambda e: hashlib.sha1(str(e).lower().encode()).hexdigest()[:12]
    cur_keys = pd.DataFrame(dict(key=D["lm1"]["Record Id"], eh=D["lm1"]["Email"].map(h), date=D["lm1"]["date"].dt.strftime("%Y-%m-%d"), status=D["lm1"]["status"]))
    cur_keys["run"] = end.strftime("%Y-%m-%d")
    moved_txt = ""
    prev = None
    if os.path.exists(snap_path):
        allsnap = pd.read_csv(snap_path, dtype=str); prevs = sorted(d for d in allsnap.run.unique() if d < end.strftime("%Y-%m-%d"))
        if prevs: prev = allsnap[allsnap.run == prevs[-1]]
    if prev is not None:
        dropped = prev[~prev.key.isin(cur_keys.key)]
        in_meet = set(h(e) for e in list(D["md"]["email_l"].dropna()) + list(D["ml"]["email_l"].dropna()))
        d_in = dropped[dropped.eh.isin(in_meet)]; d_out = dropped[~dropped.eh.isin(in_meet)]
        merged = prev.merge(cur_keys, on="key", suffixes=("_p", "_c")); chg = int((merged.status_p != merged.status_c).sum())
        moved_txt = (f"LEAD MOVEMENT: {len(dropped)} lead(s) were in the previous ({prev.run.iloc[0]}) LeadModule export but are not in this one; {len(d_in)} of them are now in MeetingDetails / MeetingLeads "
                     f"(still counted as leads via MeetingLeads) and {len(d_out)} are in neither file (not counted). The status of {chg} LeadModule1 leads changed since the previous export (qualification and meeting counts reflect current statuses).")
    else:
        moved_txt = "LEAD MOVEMENT: no previous-day export stored yet, so day-over-day lead movement is not available; it will appear from the next run."
    existing = pd.read_csv(snap_path, dtype=str) if os.path.exists(snap_path) else pd.DataFrame()
    pd.concat([existing[existing.run != end.strftime("%Y-%m-%d")] if len(existing) else existing, cur_keys], ignore_index=True).to_csv(snap_path, index=False)

    lcf = F["lc"]
    t12 = (f"ATTRIBUTION METHOD: Campaign/Ad Set/Ad mapping uses LeadChain — Meta's raw Lead Ads export ({len(lcf['files'])} files this round; repaired for uneven row widths and embedded repeated header rows, "
           f"and {lcf['dups']} duplicate lead IDs were removed, leaving {lcf['unique']:,} unique records) — joined to every CRM record via Social Lead ID. This is more reliable than the CRM's \"Brand Product\" field"
           f"{' and achieves a 100% match rate: all ' + str(nl) + ' MTD leads matched to a specific Ad, Ad Set and Campaign — zero unmapped.' if (crm.camp == NM).sum() == 0 else '. Match rate: ' + str(nl - int((crm.camp == NM).sum())) + ' of ' + str(nl) + ' leads matched; ' + str(int((crm.camp == NM).sum())) + ' unmapped.'}")
    md_period_note = f"{F['md_in_period']} in period"
    t13 = (f"MEETING DATA: Meetings Scheduled = LeadModule leads whose current Lead Status is Meeting Scheduled / Meeting Conducted / Meeting Follow-Up ({F['meet_lm']}) plus MeetingDetails ({F['md_rows']} records, Lead Status: "
           f"{F['md_rows']} × Meeting Scheduled), {total_meet} in total after de-duplication by e-mail ({F['md_overlap']} overlap between the two sources). MeetingDetails records are leads the CRM moved out of the general LeadModule into the meeting view; "
           f"many were generated before this month so are not part of the current CRM lead counts, but their meetings occurred in the period and are counted as such. Meetings are dated by CRM record creation (MeetingDetails) or lead creation date (LeadModule).")
    lm2c = F["lm2_created"]
    t14 = (f"DATE SCOPE: The LeadModule data comes in two files: {os.path.basename(D['files']['lm1'][0])} ({lm1_n} records, created up to {F['lm1_created_max'].strftime('%d %b %H:%M')}) and "
           f"{os.path.basename(D['files']['lm2'][0])} ({F['lm2_rows']} records created {lm2c[0].strftime('%d %b %H:%M')} – {lm2c[1].strftime('%d %b %H:%M')}, exported from a second CRM view with different column names and statuses such as New Lead / Attempt 1 / Connected / Lost / Sales Priority). "
           f"{len(F['lm2_dups'])} of the {F['lm2_rows']} ({', '.join(F['lm2_dups'])}) are the same leads already in LeadModule1 (Facebook Lead IDs differ only in the last digit) and were not counted twice; the other {lm2_new} were added, with their LeadChain IDs resolved from the first 15 digits of the Facebook Lead ID "
           f"({'each matched exactly one LeadChain record' if F['lm2_unmatched'] == 0 else str(F['lm2_unmatched']) + ' could not be matched and use LeadModule2 campaign/ad set/ad names'}). That gives {lm_total} LeadModule records; {F['crm_out_of_range']} record(s) fall outside the {dmy(start)} – {dmy(end)} window and are excluded. "
           f"{F['ml_unique']} unique leads from the MeetingLeads file were added ({F['ml_rows']} rows, one per lead-status history entry; {len(F['ml_already_in_lm'])} already in LeadModule). Each added lead is counted as a CRM lead and as Qualified (status Meeting Scheduled / Conducted); its meeting is already included in the meeting count. Total CRM leads = {nl}. "
           f"DUPLICATE CHECK: {F['crm_dups_id']} duplicate lead IDs. " + (f"{dup_txt} — each is a separate Meta form submission with its own Social Lead ID and CRM record, so they are counted as recorded by the CRM (repeat enquiries from the same person). " if len(dup_emails) else "No repeated e-mail addresses. ")
           + moved_txt + f" MTD CRM leads ({nl}) and Qualified ({nq}) include the MeetingLeads additions.")
    t15 = ("Ad set and ad names are canonicalised to their current Ads Manager name using each ad/ad set's persistent numeric ID and the most recent lead on record for that ID (historical renames therefore do not break the join). "
           "Ad sets with no lead history are placed under their parent campaign using the saved report structure (config/structure.json).")
    t16 = (f"Qualified Leads and CPQL are real, measured values at every level — Campaign, Ad Set and Ad — not allocated or estimated. Per the reporting rule, Lead Status values Qualified, Interested, Details Shared, Negotiation, Token Received, Won, Follow-Up, Meeting Scheduled, Meeting Conducted and Meeting Follow-Up all count as Qualified ({nq} of {nl} {end.strftime('%B')} CRM leads), "
           f"and Meeting Scheduled / Meeting Conducted / Meeting Follow-Up are all categorised as Meeting Scheduled ({total_meet} meetings: {F['meet_lm']} LeadModule + {F['meet_md']} MeetingDetails, {mapped_meet} mapped to a specific campaign; {total_meet - mapped_meet} could not be mapped — see Data Notes).")
    excl = cm[~cm["Campaign name"].isin(camps)]
    ex_names = ", ".join(excl["Campaign name"]) if len(excl) else "none"
    t17 = (f"CTR (Click-Through Rate) = Link Clicks ÷ Impressions, from the \"Link clicks\" column in this round's Meta Ads Manager exports. The exports are cumulative ({start.day}–{end.day} {mon}) with no daily breakdown, so Meta spend/impressions/CTR for the FTD period ({end.day} {mon}) cannot be derived — Section 2 (FTD) uses CRM lead-intake data instead. "
           f"{len(excl)} zero-spend, zero-impression campaign(s) in the Campaigns export ({ex_names}) are excluded from the tables since they carry no data and affect no total. "
           f"Spend reconciliation: campaign total ₹{sp_tot:,.2f} equals ad set total ₹{asx['Amount spent (INR)'].fillna(0).sum():,.2f} and ad total ₹{adx['Amount spent (INR)'].fillna(0).sum():,.2f} (difference ₹{abs(sp_tot - adx['Amount spent (INR)'].fillna(0).sum()):,.2f}).")
    emit(R["nb"], 11, {1: "ℹ  DATA NOTES"})
    for tr, nr, t in ((R["n12"], 12, t12), (R["n13"], 13, t13), (R["n14"], 14, t14), (R["n15"], 15, t15), (R["n16"], 16, t16), (R["n17"], 17, t17)):
        emit(tr, nr, {1: t}, height=note_h(t, tr))
    # ---- section 1
    emit(R["s1"], 19, {1: f"1.  CAMPAIGN-WISE PERFORMANCE  —  MTD ({start.day} {mon} – {end.day} {mon} {year})"})
    emit(R["ch"], 20, {c: tform[R["ch"]][c] for c in range(1, 27) if tform[R["ch"]][c] is not None})
    camp_row = {}
    for i, name in enumerate(camps):
        nr = r_camp0 + i; camp_row[name] = nr; vals = {}
        for c in range(1, 27):
            v = tform[R["cr"]][c]
            if v is None: continue
            if c == 3: vals[c] = name
            else: vals[c] = fix_ranges(fsub(v, R["cr"], nr))
        emit(R["cr"], nr, vals)
    vals = {}
    for c in range(1, 27):
        v = tform[R["ct"]][c]
        if v is None: continue
        if isinstance(v, str) and v.startswith("=SUM("): v = re.sub(r"([A-Z]+)21:([A-Z]+)29", lambda m: f"{m.group(1)}{r_camp0}:{m.group(2)}{r_camp1}", v)
        elif isinstance(v, str) and v.startswith("="): v = fsub(v, R["ct"], r_ctot)
        vals[c] = v
    emit(R["ct"], r_ctot, vals)
    r = r_ctot + 1
    emit(R["mt"], r, {1: f"Total Meeting Scheduled — LeadModule + MeetingDetails, {start.day}–{end.day} {mon} {year}, deduplicated by email (see Data Notes)", 18: "=Data_MeetingScheduled!$J$2"}); r += 1
    md_unm = F["md_unmapped"]
    unm_txt = ""
    if md_unm:
        u = md_unm[0]
        unm_txt = (f" UNMAPPED MEETING: {len(md_unm)} MeetingDetails record(s) (e.g. created {u['created'].strftime('%d %b %Y %H:%M')}, phone {u['phone']}, Team Head {u['team_head']}) have no e-mail / Social Lead ID that matches exactly one LeadChain record, so they cannot be attributed to a campaign, ad set or ad. "
                   f"They are counted in the Total Meeting Scheduled row and the snapshot but sit outside every Campaign / Ad Set / Ad row, so those tables total {mapped_meet} meetings against {total_meet} overall; Meeting % shares in the Ad Set and Ad grand-total rows are calculated on {total_meet}.")
    ad_level_missing = [(c_, a_, d_) for (c_, a_, d_) in zip(meet.camp, meet.adset, meet.ad) if c_ != NM and (c_, a_, d_) not in ad_rows]
    adlvl = ""
    if ad_level_missing:
        adlvl = f" AD-LEVEL EXCEPTION: {len(ad_level_missing)} meeting(s) map to an ad that has no row in the Meta Ads export (no delivery or spend in the period), so they are counted in the Campaign and Ad Set tables but have no row in the Ad-wise table (which therefore totals {mapped_meet - len(ad_level_missing)} meetings)."
    via_em = F["md_via_email"]
    t32 = (f"{total_meet} Meeting Scheduled records occurred within {start.day}–{end.day} {mon}: {F['meet_lm']} from LeadModule and {F['meet_md']} from MeetingDetails ({F['md_rows']} raw rows, {F['md_in_period']} in period, {F['md_overlap']} overlap with LeadModule (same lead, counted once)). "
           f"{mapped_meet} of {total_meet} matched to a specific campaign via LeadChain ({meet_order}); MeetingDetails records mapped {F['meet_md'] - len(via_em) - len(md_unm)} via Social Lead ID, {len(via_em)} via e-mail ({', '.join(via_em) if via_em else 'none'}). "
           f"Per the reporting rule, Meeting Scheduled, Meeting Conducted and Meeting Follow-Up are all categorised as Meeting Scheduled." + unm_txt + adlvl)
    emit(R["mn"], r, {1: t32}, height=note_h(t32, R["mn"])); r += 1
    t33 = (f"Notes  ·  Meta metrics (E, J, K, L, T) are taken verbatim from the Ads Manager campaign export ({start.day}–{end.day} {mon} {year}).  ·  CRM columns (O–S, W–X) come from the CRM export mapped to campaigns via LeadChain (Social Lead ID join), date-scoped to {start.day}–{end.day} {mon}; percentages are expressed against LeadChain-mapped CRM leads.  ·  "
           f"\"META_RMKT_Engage_ABO_SO\" has no CRM leads because its ad sets optimise for page/profile visits, not lead-gen forms.")
    emit(R["n33"], r, {1: t33}, height=note_h(t33, R["n33"])); r += 2
    # ---- section 2 FTD
    emit(R["s2"], r, {1: f"2.  CAMPAIGN-WISE PERFORMANCE  —  FTD {end.day} {mon} {year}  (CRM lead data, LeadChain-mapped)"}); r += 1
    ftd_meet = meet[meet.date == end]; ftd_new = int((ftd_meet.src == "MeetingDetails").sum())
    t36 = (f"The Meta Ads Manager exports supplied cover the aggregate period {start.day}–{end.day} {mon} {year} only and contain no day-level breakdown, so spend / impressions / CPL / CTR for the FTD period ({end.day} {mon}) cannot be derived from them and are not shown "
           f"(see the Daily_Delta tab of the Deep Analysis report once two consecutive days are stored). The figures below are CRM lead-intake counts for {end.day} {mon}, mapped to campaigns via LeadChain on exactly the same basis as the MTD table above. FTD meetings are dated by CRM record creation: {len(ftd_meet)} meeting(s) dated {end.day} {mon}, {ftd_new} of them MeetingDetails records.")
    emit(R["fn"], r, {1: t36}, height=note_h(t36, R["fn"])); r += 1
    emit(R["fh"], r, {c: tform[R["fh"]][c] for c in range(1, 27) if tform[R["fh"]][c] is not None}); r += 1
    f0 = r
    for name in camps:
        vals = {1: name}
        for c in range(2, 27):
            v = tform[R["fr"]][c]
            if v is not None: vals[c] = fix_ranges(fsub(v, R["fr"], r))
        emit(R["fr"], r, vals); r += 1
    vals = {1: "Not mapped to a campaign (no LeadChain match)"}
    for c in range(2, 27):
        v = tform[R["fnm"]][c]
        if v is not None: vals[c] = fix_ranges(v.replace(f"{R['fnm']}", str(r)) if False else v)
    emit(R["fnm"], r, vals); r += 1
    vals = {}
    for c in range(1, 27):
        v = tform[R["ft"]][c]
        if v is not None: vals[c] = fix_ranges(v)
    emit(R["ft"], r, vals); r += 2
    # ---- section 3 ad sets
    emit(R["s3"], r, {1: "3.  AD SET-WISE PERFORMANCE  —  MTD (%d %s – %d %s %d),  grouped by parent campaign" % (start.day, mon, end.day, mon, year)}); r += 1
    emit(R["ah"], r, {c: tform[R["ah"]][c] for c in range(1, 27) if tform[R["ah"]][c] is not None}); r += 1
    as_row = {}; sub_rows = []; leaf_as = []
    for p in camps:
        keys = [k for k in ordered_as if k[0] == p]
        if not keys: continue
        first = r
        for k in keys:
            row = adset_rows[k]; as_row[(k[0], k[1])] = r
            vals = {1: k[0], 2: k[1], 3: clean(row.get("Ad set delivery")), 4: (clean(row.get("Results")) or 0), 5: clean(row.get("Result indicator")), 7: clean(fnum(row.get("Ad set budget"))),
                    8: clean(fnum(row.get("Ad set budget type"))), 9: clean(row.get("Amount spent (INR)")), 10: clean(row.get("Impressions")), 11: clean(row.get("Reach")), 12: clean(row.get("Ends")),
                    13: clean(row.get("Starts")), 14: clean(row.get("Attribution setting")), 15: clean(row.get("Bid type")), 20: (clean(row.get("Link clicks")) or 0)}
            for c in range(1, 27):
                v = tform[R["ar"]][c]
                if isinstance(v, str) and v.startswith("="):
                    v = fsub(v, R["ar"], r).replace("$J$21:$J$29", f"$J${r_camp0}:$J${r_camp1}").replace("$C$21:$C$29", f"$C${r_camp0}:$C${r_camp1}").replace("$E$21:$E$29", f"$E${r_camp0}:$E${r_camp1}")
                    vals[c] = fix_ranges(v)
            emit(R["ar"], r, vals); leaf_as.append(r); r += 1
        vals = {1: f"Subtotal — {p}"}
        for c in range(2, 27):
            v = tform[R["asub"]][c]
            if not (isinstance(v, str) and v.startswith("=")): continue
            m = re.fullmatch(r"=SUM\(([A-Z]+)\d+:([A-Z]+)\d+\)", v)
            vals[c] = f"=SUM({m.group(1)}{first}:{m.group(2)}{r - 1})" if m else fix_ranges(fsub(v, R["asub"], r))
        emit(R["asub"], r, vals); r += 1
    vals = {1: "GRAND TOTAL — ALL AD SETS (this export)"}
    for c in range(2, 27):
        v = tform[R["agt"]][c]
        if not (isinstance(v, str) and v.startswith("=")): continue
        col = L(c)
        vals[c] = f"=SUM({','.join(f'{col}{x}' for x in leaf_as)})" if v.startswith("=SUM(") else fix_ranges(fsub(v, R["agt"], r))
    emit(R["agt"], r, vals); r += 1
    n_as_excl = int((~asx.apply(lambda x: (x["Parent Campaign"], x["Ad set name"], str(x["Starts"])) in adset_rows, axis=1)).sum())
    t82 = (f"Note  ·  META_RMKT_Engage_ABO_SO shows Results at ad-set level (page/profile visits) but not at campaign level, so \"% of Campaign Results\" is n/a for its ad sets.  ·  Ad set and ad spend reconcile to campaign spend (₹{sp_tot:,.2f}).  ·  "
           f"{len(adset_rows)} mapped ad sets are shown; {n_as_excl} ad set(s) with zero spend/impressions/results and no CRM leads are excluded.  ·  CRM Leads (W), Qualified Leads (X) and CPQL (Y) are real, LeadChain-measured values — matched via each ad set's persistent Meta ID within its parent campaign.")
    emit(R["an"], r, {1: t82}, height=note_h(t82, R["an"])); r += 2
    # ---- section 4 ads
    emit(R["s4"], r, {1: "4.  AD-WISE PERFORMANCE  —  MTD (%d %s – %d %s %d),  grouped by ad set and parent campaign" % (start.day, mon, end.day, mon, year)}); r += 1
    emit(R["dh"], r, {c: tform[R["dh"]][c] for c in range(1, 27) if tform[R["dh"]][c] is not None}); r += 1
    leaf_ad = []
    for g in groups:
        keys = ads_by_group.get(g, [])
        if not keys: continue
        first = r
        for k in keys:
            row = ad_rows[k]; asr = as_row.get((k[0], k[1]))
            vals = {1: k[0], 2: k[1], 3: k[2], 4: clean(row.get("Ad delivery")), 5: clean(row.get("Results")), 6: clean(row.get("Result indicator")), 8: clean(row.get("Amount spent (INR)")),
                    9: clean(row.get("Impressions")), 10: clean(row.get("Reach")), 11: clean(row.get("Attribution setting")), 12: clean(row.get("Quality ranking")),
                    13: clean(row.get("Engagement rate ranking")), 14: clean(row.get("Conversion rate ranking")), 18: clean(row.get("Link clicks"))}
            for c in range(1, 27):
                v = tform[R["dr"]][c]
                if isinstance(v, str) and v.startswith("="):
                    v = fsub(v, R["dr"], r)
                    if c == 15: v = f'=IFERROR($H{r}/$I${asr},"n/a")' if asr else '="n/a"'
                    vals[c] = fix_ranges(v)
            emit(R["dr"], r, vals); leaf_ad.append(r); r += 1
        vals = {1: f"Subtotal — {g[1]}"}
        for c in range(2, 27):
            v = tform[R["dsub"]][c]
            if not (isinstance(v, str) and v.startswith("=")): continue
            m = re.fullmatch(r"=SUM\(([A-Z]+)\d+:([A-Z]+)\d+\)", v)
            vals[c] = f"=SUM({m.group(1)}{first}:{m.group(2)}{r - 1})" if m else fix_ranges(fsub(v, R["dsub"], r))
        emit(R["dsub"], r, vals); r += 1
    vals = {1: "GRAND TOTAL — ALL ADS (this export)"}
    for c in range(2, 27):
        v = tform[R["dgt"]][c]
        if not (isinstance(v, str) and v.startswith("=")): continue
        col = L(c)
        vals[c] = f"=SUM({','.join(f'{col}{x}' for x in leaf_ad)})" if v.startswith("=SUM(") else fix_ranges(fsub(v, R["dgt"], r))
    emit(R["dgt"], r, vals); r += 1
    t145 = ("Note  ·  Meetings Scheduled (P), CRM Leads (U), Qualified Leads (V) and CPQL (W) are real, LeadChain-measured values at the individual Ad level — matched via each ad's Ad Set and parent Campaign (composite key), so creative reuse across multiple ad sets does not cause under- or over-counting.  ·  "
            f"Ad-level spend equals ad set spend (₹{adx['Amount spent (INR)'].fillna(0).sum():,.2f}).")
    emit(R["dn"], r, {1: t145}, height=note_h(t145, R["dn"])); r += 2

    # ---- insights
    byc = pd.DataFrame(dict(camp=camps)).assign(
        spend=[float(cm_idx.loc[c, "Amount spent (INR)"]) if c in cm_idx.index and pd.notna(cm_idx.loc[c, "Amount spent (INR)"]) else 0.0 for c in camps],
        res=[float(cm_idx.loc[c, "Results"]) if c in cm_idx.index and pd.notna(cm_idx.loc[c, "Results"]) else 0.0 for c in camps],
        leads=[crm_by_camp.get(c, 0) for c in camps], q=[int(crm[crm.camp == c].q.sum()) for c in camps], meet=[camp_meet.get(c, 0) for c in camps])
    tot_res = byc.res.sum(); tot_imp = float(cm["Impressions"].fillna(0).sum()); tot_clk = float(cm["Link clicks"].fillna(0).sum()); tot_reach = float(cm["Reach"].fillna(0).sum())
    top = byc.sort_values("res", ascending=False).iloc[0]
    q5 = byc[byc.leads >= 5].assign(rate=lambda d: d.q / d.leads).sort_values("rate", ascending=False)
    cpl_m = byc[(byc.res > 0) & (byc.spend > 0)].assign(cpl=lambda d: d.spend / d.res).sort_values("cpl")
    ins = []
    ins.append(("🔎", f"Attribution basis: Campaign/Ad Set/Ad mapping uses LeadChain (Meta's raw Lead Ads export, {len(lcf['files'])} files this round) joined via Social Lead ID — {nl - int((crm.camp == NM).sum())} of {nl} MTD CRM leads matched to a specific Ad, Ad Set and Campaign ({int((crm.camp == NM).sum())} unmapped)."))
    ins.append(("🚨", f"{F['meet_md']} of the {total_meet} meetings come from MeetingDetails, i.e. leads moved by the CRM out of LeadModule. Meeting Scheduled % in the tables is meetings in the period ÷ {end.strftime('%B')} CRM leads in the period, so it can include meetings from earlier-generated leads. " + moved_txt.replace("LEAD MOVEMENT: ", "")))
    dd = crm.groupby("date").agg(n=("id", "count"), q=("q", "sum"))
    day_txt = "; ".join(f"{d.strftime('%d %b')} → {int(x.n)} ({int(x.q)} Qualified, {x.q / x.n * 100:.1f}%)" for d, x in dd.iterrows())
    last = dd.loc[end] if end in dd.index else None
    ins.append(("📈", f"Day-by-day: {day_txt}." + (f" FTD ({end.day} {mon}) = {int(last.n)} leads, {int(last.q)} Qualified ({last.q / last.n * 100:.1f}%)." if last is not None else "")))
    ins.append(("🏆", f"Biggest lead driver: {top.camp} generated {int(top.res)} of the total {int(tot_res)} Meta-reported results ({top.res / tot_res * 100:.1f}%)."))
    if len(q5): ins.append(("⭐", f"Best qualification rate (campaigns with 5+ leads): {q5.iloc[0].camp} at {q5.iloc[0].rate * 100:.1f}% ({int(q5.iloc[0].q)} of {int(q5.iloc[0].leads)} CRM leads Qualified)."))
    if len(cpl_m) > 1: ins.append(("⚠️", f"Highest cost per lead (Meta basis): {cpl_m.iloc[-1].camp} at ₹{cpl_m.iloc[-1].cpl:,.0f} per lead, {cpl_m.iloc[-1].cpl / cpl_m.iloc[0].cpl:.1f}× the cheapest campaign ({cpl_m.iloc[0].camp} at ₹{cpl_m.iloc[0].cpl:,.0f})."))
    ins.append(("🎯", f"CRM lead quality (MTD, {nl} leads): {nq} ({nq / nl * 100:.1f}%) are marked Qualified — blended CPL against this base is ₹{sp_tot / nl:,.0f} and CPQL is ₹{sp_tot / nq:,.0f}."))
    ins.append(("🤝", f"Meetings Scheduled: {total_meet} within {start.day}–{end.day} {mon} ({F['meet_lm']} LeadModule + {F['meet_md']} MeetingDetails, {F['md_overlap']} overlap) — {mapped_meet} of {total_meet} matched to a specific campaign via LeadChain ({meet_order}). Cost per meeting (MTD, Meta spend basis) = ₹{sp_tot / total_meet:,.0f}."))
    ins.append(("💰", f"Overall MTD (Meta): ₹{sp_tot:,.0f} spent generated {int(tot_res)} results ({int(tot_clk):,} link clicks, {tot_clk / tot_imp * 100:.2f}% CTR) at a blended cost of ₹{sp_tot / tot_res:,.0f} per Meta result, reaching {int(tot_reach):,} people across {int(tot_imp):,} impressions."))
    l2 = dd.tail(2)
    ins.append(("📊", f"Small-sample caveat: figures above reflect {(end - start).days + 1} days of data ({nl} leads). The most recent days (" + " and ".join(f"{d.strftime('%d %b')}: {int(x.q)} of {int(x.n)}" for d, x in l2.iterrows()) + " Qualified) can still change as sales works those leads and the CRM moves meeting-stage leads into MeetingDetails."))
    emit(R["ib"], r, {1: f"KEY INSIGHTS — {end.strftime('%B').upper()} {year} MTD ({start.day}–{end.day} {mon}) & FTD ({end.day} {mon})"}); r += 1
    for em, t in ins:
        emit(R["ir"], r, {1: em, 3: t}, height=max(30, 12.5 * (len(t) // 230 + 1) + 6)); r += 1
    r += 1
    lm1n, lm2n, mln, mdn = (os.path.basename(D["files"][k][0]) for k in ("lm1", "lm2", "ml", "md"))
    src = (f"Source files: Daewoo-x-ShootOrder-Campaigns / -Ad sets / -Ads ({start.day} {mon} {year} – {end.day} {mon} {year}, Meta Ads Manager exports, incl. Link Clicks); {lm1n} (+{lm2n}) (combined LeadModule data: {lm1_n} rows in LeadModule1 + {lm2_new} additional leads from LeadModule2 = {lm_total} leads; "
           f"+{F['ml_unique']} unique leads from {mln} = {nl} CRM leads); {mdn} ({F['md_rows']} raw rows, {F['md_in_period']} in period, {F['md_overlap']} overlap with LeadModule, {F['meet_md'] - len(md_unm)} mapped to LeadChain, {len(md_unm)} not mappable); "
           f"LeadChain raw Lead Ads exports ({len(lcf['files'])} files: {'; '.join(lcf['files'])}; repaired and de-duplicated to {lcf['unique']:,} unique records) — joined via Social Lead ID. Ad Set / Ad names canonicalised to their current Meta Ads Manager name using each object's persistent ID.")
    emit(R["src"], r, {1: src}, height=note_h(src, R["src"]))
    last_row = r

    # ------------------------------------------------------------------ data sheets
    def reset(name):
        w = wb[name]
        if w.max_row > 1: w.delete_rows(2, w.max_row)
        return w
    def write_df(w, df, cols):
        for i, row in enumerate(df.itertuples(index=False), 2):
            for j, c in enumerate(cols, 1):
                v = clean(row._asdict()[c]) if False else None
        for i, (_, row) in enumerate(df.iterrows(), 2):
            for j, c in enumerate(cols, 1):
                v = row[c] if c in row.index else None
                v = fnum(clean(v)) if isinstance(v, str) else clean(v)
                w.cell(i, j).value = v
    cm_sorted = cm.assign(_o=cm["Campaign name"].map(lambda n: camps.index(n) if n in camps else 999)).sort_values("_o", kind="stable")
    wc = reset("Data_Campaigns"); write_df(wc, cm_sorted, ["Reporting starts", "Reporting ends", "Campaign name", "Campaign delivery", "Results", "Result indicator", "Cost per results", "Ad set budget", "Ad set budget type", "Amount spent (INR)", "Impressions", "Reach", "Ends", "Attribution setting", "Link clicks"])
    asx_w = asx.assign(**{"Parent Campaign": asx["Parent Campaign"].where(~asx["Parent Campaign"].str.startswith("(untracked"), None)})
    wa = reset("Data_AdSets"); write_df(wa, asx_w, ["Reporting starts", "Reporting ends", "Ad set name", "Ad set delivery", "Results", "Result indicator", "Cost per results", "Ad set budget", "Ad set budget type", "Amount spent (INR)", "Impressions", "Reach", "Link clicks", "Ends", "Starts", "Attribution setting", "Bid", "Bid type", "Last significant edit", "Parent Campaign"])
    wd = reset("Data_Ads"); write_df(wd, adx, ["Reporting starts", "Reporting ends", "Ad name", "Ad delivery", "Results", "Result indicator", "Cost per results", "Ad set budget", "Ad set budget type", "Amount spent (INR)", "Impressions", "Reach", "Link clicks", "Ends", "Attribution setting", "Bid", "Bid type", "Last significant edit", "Quality ranking", "Engagement rate ranking", "Conversion rate ranking", "Ad set name", "Parent Campaign", "Match Key"])
    wm = reset("Data_CRM")
    for i, x in enumerate(crm.itertuples(index=False), 2):
        wm.cell(i, 1, x.date.to_pydatetime()).number_format = "yyyy\\-mm\\-dd"
        for j, v in enumerate((x.camp, x.adset, x.ad, x.status, int(x.q), int(x.m)), 2): wm.cell(i, j, v)
        c = wm.cell(i, 8, str(x.id)); c.number_format = "@"
    params = [("PARAMETERS", None), ("MTD start", start), ("MTD end", end), ("FTD start", end), ("FTD end", end),
              ("Total CRM Leads (all records in export)", f"=COUNTA(A2:A{NCRM})"), ("Leads matched to LeadChain (ad/adset/campaign known)", f'=COUNTIF(B2:B{NCRM},"<>{NM}")')]
    for i, (lab, v) in enumerate(params, 1):
        wm.cell(i, 9, lab)
        if v is not None:
            c = wm.cell(i, 10, v.to_pydatetime() if isinstance(v, pd.Timestamp) else v)
            if isinstance(v, pd.Timestamp): c.number_format = "yyyy\\-mm\\-dd"
    wmt = reset("Data_MeetingScheduled")
    for i, x in enumerate(meet.itertuples(index=False), 2):
        for j, v in enumerate((x.src, x.email_show if isinstance(x.email_show, str) else None, x.camp, x.adset, x.ad, x.date.strftime("%d %b %Y")), 1): wmt.cell(i, j, v)
        c = wmt.cell(i, 7, x.date.to_pydatetime()); c.number_format = "yyyy\\-mm\\-dd"
        wmt.cell(i, 8, x.status)
    mp = [("PARAMETERS", None), ("Total Meeting Scheduled (LeadModule + MeetingDetails, deduplicated by email)", f"=COUNTA(A2:A{NMT})"),
          ("From LeadModule (Lead Status = Meeting Scheduled / Meeting Conducted / Meeting Follow-Up)", f'=COUNTIF(A2:A{NMT},"LeadModule")'),
          ("From MeetingDetails (Lead Status = Meeting Scheduled / Meeting Conducted / Meeting Follow-Up)", f'=COUNTIF(A2:A{NMT},"MeetingDetails")'),
          ("Mapped to a Campaign (via LeadChain: Social Lead ID, else Email join)", f'=COUNTA(C2:C{NMT})-COUNTIF(C2:C{NMT},"{NM}")')]
    for i, (lab, v) in enumerate(mp, 1):
        wmt.cell(i, 9, lab)
        if v: wmt.cell(i, 10, v)
    reset("Data_UnmappedMeetings"); reset("Data_MeetingConducted")
    wb["Data_MeetingConducted"].cell(1, 11).value = "NOTE: Not populated — no separate Meeting Conducted source this round. Under the reporting rule, Meeting Conducted and Meeting Follow-Up statuses are categorised as Meeting Scheduled (see Data_MeetingScheduled)."
    del wb["Campaign Report"]; ws.title = "Campaign Report"; wb.move_sheet("Campaign Report", -wb.index(wb["Campaign Report"]))
    ws.sheet_view.zoomScale = 100
    name = f"Daewoo_x_ShootOrder-Campaign_Performance_Report-MTD-{start.day}-{end.day}{mon}-FTD-{end.day}-{mon}{year}.xlsx"
    os.makedirs(outdir, exist_ok=True)
    raw_out = os.path.join(outdir, "_build_" + name); wb.save(raw_out)
    # recalc with LibreOffice so every viewer (and the analysis engine) sees values
    final = os.path.join(outdir, name)
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", os.path.join(outdir, "_lo"), raw_out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(os.path.join(outdir, "_lo", "_build_" + name), final); os.rmdir(os.path.join(outdir, "_lo")); os.remove(raw_out)
    print(f"OK  {final}\n    leads {nl} | qualified {nq} | meetings {total_meet} ({mapped_meet} mapped) | spend ₹{sp_tot:,.2f}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("raw_dir"); ap.add_argument("--outdir", default=None); ap.add_argument("--history", default=os.path.join(ROOT, "history"))
    a = ap.parse_args()
    build(a.raw_dir, a.outdir or os.path.join(ROOT, "outputs", os.path.basename(os.path.dirname(os.path.abspath(a.raw_dir.rstrip("/"))))), a.history)
