#!/usr/bin/env python3
"""Month-to-month Brand + Campaign report (FinalReport format) for one brand.

usage: build_brand_report.py <Brand name> <lead_dir> <meta_dir> <out_dir>
  lead_dir: folder holding LeadDetails_<Month>2026.csv (Jul-Oct)
  meta_dir: folder holding the monthly (or daily) Meta *Campaigns* CSV exports
Raw files contain lead PII: only Lead id / status / dates / campaign are copied to the output.
"""
import sys, glob, os, re, warnings
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.formula import ArrayFormula

warnings.filterwarnings("ignore")
MONTHS = ["Jul", "Aug", "Sep", "Oct"]
MFULL = {"Jul": "JULY 2026", "Aug": "AUGUST 2026", "Sep": "SEPTEMBER 2026", "Oct": "OCTOBER 2026 (partial — to 30 Oct)"}
QUAL = ["Qualified", "Follow-Up", "Details Shared", "Meeting Scheduled", "Meeting Conducted"]
MEET = ["Follow-Up", "Meeting Scheduled", "Meeting Conducted"]

# brand -> (Meta file prefix, CRM 'Brand' values included). Draft per user's instruction: In House / MF / FOFO / TK variants included.
BRANDS = {
    "Natuf": ("Natuf-x-Gen-Y", ["Natuf", "In House Natuf", "Natuf_MF"]),
    "Adhira & Appa Coffee": ("Inhouse---Adhira", ["Adhira & Appa Coffee", "Adhira & Appa Coffee MF", "Adhira & Appa Coffee FOFO"]),
    "Chhota Bheem": ("Shoot-Order---Chhota", ["Chhota Bheem"]),
    "Bonum Cha": ("In-House-Bonum", ["Bonum Cha", "Bonum Cha MF"]),
    "Carlton": ("Kustard-__-Carlton", ["Carlon Spa", "Carlton Salon", "Carlton Wellness Center", "In House Carlton Salon",
                                       "In House Carlton Wellness", "Carlton"]),
    "Shayreen": ("In-House-SHAYREEN", ["Shayreen by Natuf"]),
    "Acer Chhota Bheem": ("Inhouse-__-Acer", ["Acer Electric Bikes", "Acer TK"]),
}

# ---- metric layout (one block per month + total) ----
METRICS = [  # key, header, number format, group
    ("spend", "Amount Spent (INR)", "₹#,##0.00", "meta"), ("impr", "Impressions", "#,##0", "meta"),
    ("reach", "Reach", "#,##0", "meta"), ("freq", "Frequency (Impr ÷ Reach)", "0.00", "meta"),
    ("clicks", "Total Clicks (all)", "#,##0", "meta"), ("lclicks", "Link Clicks", "#,##0", "meta"),
    ("ctr", "CTR (all) = Clicks ÷ Impr", "0.00%", "meta"), ("lctr", "Link CTR = Link Clicks ÷ Impr", "0.00%", "meta"),
    ("cpc", "CPC (all) = Spend ÷ Total Clicks", "₹#,##0.00", "meta"), ("lcpc", "Link CPC = Spend ÷ Link Clicks", "₹#,##0.00", "meta"),
    ("cpm", "CPM = Spend ÷ Impr × 1,000", "₹#,##0.00", "meta"), ("lpv", "Landing Page Views", "#,##0", "meta"),
    ("mleads", "Meta Platform Leads (lead-form results)", "#,##0", "meta"), ("cplm", "CPL (Meta) = Spend ÷ Meta Leads", "₹#,##0.00", "meta"),
    ("crm", "CRM Leads", "#,##0", "crm"), ("qual", "Qualified Leads", "#,##0", "crm"),
    ("qualp", "Qualification %", "0.00%", "crm"), ("meet", "Meetings Scheduled", "#,##0", "crm"),
    ("meetp", "Meeting %", "0.00%", "crm"), ("cplc", "CPL (CRM) = Spend ÷ CRM Leads", "₹#,##0.00", "crm"),
    ("cpql", "CPQL = Spend ÷ Qualified", "₹#,##0.00", "crm"), ("cpmt", "Cost Per Meeting = Spend ÷ Meetings", "₹#,##0.00", "crm"),
    ("cont", "Contacted Leads", "#,##0", "cont"), ("contp", "Contacted %", "0.00%", "cont"),
    ("ncont", "Not Contacted Leads", "#,##0", "cont"), ("ncontp", "Not Contacted %", "0.00%", "cont"),
    ("blank", "Blank / Invalid Status", "#,##0", "cont"),
    ("atat", "Avg Lead Modification TAT (hours)", "#,##0.00", "tat"), ("mtat", "Median Lead Modification TAT (hours)", "#,##0.00", "tat"),
    ("elig", "Eligible Leads for TAT", "#,##0", "tat"),
]
KEYS = [m[0] for m in METRICS]
NM = len(METRICS)
FIX = 3  # A Brand/class, B Campaign, C Delivery
BLOCKS = MONTHS + ["Total"]
GROUP_FILL = {"meta": "2E5090", "crm": "0E7C7B", "cont": "7B3F99", "tat": "B45F06"}
NAVY, BLUE, GREY = "1F3864", "2E5090", "7F7F7F"


def colof(bi, key):
    return L(FIX + 1 + bi * NM + KEYS.index(key))


def fill(h): return PatternFill("solid", fgColor=h)


def f(bold=False, color="000000", sz=9): return Font(name="Calibri", size=sz, bold=bold, color=color)


