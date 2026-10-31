#!/usr/bin/env python3
"""Independent verifier for the Brand Comparison workbook: recomputes everything from the RAW files (own code path) and compares with
Comparison, Pivot_Data, Master Pivot body, Master Dashboard (tiles + scorecard) and Data_Leads.
usage: verify_comparison.py <leads_dir> <meta_experts_dir> <comp_dir> <workbook.xlsx>   (exit 1 on any mismatch)"""
import os, sys, glob, re, unicodedata, warnings, math
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("REPORT_CONFIG", os.path.join(HERE, "..", "config", "comparison_config.json"))
sys.path.insert(0, HERE)
import pandas as pd, numpy as np, openpyxl
import report_config as rc
import inject_pivot
warnings.filterwarnings("ignore")
LEADS, METAX, COMP, WB = sys.argv[1:5]
CFG, MONTHS, QUAL = rc.CFG, rc.MONTHS, rc.QUAL
MLAB = rc.MLAB
DASH = "–"
OUTSIDE, NOCAP = "Campaign outside Meta export", "Campaign not determinable"
bad, checked = [], 0
norm = lambda s: unicodedata.normalize("NFKC", str(s)).strip()


def cmp(tag, got, exp, tol=1e-9):
    global checked
    checked += 1
    if isinstance(exp, float) and (math.isnan(exp) or math.isinf(exp)): exp = DASH
    if isinstance(exp, str) or isinstance(got, str) or got is None:
        if got != exp: bad.append((tag, got, exp))
    elif abs(got - exp) > tol * max(1, abs(exp)): bad.append((tag, got, exp))


div = lambda a, b: (a / b) if (b is not None and b > 0) else DASH
# ------------------------------------------------------------------ raw loading (independent of the build code)
raw_leads = pd.concat([pd.read_csv(os.path.join(LEADS, rc.lead_file(m)), low_memory=False,
                                   usecols=["Lead id", "Status", "Lead Source", "Brand", "Created On", "Facebook Campaign Name", "Facebook Ad Set ID"]).assign(M=m) for m in MONTHS], ignore_index=True)
raw_leads["cr"] = pd.to_datetime(raw_leads["Created On"], format="%d/%m/%Y %H:%M:%S")
assert (raw_leads["cr"].dt.strftime("%b") == raw_leads["M"]).all()
nm_ = raw_leads[(raw_leads["Lead Source"] == "Facebook") & ~raw_leads["Facebook Campaign Name"].fillna("_").isin(["_", ""]) & ~raw_leads["Facebook Ad Set ID"].fillna("_").isin(["_", ""])]
EV = {k: set(v) for k, v in nm_.groupby("Facebook Ad Set ID")["Facebook Campaign Name"]}
FWRE = "(?i)" + CFG["fw_exclusion_regex"]


def meta_month(prefix, d):
    fs = glob.glob(os.path.join(d, f"{prefix}*Campaigns*.csv")); assert len(fs) == 1, (prefix, fs)
    m = pd.read_csv(fs[0]); m["m"] = pd.to_datetime(m["Reporting starts"]).dt.strftime("%b"); m = m[m["m"].isin(MONTHS)]
    return m


