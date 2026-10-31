#!/usr/bin/env python3
"""ONE workbook comparing two months (default Sep vs Oct 2026) for many brands: CPL, Quality Leads, Quality Lead %, CPQL.
Tabs: Master Dashboard · Comparison · Master Pivot (real PivotTable + slicers) · Data Quality Log · KPI Definitions · Validation ·
      Pivot_Data · Data_Meta · Data_Leads.

usage: build_comparison_report.py <leads_dir> <meta_experts_dir> <comp_dir> <out_dir>
  leads_dir        LeadDetails_<Month><Year>.csv per month (CRM Lead Module export; contains PII — never copied, only Lead id/status/campaign)
  meta_experts_dir Meta campaign CSVs for the brands whose meta_dir = "meta_experts"
  comp_dir         Meta CSVs + the two Daewoo reports + FW lead file for brands whose meta_dir = "comp"
Config: config/comparison_config.json (override with REPORT_CONFIG). Source/definition decisions: docs/DECISIONS.md.
"""
import os, sys, glob, re, unicodedata, subprocess, shutil, tempfile, warnings
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("REPORT_CONFIG", os.path.join(HERE, "..", "config", "comparison_config.json"))
sys.path.insert(0, HERE)
import pandas as pd, numpy as np, openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import FormulaRule
import report_config as rcfg
import build_brand_report as bb
import inject_pivot

warnings.filterwarnings("ignore")
CFG = rcfg.CFG
MONTHS, MLAB = rcfg.MONTHS, rcfg.MLAB
M1, M2 = MONTHS[0], MONTHS[1]
QUAL = rcfg.QUAL
ATTR_OK, ATTR_NOCAP, ATTR_NOTIN = "Campaign in Meta export", "Campaign not determinable", "Campaign outside Meta export"
ATTR_NOEXP = "No Meta export for this brand"
NOCAP_LABEL = "Facebook leads – campaign not determinable"
NAVY, BLUE, TEAL, GREY, LIGHT, GREEN, RED = "1F3864", "2E5090", "0E7C7B", "7F7F7F", "E8EEF7", "00803C", "C00000"
DASH = "–"


def fill(h): return PatternFill("solid", fgColor=h)
def fnt(b=False, c="000000", sz=10): return Font(name="Calibri", size=sz, bold=b, color=c)
def norm(s): return unicodedata.normalize("NFKC", str(s)).strip()


# =============================================================== data preparation
def attribute(crm, mcamps, idev):
    """Facebook-sourced leads -> (campaign label, attribution class). Same rules as build_brand_report (Ad Set ID evidence, FW ad sets dropped)."""
    fb = crm["Lead Source"].eq("Facebook")
    cn = crm["Facebook Campaign Name"].fillna("_")
    named = ~cn.isin(["_", ""])
    rc_ = pd.Series([None] * len(crm), index=crm.index, dtype=object)
    un = fb & ~named
    rc_[un] = crm.loc[un, "Facebook Ad Set ID"].map(lambda i: next(iter(idev[i])) if i in idev and len(idev[i]) == 1 else None)
    fwad = rc_.fillna("").str.match("(?i)" + rcfg.FW_REGEX)
    n_fwad = int(fwad.sum())
    keep = ~fwad
    crm, fb, cn, named, rc_ = crm[keep].reset_index(drop=True), fb[keep].reset_index(drop=True), cn[keep].reset_index(drop=True), named[keep].reset_index(drop=True), rc_[keep].reset_index(drop=True)
    rn = cn.where(named, rc_)
    f = crm[fb].copy(); rn = rn[fb]
    f["line"] = np.where(rn.isna(), NOCAP_LABEL, rn)
    f["attr"] = np.where(rn.isna(), ATTR_NOCAP, np.where(rn.isin(mcamps), ATTR_OK, ATTR_NOTIN))
    f["method"] = np.where(named[fb], "named", np.where(rn.isna(), "undetermined", "ad set id"))
    return f, n_fwad, int((~fb).sum())


def meta_rows(g, brand):
    return [(r["Month"], r["Campaign name"], r["Delivery"] if isinstance(r["Delivery"], str) else "", float(r["Spend"])) for _, r in g.iterrows()]


def leaddetails_brand(name, spec, dirs, cache):
    prefix, crm_brands = spec["meta_file_prefix"], spec["crm_brand_values"]
    crm, cst = bb.load_crm(dirs["leads"], crm_brands)
    g, mfile, raw_total, daily, inds, n_out = (None,) * 6
    mcamps = set(); mrows = []
    if prefix:
        g, mfile, raw_total, daily, inds, n_out = bb.load_meta(dirs[spec["meta_dir"]], prefix)
        mcamps = set(g["Campaign name"]); mrows = meta_rows(g, name)
    f, n_fwad, n_nonfb = attribute(crm, mcamps, cst["idev"])
    if not prefix: f.loc[f["attr"] == ATTR_NOTIN, "attr"] = ATTR_NOEXP
    leads = pd.DataFrame({"month": f["Month"].values, "ref": f["Lead id"].values, "source": "Facebook", "status": f["Status"].fillna("").values,
                          "line": f["line"].values, "attr": f["attr"].values, "quality": f["Status"].isin(QUAL).astype(int).values, "qual_formula": True})
    notes = dict(source="LeadDetails CRM + Meta export" if prefix else "LeadDetails CRM (no Meta export supplied for this brand)", meta_file=mfile, meta_daily=bool(daily),
                 crm_all=len(crm), crm_nonfb=n_nonfb, fw_excluded_name=cst["fw_excluded"], fw_excluded_adset=n_fwad, last_lead=cst["maxdate"],
                 variants={b: int((crm["Brand"] == b).sum()) for b in crm_brands}, meta_total=(float(g["Spend"].sum()) if g is not None else 0.0))
    return mrows, leads, notes


def read_xlsx_sheet(path, sheet):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet]; rows = list(ws.iter_rows(values_only=True)); wb.close()
    return pd.DataFrame(rows[1:], columns=rows[0]).dropna(how="all")


def daewoo_brand(name, spec, dirs):
    """Daewoo comes from the two Daewoo x ShootOrder reports (Daewoo CRM, report-defined qualified flag, leads on campaigns with spend)."""
    mrows, parts, notes = [], [], dict(source="Daewoo x ShootOrder reports (user's choice)", reports={}, last_lead=None, meta_daily=False, fw_excluded_name=0, fw_excluded_adset=0, crm_nonfb=0)
    for m in MONTHS:
        path = os.path.join(dirs["comp"], CFG["daewoo_reports"][m])
        dc = read_xlsx_sheet(path, "Data_Campaigns"); crm = read_xlsx_sheet(path, "Data_CRM")
        cols = list(crm.columns)
        camp_c = next(c for c in cols if c and "campaign" in str(c).lower())
        stat_c = next(c for c in cols if c and "status" in str(c).lower())
        qual_c = next(c for c in cols if c and str(c).lower().startswith("qualified"))
        id_c = next((c for c in cols if c and ("record id" in str(c).lower() or "social lead id" in str(c).lower())), cols[0])
        date_c = next(c for c in cols if c and ("created time" in str(c).lower() or "lead date" in str(c).lower()))
        act = dc[dc["Amount spent (INR)"] > 0]
        for _, r in dc.iterrows(): mrows.append((m, r["Campaign name"], r["Campaign delivery"] or "", float(r["Amount spent (INR)"])))
        sel = crm[crm[camp_c].isin(set(act["Campaign name"]))]
        notes["reports"][m] = dict(file=os.path.basename(path), rows=len(crm), on_active=len(sel), unmapped=int(crm[camp_c].isna().sum()), spend=float(dc["Amount spent (INR)"].sum()),
                                   qual_flag=int(pd.to_numeric(sel[qual_c], errors="coerce").fillna(0).sum()),
                                   qual_7rule=int(sel[stat_c].map(norm).isin(QUAL).sum()), last=str(pd.to_datetime(sel[date_c]).max()))
        parts.append(pd.DataFrame({"month": m, "ref": sel[id_c].astype(str).values, "source": "Daewoo CRM (report)", "status": sel[stat_c].map(norm).values,
                                   "line": sel[camp_c].values, "attr": ATTR_OK, "quality": pd.to_numeric(sel[qual_c], errors="coerce").fillna(0).astype(int).values, "qual_formula": False}))
        notes["last_lead"] = pd.to_datetime(sel[date_c]).max() if notes["last_lead"] is None or pd.to_datetime(sel[date_c]).max() > notes["last_lead"] else notes["last_lead"]
    notes["crm_all"] = sum(len(p) for p in parts); notes["variants"] = {}
    notes["meta_total"] = sum(x[3] for x in mrows)
    return mrows, pd.concat(parts, ignore_index=True), notes