# ---------------------------------------------------------------- data loading
def load_crm(lead_dir, crm_brands):
    out, stats = [], {}
    for m, name in zip(MONTHS, ["July", "August", "September", "October"]):
        d = pd.read_csv(os.path.join(lead_dir, f"LeadDetails_{name}2026.csv"), low_memory=False,
                        usecols=["Lead id", "Created On", "Modified On", "Brand", "Lead Source", "Status", "Facebook Campaign Name"])
        stats[m] = {"file_rows": len(d)}
        d["File"] = m
        out.append(d)
    d = pd.concat(out, ignore_index=True)
    d["Created"] = pd.to_datetime(d["Created On"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    d["Modified"] = pd.to_datetime(d["Modified On"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    d["Month"] = d["Created"].dt.strftime("%b")
    inb = d[d["Brand"].isin(crm_brands)].copy()
    fw = inb["Facebook Campaign Name"].fillna("").str.match(r"(?i)^fw[_ \-|]")
    stats["fw_excluded"] = int(fw.sum())
    inb = inb[~fw]
    stats["bad_month"] = int((~inb["Month"].isin(MONTHS)).sum())
    inb = inb[inb["Month"].isin(MONTHS)]
    stats["dup_ids"] = int(inb["Lead id"].duplicated().sum())
    stats["maxdate"] = d["Created"].max()
    stats["blank_brand"] = int((d["Brand"] == "-").sum())
    stats["fw_brand_rows"] = int(d["Brand"].fillna("").str.match(r"(?i)^(fw[_\- ]|franchise world)").sum())
    return inb.reset_index(drop=True), stats


def load_meta(meta_dir, prefix):
    fs = [x for x in glob.glob(os.path.join(meta_dir, f"{prefix}*Campaigns*.csv"))]
    assert len(fs) == 1, fs
    d = pd.read_csv(fs[0])
    d["Month"] = pd.to_datetime(d["Reporting starts"]).dt.strftime("%b")
    if "Landing page views" not in d.columns: d["Landing page views"] = float("nan")  # not supplied -> N/A
    daily = (pd.to_datetime(d["Reporting ends"]) - pd.to_datetime(d["Reporting starts"])).dt.days.max() == 0
    raw_total = d["Amount spent (INR)"].sum()
    ind = d["Result indicator"].fillna("")
    d["Meta Leads"] = d["Results"].where(ind == "actions:leadgen.other", 0).fillna(0)
    d["Results"] = d["Results"].fillna(0)
    g = d.groupby(["Month", "Campaign name"], as_index=False).agg(
        Delivery=("Campaign delivery", "last"), Spend=("Amount spent (INR)", "sum"), Impr=("Impressions", "sum"),
        Reach=("Reach", "sum"), LClicks=("Link clicks", "sum"), Clicks=("Clicks (all)", "sum"), LPV=("Landing page views", lambda s_: s_.sum(min_count=1)),
        MLeads=("Meta Leads", "sum"), Results=("Results", "sum"), Rows=("Amount spent (INR)", "size"))
    if daily:  # unique reach is not additive across days
        g["Reach"] = None
    inds = sorted(set(ind) - {""})
    return g, os.path.basename(fs[0]), raw_total, daily, inds


# ---------------------------------------------------------------- formulas
class Ctx:
    def __init__(self, nm, nc):
        self.nm, self.nc = nm, nc  # last data row of Data_Meta / Data_CRM


def mrng(ctx, c): return f"Data_Meta!${c}$2:${c}${ctx.nm}"
def crng(ctx, c): return f"Data_CRM!${c}$2:${c}${ctx.nc}"
# Data_Meta: A Month B Campaign C Delivery D Spend E Impr F Reach G LinkClicks H Clicks I LPV J MetaLeads K Results
MCOL = {"spend": "D", "impr": "E", "reach": "F", "lclicks": "G", "clicks": "H", "lpv": "I", "mleads": "J"}
# Data_CRM: A Lead id B Created C Modified D Month E CRM Brand F Source G Status H CRM campaign I Report campaign J FB
#           K Qual L Meet M Contacted N NotContacted O Blank P TAT Q ValidTAT
CCOL = {"crm": None, "qual": "K", "meet": "L", "cont": "M", "ncont": "N", "blank": "O"}


def build_formula(ctx, key, bi, row, spec):
    """spec: dict(meta=None|[(col,crit)], crm=[(col,crit)] , kind='data'|'total', first, last)"""
    c = lambda k, b=bi: f"{colof(b, k)}{row}"
    month = MONTHS[bi] if bi < 4 else None
    ratio = lambda num, den, mult="": f'=IFERROR(IF({den}>0,{num}/{den}{mult},"N/A"),"N/A")'
    if key in ("spend", "impr", "clicks", "lclicks", "lpv", "mleads", "reach"):
        if spec["meta"] is None or key == "reach" and (spec["kind"] == "total" or bi == 4 or spec.get("noreach")):
            return "N/A"
        if bi == 4:
            rng_ = ",".join(f"{colof(b, key)}{row}" for b in range(4))
            return f'=IF(COUNT({rng_})=0,"N/A",SUM({rng_}))' if key == "lpv" else "=SUM(" + rng_ + ")"
        if spec["kind"] == "total":
            rng_ = f"{colof(bi, key)}{spec['first']}:{colof(bi, key)}{spec['last']}"
            return f'=IF(COUNT({rng_})=0,"N/A",SUM({rng_}))' if key == "lpv" else f"=SUM({rng_})"
        crit = [(mrng(ctx, "A"), f'"{month}"')] + [(mrng(ctx, x), y) for x, y in spec["meta"]]
        cs = ",".join(f"{a},{b}" for a, b in crit)
        s = f"SUMIFS({mrng(ctx, MCOL[key])},{cs})"
        if key in ("reach", "lpv"):
            return f'=IF(COUNTIFS({cs},{mrng(ctx, MCOL[key])},"<>")=0,"N/A",{s})'
        return "=" + s
    if key == "freq":
        return f'=IF(ISNUMBER({c("reach")}),IF({c("reach")}>0,{c("impr")}/{c("reach")},"N/A"),"N/A")'
    if key == "ctr": return ratio(c("clicks"), c("impr"))
    if key == "lctr": return ratio(c("lclicks"), c("impr"))
    if key == "cpc": return ratio(c("spend"), c("clicks"))
    if key == "lcpc": return ratio(c("spend"), c("lclicks"))
    if key == "cpm": return ratio(c("spend"), c("impr"), "*1000")
    if key == "cplm": return ratio(c("spend"), c("mleads"))
    if key in ("crm", "qual", "meet", "cont", "ncont", "blank", "elig"):
        if bi == 4: return "=SUM(" + ",".join(f"{colof(b, key)}{row}" for b in range(4)) + ")"
        if spec["kind"] == "total" and key != "elig":
            return f"=SUM({colof(bi, key)}{spec['first']}:{colof(bi, key)}{spec['last']})"
        if spec["kind"] == "total":
            return f"=SUM({colof(bi, key)}{spec['first']}:{colof(bi, key)}{spec['last']})"
        crit = [(crng(ctx, "D"), f'"{month}"')] + [(crng(ctx, x), y) for x, y in spec["crm"]]
        if key == "elig": crit.append((crng(ctx, "Q"), "1"))
        elif CCOL[key]: crit.append((crng(ctx, CCOL[key]), "1"))
        return "=COUNTIFS(" + ",".join(f"{a},{b}" for a, b in crit) + ")"
    if key == "qualp": return ratio(c("qual"), c("crm"))
    if key == "meetp": return ratio(c("meet"), c("crm"))
    if key == "contp": return ratio(c("cont"), c("crm"))
    if key == "ncontp": return ratio(c("ncont"), c("crm"))
    if key == "cplc": return ratio(c("spend"), c("crm"))
    if key == "cpql": return ratio(c("spend"), c("qual"))
    if key == "cpmt": return ratio(c("spend"), c("meet"))
    if key in ("atat", "mtat"):
        crit = ([] if month is None else [(crng(ctx, "D"), f'"{month}"')]) + [(crng(ctx, x), y) for x, y in spec["crm"]]
        crit.append((crng(ctx, "Q"), "1"))
        if key == "atat":
            cs = ",".join(f"{a},{b}" for a, b in crit)
            return f'=IFERROR(IF({c("elig")}>0,SUMIFS({crng(ctx, "P")},{cs})/{c("elig")},"N/A"),"N/A")'
        cond = "*".join(f"({a}={b})" for a, b in crit if b != '"<>"')
        return ("ARRAY", f'=IFERROR(MEDIAN(IF({cond},{crng(ctx, "P")})),"N/A")')
    raise KeyError(key)


def write_grid(ws, ctx, rows, start_row):
    """rows: list of dict(kind=section|data|total|blank, label, camp, deliv, spec, grey)"""
    r = start_row
    ncol = FIX + len(BLOCKS) * NM
    for rw in rows:
        k = rw["kind"]
        if k == "blank":
            r += 1; continue
        if k == "section":
            ws.cell(r, 1, rw["label"])
            for cidx in range(1, ncol + 1):
                ws.cell(r, cidx).fill = fill(BLUE); ws.cell(r, cidx).font = f(True, "FFFFFF", 10)
            r += 1; continue
        ws.cell(r, 1, rw["brand"]); ws.cell(r, 2, rw["camp"]); ws.cell(r, 3, rw.get("deliv", ""))
        rw["row"] = r
        spec = rw["spec"]
        for bi in range(len(BLOCKS)):
            for key, hdr, fmt, grp in METRICS:
                cell = ws[f"{colof(bi, key)}{r}"]
                v = build_formula(ctx, key, bi, r, spec)
                if isinstance(v, tuple):
                    cell.value = ArrayFormula(cell.coordinate, v[1])
                else:
                    cell.value = v
                cell.number_format = fmt
                cell.alignment = Alignment(horizontal="right")
                cell.font = f(k == "total", "FFFFFF" if k == "total" else (GREY if rw.get("grey") else "000000"))
        for cidx in range(1, 4):
            ws.cell(r, cidx).font = f(True if k == "total" else cidx == 1, "FFFFFF" if k == "total" else (GREY if rw.get("grey") else "000000"))
        if k == "total":
            for cidx in range(1, ncol + 1): ws.cell(r, cidx).fill = fill(NAVY)
        r += 1
    return r


def header(ws, title, sub, nrows_note=None):
    ncol = FIX + len(BLOCKS) * NM
    ws["A1"] = title; ws["A2"] = sub
    for rr, (sz, b) in ((1, (16, True)), (2, (10, False))):
        for cidx in range(1, ncol + 1):
            ws.cell(rr, cidx).fill = fill(NAVY); ws.cell(rr, cidx).font = f(b, "FFFFFF", sz)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top"); ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=24)
    ws.row_dimensions[2].height = 54
    ws["A4"] = "HIERARCHY"
    for cidx in range(1, FIX + 1):
        ws.cell(4, cidx).fill = fill(NAVY); ws.cell(4, cidx).font = f(True, "FFFFFF", 10)
        h = ["Brand / class", "Campaign", "Delivery (latest)"][cidx - 1]
        ws.cell(5, cidx, h); ws.cell(5, cidx).fill = fill(NAVY); ws.cell(5, cidx).font = f(True, "FFFFFF")
        ws.cell(5, cidx).alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    for bi, b in enumerate(BLOCKS):
        lab = (MFULL[b] if b in MFULL else "JULY – OCTOBER 2026 TOTAL (Oct partial)")
        ws[f"{colof(bi, KEYS[0])}4"] = lab
        for mi, (key, hdr, fmt, grp) in enumerate(METRICS):
            cl = colof(bi, key)
            ws[f"{cl}4"].fill = fill(NAVY if bi % 2 == 0 else "264478"); ws[f"{cl}4"].font = f(True, "FFFFFF", 10)
            ws[f"{cl}5"] = hdr
            ws[f"{cl}5"].fill = fill(GROUP_FILL[grp]); ws[f"{cl}5"].font = f(True, "FFFFFF")
            ws[f"{cl}5"].alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
            ws.column_dimensions[cl].width = 14
    ws.row_dimensions[5].height = 62
    ws.column_dimensions["A"].width = 30; ws.column_dimensions["B"].width = 52; ws.column_dimensions["C"].width = 14
    ws.freeze_panes = "D6"
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------- main
def main(brand, lead_dir, meta_dir, out_dir):
    prefix, crm_brands = BRANDS[brand]
    crm, cst = load_crm(lead_dir, crm_brands)
    meta, mfile, raw_total, daily, inds = load_meta(meta_dir, prefix)
    mcamps = sorted(set(meta["Campaign name"]))
    NOCAP, NOTIN, OTHER = ("Facebook leads – campaign name not captured (blank / '_')",
                           "Facebook leads – campaign not in this brand's Meta export", "Other lead sources (non-Facebook)")
    fb = crm["Lead Source"].eq("Facebook")
    cn = crm["Facebook Campaign Name"].fillna("_")
    key = pd.Series(OTHER, index=crm.index)
    key[fb & cn.isin(mcamps)] = cn[fb & cn.isin(mcamps)]
    key[fb & cn.isin(["_", ""])] = NOCAP
    key[fb & ~cn.isin(mcamps) & ~cn.isin(["_", ""])] = NOTIN
    crm["Key"] = key; crm["FB"] = fb.astype(int)
    crm = crm.sort_values("Created").reset_index(drop=True)
    nm, nc = len(meta) + 1, len(crm) + 1
    ctx = Ctx(nm, nc)

    wb = Workbook()
    wsF = wb.active; wsF.title = "All Reports (One Tab)"
    wsM = wb.create_sheet("Month-on-Month")
    wsB = wb.create_sheet("Brand-Wise"); wsC = wb.create_sheet("Campaign-Wise")
    wsK = wb.create_sheet("KPI Definitions"); wsQ = wb.create_sheet("Data Quality Log"); wsV = wb.create_sheet("Validation")
    wsDM = wb.create_sheet("Data_Meta"); wsDC = wb.create_sheet("Data_CRM")

    # ---- Data_Meta
    hdr = ["Month", "Campaign name", "Delivery", "Amount spent (INR)", "Impressions", "Reach (unique; blank = not additive)", "Link clicks",
           "Clicks (all)", "Landing page views", "Meta Platform Leads (actions:leadgen.other)", "Results (all indicators)"]
    wsDM.append(hdr)
    for _, x in meta.iterrows():
        wsDM.append([x["Month"], x["Campaign name"], x["Delivery"], float(x["Spend"]), float(x["Impr"]), None if pd.isna(x["Reach"]) else float(x["Reach"]),
                     float(x["LClicks"]), float(x["Clicks"]), None if pd.isna(x["LPV"]) else float(x["LPV"]), float(x["MLeads"]), float(x["Results"])])
    # ---- Data_CRM
    wsDC.append(["Lead id", "Created On", "Modified On", "Month", "CRM Brand", "Lead Source", "Status", "CRM campaign (raw)", "Report campaign",
                 "Facebook-sourced (1/0)", "Qualified (1/0)", "Meeting (1/0)", "Contacted (1/0) — Status ≠ New Lead", "Not Contacted (1/0)",
                 "Blank status (1/0)", "TAT = Modified − Created (hours)", "Valid TAT (1/0)"])
    qs = ",".join(f'G{{r}}="{s}"' for s in QUAL); ms = ",".join(f'G{{r}}="{s}"' for s in MEET)
    cols = ["Lead id", "Created", "Modified", "Month", "Brand", "Lead Source", "Status", "Facebook Campaign Name", "Key", "FB"]
    for i, x in enumerate(crm[cols].itertuples(index=False), start=2):
        wsDC.append([x[0], x[1].to_pydatetime() if pd.notna(x[1]) else None, x[2].to_pydatetime() if pd.notna(x[2]) else None,
                     x[3], x[4], x[5], x[6] if isinstance(x[6], str) else "", x[7] if isinstance(x[7], str) else "", x[8], x[9],
                     f"=IF(OR({qs.format(r=i)}),1,0)", f"=IF(OR({ms.format(r=i)}),1,0)",
                     f'=IF(TRIM(G{i})="",0,IF(G{i}="New Lead",0,1))', f'=IF(G{i}="New Lead",1,0)', f'=IF(TRIM(G{i})="",1,0)',
                     f'=IF(AND(ISNUMBER(B{i}),ISNUMBER(C{i})),(C{i}-B{i})*24,"")', f"=IF(ISNUMBER(P{i}),IF(P{i}>=0,1,0),0)"])
        wsDC.cell(i, 2).number_format = wsDC.cell(i, 3).number_format = "yyyy-mm-dd hh:mm:ss"
    for ws_ in (wsDM, wsDC):
        for c in ws_[1]:
            c.font = f(True, "FFFFFF"); c.fill = fill(NAVY); c.alignment = Alignment(wrap_text=True)
        ws_.freeze_panes = "A2"

    # ---- campaign rows (ordered by total spend, zero-activity last)
    tot = meta.groupby("Campaign name")["Spend"].sum()
    crmc = crm[crm["FB"] == 1].groupby("Key").size()
    first = {c: g.sort_values("Month", key=lambda s: s.map({m: i for i, m in enumerate(MONTHS)}))["Delivery"].iloc[-1] for c, g in meta.groupby("Campaign name")}
    order = sorted(mcamps, key=lambda c: (-int(bool(tot[c] > 0 or crmc.get(c, 0) > 0)), -tot[c], -crmc.get(c, 0), c))
    crow = []
    crow.append({"kind": "section", "label": f"CAMPAIGN-WISE — {len(mcamps)} campaigns in the Meta export (incl. zero-activity, grey) + Facebook leads that cannot be tied to a campaign"})
    for cname in order:
        grey = tot[cname] == 0 and crmc.get(cname, 0) == 0 and meta[meta["Campaign name"] == cname]["MLeads"].sum() == 0
        crow.append({"kind": "data", "brand": brand, "camp": cname, "deliv": first[cname], "grey": grey,
                     "spec": {"kind": "data", "meta": [("B", "$B{r}")], "crm": [("I", "$B{r}")], "noreach": False}})
    for extra in (NOCAP, NOTIN):
        crow.append({"kind": "data", "brand": brand + " (unattributed)", "camp": extra, "deliv": "",
                     "spec": {"kind": "data", "meta": None, "crm": [("I", "$B{r}")]}})
    # fix {r}
    r0 = 6
    r = r0
    for rw in crow:
        if rw["kind"] == "section": r += 1; continue
        for key_ in ("meta", "crm"):
            if rw["spec"][key_]: rw["spec"][key_] = [(a, b.replace("{r}", str(r))) for a, b in rw["spec"][key_]]
        r += 1
    firstrow, lastrow = r0 + 1, r - 1
    crow.append({"kind": "total", "brand": f"TOTAL — ALL CAMPAIGNS ({brand})", "camp": "Facebook-sourced CRM leads only; Reach/Frequency not additive → N/A",
                 "spec": {"kind": "total", "meta": [], "crm": [("J", "1")], "first": firstrow, "last": lastrow}})
    header(wsC, f"CAMPAIGN-WISE PERFORMANCE — {brand.upper()}  ·  MONTH-TO-MONTH (JUL–OCT 2026)",
           "Brand → Campaign. Meta spend & delivery metrics from the monthly Meta campaign export; CRM metrics = Facebook-sourced CRM leads by 'Created On' month (Lead Module). "
           "CRM leads are tied to a Meta campaign via the 'Facebook Campaign Name' on the lead — leads with no campaign name are shown on their own line. "
           "Cost metrics (CPL, CPQL, cost per meeting) = Meta spend ÷ Facebook-sourced CRM leads. October is partial (data to 30 Oct). N/A = cannot be calculated / not supplied.")
    write_grid(wsC, ctx, crow, r0)
    crow_total = [x for x in crow if x["kind"] == "total"][0]["row"]

    # ---- brand rows
    brow = [{"kind": "section", "label": "A · BRAND TOTAL — Meta (all campaigns) + Facebook-sourced CRM leads (cost metrics are valid on this line)"}]
    brow.append({"kind": "data", "brand": brand, "camp": "Brand total (Meta + Facebook-sourced CRM)", "deliv": "",
                 "spec": {"kind": "data", "meta": [], "crm": [("J", "1")], "noreach": True}})
    brow.append({"kind": "blank"})
    brow.append({"kind": "section", "label": "B · CRM BRAND SPLIT — Facebook-sourced leads by CRM 'Brand' value (Meta spend cannot be split by CRM brand → cost metrics N/A)"})
    for cb in crm_brands:
        brow.append({"kind": "data", "brand": brand, "camp": cb, "deliv": "", "grey": int((crm["Brand"] == cb).sum()) == 0,
                     "spec": {"kind": "data", "meta": None, "crm": [("E", "$B{r}"), ("J", "1")]}})
    brow.append({"kind": "blank"})
    brow.append({"kind": "section", "label": "C · ALL LEAD SOURCES (CRM only — includes WhatsApp / Website / Excel / Zoho etc.; Meta cost metrics N/A)"})
    brow.append({"kind": "data", "brand": brand, "camp": "All CRM leads — all sources", "deliv": "", "spec": {"kind": "data", "meta": None, "crm": [(crng_a, "\"<>\"") for crng_a in ["A"]]}})
    brow.append({"kind": "data", "brand": brand, "camp": "   of which Facebook-sourced", "deliv": "", "spec": {"kind": "data", "meta": None, "crm": [("J", "1")]}})
    brow.append({"kind": "data", "brand": brand, "camp": "   of which other sources (non-Facebook)", "deliv": "", "spec": {"kind": "data", "meta": None, "crm": [("J", "0")]}})
    r = 6
    for rw in brow:
        if rw["kind"] in ("section", "blank"): r += 1; continue
        rw["spec"]["crm"] = [(a if a.startswith("Data_") else a, b.replace("{r}", str(r))) for a, b in rw["spec"]["crm"]]
        r += 1
    # crm criterion column 'A' for 'all' row must resolve to a column letter -> handled in build (col letter); fine
    header(wsB, f"BRAND-WISE PERFORMANCE — {brand.upper()}  ·  MONTH-TO-MONTH (JUL–OCT 2026)",
           "Sections are alternative views of the same leads and are never added together. A = brand total with valid cost metrics; B = split by CRM Brand value; C = all lead sources. "
           "Reach / Frequency are not additive across campaigns → N/A at brand level. October is partial (data to 30 Oct).")
    write_grid(wsB, ctx, brow, 6)
    brand_row = brow[1]["row"]

    # ---- front tab: mirror of Brand-Wise and Campaign-Wise
    header(wsF, f"ALL REPORTS IN ONE TAB — {brand.upper()}  ·  MONTH-TO-MONTH JUL · AUG · SEP · OCT 2026  ·  Brand → Campaign",
           "One column grid: each row is one entity; Meta + CRM KPIs per month with a Jul–Oct total block. Every cell is a live link to the detailed tab named in the section band. "
           "Brand and Campaign views are alternative views of the same activity — never add them together. Grey row = zero-activity campaign in source. October is partial (to 30 Oct). N/A = cannot be calculated / not supplied.")
    ncol = FIX + len(BLOCKS) * NM
    r = 6
    def mirror(src_ws, src_first, src_last, label):
        nonlocal r
        wsF.cell(r, 1, label)
        for cidx in range(1, ncol + 1):
            wsF.cell(r, cidx).fill = fill(BLUE); wsF.cell(r, cidx).font = f(True, "FFFFFF", 10)
        r += 1
        for sr in range(src_first, src_last + 1):
            if src_ws.cell(sr, 1).value is None and src_ws.cell(sr, 4).value is None:
                r += 1; continue
            sec = src_ws.cell(sr, 4).value is None
            for cidx in range(1, ncol + 1):
                srcc = f"'{src_ws.title}'!{L(cidx)}{sr}"
                if sec:
                    if cidx == 1: wsF.cell(r, 1, f"={srcc}")
                    wsF.cell(r, cidx).fill = fill("D9E2F3"); wsF.cell(r, cidx).font = f(True, NAVY, 9)
                    continue
                cell = wsF.cell(r, cidx, f'=IF({srcc}="","",{srcc})')
                s = src_ws.cell(sr, cidx)
                cell.number_format = s.number_format; cell.font = s.font.copy(); cell.fill = s.fill.copy(); cell.alignment = s.alignment.copy()
            r += 1
    wsF.cell(r, 1, f"0 · {brand.upper()} — BRAND TOTAL (source tab: Brand-Wise, section A)")
    for cidx in range(1, ncol + 1):
        wsF.cell(r, cidx).fill = fill(BLUE); wsF.cell(r, cidx).font = f(True, "FFFFFF", 10)
    r += 1
    for cidx in range(1, ncol + 1):
        srcc = f"'Brand-Wise'!{L(cidx)}{brand_row}"
        cell = wsF.cell(r, cidx, f'=IF({srcc}="","",{srcc})'); s = wsB.cell(brand_row, cidx)
        cell.number_format = s.number_format; cell.font = f(True, "FFFFFF"); cell.fill = fill(NAVY); cell.alignment = s.alignment.copy()
    r += 2
    mirror(wsB, 6, wsB.max_row, "1 · BRAND-WISE  (source tab: Brand-Wise)")
    r += 1
    mirror(wsC, 6, wsC.max_row, f"2 · CAMPAIGN-WISE  (source tab: Campaign-Wise · {len(mcamps)} campaigns incl. zero-activity)")
    r += 1
    notes_row = r
    wsF.cell(r, 1, "3 · HOW TO READ THIS TAB — DEFINITIONS, RECONCILIATION AND LIMITATIONS (full detail: Data Quality Log, KPI Definitions, Validation tabs)")
    for cidx in range(1, 21): wsF.cell(r, cidx).fill = fill(BLUE); wsF.cell(r, cidx).font = f(True, "FFFFFF", 10)
    r += 1
    paid = int((crm["FB"] == 1).sum())
    notes = [
        "PERIODS: Jul, Aug, Sep, Oct 2026 month blocks + Jul–Oct total. CRM: lead 'Created On' month (Lead Module). Meta: monthly campaign export"
        + (" (daily rows aggregated to months)" if daily else "") + ". October is a PARTIAL month (Meta to 30 Oct; CRM to " + f"{cst['maxdate']:%d %b %H:%M})" + " — do not compare it with full months without allowing for this. FTD is not reported.",
        "DEFINITIONS: Qualified = Qualified, Follow-Up, Details Shared, Meeting Scheduled, Meeting Conducted. Meetings Scheduled = Follow-Up + Meeting Scheduled + Meeting Conducted (distinct leads). Contacted = Status ≠ New Lead; Not Contacted = New Lead. "
        "TAT = Modified On − Created On (lead-modification TAT, NOT first-response time). 'Meeting Conducted but NOT QUALIFIED' counts as Contacted only.",
        f"SCOPE: CRM Brand values included for {brand}: {', '.join(crm_brands)}. Leads on campaigns named FW_* ({cst['fw_excluded']}) and all FW brands are excluded (FW is a separate brand). Meta-vs-CRM lead-by-lead matching is NOT reported (Meta Leads Center export not supplied).",
        f"COST METRICS: CPL / CPQL / cost per meeting = Meta spend ÷ Facebook-sourced CRM leads ({paid:,} of {len(crm):,} brand leads). Other sources (WhatsApp, Website, Excel…) are shown in Brand-Wise section C without cost. Facebook leads with no campaign name cannot be tied to a campaign: shown on their own lines.",
        "REACH / FREQUENCY: Meta unique values per campaign per month; not additive, so brand / total / Jul–Oct blocks show N/A" + ("; this account's export is daily, so campaign reach is N/A too." if daily else "."),
        "LEVELS: Campaign totals and Brand totals are alternative views of the same spend / leads — never added together. Ad-set and ad level are intentionally not reported.",
    ]
    for n in notes:
        wsF.cell(r, 1, n); wsF.merge_cells(start_row=r, start_column=1, end_row=r, end_column=20)
        wsF.cell(r, 1).alignment = Alignment(wrap_text=True, vertical="top"); wsF.cell(r, 1).fill = fill("F2F2F2"); wsF.cell(r, 1).font = f(False, "404040")
        wsF.row_dimensions[r].height = 42; r += 1

    # ---- Month-on-Month
    wsM["A1"] = f"MONTH-ON-MONTH — {brand.upper()} (brand total, Meta + Facebook-sourced CRM)"
    wsM["A2"] = "Live links to Brand-Wise section A. MoM % = change vs previous month; October is partial so Oct vs Sep is not like-for-like. N/A where a value cannot be calculated."
    for rr in (1, 2):
        for cidx in range(1, 12): wsM.cell(rr, cidx).fill = fill(NAVY); wsM.cell(rr, cidx).font = f(rr == 1, "FFFFFF", 14 if rr == 1 else 10)
    heads = ["KPI", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026 (partial)", "Jul–Oct total", "Aug vs Jul %", "Sep vs Aug %", "Oct vs Sep % (partial)"]
    for i, h in enumerate(heads, 1):
        c = wsM.cell(4, i, h); c.fill = fill(NAVY); c.font = f(True, "FFFFFF"); c.alignment = Alignment(horizontal="center", wrap_text=True)
    for j, (k_, h_, fm, grp) in enumerate(METRICS):
        rr = 5 + j
        wsM.cell(rr, 1, h_).font = f(True); wsM.cell(rr, 1).fill = fill("E8EEF7")
        for bi in range(5):
            c = wsM.cell(rr, 2 + bi, f"='Brand-Wise'!{colof(bi, k_)}{brand_row}"); c.number_format = fm; c.font = f(); c.alignment = Alignment(horizontal="right")
        for q, (a, b) in enumerate([("B", "C"), ("C", "D"), ("D", "E")]):
            c = wsM.cell(rr, 7 + q, f'=IFERROR(IF({a}{rr}=0,"N/A",({b}{rr}-{a}{rr})/ABS({a}{rr})),"N/A")'); c.number_format = "0.0%"; c.font = f(); c.alignment = Alignment(horizontal="right")
    wsM.column_dimensions["A"].width = 42
    for cl in "BCDEFGHI": wsM.column_dimensions[cl].width = 17
    wsM.freeze_panes = "B5"; wsM.sheet_view.showGridLines = False

    # ---- KPI definitions
    kd = [("KPI", "Formula / rule", "Source"),
          ("Amount Spent / Impressions / Clicks / Link clicks / LPV", "Source values summed by campaign and month", "Meta campaign export"),
          ("Reach / Frequency", "Reach = Meta unique value per campaign per month; Frequency = Impressions ÷ Reach; N/A when not additive / not supplied", "Meta"),
          ("CTR (all) / Link CTR", "Clicks (or Link clicks) ÷ Impressions", "Meta"), ("CPC / Link CPC", "Spend ÷ Clicks (or Link clicks)", "Meta"),
          ("CPM", "Spend ÷ Impressions × 1,000", "Meta"), ("Meta Platform Leads", "Results where Result indicator = actions:leadgen.other", "Meta"),
          ("CPL (Meta)", "Spend ÷ Meta Platform Leads", "Meta"),
          ("CRM Leads", "Distinct Lead id created in the month, Facebook-sourced, on the campaign named on the lead", "Lead Module"),
          ("Qualified Leads", "Status in {" + ", ".join(QUAL) + "}", "Lead Module"), ("Qualification %", "Qualified ÷ CRM Leads", ""),
          ("Meetings Scheduled", "Status in {" + ", ".join(MEET) + "} (distinct leads)", "Lead Module"), ("Meeting %", "Meetings ÷ CRM Leads", ""),
          ("CPL (CRM)", "Spend ÷ CRM Leads", ""), ("CPQL", "Spend ÷ Qualified Leads", ""), ("Cost Per Meeting", "Spend ÷ Meetings Scheduled", ""),
          ("Contacted / Not Contacted", "Contacted = Status ≠ New Lead; Not Contacted = New Lead; Blank / Invalid = empty status", "Lead Module"),
          ("Lead Modification TAT", "(Modified On − Created On) in hours; Eligible = both timestamps valid and TAT ≥ 0; NOT first-response time", "Lead Module"),
          ("N/A rule", "Shown when the denominator is zero or the input is not supplied — never an artificial zero", ""),
          ("Not reported", "Meta-vs-CRM lead-by-lead match (no Meta Leads Center export), FTD, ad-set and ad level", "")]
    for row_ in kd: wsK.append(list(row_))
    for c in wsK[1]: c.font = f(True, "FFFFFF"); c.fill = fill(NAVY)
    wsK.column_dimensions["A"].width = 48; wsK.column_dimensions["B"].width = 100; wsK.column_dimensions["C"].width = 22

    # ---- Data quality log
    mo_counts = crm.groupby("Month").size().reindex(MONTHS).fillna(0).astype(int)
    nonfb = int((crm["FB"] == 0).sum()); nocap = int((crm["Key"] == NOCAP).sum()); notin = int((crm["Key"] == NOTIN).sum())
    mnc = int(crm["Status"].eq("Meeting Conducted but NOT QUALIFIED").sum())
    dq = [("#", "Area", "Check", "Result", "Detail"),
          (1, "Source files", "Meta export covers Jul–Oct", "PASS", f"{mfile}; months present: {', '.join(sorted(set(meta['Month']), key=MONTHS.index))}" + ("; export is DAILY — aggregated to months" if daily else "")),
          (2, "Source files", "Lead Module files cover each month", "WARN", f"Leads in scope by month: " + ", ".join(f"{m} {mo_counts[m]:,}" for m in MONTHS) + f". October extract ends {cst['maxdate']:%d %b %Y %H:%M} → partial month."),
          (3, "Scope", "CRM Brand values included", "INFO", ", ".join(f"{b} ({int((crm['Brand']==b).sum()):,})" for b in crm_brands)),
          (4, "Scope", "FW excluded", "INFO", f"{cst['fw_excluded']} in-scope-brand leads on FW_* campaigns excluded; FW brands ({cst['fw_brand_rows']:,} rows across files) are not part of this report."),
          (5, "Scope", "Leads with Brand '-' (blank)", "WARN", f"{cst['blank_brand']:,} leads across the four files have no brand and are not attributable → excluded."),
          (6, "Spend", "Data_Meta total = raw Meta export total", "PASS" if abs(raw_total - meta['Spend'].sum()) < 0.01 else "FAIL", f"Raw export ₹{raw_total:,.2f}; Data_Meta ₹{meta['Spend'].sum():,.2f}."),
          (7, "Spend", "Differs from the earlier single-period (1 Jul–30 Oct) export", "INFO", "The monthly export totals differ slightly (Meta restatement) from the earlier 4-month file; the monthly export is used."),
          (8, "Reach", "Reach / Frequency", "WARN", "Unique reach is not additive: N/A at brand / total / Jul–Oct level" + ("; daily export → campaign reach N/A as well." if daily else ".")),
          (9, "Attribution", "Facebook leads with no campaign name", "WARN", f"{nocap:,} Facebook-sourced leads ({nocap/max(paid,1):.1%}) have a blank campaign name and cannot be tied to a campaign; {notin:,} name a campaign that is not in this brand's Meta export."),
          (10, "Attribution", "Non-Facebook lead sources", "INFO", f"{nonfb:,} leads (WhatsApp / Website / Excel / etc.) are in Brand-Wise section C only; no cost metrics."),
          (11, "Duplicates", "Duplicate Lead ids", "PASS" if cst['dup_ids'] == 0 else "WARN", f"{cst['dup_ids']} duplicate Lead id(s) in scope."),
          (12, "CRM status", "Status 'Meeting Conducted but NOT QUALIFIED'", "INFO", f"{mnc} leads: counted as Contacted, not as Qualified / Meeting."),
          (13, "Meta results", "Result indicators in export", "INFO", "; ".join(inds) + ". Meta Platform Leads uses actions:leadgen.other only."),
          (14, "Not reported", "Meta-vs-CRM lead match", "INFO", "Meta Leads Center export not supplied → match / unmatched / variance columns removed."),
          (15, "Not reported", "FTD, ad-set, ad level", "INFO", "Out of scope by instruction."),
          (16, "Meta", "Landing page views not supplied", "INFO",
           "Blank in source (shown N/A, not 0) for: " + (", ".join(m for m in MONTHS if m in set(meta['Month']) and meta[meta['Month'] == m]['LPV'].isna().all()) or "none"))]
    for row_ in dq: wsQ.append(list(row_))
    for c in wsQ[1]: c.font = f(True, "FFFFFF"); c.fill = fill(NAVY)
    for i, w in enumerate([5, 16, 46, 9, 130], 1): wsQ.column_dimensions[L(i)].width = w

    # ---- Validation (live)
    cT = crow_total; tb = brand_row
    tc = lambda k, b=4: f"'Campaign-Wise'!{colof(b, k)}{cT}"
    bc = lambda k, b=4: f"'Brand-Wise'!{colof(b, k)}{tb}"
    checks = [("A. SPEND", None, None),
              ("Campaign-Wise total spend vs Data_Meta total", f"={tc('spend')}", f"=SUM(Data_Meta!$D$2:$D${nm})"),
              ("Data_Meta total vs raw Meta export total (hard-coded from source file)", f"=SUM(Data_Meta!$D$2:$D${nm})", f"={round(raw_total, 2)}"),
              ("Brand-Wise total spend vs Campaign-Wise total spend", f"={bc('spend')}", f"={tc('spend')}"),
              ("Sum of 4 monthly blocks vs Jul–Oct block (campaign total)", "=" + "+".join(tc('spend', b) for b in range(4)), f"={tc('spend')}"),
              ("B. META VOLUMES", None, None),
              ("Impressions: Campaign-Wise vs Data_Meta", f"={tc('impr')}", f"=SUM(Data_Meta!$E$2:$E${nm})"),
              ("Link clicks: Campaign-Wise vs Data_Meta", f"={tc('lclicks')}", f"=SUM(Data_Meta!$G$2:$G${nm})"),
              ("Meta leads: Campaign-Wise vs Data_Meta", f"={tc('mleads')}", f"=SUM(Data_Meta!$J$2:$J${nm})"),
              ("C. CRM", None, None),
              ("CRM leads: Campaign-Wise total vs Facebook-sourced records in Data_CRM", f"={tc('crm')}", f"=COUNTIFS(Data_CRM!$J$2:$J${nc},1)"),
              ("CRM leads: Brand-Wise A vs Campaign-Wise total", f"={bc('crm')}", f"={tc('crm')}"),
              ("CRM leads: Brand-Wise all sources vs Data_CRM records", f"='Brand-Wise'!{colof(4, 'crm')}{brow[-3]['row']}", f"={len(crm)}"),
              ("CRM leads: Brand-Wise B (sum of CRM brands) vs A", "=" + "+".join(f"'Brand-Wise'!{colof(4, 'crm')}{x['row']}" for x in brow if x['kind'] == 'data' and x['camp'] in crm_brands), f"={bc('crm')}"),
              ("Duplicate Lead ids in Data_CRM (hard-coded check)", f"={cst['dup_ids']}", "=0"),
              ("Qualified: Campaign-Wise vs status count", f"={tc('qual')}", f"=SUMIFS(Data_CRM!$K$2:$K${nc},Data_CRM!$J$2:$J${nc},1)"),
              ("Meetings: Campaign-Wise vs status count", f"={tc('meet')}", f"=SUMIFS(Data_CRM!$L$2:$L${nc},Data_CRM!$J$2:$J${nc},1)"),
              ("Contacted + Not Contacted + Blank = CRM leads (brand total)", f"={bc('cont')}+{bc('ncont')}+{bc('blank')}", f"={bc('crm')}"),
              ("Months present in Data_CRM = Jul/Aug/Sep/Oct only", f"=COUNTIFS(Data_CRM!$D$2:$D${nc},\"Jul\")+COUNTIFS(Data_CRM!$D$2:$D${nc},\"Aug\")+COUNTIFS(Data_CRM!$D$2:$D${nc},\"Sep\")+COUNTIFS(Data_CRM!$D$2:$D${nc},\"Oct\")", f"={len(crm)}")]
    wsV["A1"] = f"VALIDATION & RECONCILIATION — {brand.upper()} — all checks are live formulas"
    wsV["A1"].font = f(True, "FFFFFF", 14); [setattr(wsV.cell(1, i), "fill", fill(NAVY)) for i in range(1, 6)]
    for i, h in enumerate(["Check", "Value A", "Value B", "Difference", "Status"], 1):
        c = wsV.cell(3, i, h); c.font = f(True, "FFFFFF"); c.fill = fill(NAVY)
    rr = 4
    for name, a, b in checks:
        wsV.cell(rr, 1, name)
        if a is None:
            wsV.cell(rr, 1).font = f(True, "FFFFFF", 10)
            for i in range(1, 6): wsV.cell(rr, i).fill = fill(BLUE)
        else:
            wsV.cell(rr, 2, a); wsV.cell(rr, 3, b); wsV.cell(rr, 4, f"=ROUND(B{rr}-C{rr},2)")
            wsV.cell(rr, 5, f'=IF(D{rr}=0,"✔ ties","✘ CHECK")')
        rr += 1
    wsV.column_dimensions["A"].width = 85
    for cl in "BCDE": wsV.column_dimensions[cl].width = 18
    wb.move_sheet("All Reports (One Tab)", 0)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{brand.replace(' & ', '_and_').replace(' ', '_')}_FinalReport_Jul-Oct2026.xlsx")
    wb.save(out)
    print(out, "| crm rows", len(crm), "| meta rows", len(meta), "| fb", paid, "nocap", nocap, "fw_ex", cst["fw_excluded"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