def expected_for(name, spec):
    """returns dict month -> dict(spend, basis_leads, quality, outside, nocap) and per-line dict (camp,month)->(spend, leads, quality, attr)"""
    src = spec["source"]; dirs = {"meta_experts": METAX, "comp": COMP}
    lines, tot = {}, {m: dict(spend=0.0, leads=0, quality=0, outside=0, nocap=0) for m in MONTHS}
    def put(m, camp, attr, leads=0, q=0, spend=0.0):
        k = (camp, m); a = lines.get(k, [0.0, 0, 0, attr]); a[0] += spend; a[1] += leads; a[2] += q; lines[k] = a
    if src == "daewoo_reports":
        for m in MONTHS:
            path = os.path.join(COMP, CFG["daewoo_reports"][m])
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            dc = pd.DataFrame(list(wb["Data_Campaigns"].iter_rows(values_only=True))[1:], columns=list(wb["Data_Campaigns"].iter_rows(values_only=True))[0]).dropna(how="all")
            crm_rows = list(wb["Data_CRM"].iter_rows(values_only=True)); crm = pd.DataFrame(crm_rows[1:], columns=crm_rows[0]).dropna(how="all"); wb.close()
            cols = list(crm.columns); camp_c = next(c for c in cols if c and "campaign" in str(c).lower()); qc = next(c for c in cols if c and str(c).lower().startswith("qualified"))
            act = set(dc[dc["Amount spent (INR)"] > 0]["Campaign name"])
            for _, r in dc.iterrows(): put(m, r["Campaign name"], "Campaign in Meta export", spend=float(r["Amount spent (INR)"]))
            sel = crm[crm[camp_c].isin(act)]
            for camp, g in sel.groupby(camp_c): put(m, camp, "Campaign in Meta export", len(g), int(pd.to_numeric(g[qc], errors="coerce").fillna(0).sum()))
            tot[m]["spend"] = float(dc["Amount spent (INR)"].sum()); tot[m]["leads"] = len(sel); tot[m]["quality"] = int(pd.to_numeric(sel[qc], errors="coerce").fillna(0).sum())
        return tot, lines
    mc = set(); mt = None
    if spec["meta_file_prefix"]:
        mt = meta_month(spec["meta_file_prefix"], dirs[spec["meta_dir"]]); mc = set(mt["Campaign name"])
        for (m, camp), g in mt.groupby(["m", "Campaign name"]): put(m, camp, "Campaign in Meta export", spend=float(g["Amount spent (INR)"].sum()))
        for m in MONTHS: tot[m]["spend"] = float(mt[mt["m"] == m]["Amount spent (INR)"].sum())
    if src == "fw_leads":
        L = pd.read_csv(os.path.join(COMP, CFG["fw_lead_file"]), low_memory=False, usecols=["Status", "Lead Source", "Created On", "Facebook Campaign Name"])
        L["cr"] = pd.to_datetime(L["Created On"], format="%d/%m/%Y %H:%M:%S", errors="coerce"); L["m"] = L["cr"].dt.strftime("%b")
        f = L[L["m"].isin(MONTHS) & L["Lead Source"].fillna("").str.lower().str.replace(r"\s+", "", regex=True).eq("facebook")]
        rows = [(r["m"], (r["Facebook Campaign Name"] if isinstance(r["Facebook Campaign Name"], str) and r["Facebook Campaign Name"] not in ("_", "") else None), r["Status"]) for _, r in f.iterrows()]
    else:
        c = raw_leads[raw_leads["Brand"].isin(spec["crm_brand_values"])]
        c = c[~c["Facebook Campaign Name"].fillna("").str.match(FWRE)]
        c = c[c["Lead Source"] == "Facebook"]
        rows = []
        for _, r in c.iterrows():
            cn = r["Facebook Campaign Name"] if isinstance(r["Facebook Campaign Name"], str) else "_"
            if cn in ("_", ""):
                s = EV.get(r["Facebook Ad Set ID"]); rn = next(iter(s)) if s and len(s) == 1 else None
                if rn and re.match(FWRE, rn): continue      # FW ad set -> FW lead, excluded
            else: rn = cn
            rows.append((r["M"], rn, r["Status"]))
    for m, rn, st in rows:
        q = 1 if st in QUAL else 0
        if rn is None: attr = NOCAP
        elif rn in mc: attr = "Campaign in Meta export"
        else: attr = OUTSIDE if spec["meta_file_prefix"] else "No Meta export for this brand"
        camp = rn if rn is not None else "Facebook leads – campaign not determinable"
        put(m, camp, attr, 1, q)
        if attr == OUTSIDE: tot[m]["outside"] += 1
        else:
            tot[m]["leads"] += 1; tot[m]["quality"] += q
            if attr == NOCAP: tot[m]["nocap"] += 1
    return tot, lines


wb = openpyxl.load_workbook(WB, data_only=True)
cmpws = wb["Comparison"]; disp_rows = {cmpws.cell(r, 1).value: r for r in range(6, 40) if cmpws.cell(r, 1).value}
EXP, ELINES = {}, {}
for name, spec in CFG["brands"].items():
    EXP[spec["display"]], ELINES[spec["display"]] = expected_for(name, spec)