def fw_brand(name, spec, dirs):
    g, mfile, raw_total, daily, inds, n_out = bb.load_meta(dirs["comp"], spec["meta_file_prefix"])
    mcamps = set(g["Campaign name"]); mrows = meta_rows(g, name)
    L_ = pd.read_csv(os.path.join(dirs["comp"], CFG["fw_lead_file"]), low_memory=False,
                     usecols=["Status", "Lead Source", "Brand", "Created On", "Facebook Campaign Name", "Unique Lead ID"])
    L_["cr"] = pd.to_datetime(L_["Created On"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    L_["Month"] = L_["cr"].dt.strftime("%b")
    L_ = L_[L_["Month"].isin(MONTHS)].reset_index(drop=True)
    isfb = L_["Lead Source"].fillna("").str.lower().str.replace(r"\s+", "", regex=True).eq("facebook")
    f = L_[isfb].copy()
    cn = f["Facebook Campaign Name"].fillna("_")
    line = np.where(cn.isin(["_", ""]), NOCAP_LABEL, cn)
    attr = np.where(cn.isin(["_", ""]), ATTR_NOCAP, np.where(cn.isin(mcamps), ATTR_OK, ATTR_NOTIN))
    leads = pd.DataFrame({"month": f["Month"].values, "ref": ["FW-" + str(i + 2) for i in f.index], "source": "Facebook (FW lead file)", "status": f["Status"].fillna("").values,
                          "line": line, "attr": attr, "quality": f["Status"].isin(QUAL).astype(int).values, "qual_formula": True})
    notes = dict(source="Kustard–FW Meta export + FW_LeadData (Facebook form leads only)", meta_file=mfile, meta_daily=False, crm_all=len(L_), crm_nonfb=int((~isfb).sum()),
                 fw_excluded_name=0, fw_excluded_adset=0, last_lead=L_["cr"].max(), variants={}, meta_total=float(g["Spend"].sum()), fw_all_leads=len(L_),
                 fw_excel=int(L_["Lead Source"].eq("Excel").sum()))
    return mrows, leads, notes


def prepare(dirs):
    out = []
    for name, spec in CFG["brands"].items():
        src = spec["source"]
        print(f"  preparing {name} ({src})", flush=True)
        if src == "leaddetails": mrows, leads, notes = leaddetails_brand(name, spec, dirs, None)
        elif src == "daewoo_reports": mrows, leads, notes = daewoo_brand(name, spec, dirs)
        elif src == "fw_leads": mrows, leads, notes = fw_brand(name, spec, dirs)
        else: raise ValueError(src)
        out.append(dict(name=name, display=spec["display"], meta=mrows, leads=leads, notes=notes))
    return out


def build_lines(brands):
    """Pivot lines: one per (brand, campaign) with any spend or lead; unattributed 'not determinable' lines go last (shared-item order)."""
    real, last = [], []
    for b in brands:
        mt = pd.DataFrame(b["meta"], columns=["m", "camp", "deliv", "spend"]) if b["meta"] else pd.DataFrame(columns=["m", "camp", "deliv", "spend"])
        spend = mt.groupby("camp")["spend"].sum() if len(mt) else pd.Series(dtype=float)
        ld = b["leads"]
        cnt = ld.groupby("line").size() if len(ld) else pd.Series(dtype=int)
        attr = ld.groupby("line")["attr"].first() if len(ld) else pd.Series(dtype=object)
        names = set(spend[spend > 0].index) | set(cnt.index)
        names.discard(NOCAP_LABEL)
        order = sorted(names, key=lambda c: (-float(spend.get(c, 0)), -int(cnt.get(c, 0)), c))
        inactive = len(set(mt["camp"])) - len(set(mt["camp"]) & names) if len(mt) else 0
        b["inactive_omitted"] = inactive
        for c in order:
            at = ATTR_OK if c in set(mt["camp"]) else (attr.get(c, ATTR_NOTIN))
            real.append(dict(brand=b["display"], camp=c, attr=at))
        if NOCAP_LABEL in cnt.index: last.append(dict(brand=b["display"], camp=NOCAP_LABEL, attr=ATTR_NOCAP))
    return real + last


# =============================================================== workbook
def write_workbook(brands, lines, dirs, out_path):
    wb = Workbook()
    ws_dash, ws_cmp, ws_piv, ws_log, ws_kpi, ws_val = (wb.active, wb.create_sheet("Comparison"), wb.create_sheet("Master Pivot"), wb.create_sheet("Data Quality Log"),
                                                      wb.create_sheet("KPI Definitions"), wb.create_sheet("Validation"))
    ws_dash.title = "Master Dashboard"
    ws_pd, ws_dm, ws_dl, ws_dd = wb.create_sheet("Pivot_Data"), wb.create_sheet("Data_Meta"), wb.create_sheet("Data_Leads"), wb.create_sheet("Dashboard_Data")
    disp = [b["display"] for b in brands]

    # ---- Data_Meta
    ws_dm.append(["Month", "Brand", "Campaign", "Delivery", "Amount Spent (INR)"])
    for b in brands:
        for m, camp, deliv, sp in b["meta"]: ws_dm.append([MLAB[m], b["display"], camp, deliv, sp])
    nm = ws_dm.max_row
    # ---- Data_Leads
    ws_dl.append(["Month", "Brand", "Lead ref", "Lead Source", "Status", "Campaign line", "Lead attribution", "Quality Lead (1/0)"])
    qs = ",".join(f'E{{r}}="{s}"' for s in QUAL)
    r = 2
    for b in brands:
        ld = b["leads"]
        for m, ref, src, st, line, at, q, fq in ld[["month", "ref", "source", "status", "line", "attr", "quality", "qual_formula"]].itertuples(index=False):
            ws_dl.append([MLAB[m], b["display"], ref, src, st, line, at, (f"=IF(OR({qs.format(r=r)}),1,0)" if fq else int(q))]); r += 1
    nl = ws_dl.max_row
    for ws_ in (ws_dm, ws_dl):
        for c in ws_[1]: c.font = fnt(True, "FFFFFF"); c.fill = fill(NAVY)
        ws_.freeze_panes = "A2"
    for i, w in enumerate([18, 22, 62, 14, 18], 1): ws_dm.column_dimensions[L(i)].width = w
    for i, w in enumerate([18, 22, 26, 22, 22, 62, 28, 12], 1): ws_dl.column_dimensions[L(i)].width = w

    # ---- Pivot_Data (formulas on Data_Meta / Data_Leads) + python mirror for the static pivot body
    ws_pd.append(["Month", "Brand", "Campaign", "Lead attribution", "Amount Spent (INR)", "CRM Leads Count", "Quality Leads Count"])
    mrange = lambda c: f"Data_Meta!${c}$2:${c}${nm}"
    lrange = lambda c: f"Data_Leads!${c}$2:${c}${nl}"
    vals = {}
    meta_idx = {}
    for b in brands:
        for m, camp, deliv, sp in b["meta"]: meta_idx[(b["display"], m, camp)] = meta_idx.get((b["display"], m, camp), 0) + sp
    lead_idx = {}
    for b in brands:
        ld = b["leads"]
        for (m, line), g in ld.groupby(["month", "line"]): lead_idx[(b["display"], m, line)] = (len(g), int(g["quality"].sum()))
    r = 2
    for ln in lines:
        for m in MONTHS:
            sp = meta_idx.get((ln["brand"], m, ln["camp"]), 0.0) if ln["attr"] == ATTR_OK else 0.0
            n_, q_ = lead_idx.get((ln["brand"], m, ln["camp"]), (0, 0))
            vals[(ln["brand"], ln["camp"], m)] = (sp, n_, q_)
            ws_pd.append([MLAB[m], ln["brand"], ln["camp"], ln["attr"],
                          f'=SUMIFS({mrange("E")},{mrange("A")},A{r},{mrange("B")},B{r},{mrange("C")},C{r})',
                          f'=COUNTIFS({lrange("A")},A{r},{lrange("B")},B{r},{lrange("F")},C{r})',
                          f'=SUMIFS({lrange("H")},{lrange("A")},A{r},{lrange("B")},B{r},{lrange("F")},C{r})'])
            r += 1
    npd = ws_pd.max_row
    for c in ws_pd[1]: c.font = fnt(True, "FFFFFF"); c.fill = fill(NAVY)
    ws_pd.freeze_panes = "A2"
    for i, w in enumerate([18, 22, 66, 28, 18, 16, 18], 1): ws_pd.column_dimensions[L(i)].width = w
    prng = lambda c: f"Pivot_Data!${c}$2:${c}${npd}"

    # ---- Comparison
    build_comparison(ws_cmp, disp, prng)
    # ---- Master Pivot (static body; real PivotTable injected after recalculation)
    pivot_rows = build_master_pivot(ws_piv, brands, lines, vals)
    # ---- Dashboard
    build_dashboard(ws_dash, ws_dd, disp, brands)
    # ---- docs tabs
    build_logs(ws_log, ws_kpi, ws_val, brands, lines, vals, prng, nm, nl, npd, pivot_rows)
    wb._sheets = [wb[n] for n in ["Master Dashboard", "Comparison", "Master Pivot", "Data Quality Log", "KPI Definitions", "Validation", "Dashboard_Data", "Pivot_Data", "Data_Meta", "Data_Leads"]]
    wb.active = 0
    wb.save(out_path)
    return dict(npd=npd, nm=nm, nl=nl)


CMP_FIRST = 6   # first brand row on Comparison


def build_comparison(ws, disp, prng):
    n = len(disp); last = CMP_FIRST + n - 1; port = last + 1
    ws.sheet_view.showGridLines = False; ws.sheet_properties.tabColor = BLUE
    ws["A1"] = f"BRAND COMPARISON — {MLAB[M1].upper()} vs {MLAB[M2].upper()}"; ws["A2"] = ("CPL · Quality Leads · Quality Lead % · CPQL for every brand. CRM leads (cost basis) = Facebook-sourced leads created in the month, EXCLUDING leads on campaigns whose spend is not in the supplied Meta files (shown in the orange columns at the right) so cost and leads match; Quality Lead = status in "
        + ", ".join(QUAL) + ". Cost = Meta spend ÷ the count. A dash (–) = cannot be calculated or not supplied. " + rcfg.partial_sentence() + ".")
    for rr, (sz, b) in ((1, (16, True)), (2, (10, False))):
        for ci in range(1, 30): ws.cell(rr, ci).fill = fill(NAVY); ws.cell(rr, ci).font = fnt(b, "FFFFFF", sz)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top"); ws.merge_cells("A2:X2"); ws.row_dimensions[2].height = 58
    groups = [("Spend (₹)", 2, 2, BLUE), ("CRM Leads (cost basis)", 4, 2, TEAL), ("1 · CPL — Cost Per Lead (₹)", 6, 5, BLUE), ("2 · QUALITY LEADS", 11, 5, TEAL),
              ("3 · QUALITY LEAD %", 16, 4, BLUE), ("4 · CPQL — Cost Per Quality Lead (₹)", 20, 5, TEAL)]
    for lab, c0, w, col in groups:
        ws.cell(4, c0, lab); ws.merge_cells(start_row=4, start_column=c0, end_row=4, end_column=c0 + w - 1)
        for ci in range(c0, c0 + w): ws.cell(4, ci).fill = fill(col); ws.cell(4, ci).font = fnt(True, "FFFFFF", 10)
    s1, s2 = MLAB[M1], MLAB[M2]
    heads = ["Brand", s1, s2, s1, s2, s1, s2, "Change (₹)", "Change %", "Verdict", s1, s2, "Change", "Change %", "Verdict", s1, s2, "Change (pp)", "Verdict",
             s1, s2, "Change (₹)", "Change %", "Verdict"]
    for i, h in enumerate(heads, 1):
        c = ws.cell(5, i, h); c.font = fnt(True, "FFFFFF", 9); c.fill = fill(NAVY); c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    ws.row_dimensions[5].height = 62
    ws.column_dimensions["A"].width = 26
    for i in range(2, 25): ws.column_dimensions[L(i)].width = 13
    # helper columns (cost basis: only brands that have Meta spend)
    for i, h in enumerate([f"Leads (spend brands) {s1}", f"Leads (spend brands) {s2}", f"Quality (spend brands) {s1}", f"Quality (spend brands) {s2}"], 26):
        c = ws.cell(5, i, h); c.font = fnt(True, "FFFFFF", 8); c.fill = fill(GREY); c.alignment = Alignment(wrap_text=True)
        ws.column_dimensions[L(i)].width = 13
    for i, h in enumerate([f"Leads on campaigns OUTSIDE the Meta export {s1} (not in CPL basis)", f"Leads on campaigns OUTSIDE the Meta export {s2} (not in CPL basis)",
                           f"Leads, campaign NOT DETERMINABLE {s1} (in CPL basis)", f"Leads, campaign NOT DETERMINABLE {s2} (in CPL basis)"], 30):
        c = ws.cell(5, i, h); c.font = fnt(True, "FFFFFF", 8); c.fill = fill("B45F06"); c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[L(i)].width = 16
    ws.cell(4, 30, "Lead coverage (for transparency)"); ws.merge_cells(start_row=4, start_column=30, end_row=4, end_column=33)
    for ci in range(30, 34): ws.cell(4, ci).fill = fill("B45F06"); ws.cell(4, ci).font = fnt(True, "FFFFFF", 10)
    q = lambda a, mi, ex=False: f'SUMIFS({prng(a)},{prng("A")},"{MLAB[MONTHS[mi]]}",{prng("B")},$A{{r}}' + (f',{prng("D")},"<>{ATTR_NOTIN}"' if ex else "") + ")"
    qa = lambda a, mi, attr: f'SUMIFS({prng(a)},{prng("A")},"{MLAB[MONTHS[mi]]}",{prng("B")},$A{{r}},{prng("D")},"{attr}")'
    for k, name in enumerate(disp + ["All brands with Meta spend"]):
        r = CMP_FIRST + k; isp = k == n
        ws.cell(r, 1, name).font = fnt(True, "FFFFFF" if isp else "000000", 10)
        if not isp:
            for mi in (0, 1):
                ws.cell(r, 2 + mi, "=" + q("E", mi).format(r=r)); ws.cell(r, 4 + mi, "=" + q("F", mi, True).format(r=r))
                ws.cell(r, 11 + mi, "=" + q("G", mi, True).format(r=r))
                ws.cell(r, 30 + mi, "=" + qa("F", mi, ATTR_NOTIN).format(r=r)); ws.cell(r, 32 + mi, "=" + qa("F", mi, ATTR_NOCAP).format(r=r))
            for mi in (0, 1):
                ws.cell(r, 26 + mi, f"=IF({L(2 + mi)}{r}>0,{L(4 + mi)}{r},0)"); ws.cell(r, 28 + mi, f"=IF({L(2 + mi)}{r}>0,{L(11 + mi)}{r},0)")
        else:
            for mi in (0, 1):
                ws.cell(r, 2 + mi, f"=SUM({L(2 + mi)}{CMP_FIRST}:{L(2 + mi)}{last})")
                ws.cell(r, 4 + mi, f"=SUM({L(26 + mi)}{CMP_FIRST}:{L(26 + mi)}{last})")
                ws.cell(r, 11 + mi, f"=SUM({L(28 + mi)}{CMP_FIRST}:{L(28 + mi)}{last})")
                ws.cell(r, 30 + mi, f"=SUM({L(30 + mi)}{CMP_FIRST}:{L(30 + mi)}{last})"); ws.cell(r, 32 + mi, f"=SUM({L(32 + mi)}{CMP_FIRST}:{L(32 + mi)}{last})")
        for mi in (0, 1):
            sp, ld, ql = f"{L(2 + mi)}{r}", f"{L(4 + mi)}{r}", f"{L(11 + mi)}{r}"
            ws.cell(r, 6 + mi, f'=IFERROR(IF(AND({ld}>0,{sp}>0),{sp}/{ld},"{DASH}"),"{DASH}")')
            ws.cell(r, 16 + mi, f'=IFERROR(IF({ld}>0,{ql}/{ld},"{DASH}"),"{DASH}")')
            ws.cell(r, 20 + mi, f'=IFERROR(IF(AND({ql}>0,{sp}>0),{sp}/{ql},"{DASH}"),"{DASH}")')
        def change(a, b, out_abs, out_pct=None, thr=0.01, lower_better=True, verdict=None, pp=False):
            x, y = f"{a}{r}", f"{b}{r}"
            ws.cell(r, out_abs, f'=IF(AND(ISNUMBER({x}),ISNUMBER({y})),{y}-{x},"{DASH}")')
            if out_pct: ws.cell(r, out_pct, f'=IF(AND(ISNUMBER({x}),ISNUMBER({y})),IF({x}<>0,{y}/{x}-1,"{DASH}"),"{DASH}")')
            key = f"{L(out_pct)}{r}" if out_pct else f"{L(out_abs)}{r}"
            lo, hi = ("Improved", "Worsened") if lower_better else ("Worsened", "Improved")
            ws.cell(r, verdict, f'=IF(NOT(ISNUMBER({key})),"{DASH}",IF({key}<={-thr},"{lo}",IF({key}>={thr},"{hi}","Flat")))')
        change("F", "G", 8, 9, 0.01, True, 10)
        change("K", "L", 13, 14, 0.01, False, 15)
        change("P", "Q", 18, None, 0.005, False, 19)
        change("T", "U", 22, 23, 0.01, True, 24)
        fmts = {2: '₹#,##0', 3: '₹#,##0', 4: '#,##0', 5: '#,##0', 6: '₹#,##0', 7: '₹#,##0', 8: '₹#,##0;-₹#,##0', 9: '0.0%;-0.0%', 11: '#,##0', 12: '#,##0', 13: '#,##0;-#,##0',
                14: '0.0%;-0.0%', 16: '0.0%', 17: '0.0%', 30: '#,##0', 31: '#,##0', 32: '#,##0', 33: '#,##0', 18: '0.0" pp";-0.0" pp"', 20: '₹#,##0', 21: '₹#,##0', 22: '₹#,##0;-₹#,##0', 23: '0.0%;-0.0%'}
        for ci in range(2, 34):
            c = ws.cell(r, ci); c.alignment = Alignment(horizontal="center" if ci in (10, 15, 19, 24) else "right")
            if ci in fmts: c.number_format = fmts[ci]
            c.font = fnt(isp, "FFFFFF" if isp else "000000", 10)
        # change in pp is stored as a fraction -> show as pp
        ws.cell(r, 18).number_format = '0.0%;-0.0%'
        if isp:
            for ci in range(1, 25): ws.cell(r, ci).fill = fill(NAVY)
    for col in ("J", "O", "S", "X"):
        rng = f"{col}{CMP_FIRST}:{col}{port}"
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{col}{CMP_FIRST}="Improved"'], fill=PatternFill("solid", bgColor="C6EFCE", fgColor="C6EFCE"), font=Font(color="006100", bold=True)))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{col}{CMP_FIRST}="Worsened"'], fill=PatternFill("solid", bgColor="FFC7CE", fgColor="FFC7CE"), font=Font(color="9C0006", bold=True)))
    ws.cell(port + 2, 1, ("Verdict rules: CPL and CPQL lower = Improved; Quality Leads and Quality Lead % higher = Improved; ±1% (±0.5 pp for Quality Lead %) = Flat. "
                          "'All brands with Meta spend' leaves out brands that have no Meta spend in the files (Adhira & Appa Toys) so cost and rates use the same base. "
                          + rcfg.partial_sentence() + ": counts (Quality Leads) are not like-for-like with a full month; costs and percentages are."))
    ws.merge_cells(start_row=port + 2, start_column=1, end_row=port + 2, end_column=24)
    ws.cell(port + 2, 1).alignment = Alignment(wrap_text=True, vertical="top"); ws.cell(port + 2, 1).font = fnt(False, "404040", 9); ws.row_dimensions[port + 2].height = 44
    ws.freeze_panes = "B6"


