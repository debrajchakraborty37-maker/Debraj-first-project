import sys, os, openpyxl, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_config as rc
warnings.filterwarnings("ignore")
f, sel = sys.argv[1], sys.argv[2]
wb = openpyxl.load_workbook(f, data_only=True)
rows = list(wb["Pivot_Data"].iter_rows(values_only=True)); df = pd.DataFrame(rows[1:], columns=rows[0]).dropna(subset=["Month"])
d = wb["Master Dashboard"]; dd = wb["Dashboard_Data"]
bad = []; n = 0
def cmp(tag, got, exp):
    global n; n += 1
    if isinstance(exp, str) or isinstance(got, str) or got is None or exp is None:
        if got != exp: bad.append((tag, got, exp))
    elif abs(got - exp) > 1e-6 * max(1, abs(exp)): bad.append((tag, got, exp))
months = [rc.MLAB[m_] for m_ in rc.MONTHS]
def agg(sub):
    sp, ml, crm, q, mt, ct = (sub["Amount Spent (INR)"].sum(), sub["Meta Platform Leads"].sum(), sub["CRM Leads Count"].sum(), sub["Qualified Leads Count"].sum(),
                              sub["Meetings Scheduled Count"].sum(), sub["Contacted Leads Count"].sum())
    div = lambda a, b: a / b if b > 0 else "–"
    return dict(sp=sp, ml=ml, crm=crm, q=q, mt=mt, cpl=div(sp, crm) if sp > 0 else "–", cpq=div(sp, q) if sp > 0 else "–", cpm=div(sp, mt) if sp > 0 else "–",
                qr=div(q, crm), cr=div(ct, crm))
cmp("selection cell", d["C4"].value, sel)
cur = df if sel == "All months" else df[df["Month"] == sel]
e = agg(cur)
tiles = [("sp", 2, 8), ("ml", 4, 8), ("crm", 6, 8), ("q", 8, 8), ("mt", 10, 8), ("cpl", 2, 13), ("cpq", 4, 13), ("cpm", 6, 13), ("qr", 8, 13), ("cr", 10, 13)]
for k, c, r in tiles: cmp(f"tile {k}", d.cell(r, c).value, e[k])
# change-vs-previous subtext
idx = 0 if sel == "All months" else months.index(sel) + 1
if idx >= 2:
    p = agg(df[df["Month"] == months[idx - 2]])
    for k, c, r in tiles:
        a, b = e[k], p[k]
        want = "vs previous month: –" if (isinstance(a, str) or isinstance(b, str) or b == 0) else (("▲ " if a >= b else "▼ ") + f"{abs(a / b - 1):.1%}" + " vs previous month")
        cmp(f"sub {k}", d.cell(r + 1, c).value, want)
elif idx == 0:
    for k, c, r in tiles: cmp(f"sub {k}", d.cell(r + 1, c).value, rc.TOTAL_LABEL)
else:
    for k, c, r in tiles: cmp(f"sub {k}", d.cell(r + 1, c).value, "First month of the period")
# monthly table (rows 20..24) always all months
for i, m in enumerate(months):
    a = agg(df[df["Month"] == m]); row = 20 + i
    cmp(f"table {m} label", d.cell(row, 2).value, m)
    for col, k in zip(range(3, 12), ["sp", "ml", "crm", "q", "mt", "cpl", "cpq", "qr", "cr"]): cmp(f"table {m} {k}", d.cell(row, col).value, a[k])
a = agg(df)
for col, k in zip(range(3, 12), ["sp", "ml", "crm", "q", "mt", "cpl", "cpq", "qr", "cr"]): cmp(f"table total {k}", d.cell(20 + rc.N, col).value, a[k])
# top 10 (Meta-export campaigns only), selected view
ok = cur[cur["Lead attribution"] == "Campaign in Meta export"].groupby("Campaign", sort=False).agg(sp=("Amount Spent (INR)", "sum"), q=("Qualified Leads Count", "sum"))
order = list(dict.fromkeys(df[df["Lead attribution"] == "Campaign in Meta export"]["Campaign"]))
ok = ok.reindex(order).fillna(0)
ts = ok[ok.sp > 0].reset_index(); ts["o"] = range(len(ts)); ts = ts.sort_values(["sp", "o"], ascending=[False, True]).head(10)
tq = ok[ok.q > 0].reset_index(); tq["o"] = range(len(tq)); tq = tq.sort_values(["q", "o"], ascending=[False, True]).head(10)
for i in range(10):
    r = 8 + i
    es = (ts.iloc[i]["Campaign"], ts.iloc[i]["sp"]) if i < len(ts) else ("", "")
    eq = (tq.iloc[i]["Campaign"], tq.iloc[i]["q"]) if i < len(tq) else ("", "")
    cmp(f"top spend name {i}", dd.cell(r, 18).value or "", es[0]); cmp(f"top spend val {i}", dd.cell(r, 19).value if es[0] else "", es[1] if es[0] else "") if es[0] else None
    cmp(f"top qual name {i}", dd.cell(r, 20).value or "", eq[0]); cmp(f"top qual val {i}", dd.cell(r, 21).value, eq[1]) if eq[0] else None
# attribution split
for j, a_ in enumerate(["Campaign in Meta export", "Campaign not determinable", "Campaign outside Meta export"]):
    cmp(f"attr {a_}", dd.cell(22 + j, 9).value, float(cur[cur["Lead attribution"] == a_]["CRM Leads Count"].sum()))
print(f"{f.split('/')[-1][:24]:24s} sel={sel:20s} checks={n} mismatches={len(bad)}", bad[:3])
sys.exit(1 if bad else 0)