# ------------------------------------------------------------------ Comparison tab
def verdict(change, thr, lower_better):
    if not isinstance(change, (int, float)): return DASH
    lo, hi = ("Improved", "Worsened") if lower_better else ("Worsened", "Improved")
    return lo if change <= -thr else (hi if change >= thr else "Flat")

def metrics(t):
    sp, ld, q = t["spend"], t["leads"], t["quality"]
    return dict(cpl=div(sp, ld) if sp > 0 else DASH, qp=div(q, ld), cpql=div(sp, q) if sp > 0 else DASH)

S = {}
for b, tot in EXP.items():
    r = disp_rows[b]; mm = [metrics(tot[m]) for m in MONTHS]; S[b] = (tot, mm)
    for mi, m in enumerate(MONTHS):
        cmp(f"{b}|{m}|spend", cmpws.cell(r, 2 + mi).value, tot[m]["spend"], 1e-9)
        cmp(f"{b}|{m}|leads", cmpws.cell(r, 4 + mi).value, tot[m]["leads"]); cmp(f"{b}|{m}|quality", cmpws.cell(r, 11 + mi).value, tot[m]["quality"])
        cmp(f"{b}|{m}|CPL", cmpws.cell(r, 6 + mi).value, mm[mi]["cpl"]); cmp(f"{b}|{m}|Q%", cmpws.cell(r, 16 + mi).value, mm[mi]["qp"]); cmp(f"{b}|{m}|CPQL", cmpws.cell(r, 20 + mi).value, mm[mi]["cpql"])
        cmp(f"{b}|{m}|outside", cmpws.cell(r, 30 + mi).value, tot[m]["outside"]); cmp(f"{b}|{m}|nocap", cmpws.cell(r, 32 + mi).value, tot[m]["nocap"])
    a, c_ = mm[0], mm[1]
    ch = lambda x, y: (y - x) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else DASH
    pc = lambda x, y: (y / x - 1) if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x != 0 else DASH
    cmp(f"{b}|dCPL", cmpws.cell(r, 8).value, ch(a["cpl"], c_["cpl"])); cmp(f"{b}|dCPL%", cmpws.cell(r, 9).value, pc(a["cpl"], c_["cpl"]))
    cmp(f"{b}|vCPL", cmpws.cell(r, 10).value, verdict(pc(a["cpl"], c_["cpl"]), 0.01, True))
    q1, q2 = tot[MONTHS[0]]["quality"], tot[MONTHS[1]]["quality"]
    cmp(f"{b}|dQ", cmpws.cell(r, 13).value, q2 - q1); cmp(f"{b}|dQ%", cmpws.cell(r, 14).value, pc(q1, q2) if q1 != 0 else DASH)
    cmp(f"{b}|vQ", cmpws.cell(r, 15).value, verdict(pc(q1, q2) if q1 != 0 else DASH, 0.01, False))
    cmp(f"{b}|dQP", cmpws.cell(r, 18).value, ch(a["qp"], c_["qp"])); cmp(f"{b}|vQP", cmpws.cell(r, 19).value, verdict(ch(a["qp"], c_["qp"]), 0.005, False))
    cmp(f"{b}|dCPQL", cmpws.cell(r, 22).value, ch(a["cpql"], c_["cpql"])); cmp(f"{b}|dCPQL%", cmpws.cell(r, 23).value, pc(a["cpql"], c_["cpql"]))
    cmp(f"{b}|vCPQL", cmpws.cell(r, 24).value, verdict(pc(a["cpql"], c_["cpql"]), 0.01, True))
# portfolio row (brands with Meta spend in both... = spend>0 per month)
pr = disp_rows["All brands with Meta spend"]
for mi, m in enumerate(MONTHS):
    sp = sum(S[b][0][m]["spend"] for b in S); ld = sum(S[b][0][m]["leads"] for b in S if S[b][0][m]["spend"] > 0); q = sum(S[b][0][m]["quality"] for b in S if S[b][0][m]["spend"] > 0)
    cmp(f"PORT|{m}|spend", cmpws.cell(pr, 2 + mi).value, sp, 1e-9); cmp(f"PORT|{m}|leads", cmpws.cell(pr, 4 + mi).value, ld); cmp(f"PORT|{m}|quality", cmpws.cell(pr, 11 + mi).value, q)
    cmp(f"PORT|{m}|CPL", cmpws.cell(pr, 6 + mi).value, div(sp, ld) if sp > 0 else DASH); cmp(f"PORT|{m}|Q%", cmpws.cell(pr, 16 + mi).value, div(q, ld)); cmp(f"PORT|{m}|CPQL", cmpws.cell(pr, 20 + mi).value, div(sp, q) if sp > 0 else DASH)