MP_FIRST = 17


def build_master_pivot(ws, brands, lines, vals):
    ws.sheet_properties.tabColor = TEAL; ws.sheet_view.showGridLines = False; ws.sheet_view.zoomScale = 85; ws.sheet_view.zoomScaleNormal = 85
    ncol = 1 + 6 * len(MONTHS)
    ws["A1"] = "MASTER PIVOT  —  BRAND COMPARISON  ·  " + f"{MLAB[M1]} vs {MLAB[M2]}"
    ws["A2"] = ("Interactive PivotTable · click the slicers (Brand, Month, Lead attribution, Campaign) to filter — Ctrl+click for several, ✕ to clear; drag fields in the PivotTable Field List to re-cut. "
                "Spend is Meta spend; leads are Facebook-sourced CRM leads. A dash (–) means spend or leads are zero (never a fake 0). " + rcfg.partial_sentence() + ".")
    for rr, (sz, b) in ((1, (16, True)), (2, (10, False))):
        for ci in range(1, ncol + 1): ws.cell(rr, ci).fill = fill(NAVY); ws.cell(rr, ci).font = fnt(b, "FFFFFF", sz)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=13); ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=13)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top"); ws.row_dimensions[2].height = 44
    ws["A13"] = "▸  Click any slicer item to filter. The table below is a real Excel PivotTable (refreshes when the file opens in desktop Excel)."
    ws.merge_cells("A13:M13")
    for ci in range(1, 14): ws.cell(13, ci).fill = fill(LIGHT); ws.cell(13, ci).font = fnt(True, NAVY, 9)
    ws.column_dimensions["A"].width = 62
    for ci in range(2, ncol + 1): ws.column_dimensions[L(ci)].width = 14
    for r_ in range(4, 12): ws.row_dimensions[r_].height = 20
    meas = [("Spend (₹)", "₹#,##0"), ("CRM Leads", "#,##0"), ("CPL (₹)", "₹#,##0"), ("Quality Leads", "#,##0"), ("Quality Lead %", "0.0%"), ("CPQL (₹)", "₹#,##0")]
    ws["B14"] = "Month"
    for ci in range(1, ncol + 1):
        for rr in (14, 15, 16): ws.cell(rr, ci).fill = fill(NAVY if rr < 16 else BLUE); ws.cell(rr, ci).font = fnt(True, "FFFFFF", 9)
    ws["A16"] = "Brand  ›  Campaign"
    for mi, m in enumerate(MONTHS):
        c0 = 2 + mi * 6
        ws.cell(15, c0, MLAB[m]).alignment = Alignment(horizontal="left")
        for k, (cap, fm) in enumerate(meas): ws.cell(16, c0 + k, cap).alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    ws.row_dimensions[16].height = 30

    def write(r, label, key_rows, bold=False, fillc=None, fc="000000"):
        ws.cell(r, 1, label)
        for mi, m in enumerate(MONTHS):
            sp = sum(vals[(b, c, m)][0] for b, c in key_rows); ld = sum(vals[(b, c, m)][1] for b, c in key_rows); ql = sum(vals[(b, c, m)][2] for b, c in key_rows)
            row = [sp, ld, (sp / ld if ld > 0 and sp > 0 else DASH), ql, (ql / ld if ld > 0 else DASH), (sp / ql if ql > 0 and sp > 0 else DASH)]
            for k, v in enumerate(row):
                c = ws.cell(r, 2 + mi * 6 + k, v); c.number_format = meas[k][1]; c.alignment = Alignment(horizontal="right")
        for ci in range(1, ncol + 1):
            ws.cell(r, ci).font = fnt(bold, fc, 9)
            if fillc: ws.cell(r, ci).fill = fill(fillc)
    # order: Brand items in first-appearance order; inside a brand the campaigns in shared-item (first-appearance) order
    order_brand = list(dict.fromkeys(l["brand"] for l in lines))
    camp_rank = {}
    for l in lines: camp_rank.setdefault(l["camp"], len(camp_rank))
    r = MP_FIRST; layout = []
    for b in order_brand:
        kids = sorted({l["camp"] for l in lines if l["brand"] == b}, key=lambda c: camp_rank[c])
        write(r, b, [(b, c) for c in kids], True, LIGHT, NAVY); r += 1
        for c in kids:
            write(r, c, [(b, c)]); ws.cell(r, 1).alignment = Alignment(indent=1); r += 1
        layout.append((b, kids))
    write(r, "Grand Total", [(l["brand"], l["camp"]) for l in lines], True, NAVY, "FFFFFF")
    grand = r
    ws.cell(r + 2, 1, ("Notes: values are exact sums of Pivot_Data (one row per brand × campaign × month). The pivot shows ALL Facebook leads incl. those on campaigns 'outside Meta export' and brands without Meta spend, "
                       "so its CPL / CPQL are lower than the Comparison tab (which excludes them) — to match the Comparison, un-tick 'Campaign outside Meta export' in the Lead attribution slicer. " + rcfg.partial_sentence() + "."))
    ws.merge_cells(start_row=r + 2, start_column=1, end_row=r + 2, end_column=13)
    ws.cell(r + 2, 1).alignment = Alignment(wrap_text=True, vertical="top"); ws.cell(r + 2, 1).font = fnt(False, "404040", 9); ws.row_dimensions[r + 2].height = 44
    return dict(grand=grand, layout=layout)


