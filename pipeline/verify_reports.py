"""Independent verifier: recompute every Brand-Wise / Campaign-Wise cell from RAW files and compare to the workbook."""
import sys, glob, os, importlib.util, warnings, math
import pandas as pd, numpy as np, openpyxl
warnings.filterwarnings("ignore")
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import report_config as rc
spec = importlib.util.spec_from_file_location("bb", os.path.join(_HERE, "build_brand_report.py"))
bb = importlib.util.module_from_spec(spec); spec.loader.exec_module(bb)
RAW, META, OUT = sys.argv[1:4]
MONTHS = bb.MONTHS
QUAL, MEET = bb.QUAL, bb.MEET
# ---- raw CRM (all rows, no pre-filter) ----
fr = []
for m in MONTHS:
    d = pd.read_csv(f"{RAW}/{rc.lead_file(m)}", low_memory=False,
                    usecols=["Lead id", "Status", "Lead Source", "Brand", "Created On", "Modified On", "Facebook Campaign Name", "Facebook Ad Set ID"])
    d["file_m"] = m
    fr.append(d)
crm_all = pd.concat(fr, ignore_index=True)
crm_all["cr"] = pd.to_datetime(crm_all["Created On"], format="%d/%m/%Y %H:%M:%S")
crm_all["mo"] = pd.to_datetime(crm_all["Modified On"], format="%d/%m/%Y %H:%M:%S")
crm_all["m"] = crm_all["cr"].dt.strftime("%b")
# file month must equal created month (sanity)
print("file-month vs created-month mismatches:", int((crm_all["m"] != crm_all["file_m"]).sum()))
print("total CRM rows:", len(crm_all), "| dup Lead id overall:", int(crm_all["Lead id"].duplicated().sum()))
crm_all["tat"] = (crm_all["mo"] - crm_all["cr"]).dt.total_seconds() / 3600

def isn(x): return isinstance(x, str) and x == "–"
bad = []; checked = 0
def cmp(tag, got, exp, tol=1e-6):
    global checked
    checked += 1
    if exp is None or (isinstance(exp, float) and (math.isnan(exp) or math.isinf(exp))): exp = "–"
    if isinstance(exp, str) or isinstance(got, str) or got is None:
        if not (isinstance(exp, str) and isinstance(got, str) and exp == got): bad.append((tag, got, exp))
        return
    if abs(got - exp) > tol * max(1, abs(exp)): bad.append((tag, got, exp))

def ratio(n, dn, mult=1):
    return "–" if (isinstance(n, str) or isinstance(dn, str) or dn is None or dn <= 0) else n / dn * mult

