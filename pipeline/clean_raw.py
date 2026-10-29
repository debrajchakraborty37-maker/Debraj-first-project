"""Clean and map the raw daily exports (Meta x3, LeadChain x2, CRM LeadModule 1/2, MeetingLeads, MeetingDetails).

Rules (from the Daewoo x ShootOrder Data Notes):
  * LeadChain CSV: rows are padded with empty columns in the middle (+12 per 100 rows) and a header row can repeat -> realign by
    fixed head/tail columns, drop repeated headers, drop duplicate lead IDs.
  * Ad / ad set / campaign names are canonicalised to the name on the most recent lead for that persistent numeric ID.
  * LeadModule1 joins to LeadChain on Social Lead ID; LeadModule2 on the first 15 digits of the Facebook Lead ID.
  * LeadModule2 leads that duplicate LeadModule1 (same first-15 ID) are counted once.
  * MeetingLeads (grouped layout) adds leads that moved out of LeadModule: unique by e-mail, counted as CRM + Qualified leads.
  * Qualified = Qualified, Interested, Details Shared, Negotiation, Token Received, Won, Follow-Up, Meeting Scheduled/Conducted/Follow-Up.
  * Meeting = Meeting Scheduled / Conducted / Follow-Up in LeadModule + all MeetingDetails records, de-duplicated by e-mail.
"""
import csv, glob, os, re, unicodedata, json
import numpy as np
import pandas as pd

QUAL = {"Qualified", "Interested", "Details Shared", "Negotiation", "Token Received", "Won", "Follow-Up",
        "Meeting Scheduled", "Meeting Conducted", "Meeting Follow-Up"}
MEET = {"Meeting Scheduled", "Meeting Conducted", "Meeting Follow-Up"}
NOT_MAPPED = "Not mapped to a campaign"
TAIL = 14  # LEAD TYPE .. STATUS


class MissingFiles(Exception):
    pass


def find_files(raw_dir):
    files = [f for f in glob.glob(os.path.join(raw_dir, "*")) if os.path.isfile(f)]
    low = {f: os.path.basename(f).lower() for f in files}
    pick = lambda pred: sorted(f for f in files if pred(low[f]))
    found = {
        "campaigns": pick(lambda n: "campaigns" in n and n.endswith(".csv")),
        "adsets": pick(lambda n: ("ad-sets" in n or "ad sets" in n or "ad_sets" in n) and n.endswith(".csv")),
        "ads": pick(lambda n: re.search(r"[-_ ]ads[-_ ]", n) is not None and "ad-sets" not in n and n.endswith(".csv")),
        "leadchain": pick(lambda n: "leadchain" in n and n.endswith(".csv")),
        "lm1": pick(lambda n: "leadmodule1" in n and n.endswith((".xlsx", ".xls"))),
        "lm2": pick(lambda n: "leadmodule2" in n and n.endswith((".xlsx", ".xls"))),
        "ml": pick(lambda n: "meetingleads" in n and n.endswith((".xlsx", ".xls"))),
        "md": pick(lambda n: "meetingdetails" in n and n.endswith((".xlsx", ".xls"))),
    }
    missing = [k for k, v in found.items() if not v]
    if missing:
        raise MissingFiles("Missing raw file(s): " + ", ".join(missing) +
                           " — expected Meta Campaigns/Ad sets/Ads CSVs, LeadChain CSV(s), LeadModule1, LeadModule2, MeetingLeads, MeetingDetails.")
    return found


def norm(s):
    return unicodedata.normalize("NFKC", str(s)).strip() if pd.notna(s) else s


def phone10(p):
    d = re.sub(r"\D", "", str(p)) if pd.notna(p) else ""
    return d[-10:] if len(d) >= 10 else ""