def build_dashboard(ws, wd, disp, brands):
    n = len(disp); last = CMP_FIRST + n - 1; port = last + 1
    C = "Comparison!"
    ws.sheet_view.showGridLines = False; ws.sheet_view.zoomScale = 90; ws.sheet_properties.tabColor = NAVY
    wd.sheet_properties.tabColor = GREY
    for i, w in enumerate([2, 22, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 2], 1): ws.column_dimensions[L(i)].width = w
    for ci in range(1, 15):
        for rr in (1, 2, 3): ws.cell(rr, ci).fill = fill(NAVY)
    ws["B1"] = "MASTER DASHBOARD — BRAND COMPARISON"; ws["B1"].font = fnt(True, "FFFFFF", 20)
    ws["B2"] = f"{MLAB[M1]}  vs  {MLAB[M2]}   ·   {n} brands   ·   Cost per Lead · Quality Leads · Quality Lead % · Cost per Quality Lead"; ws["B2"].font = fnt(False, "FFFFFF", 11)
    ws["B3"] = rcfg.partial_sentence() + ". Spend is Meta spend; leads are Facebook-sourced CRM leads on campaigns whose spend is in the Meta files. FW and Adhira & Appa Toys are separate brands."; ws["B3"].font = fnt(False, "DDE6F5", 9)
    ws.row_dimensions[1].height = 34
    # ---- helper (chart data with NA() gaps)
    wd["A1"] = "Chart helper — formulas only. #N/A is intentional (leaves a gap in the chart instead of a fake zero)."; wd["A1"].font = fnt(True, NAVY, 11)
    hd = ["Brand", f"CPL {MLAB[M1]}", f"CPL {MLAB[M2]}", f"Quality Leads {MLAB[M1]}", f"Quality Leads {MLAB[M2]}", f"Quality % {MLAB[M1]}", f"Quality % {MLAB[M2]}", f"CPQL {MLAB[M1]}", f"CPQL {MLAB[M2]}"]
    src = ["A", "F", "G", "K", "L", "P", "Q", "T", "U"]
    for i, h in enumerate(hd, 1):
        c = wd.cell(3, i, h); c.font = fnt(True, "FFFFFF", 9); c.fill = fill(NAVY); c.alignment = Alignment(wrap_text=True)
        wd.column_dimensions[L(i)].width = 18
    for k in range(n):
        for i, s in enumerate(src, 1):
            r = 4 + k; ref = f"{C}{s}{CMP_FIRST + k}"
            wd.cell(r, i, f"={ref}" if i == 1 else f"=IF(ISNUMBER({ref}),{ref},NA())")
    # ---- helper columns for the "graphical interpretation" charts (green = improved / red = worsened as two series; NA() = gap)
    gh = ["CPL change % — improved", "CPL change % — worsened", "CPQL change % — improved", "CPQL change % — worsened", "Quality Lead % change — improved", "Quality Lead % change — worsened",
          f"{MLAB[M2]} share of Meta spend", f"{MLAB[M2]} share of quality leads"]
    for i, h in enumerate(gh, 11):
        c = wd.cell(3, i, h); c.font = fnt(True, "FFFFFF", 9); c.fill = fill(TEAL); c.alignment = Alignment(wrap_text=True); wd.column_dimensions[L(i)].width = 18
    for k in range(n):
        r = 4 + k; cr_ = CMP_FIRST + k
        for col, srcc, good_neg in ((11, "I", True), (13, "W", True), (15, "R", False)):
            x = f"{C}{srcc}{cr_}"
            wd.cell(r, col, f"=IF(ISNUMBER({x}),IF({x}{'<' if good_neg else '>'}0,{x},NA()),NA())")
            wd.cell(r, col + 1, f"=IF(ISNUMBER({x}),IF({x}{'>' if good_neg else '<'}0,{x},NA()),NA())")
        wd.cell(r, 17, f"=IF(AND(ISNUMBER({C}C{cr_}),{C}C{port}>0),IF({C}C{cr_}>0,{C}C{cr_}/{C}C{port},0),0)")
        wd.cell(r, 18, f"=IF(AND(ISNUMBER({C}C{cr_}),{C}L{port}>0),IF({C}C{cr_}>0,{C}L{cr_}/{C}L{port},0),0)")
        for col in range(11, 19): wd.cell(r, col).number_format = "0.0%"
    # ---- portfolio tiles
    ws["B5"] = "ALL BRANDS WITH META SPEND — AT A GLANCE"; ws["B5"].font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(5, ci).fill = fill(BLUE)
    tiles = [("Meta Spend", "B", "C", "₹#,##0", None), ("CRM Leads (cost basis)", "D", "E", "#,##0", None), ("Cost per Lead (CPL)", "F", "G", "₹#,##0", True),
             ("Quality Leads", "K", "L", "#,##0", False), ("Quality Lead %", "P", "Q", "0.0%", False), ("Cost per Quality Lead (CPQL)", "T", "U", "₹#,##0", True)]
    for ti, (lab, c1, c2, fm, lower) in enumerate(tiles):
        c0 = 2 + ti * 2
        for rr in range(6, 11):
            for cc in (c0, c0 + 1): ws.cell(rr, cc).fill = fill("F4F7FB")
        for rr in range(6, 11): ws.merge_cells(start_row=rr, start_column=c0, end_row=rr, end_column=c0 + 1)
        a = ws.cell(6, c0, lab); a.font = fnt(True, NAVY, 9); a.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
        v = ws.cell(7, c0, f"={C}{c2}{port}"); v.number_format = fm; v.font = fnt(True, NAVY, 20); v.alignment = Alignment(horizontal="center", vertical="center")
        s = ws.cell(8, c0, f'="{MLAB[M2]}"'); s.font = fnt(False, GREY, 8); s.alignment = Alignment(horizontal="center")
        p = ws.cell(9, c0, f'="{MLAB[M1]}:  "&IF(ISNUMBER({C}{c1}{port}),TEXT({C}{c1}{port},"{fm.replace(chr(8377), chr(8377))}"),"{DASH}")'); p.font = fnt(False, GREY, 9); p.alignment = Alignment(horizontal="center")
        ch = ws.cell(10, c0, f'=IF(AND(ISNUMBER({C}{c1}{port}),ISNUMBER({C}{c2}{port})),IF({C}{c1}{port}=0,"{DASH}",IF({C}{c2}{port}>={C}{c1}{port},"▲ ","▼ ")&TEXT(ABS({C}{c2}{port}/{C}{c1}{port}-1),"0.0%")&" vs {MLAB[M1].split()[0]}"),"{DASH}")')
        ch.font = fnt(True, GREY, 10); ch.alignment = Alignment(horizontal="center")
        if lower is not None:
            good, bad = (GREEN, RED) if lower else (RED, GREEN)
            cell = ch.coordinate
            ws.conditional_formatting.add(cell, FormulaRule(formula=[f'LEFT({cell},1)="▲"'], font=Font(color=bad if lower else good, bold=True)))
            ws.conditional_formatting.add(cell, FormulaRule(formula=[f'LEFT({cell},1)="▼"'], font=Font(color=good if lower else bad, bold=True)))
    ws.row_dimensions[7].height = 34
    # ---- scorecard
    r0 = 12
    ws.cell(r0, 2, "SCORECARD — DID EACH BRAND IMPROVE? (green = better, red = worse, grey = flat / not comparable)").font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(r0, ci).fill = fill(TEAL)
    sh = ["Brand", f"CPL {MLAB[M2].split()[0]}", "CPL verdict", f"Quality Leads {MLAB[M2].split()[0]}", "Quality Leads verdict", f"Quality % {MLAB[M2].split()[0]}", "Quality % verdict",
          f"CPQL {MLAB[M2].split()[0]}", "CPQL verdict"]
    scols = [2, 3, 4, 5, 6, 7, 8, 9, 10]
    srcc = [("A", None), ("G", '₹#,##0'), ("J", None), ("L", '#,##0'), ("O", None), ("Q", '0.0%'), ("S", None), ("U", '₹#,##0'), ("X", None)]
    for i, h in enumerate(sh):
        c = ws.cell(r0 + 1, scols[i], h); c.font = fnt(True, NAVY, 9); c.fill = fill(LIGHT); c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    ws.row_dimensions[r0 + 1].height = 30
    for k in range(n + 1):
        r = r0 + 2 + k
        for i, (s, fm) in enumerate(srcc):
            c = ws.cell(r, scols[i], f"={C}{s}{CMP_FIRST + k}"); c.alignment = Alignment(horizontal="left" if i == 0 else "center"); c.font = fnt(i == 0 or k == n, "000000", 10)
            if fm: c.number_format = fm
            if k == n: c.fill = fill(LIGHT)
    sr1, sr2 = r0 + 2, r0 + 2 + n
    for col in "DFHJ":
        rng = f"{col}{sr1}:{col}{sr2}"
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{col}{sr1}="Improved"'], fill=PatternFill("solid", bgColor="C6EFCE", fgColor="C6EFCE"), font=Font(color="006100", bold=True)))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{col}{sr1}="Worsened"'], fill=PatternFill("solid", bgColor="FFC7CE", fgColor="FFC7CE"), font=Font(color="9C0006", bold=True)))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'OR({col}{sr1}="Flat",{col}{sr1}="{DASH}")'], fill=PatternFill("solid", bgColor="EDEDED", fgColor="EDEDED"), font=Font(color="595959")))
    # ---- key insights (formula-driven)
    ir = sr2 + 2
    ws.cell(ir, 2, "KEY INSIGHTS (update automatically)").font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(ir, ci).fill = fill(TEAL)
    rng = lambda col: f"{C}${col}${CMP_FIRST}:${col}${last}"
    names = f"{C}$A${CMP_FIRST}:$A${last}"
    def best(col, fn): return f'INDEX({names},MATCH({fn}({rng(col)}),{rng(col)},0))'
    s1, s2 = MLAB[M1].split()[0], MLAB[M2].split()[0]
    ins = [
        f'="• Portfolio (brands with Meta spend): CPL went from ₹"&TEXT({C}F{port},"#,##0")&" in {s1} to ₹"&TEXT({C}G{port},"#,##0")&" in {s2} ("&IF({C}I{port}<0,"down ","up ")&TEXT(ABS({C}I{port}),"0.0%")&"); Quality Lead % went from "&TEXT({C}P{port},"0.0%")&" to "&TEXT({C}Q{port},"0.0%")&"; cost per quality lead from ₹"&TEXT({C}T{port},"#,##0")&" to ₹"&TEXT({C}U{port},"#,##0")&"."',
        f'=IFERROR("• Biggest CPL improvement: "&{best("I", "MIN")}&" ("&TEXT(MIN({rng("I")}),"0.0%")&"). Biggest CPL rise: "&{best("I", "MAX")}&" (+"&TEXT(MAX({rng("I")}),"0.0%")&").","• CPL change could not be ranked.")',
        f'=IFERROR("• Highest Quality Lead % in {s2}: "&{best("Q", "MAX")}&" ("&TEXT(MAX({rng("Q")}),"0.0%")&"). Lowest: "&{best("Q", "MIN")}&" ("&TEXT(MIN({rng("Q")}),"0.0%")&").","• Quality % could not be ranked.")',
        f'=IFERROR("• Lowest cost per quality lead in {s2}: "&{best("U", "MIN")}&" (₹"&TEXT(MIN({rng("U")}),"#,##0")&"). Highest: "&{best("U", "MAX")}&" (₹"&TEXT(MAX({rng("U")}),"#,##0")&").","• CPQL could not be ranked.")',
        f'="• Brands improved on CPL: "&COUNTIF({rng("J")},"Improved")&" of "&(COUNTIF({rng("J")},"Improved")+COUNTIF({rng("J")},"Worsened")+COUNTIF({rng("J")},"Flat"))&" comparable brands; on CPQL: "&COUNTIF({rng("X")},"Improved")&" of "&(COUNTIF({rng("X")},"Improved")+COUNTIF({rng("X")},"Worsened")+COUNTIF({rng("X")},"Flat"))&"; on Quality Lead %: "&COUNTIF({rng("S")},"Improved")&" of "&(COUNTIF({rng("S")},"Improved")+COUNTIF({rng("S")},"Worsened")+COUNTIF({rng("S")},"Flat"))&"."',
    ]
    for i, f_ in enumerate(ins):
        c = ws.cell(ir + 1 + i, 2, f_); c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = fnt(False, "000000", 10)
        ws.merge_cells(start_row=ir + 1 + i, start_column=2, end_row=ir + 1 + i, end_column=13); ws.row_dimensions[ir + 1 + i].height = 32
    # ---- charts
    cr = ir + len(ins) + 3
    ws.cell(cr - 1, 2, "CHARTS — " + f"{MLAB[M1]} vs {MLAB[M2]}" + " (a missing bar = not calculable for that brand)").font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(cr - 1, ci).fill = fill(BLUE)
    cat = Reference(wd, min_col=1, min_row=4, max_row=3 + n)
    specs = [(2, "1 · Cost Per Lead (₹) — lower is better", BLUE, "₹#,##0"), (4, "2 · Quality Leads (count)", TEAL, "#,##0"), (6, "3 · Quality Lead % — higher is better", BLUE, "0%"), (8, "4 · Cost Per Quality Lead (₹) — lower is better", TEAL, "₹#,##0")]
    for k, (c0, title, col, nf) in enumerate(specs):
        ch = BarChart(); ch.type = "col"; ch.title = title; ch.width = 19; ch.height = 9; ch.legend.position = "b"
        ch.add_data(Reference(wd, min_col=c0, max_col=c0 + 1, min_row=3, max_row=3 + n), titles_from_data=True); ch.set_categories(cat)
        ch.series[0].graphicalProperties.solidFill = "9DB2D6"; ch.series[1].graphicalProperties.solidFill = col
        ch.y_axis.number_format = nf; ch.y_axis.delete = False; ch.x_axis.delete = False; ch.y_axis.majorGridlines = None
        ws.add_chart(ch, f"{'B' if k % 2 == 0 else 'H'}{cr + (k // 2) * 19}")
    # ---- graphical interpretation
    gr = cr + 2 * 19 + 1
    ws.cell(gr, 2, f"GRAPHICAL INTERPRETATION — HOW EACH BRAND MOVED ({MLAB[M1]} → {MLAB[M2]}) AND WHERE THE MONEY WENT").font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(gr, ci).fill = fill(TEAL)
    c_ = ws.cell(gr + 1, 2, "How to read: GREEN bars = the brand got better, RED = got worse. For cost charts a bar to the LEFT of zero means the cost fell (good); for Quality Lead % a bar to the RIGHT means a higher share of good leads (good). "
                 "The last chart compares each brand's share of October Meta spend with its share of October quality leads — a brand whose quality-lead share is higher than its spend share is delivering more than it costs.")
    c_.alignment = Alignment(wrap_text=True, vertical="top"); c_.font = fnt(False, "404040", 9); ws.merge_cells(start_row=gr + 1, start_column=2, end_row=gr + 1, end_column=13); ws.row_dimensions[gr + 1].height = 44
    cat2 = Reference(wd, min_col=1, min_row=4, max_row=3 + n)
    from openpyxl.chart.label import DataLabelList as _DLL
    def dlabels(series, fm):
        series.dLbls = _DLL(); series.dLbls.showVal = True; series.dLbls.showSerName = False; series.dLbls.showCatName = False; series.dLbls.showLegendKey = False; series.dLbls.showPercent = False; series.dLbls.numFmt = fm
    def change_chart(title, c0, fm, anchor):
        ch = BarChart(); ch.type = "bar"; ch.grouping = "clustered"; ch.overlap = 100; ch.gapWidth = 40
        ch.title = title; ch.width = 19; ch.height = 10.5; ch.legend.position = "b"
        ch.add_data(Reference(wd, min_col=c0, max_col=c0 + 1, min_row=3, max_row=3 + n), titles_from_data=True); ch.set_categories(cat2)
        ch.series[0].graphicalProperties.solidFill = "2E9E5B"; ch.series[1].graphicalProperties.solidFill = "D64545"
        for sr_ in ch.series: dlabels(sr_, fm)
        ch.x_axis.scaling.orientation = "maxMin"; ch.x_axis.tickLblPos = "low"; ch.x_axis.delete = False; ch.y_axis.delete = False
        ch.y_axis.number_format = fm; ch.y_axis.majorGridlines = None
        ws.add_chart(ch, anchor)
    change_chart("A · Cost Per Lead — change vs " + MLAB[M1].split()[0] + " (left = cheaper)", 11, "0%", f"B{gr + 3}")
    change_chart("B · Cost Per Quality Lead — change vs " + MLAB[M1].split()[0] + " (left = cheaper)", 13, "0%", f"H{gr + 3}")
    change_chart("C · Quality Lead % — change in percentage points (right = better)", 15, "0.0%", f"B{gr + 3 + 22}")
    d_ch = BarChart(); d_ch.type = "bar"; d_ch.grouping = "clustered"; d_ch.gapWidth = 60
    d_ch.title = f"D · Share of {MLAB[M2]} Meta spend vs share of {MLAB[M2]} quality leads"; d_ch.width = 19; d_ch.height = 10.5; d_ch.legend.position = "b"
    d_ch.add_data(Reference(wd, min_col=17, max_col=18, min_row=3, max_row=3 + n), titles_from_data=True); d_ch.set_categories(cat2)
    d_ch.series[0].graphicalProperties.solidFill = "9DB2D6"; d_ch.series[1].graphicalProperties.solidFill = TEAL
    for sr_ in d_ch.series: dlabels(sr_, "0%")
    d_ch.x_axis.scaling.orientation = "maxMin"; d_ch.x_axis.delete = False; d_ch.y_axis.delete = False; d_ch.y_axis.number_format = "0%"; d_ch.y_axis.majorGridlines = None
    ws.add_chart(d_ch, f"H{gr + 3 + 22}")
    # ---- caveats
    vr = gr + 3 + 22 * 2 + 1
    ws.cell(vr, 2, "HOW TO READ THIS PAGE · DATA NOTES").font = fnt(True, "FFFFFF", 11)
    for ci in range(2, 14): ws.cell(vr, ci).fill = fill(GREY)
    notes = [
        "• Cost Per Lead (CPL) = Meta spend ÷ CRM leads that came from Facebook. Quality Lead = lead that reached Qualified, Follow-Up, Details Shared, Meeting Scheduled or Meeting Conducted. Quality Lead % = Quality Leads ÷ CRM leads. Cost Per Quality Lead (CPQL) = Meta spend ÷ Quality Leads.",
        "• " + rcfg.partial_sentence() + "; lead data ends 30 Oct for most brands (FW leads end 27 Oct, so FW's October cost per lead is overstated). Counts such as Quality Leads are not like-for-like with a full month — compare costs and percentages first.",
        "• Daewoo comes from your two Daewoo reports (its own CRM; its 'qualified' also counts Interested, Negotiation, Token Received, Won). FW = Kustard-FW Meta spend ÷ Facebook form leads in the FW lead file (bulk Excel uploads are not counted).",
        "• Leads on campaigns whose spend is NOT in the supplied Meta files are left out of CPL, Quality % and CPQL so cost and leads match (Natuf: 86% of Sep and 39% of Oct leads; Carlton 18% of Oct; Adhira & Appa ~10%). They are listed in the orange columns of the Comparison tab. 'Campaign not determinable' leads (no campaign name, ad set not mappable) stay in.",
        "• Adhira & Appa Toys has leads but no Meta spend in the supplied files, so its cost figures show a dash; its Quality Lead % is real.",
        "• Open the Master Pivot tab for the interactive view (slicers need desktop Excel) and the Comparison tab for every number behind this page.",
    ]
    for i, t in enumerate(notes):
        c = ws.cell(vr + 1 + i, 2, t); c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = fnt(False, "404040", 9)
        ws.merge_cells(start_row=vr + 1 + i, start_column=2, end_row=vr + 1 + i, end_column=13); ws.row_dimensions[vr + 1 + i].height = 30
    ws.page_setup.orientation = "portrait"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_logs(ws_log, ws_kpi, ws_val, brands, lines, vals, prng, nm, nl, npd, pivot_rows):
    # ---- KPI definitions
    kd = [("KPI", "Definition", "Source"),
          ("CRM Leads (cost basis)", "Facebook-sourced leads created in the month (Lead Source = Facebook; FW file: 'face book'; Daewoo: leads on campaigns with spend in the Daewoo reports), EXCLUDING leads on campaigns whose spend is not in the supplied Meta files (they would raise leads without raising cost). Leads with no determinable campaign stay in.", "LeadDetails / FW_LeadData / Daewoo reports"),
          ("Quality Lead", "Status in {" + ", ".join(QUAL) + "}. Daewoo: the Daewoo report's own Qualified flag (also counts Interested, Negotiation, Token Received, Won).", "CRM"),
          ("Quality Lead %", "Quality Leads ÷ CRM Leads", ""),
          ("CPL — Cost Per Lead", "Meta spend ÷ CRM Leads", "Meta campaign export (Daewoo: Daewoo report)"),
          ("CPQL — Cost Per Quality Lead", "Meta spend ÷ Quality Leads", ""),
          ("Verdict", "CPL/CPQL lower = Improved; Quality Leads / Quality Lead % higher = Improved; ±1 % (±0.5 pp) = Flat", ""),
          ("Dash (–)", "Cannot be calculated or not supplied by the source (zero spend / zero leads / no Meta export). Never a fake zero.", ""),
          ("Lead attribution", "Campaign in Meta export · Campaign outside Meta export (named, but its spend is not in the supplied Meta file) · Campaign not determinable (no campaign name and ad set not uniquely mapped)", "")]
    for row_ in kd: ws_kpi.append(list(row_))
    for c in ws_kpi[1]: c.font = fnt(True, "FFFFFF"); c.fill = fill(NAVY)
    ws_kpi.column_dimensions["A"].width = 32; ws_kpi.column_dimensions["B"].width = 120; ws_kpi.column_dimensions["C"].width = 36
    # ---- Data Quality Log
    ws_log.append(["#", "Brand / area", "Check", "Result", "Detail"])
    items = []
    def add(area, check, res, detail): items.append((area, check, res, detail))
    add("All", "Period & cut-offs", "WARN", f"{rcfg.partial_sentence()}. Meta exports (Rahul set) end 30 Oct; the new Meta files (Govintham, FW, Nonstop) end 31 Oct; LeadDetails ends 30 Oct 13:15; FW leads end 27 Oct; Daewoo reports end 30 Oct.")
    add("All", "Quality Lead definition", "INFO", "Qualified, Follow-Up, Details Shared, Meeting Scheduled, Meeting Conducted (same as the 7 brand reports). Daewoo uses its own report flag.")
    add("All", "FW is a separate brand", "INFO", "FW-prefixed CRM brands / campaigns are excluded from every other brand and reported only under FW (FW_LeadData + Kustard–FW Meta).")
    add("Adhira & Appa", "TK variants included", "INFO", "'Adhira & Appa Tk UF/MF' leads sit on 'AAC | … | TN-Kerala' campaigns (TK = Tamil Nadu–Kerala), i.e. Adhira & Appa Coffee, so they are counted here. The earlier 7 brand reports excluded them — Adhira & Appa's September leads there are ~226 lower.")
    add("Adhira & Appa Toys", "No Meta spend supplied", "WARN", "Leads on 'E_Adhira & Appa Toys_23092026' are in the CRM, but that campaign is in none of the Meta exports. CPL / CPQL show a dash; leads and quality % are real.")
    add("Daewoo", "Source", "INFO", "Taken from the two Daewoo × ShootOrder reports (user's choice): spend and leads on campaigns with spend; qualified = report flag.")
    for b in brands:
        nt = b["notes"]; ld = b["leads"]; n_ld = len(ld)
        if b["name"] == "Daewoo":
            for m, rp in nt["reports"].items():
                add("Daewoo", f"{m} report", "INFO", f"{rp['file']}: {rp['rows']:,} CRM rows, {rp['on_active']:,} on spend campaigns (used), {rp['unmapped']} unmapped; spend ₹{rp['spend']:,.2f}; qualified by report flag {rp['qual_flag']:,} (under the 7-brand status rule it would be {rp['qual_7rule']:,}).")
            add("Daewoo", "Meta CSV vs report spend", "INFO", "The new Daewoo Meta CSV (to 31 Oct) differs from the reports (to 30 Oct); the reports are used so spend and leads share the same cut-off.")
            continue
        extra = ""
        if b["name"] == "FW":
            extra = f" FW lead file: {nt['fw_all_leads']:,} leads in {'/'.join(MONTHS)}; only {n_ld:,} are Facebook form leads (rest: bulk uploads {nt['fw_excel']:,} + other). No usable lead id (Lead Id is '_' on every row)."
        nocap = int((ld["attr"] == ATTR_NOCAP).sum()); notin = int((ld["attr"] == ATTR_NOTIN).sum())
        add(b["display"], "Lead attribution", "WARN" if (nocap + notin) / max(n_ld, 1) > 0.3 else "INFO",
            f"{n_ld:,} Facebook-sourced leads; {nocap:,} ({nocap / max(n_ld, 1):.0%}) campaign not determinable; {notin:,} ({notin / max(n_ld, 1):.0%}) on campaigns outside the Meta export (their spend is not in the cost); "
            f"{nt['crm_nonfb']:,} leads from other sources are not counted; last lead {nt['last_lead']:%d %b %H:%M}." + extra)
        add(b["display"], "Source files", "INFO", f"{nt['source']}" + (f"; Meta file {nt['meta_file']}" if nt.get("meta_file") else "") + (" (daily rows summed to months)" if nt.get("meta_daily") else "") + f"; Meta spend in period ₹{nt['meta_total']:,.2f}; {b['inactive_omitted']} Meta campaigns with no spend and no leads are omitted from the pivot.")
        if nt.get("fw_excluded_name") or nt.get("fw_excluded_adset"):
            add(b["display"], "FW exclusion", "INFO", f"{nt['fw_excluded_name']} leads on FW_* campaigns and {nt['fw_excluded_adset']} leads on FW ad sets excluded (FW is a separate brand).")
    for i, (area, check, res, detail) in enumerate(items, 1): ws_log.append([i, area, check, res, detail])
    for c in ws_log[1]: c.font = fnt(True, "FFFFFF"); c.fill = fill(NAVY)
    for i, w in enumerate([5, 22, 30, 9, 170], 1): ws_log.column_dimensions[L(i)].width = w
    for row in ws_log.iter_rows(min_row=2):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")
    # ---- Validation (live)
    ws_val["A1"] = "VALIDATION — live formulas"; ws_val["A1"].font = fnt(True, "FFFFFF", 14)
    for i in range(1, 6): ws_val.cell(1, i).fill = fill(NAVY)
    for i, h in enumerate(["Check", "Value A", "Value B", "Difference", "Status"], 1):
        c = ws_val.cell(3, i, h); c.font = fnt(True, "FFFFFF"); c.fill = fill(NAVY)
    P = lambda c: prng(c)
    checks = [("Pivot_Data spend total vs Data_Meta (active campaigns' spend)", f"=SUM({P('E')})", None),
              ("Pivot_Data CRM leads total vs Data_Leads rows", f"=SUM({P('F')})", f"=COUNTA(Data_Leads!$A$2:$A${nl})"),
              ("Pivot_Data quality leads total vs Data_Leads quality flags", f"=SUM({P('G')})", f"=SUM(Data_Leads!$H$2:$H${nl})"),
              ("Comparison: total spend (all brands) vs Pivot_Data", f"=SUM(Comparison!B{CMP_FIRST}:C{CMP_FIRST + len(brands) - 1})", f"=SUM({P('E')})"),
              ("Comparison: cost-basis leads + leads outside the Meta export = all Pivot_Data leads", f"=SUM(Comparison!D{CMP_FIRST}:E{CMP_FIRST + len(brands) - 1})+SUM(Comparison!AD{CMP_FIRST}:AE{CMP_FIRST + len(brands) - 1})", f"=SUM({P('F')})"),
              ("Comparison: quality leads (cost basis) vs Pivot_Data excluding campaigns outside the Meta export", f"=SUM(Comparison!K{CMP_FIRST}:L{CMP_FIRST + len(brands) - 1})", f'=SUMIFS({P("G")},{P("D")},"<>{ATTR_NOTIN}")')]
    g = pivot_rows["grand"]
    for mi in range(len(MONTHS)):
        c0 = 2 + mi * 6
        checks.append((f"Master Pivot grand total spend {MLAB[MONTHS[mi]]} vs Pivot_Data", f"='Master Pivot'!{L(c0)}{g}", f'=SUMIFS({P("E")},{P("A")},"{MLAB[MONTHS[mi]]}")'))
        checks.append((f"Master Pivot grand total CRM leads {MLAB[MONTHS[mi]]} vs Pivot_Data", f"='Master Pivot'!{L(c0 + 1)}{g}", f'=SUMIFS({P("F")},{P("A")},"{MLAB[MONTHS[mi]]}")'))
        checks.append((f"Master Pivot grand total quality leads {MLAB[MONTHS[mi]]} vs Pivot_Data", f"='Master Pivot'!{L(c0 + 3)}{g}", f'=SUMIFS({P("G")},{P("A")},"{MLAB[MONTHS[mi]]}")'))
    rr = 4
    for name, a, b in checks:
        ws_val.cell(rr, 1, name); ws_val.cell(rr, 2, a)
        if b is None:   # spend: Pivot_Data (active campaigns) vs Data_Meta total of those campaigns
            act = {(l["brand"], l["camp"]) for l in lines if l["attr"] == ATTR_OK}
            tot = sum(v[0] for (bb_, cc_, mm_), v in vals.items())
            b = f"={round(tot, 2)}"
        ws_val.cell(rr, 3, b); ws_val.cell(rr, 4, f"=ROUND(B{rr}-C{rr},2)"); ws_val.cell(rr, 5, f'=IF(D{rr}=0,"✔ ties","✘ CHECK")'); rr += 1
    ws_val.column_dimensions["A"].width = 80
    for cl in "BCDE": ws_val.column_dimensions[cl].width = 18