# independent ad-set evidence: Ad Set ID -> set of campaign names on leads that name a campaign (all brands)
_n = crm_all[(crm_all["Lead Source"] == "Facebook") & ~crm_all["Facebook Campaign Name"].fillna("_").isin(["_", ""]) & ~crm_all["Facebook Ad Set ID"].fillna("_").isin(["_", ""])]
EV = {k: set(v) for k, v in _n.groupby("Facebook Ad Set ID")["Facebook Campaign Name"]}
BR = bb.BRANDS
for brand, (prefix, cbs) in BR.items():
    f = glob.glob(f"{OUT}/{brand.replace(' & ', '_and_').replace(' ', '_')}_FinalReport_{rc.FILE_TAG}.xlsx")[0]
    wb = openpyxl.load_workbook(f, data_only=True)
    # ----- raw meta
    mf = glob.glob(f"{META}/{prefix}*Campaigns*.csv"); assert len(mf) == 1
    mt = pd.read_csv(mf[0]); mt["m"] = pd.to_datetime(mt["Reporting starts"]).dt.strftime("%b")
    mt = mt[mt["m"].isin(MONTHS)].copy()
    daily = (pd.to_datetime(mt["Reporting ends"]) - pd.to_datetime(mt["Reporting starts"])).dt.days.max() == 0
    mt["ml"] = np.where(mt["Result indicator"] == "actions:leadgen.other", mt["Results"].fillna(0), 0)
    has_lpv = "Landing page views" in mt.columns
    # ----- raw CRM for brand: independent filter
    c = crm_all[crm_all["Brand"].isin(cbs)].copy()
    fwmask = c["Facebook Campaign Name"].fillna("").str.match("(?i)" + rc.FW_REGEX)
    c = c[~fwmask]
    c["fb"] = c["Lead Source"].eq("Facebook")
    cn0 = c["Facebook Campaign Name"].fillna("_")
    c["rn"] = np.where(c["fb"] & ~cn0.isin(["_", ""]), cn0,
                       c["Facebook Ad Set ID"].map(lambda i: next(iter(EV[i])) if i in EV and len(EV[i]) == 1 else None))
    c.loc[~c["fb"], "rn"] = None
    fwad = c["fb"] & c["rn"].fillna("").str.match("(?i)" + rc.FW_REGEX)
    c = c[~fwad].copy()
    c["q"] = c["Status"].isin(QUAL); c["mt"] = c["Status"].isin(MEET)
    c["ct"] = c["Status"].notna() & (c["Status"].fillna("").str.strip() != "") & (c["Status"] != "New Lead")
    c["nc"] = c["Status"].eq("New Lead"); c["bl"] = c["Status"].fillna("").str.strip().eq("")
    c["ok"] = c["tat"].notna() & (c["tat"] >= 0)
    camps = set(mt["Campaign name"])
    rn = c["rn"]
    c["key"] = np.where(~c["fb"], "OTHER", np.where(rn.isin(camps), rn, np.where(rn.isna(), "NOCAP", "NOTIN")))

    def block(mask_crm, mask_meta, month, with_meta=True, reach_ok=True):
        """return dict of metric -> expected for given month (None = all months)"""
        cc = c[mask_crm] if month is None else c[mask_crm & (c["m"] == month)]
        o = {}
        if with_meta:
            mm = mt[mask_meta] if month is None else mt[mask_meta & (mt["m"] == month)]
            o["spend"] = mm["Amount spent (INR)"].sum(); o["impr"] = mm["Impressions"].sum()
            o["clicks"] = mm["Clicks (all)"].sum(); o["lclicks"] = mm["Link clicks"].sum()
            o["mleads"] = mm["ml"].sum()
            o["lpv"] = (mm["Landing page views"].sum() if has_lpv and mm["Landing page views"].notna().any() else "–")
            o["reach"] = (mm["Reach"].sum() if (reach_ok and not daily and month is not None and mm["Reach"].notna().any()) else "–")
        else:
            for k in ("spend", "impr", "clicks", "lclicks", "mleads", "lpv", "reach"): o[k] = "–"
        o["freq"] = ratio(o["impr"], o["reach"]) if o["reach"] != "–" else "–"
        o["ctr"] = ratio(o["clicks"], o["impr"]); o["lctr"] = ratio(o["lclicks"], o["impr"])
        o["cpc"] = ratio(o["spend"], o["clicks"]); o["lcpc"] = ratio(o["spend"], o["lclicks"])
        o["cpm"] = ratio(o["spend"], o["impr"], 1000); o["cplm"] = ratio(o["spend"], o["mleads"])
        o["crm"] = len(cc); o["qual"] = int(cc["q"].sum()); o["meet"] = int(cc["mt"].sum())
        o["cont"] = int(cc["ct"].sum()); o["ncont"] = int(cc["nc"].sum()); o["blank"] = int(cc["bl"].sum())
        o["qualp"] = ratio(o["qual"], o["crm"]); o["meetp"] = ratio(o["meet"], o["crm"])
        o["contp"] = ratio(o["cont"], o["crm"]); o["ncontp"] = ratio(o["ncont"], o["crm"])
        o["cplc"] = ratio(o["spend"], o["crm"]); o["cpql"] = ratio(o["spend"], o["qual"]); o["cpmt"] = ratio(o["spend"], o["meet"])
        ok = cc[cc["ok"]]
        o["elig"] = len(ok)
        o["atat"] = ok["tat"].mean() if len(ok) else "–"
        o["mtat"] = ok["tat"].median() if len(ok) else "–"
        return o

    wpd = wb["Pivot_Data"]; PD = {}
    for rr in wpd.iter_rows(min_row=2, values_only=True):
        if rr[0] is not None: PD[(rr[2], rr[0])] = rr
    MLAB = rc.MLAB
    PDKEYS = ["spend", "impr", "clicks", "lclicks", "mleads", "crm", "qual", "meet", "cont", "ncont"]
    seen_pd = set()
    def check_row(ws, r, tag, mask_crm, mask_meta, with_meta, brand_level=False, pname=None):
        if pname is not None:
            for month in MONTHS:
                exp = block(mask_crm, mask_meta, month, with_meta, reach_ok=True)
                rr = PD[(pname, MLAB[month])]; seen_pd.add((pname, MLAB[month]))
                cmp(f"{brand}|PIVOT_DATA|{pname[:30]}|{month}|brand", rr[1], brand)
                for j, k in enumerate(PDKEYS):
                    e = exp[k]; e = 0 if isinstance(e, str) else e
                    cmp(f"{brand}|PIVOT_DATA|{pname[:30]}|{month}|{k}", rr[5 + j], float(e), 1e-9)
        for bi, month in enumerate(MONTHS + [None]):
            exp = block(mask_crm, mask_meta, month, with_meta, reach_ok=not brand_level)
            for k in bb.KEYS:
                got = ws[f"{bb.colof(bi, k)}{r}"].value
                e = exp[k]
                if isinstance(e, float) and not isinstance(got, str) and k in ("spend",): cmp(f"{brand}|{tag}|{month or 'Total'}|{k}", got, e, 1e-9)
                else: cmp(f"{brand}|{tag}|{month or 'Total'}|{k}", got, e, 1e-7)

    allm = pd.Series(True, index=mt.index); allc = pd.Series(True, index=c.index)
    # ---- Campaign-Wise
    ws = wb["Campaign-Wise"]
    seen = set(); total_row = None
    for r in range(7, ws.max_row + 1):
        name = ws.cell(r, 2).value; a = ws.cell(r, 1).value
        if name is None: continue
        if isinstance(a, str) and a.startswith("TOTAL"):
            total_row = r; continue
        if name in camps:
            seen.add(name)
            check_row(ws, r, f"camp:{name[:30]}", (c["key"] == name) & c["fb"], mt["Campaign name"] == name, True, pname=name)
        elif name.startswith("Facebook leads – campaign not determinable"):
            check_row(ws, r, "NOCAP", c["key"] == "NOCAP", allm, False, pname=name)
        elif name.startswith("Facebook leads – campaign not in"):
            check_row(ws, r, "NOTIN", c["key"] == "NOTIN", allm, False, pname=name)
        else:
            bad.append((brand, "unexpected campaign row", name))
    assert seen == camps, (brand, camps - seen)
    assert len(seen_pd) == len(PD), (brand, len(seen_pd), len(PD))
    # campaign TOTAL row
    check_row(ws, total_row, "CAMP-TOTAL", c["fb"], allm, True, brand_level=True)
    # ---- Brand-Wise
    ws = wb["Brand-Wise"]
    rows = {ws.cell(r, 2).value: r for r in range(7, ws.max_row + 1) if ws.cell(r, 2).value}
    check_row(ws, rows["Brand total (Meta + Facebook-sourced CRM)"], "BRAND-A", c["fb"], allm, True, brand_level=True)
    for cb in cbs: check_row(ws, rows[cb], f"BRAND-B:{cb}", (c["Brand"] == cb) & c["fb"], allm, False)
    check_row(ws, rows["All CRM leads — all sources"], "BRAND-C-all", allc, allm, False)
    check_row(ws, rows["   of which Facebook-sourced"], "BRAND-C-fb", c["fb"], allm, False)
    check_row(ws, rows["   of which other sources (non-Facebook)"], "BRAND-C-other", ~c["fb"], allm, False)
    # ---- front tab mirrors Brand/Campaign (value equality)
    wf = wb["All Reports (One Tab)"]; wc = wb["Campaign-Wise"]; wbw = wb["Brand-Wise"]
    ncol = bb.FIX + 5 * bb.NM
    camp_rows_f = {}
    for r in range(6, wf.max_row + 1):
        if wf.cell(r, 2).value: camp_rows_f.setdefault(wf.cell(r, 2).value, []).append(r)
    mism = 0
    for src in (wc, wbw):
        for r in range(7, src.max_row + 1):
            nm = src.cell(r, 2).value
            if not nm or src.cell(r, 4).value is None: continue
            cand = camp_rows_f.get(nm, [])
            hit = any(all((wf.cell(fr_, ci).value in (None, "") and src.cell(r, ci).value in (None, "")) or wf.cell(fr_, ci).value == src.cell(r, ci).value
                          for ci in range(1, ncol + 1)) for fr_ in cand)
            checked += 1
            if not hit: mism += 1; bad.append((brand, "front tab row differs from source", nm))
    # ---- Month-on-Month vs Brand-Wise A
    wm = wb["Month-on-Month"]; ra = rows["Brand total (Meta + Facebook-sourced CRM)"]
    for j, k in enumerate(bb.KEYS):
        for bi in range(len(MONTHS) + 1):
            cmp(f"{brand}|MoM|{k}|{bi}", wm.cell(5 + j, 2 + bi).value, wbw[f"{bb.colof(bi, k)}{ra}"].value)
    # ---- raw-total reconciliations
    sp_raw = mt["Amount spent (INR)"].sum()
    cmp(f"{brand}|raw spend vs report total", wb["Campaign-Wise"][f"{bb.colof(len(MONTHS), 'spend')}{total_row}"].value, sp_raw, 1e-9)
    print(f"{brand:22s} crm in scope {len(c):6d} (fb {int(c['fb'].sum()):6d}) | FW removed {int(fwmask.sum())+int(fwad.sum()):3d} (name {int(fwmask.sum())}+adset {int(fwad.sum())}) | undeterminable {int((c.key=='NOCAP').sum())} | notin {int((c.key=='NOTIN').sum())} | meta spend {sp_raw:14,.2f} | campaigns {len(camps)}")

print(f"\nCELL COMPARISONS: {checked:,} | MISMATCHES: {len(bad)}")
for b in bad[:40]: print(b)
sys.exit(1 if bad else 0)