# ---------------------------------------------------------------- LeadChain
def load_leadchain(paths):
    frames, raw_rows, repaired = [], 0, 0
    for f in paths:
        rows = list(csv.reader(open(f, encoding="utf-8-sig", newline="")))
        hdr = rows[0]; head_n = len(hdr) - TAIL
        recs = []
        for r in rows[1:]:
            if not r or r[0] == hdr[0]:
                repaired += 1; continue            # repeated header row
            if len(r) != len(hdr): repaired += 1
            recs.append(r[:head_n] + r[-TAIL:])
        frames.append(pd.DataFrame(recs, columns=hdr)); raw_rows += len(recs)
    lc = pd.concat(frames, ignore_index=True)
    lc = lc[lc["ID"].str.strip() != ""]
    dups = int(lc["ID"].duplicated().sum())
    lc = lc.drop_duplicates("ID").copy()
    lc["t"] = pd.to_datetime(lc["CREATED TIME"], errors="coerce")
    srt = lc.sort_values("t")
    for idc, nmc, out in (("CAMPAIGN ID", "CAMPAIGN NAME", "camp"), ("ADSET ID", "ADSET NAME", "adset"), ("AD ID", "AD NAME", "ad")):
        canon = srt[srt[idc].str.strip() != ""].groupby(idc)[nmc].last()
        lc[out] = lc[idc].map(canon).fillna(lc[nmc])
    lc["id15"] = lc["ID"].str[:15]
    lc["email_l"] = lc["EMAIL"].str.lower().str.strip()
    lc["ph10"] = lc["PHONE NUMBER"].map(phone10)
    info = dict(files=[os.path.basename(p) for p in paths], raw_rows=raw_rows, repaired_rows=repaired, dups=dups, unique=len(lc))
    return lc, info