# ------------------------------------------------------------------ Pivot_Data (every line x month)
pdrows = [r for r in wb["Pivot_Data"].iter_rows(min_row=2, values_only=True) if r[0] is not None]
inv = {MLAB[m]: m for m in MONTHS}
seen = set(); PD = {}
for mlab, brand, camp, attr, sp, ld, q in pdrows:
    m = inv[mlab]; k = (camp, m); e = ELINES[brand].get(k, [0.0, 0, 0, attr]); seen.add((brand, camp, m)); PD[(brand, camp, m)] = (sp, ld, q)
    cmp(f"PD|{brand}|{camp[:40]}|{m}|spend", sp, e[0] if attr == "Campaign in Meta export" else 0.0, 1e-9); cmp(f"PD|{brand}|{camp[:40]}|{m}|leads", ld, e[1]); cmp(f"PD|{brand}|{camp[:40]}|{m}|q", q, e[2])
# every expected line with activity must appear in Pivot_Data (active = spend>0 or leads>0 in any month)
for b, lines in ELINES.items():
    act = {c for (c, m), v in lines.items() if v[0] > 0 or v[1] > 0}
    for c in act:
        for m in MONTHS: checked += 1; (seen.__contains__((b, c, m)) or bad.append(("missing line in Pivot_Data", b, c, m)))
    # totals: pivot lines sum to brand totals (incl. outside-export leads)
    for m in MONTHS:
        tot = EXP[b][m]
        cmp(f"PDSUM|{b}|{m}|spend", sum(v[0] for (bb, c, mm), v in PD.items() if bb == b and mm == m), tot["spend"], 1e-9)
        cmp(f"PDSUM|{b}|{m}|leads", sum(v[1] for (bb, c, mm), v in PD.items() if bb == b and mm == m), tot["leads"] + tot["outside"])
# ------------------------------------------------------------------ Data_Leads counts per brand/month
dl = pd.DataFrame([r[:8] for r in wb["Data_Leads"].iter_rows(min_row=2, values_only=True) if r[0] is not None], columns=["Month", "Brand", "ref", "src", "status", "line", "attr", "q"])
for b in EXP:
    for m in MONTHS:
        g = dl[(dl["Brand"] == b) & (dl["Month"] == MLAB[m])]
        cmp(f"DL|{b}|{m}|rows", len(g), EXP[b][m]["leads"] + EXP[b][m]["outside"]); cmp(f"DL|{b}|{m}|quality(all)", int(pd.to_numeric(g["q"]).sum()), sum(v[2] for (c, mm), v in ELINES[b].items() if mm == m))
# ------------------------------------------------------------------ Master Pivot body (plain values) vs Pivot_Data
mp = wb["Master Pivot"]; order = {}
for r in range(17, mp.max_row + 1):
    lab = mp.cell(r, 1).value
    if lab is None or str(lab).startswith("Notes"): break
    cur = lab if lab in EXP else None
    if lab in EXP: brand = lab; sub = {k: v for k, v in PD.items() if k[0] == lab}
    elif lab == "Grand Total": sub = dict(PD)
    else: sub = {k: v for k, v in PD.items() if k[0] == brand and k[1] == lab}
    for mi, m in enumerate(MONTHS):
        sp = sum(v[0] for k, v in sub.items() if k[2] == m); ld = sum(v[1] for k, v in sub.items() if k[2] == m); q = sum(v[2] for k, v in sub.items() if k[2] == m)
        exp = [sp, ld, div(sp, ld) if sp > 0 else DASH, q, div(q, ld), div(sp, q) if sp > 0 else DASH]
        for k, e in enumerate(exp): cmp(f"MP|{lab[:30]}|{m}|{k}", mp.cell(r, 2 + mi * 6 + k).value, e)