# =============================================================== driver
def main(leads_dir, meta_experts_dir, comp_dir, out_dir):
    dirs = {"leads": leads_dir, "meta_experts": meta_experts_dir, "comp": comp_dir}
    os.makedirs(out_dir, exist_ok=True)
    brands = prepare(dirs)
    rcfg.set_data_end(max(b["notes"]["last_lead"] for b in brands if b["notes"].get("last_lead") is not None and b["name"] != "FW"))   # partial-month wording
    lines = build_lines(brands)
    tmp = tempfile.mkdtemp(prefix="cmp_")
    raw = os.path.join(tmp, "Brand_Comparison_Sep-Oct2026.xlsx")
    info = write_workbook(brands, lines, dirs, raw)
    calc = os.path.join(tmp, "calc")
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", calc, raw], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    spec = dict(
        MONTHS=[MLAB[m] for m in MONTHS],
        STR_FIELDS=["Month", "Brand", "Campaign", "Lead attribution"],
        NUM_FIELDS=["Amount Spent (INR)", "CRM Leads Count", "Quality Leads Count"],
        CALC=[("CPL ratio", "'Amount Spent (INR)'/'CRM Leads Count'"), ("Quality pct ratio", "'Quality Leads Count'/'CRM Leads Count'"), ("CPQL ratio", "'Amount Spent (INR)'/'Quality Leads Count'")],
        DATA_FIELDS=[("Spend (₹)", 4, "cost"), ("CRM Leads", 5, 3), ("CPL (₹)", 7, "cost"), ("Quality Leads", 6, 3), ("Quality Lead %", 8, "pct"), ("CPQL (₹)", 9, "cost")],
        SLICERS=[("Brand", 1, "Slicer_Brand"), ("Month", 0, "Slicer_Month"), ("Lead attribution", 3, "Slicer_Lead_attribution"), ("Campaign", 2, "Slicer_Campaign")],
        COL_FIELD=0, ROW_FIELDS=(1, 2), ROW_CAPTION="Brand  ›  Campaign", COL_CAPTION="Month",
        SLICER_LAYOUT=[(95250, 1800000), (2000000, 1300000), (3400000, 2500000), (6000000, 4300000)])
    out = os.path.join(out_dir, "Brand_Comparison_Sep-Oct2026.xlsx")
    res = inject_pivot.inject(os.path.join(calc, os.path.basename(raw)), out, spec)
    inject_pivot.configure(None)
    shutil.rmtree(tmp, ignore_errors=True)
    print(out, info, res)
    return out


if __name__ == "__main__":
    main(*sys.argv[1:5])