# ---------------------------------------------------------------- CRM
def load_all(raw_dir):
    F = find_files(raw_dir)
    lc, lc_info = load_leadchain(F["leadchain"])
    lm1 = pd.read_excel(F["lm1"][0], dtype=str); lm2 = pd.read_excel(F["lm2"][0], dtype=str)
    ml = pd.read_excel(F["ml"][0], dtype=str); md = pd.read_excel(F["md"][0], dtype=str)
    meta = {k: pd.read_csv(F[k][0]) for k in ("campaigns", "adsets", "ads")}
    start = pd.to_datetime(meta["campaigns"]["Reporting starts"].iloc[0]); end = pd.to_datetime(meta["campaigns"]["Reporting ends"].iloc[0])
    facts = dict(start=start, end=end, files={k: [os.path.basename(p) for p in v] for k, v in F.items()}, lc=lc_info)
    by_id = lc.set_index("ID")
    l15 = lc.drop_duplicates("id15", keep=False).set_index("id15")   # unambiguous 15-digit prefixes

    # ---- LeadModule1
    lm1 = lm1.copy(); lm1["status"] = lm1["Lead Status"].map(norm)
    lm1["created"] = pd.to_datetime(lm1["Created Time"]); lm1["date"] = lm1["created"].dt.normalize()
    lm1["email_l"] = lm1["Email"].str.lower().str.strip()
    facts["lm1_rows"] = len(lm1)
    facts["lm1_created_max"] = lm1["created"].max()
    # ---- LeadModule2 (dedupe against LM1, resolve IDs from the first 15 digits)
    lm2 = lm2.copy(); lm2["status"] = lm2["Status"].map(norm)
    lm2["created"] = pd.to_datetime(lm2["Created On"], errors="coerce"); lm2["date"] = lm2["created"].dt.normalize()
    lm2["id15"] = lm2["Facebook Lead ID"].str[:15]; lm2["email_l"] = lm2["Email"].str.lower().str.strip()
    dup_mask = lm2["id15"].isin(lm1["Social Lead ID"].str[:15])
    facts["lm2_rows"] = len(lm2); facts["lm2_dups"] = lm2.loc[dup_mask, "Email"].tolist(); facts["lm2_created"] = (lm2["created"].min(), lm2["created"].max())
    lm2n = lm2[~dup_mask].copy()

    # vectorised map for LM1
    m1 = lm1.merge(lc[["ID", "camp", "adset", "ad", "t"]], left_on="Social Lead ID", right_on="ID", how="left")
    crm1 = pd.DataFrame(dict(date=m1["date"], camp=m1["camp"].fillna(NOT_MAPPED), adset=m1["adset"].fillna(NOT_MAPPED), ad=m1["ad"].fillna(NOT_MAPPED),
                             status=m1["status"], id=m1["Social Lead ID"], src="LeadModule1", email=m1["email_l"]))
    # LM2
    m2 = lm2n.merge(l15[["camp", "adset", "ad", "ID"]].reset_index(), on="id15", how="left")
    fb = m2["camp"].isna()
    camp2 = m2["camp"].where(~fb, m2["Facebook Campaign Name"]); adset2 = m2["adset"].where(~fb, m2["Facebook Ad Set Name"]); ad2 = m2["ad"].where(~fb, m2["Facebook Ad"])
    facts["lm2_unmatched"] = int(fb.sum())
    crm2 = pd.DataFrame(dict(date=m2["date"], camp=camp2.fillna(NOT_MAPPED), adset=adset2.fillna(NOT_MAPPED), ad=ad2.fillna(NOT_MAPPED),
                             status=m2["status"], id=m2["ID"].fillna(m2["Facebook Lead ID"]), src="LeadModule2", email=m2["email_l"]))
    # ---- MeetingLeads (grouped layout)
    ml = ml.copy()
    for c in ("Team Head", "BDE", "Lead Status (Lead Status history)"):
        ml[c] = ml[c].ffill()
    ml["email_l"] = ml["Email"].str.lower().str.strip(); ml["ph10"] = ml["Phone"].map(phone10)
    ml["ct"] = pd.to_datetime(ml["Created Time"], errors="coerce")
    mlu = ml.sort_values("ct").drop_duplicates(["email_l", "Full Name"]).copy()   # one row per lead (e-mail + name)
    facts["ml_rows"] = len(ml); facts["ml_unique"] = len(mlu)
    existing_ids = set(lm1["Social Lead ID"]) | set(lm2["Facebook Lead ID"]); existing15 = set(lm1["Social Lead ID"].str[:15]) | set(lm2["id15"])

    def match_lc(email, ph, ct):
        c = lc[(lc.email_l == email)] if isinstance(email, str) and email else lc.iloc[0:0]
        if c.empty and ph: c = lc[lc.ph10 == ph]
        if c.empty: return None
        if len(c) > 1 and pd.notna(ct):
            c = c.assign(d=(c.t + pd.Timedelta(hours=5.5) - ct).abs()).sort_values("d")
        return c.iloc[0]
    add_rows, ml_unmatched, ml_dupe = [], [], []
    for r in mlu.itertuples():
        hit = match_lc(r.email_l, r.ph10, r.ct)
        if hit is None:
            ml_unmatched.append(r.Email); continue
        if hit.ID in existing_ids or hit.id15 in existing15:
            ml_dupe.append(r.Email); continue
        add_rows.append(dict(date=pd.Timestamp(r.ct).normalize(), camp=hit.camp, adset=hit.adset, ad=hit.ad, status="Meeting Scheduled", id=r.email_l if False else r.Email, src="MeetingLeads", email=r.email_l))
    crm3 = pd.DataFrame(add_rows)
    facts["ml_added"] = len(crm3); facts["ml_unmatched"] = ml_unmatched; facts["ml_already_in_lm"] = ml_dupe

    crm = pd.concat([crm1, crm2, crm3], ignore_index=True)
    out_of_range = crm[(crm.date < start) | (crm.date > end)]
    facts["crm_out_of_range"] = len(out_of_range)
    crm = crm[(crm.date >= start) & (crm.date <= end)].copy()
    crm["q"] = crm["status"].isin(QUAL).astype(int)
    crm["m"] = ((crm["status"].isin(MEET)) & (crm["src"] != "MeetingLeads")).astype(int)
    crm = crm.sort_values(["date", "src"], kind="stable").reset_index(drop=True)
    facts["crm_dups_id"] = int(crm["id"].duplicated().sum())

    # ---- Meetings: LeadModule meetings + MeetingDetails
    lmm = pd.concat([lm1[lm1["status"].isin(MEET)].merge(lc[["ID", "camp", "adset", "ad"]], left_on="Social Lead ID", right_on="ID", how="left").assign(src="LeadModule")[["email_l", "camp", "adset", "ad", "date", "status", "src"]],
                     lm2n[lm2n["status"].isin(MEET)].merge(l15[["camp", "adset", "ad"]].reset_index(), on="id15", how="left").assign(src="LeadModule")[["email_l", "camp", "adset", "ad", "date", "status", "src"]]], ignore_index=True)
    lmm = lmm[(lmm.date >= start) & (lmm.date <= end)]
    md = md.copy(); md["email_l"] = md["Email"].str.lower().str.strip(); md["ph10"] = md["Phone"].map(phone10)
    md["created"] = pd.to_datetime(md["Created Time"]); md["date"] = md["created"].dt.normalize(); md["status"] = md["Lead Status"].map(norm)
    facts["md_rows"] = len(md)
    md_in = md[(md.date >= start) & (md.date <= end)].copy(); facts["md_in_period"] = len(md_in)
    overlap = md_in["email_l"].isin(lmm["email_l"]) & md_in["email_l"].notna(); facts["md_overlap"] = int(overlap.sum())
    md_in = md_in[~overlap]
    mapped, via_email, unmapped = [], [], []
    for _, r in md_in.iterrows():
        sid = r.get("Social Lead ID"); hit = None; how = "Social Lead ID"
        if isinstance(sid, str) and sid in by_id.index:
            hit = by_id.loc[sid]
        else:
            how = "email"
            c = lc[lc.email_l == r.email_l] if isinstance(r.email_l, str) else lc.iloc[0:0]
            if len(c) != 1 and r.ph10:
                c2 = lc[lc.ph10 == r.ph10]
                c = c2 if len(c) == 0 or (len(c2) == 1) else c
            if len(c) == 1: hit = c.iloc[0]
        if hit is None:
            unmapped.append(dict(email=r.get("Email"), phone=r.get("Phone"), created=r["created"], source=r.get("Lead Source"), team_head=r.get("Team Head")))
            mapped.append((NOT_MAPPED,) * 3 + (r.email_l, r.date, r.status, "MeetingDetails", how))
        else:
            mapped.append((hit.camp, hit.adset, hit.ad, r.email_l, r.date, r.status, "MeetingDetails", how))
            if how == "email": via_email.append(r.get("Email"))
    mdm = pd.DataFrame(mapped, columns=["camp", "adset", "ad", "email_l", "date", "status", "src", "how"])
    facts["md_via_email"] = via_email; facts["md_unmapped"] = unmapped
    meet = pd.concat([lmm.assign(how="Social Lead ID").rename(columns={}), mdm], ignore_index=True)
    meet = meet.rename(columns={"email_l": "email"}).sort_values(["src", "date"], ascending=[False, True], kind="stable").reset_index(drop=True)
    orig = {}
    for df_, col in ((lm1, "Email"), (lm2n, "Email"), (md, "Email")):
        for e in df_[col].dropna(): orig.setdefault(str(e).lower().strip(), str(e).strip())
    meet["email_show"] = meet["email"].map(orig).fillna(meet["email"])
    facts["meet_total"] = len(meet); facts["meet_lm"] = int((meet.src == "LeadModule").sum()); facts["meet_md"] = int((meet.src == "MeetingDetails").sum())
    facts["meet_mapped"] = int((meet.camp != NOT_MAPPED).sum())
    return dict(crm=crm, meet=meet, lc=lc, meta=meta, lm1=lm1, lm2=lm2, ml=ml, md=md, facts=facts, files=F)