# structure: no merges/formulas in pivot range, no panes; pivot parts present
import zipfile
z = zipfile.ZipFile(WB); wbx = z.read("xl/workbook.xml").decode()
rid = re.search(r'<sheet [^>]*name="Master Pivot"[^>]*r:id="([^"]+)"', wbx).group(1)
tg = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="{rid}"', z.read("xl/_rels/workbook.xml.rels").decode())
sheet = "xl/" + (tg.group(1) or tg.group(2)); sx = z.read(sheet).decode()
ref = re.search(r'<location ref="([^"]+)"', z.read("xl/pivotTables/pivotTable1.xml").decode()).group(1)
try: inject_pivot.check_pivot_range_is_clean(sx, ref)
except ValueError as e: bad.append(("pivot structure", str(e)))
checked += 3
if "<pane " in sx: bad.append(("Master Pivot has frozen panes",))
if 'zoomScale="85"' not in sx: bad.append(("Master Pivot zoom",))
sl = [n for n in z.namelist() if n.startswith("xl/slicerCaches/")]; cmp("slicer caches", len(sl), 4)
cache = z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode(); cmp("pivot cache record count", int(re.search(r'recordCount="(\d+)"', cache).group(1)), len(pdrows))
# ------------------------------------------------------------------ Dashboard tiles + scorecard
d = wb["Master Dashboard"]
for ti, (c1, c2) in enumerate([("B", "C"), ("D", "E"), ("F", "G"), ("K", "L"), ("P", "Q"), ("T", "U")]):
    col = 2 + ti * 2; cmp(f"DASH tile {ti}", d.cell(7, col).value, cmpws[f"{c2}{pr}"].value)
n = len(EXP)
for k, b in enumerate(list(EXP)):
    r = 14 + k
    cmp(f"DASH score {b} name", d.cell(r, 2).value, b)
    for col, src in zip((3, 4, 5, 6, 7, 8, 9, 10), ("G", "J", "L", "O", "Q", "S", "U", "X")): cmp(f"DASH score {b} c{col}", d.cell(r, col).value, cmpws[f"{src}{disp_rows[b]}"].value)
# ------------------------------------------------------------------ chart helper (graphical interpretation) vs independent values
dd = wb["Dashboard_Data"]
NA_ = "#N/A"
for k, b in enumerate(list(EXP)):
    r = 4 + k; mm = S[b][1]; tot = S[b][0]
    pc_ = lambda x, y: (y / x - 1) if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x != 0 else None
    pcl, pcq = pc_(mm[0]["cpl"], mm[1]["cpl"]), pc_(mm[0]["cpql"], mm[1]["cpql"])
    pp = (mm[1]["qp"] - mm[0]["qp"]) if isinstance(mm[0]["qp"], (int, float)) and isinstance(mm[1]["qp"], (int, float)) else None
    for col, val, good_neg in ((11, pcl, True), (13, pcq, True), (15, pp, False)):
        good = val is not None and ((val < 0) if good_neg else (val > 0)); badv = val is not None and ((val > 0) if good_neg else (val < 0))
        cmp(f"CHART {b} c{col} improved", dd.cell(r, col).value, val if good else NA_); cmp(f"CHART {b} c{col + 1} worsened", dd.cell(r, col + 1).value, val if badv else NA_)
    m2 = MONTHS[1]
    sp_tot = sum(S[x][0][m2]["spend"] for x in S); q_tot = sum(S[x][0][m2]["quality"] for x in S if S[x][0][m2]["spend"] > 0)
    cmp(f"CHART {b} spend share", dd.cell(r, 17).value, (tot[m2]["spend"] / sp_tot) if tot[m2]["spend"] > 0 else 0.0)
    cmp(f"CHART {b} quality share", dd.cell(r, 18).value, (tot[m2]["quality"] / q_tot) if tot[m2]["spend"] > 0 else 0.0)
nch = len([n for n in z.namelist() if re.match(r"xl/charts/chart\d+\.xml", n)]); cmp("number of charts on the workbook", nch, 8)
print(f"BRAND COMPARISON CHECKS: {checked:,} | MISMATCHES: {len(bad)}")
for x in bad[:30]: print("  ", x)
sys.exit(1 if bad else 0)
