"""Check each workbook's Master Pivot (plain-value body + injected PivotTable parts) against Pivot_Data."""
import sys, re, zipfile, warnings, openpyxl, pandas as pd
warnings.filterwarnings("ignore")
MONTHS = ["Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026 (partial)"]
tot = bad = 0
for f in sys.argv[1:]:
    wb = openpyxl.load_workbook(f, data_only=True)
    rows = list(wb["Pivot_Data"].iter_rows(values_only=True)); df = pd.DataFrame(rows[1:], columns=rows[0]).dropna(subset=["Month"])
    ws = wb["Master Pivot"]; b0 = bad
    metrics = [("Amount Spent (INR)", None), ("Impressions Delivered", None), ("Link Clicks (Meta)", None), ("Link Clicks (Meta)", "Impressions Delivered"),
               ("Meta Platform Leads", None), ("Amount Spent (INR)", "Meta Platform Leads"), ("CRM Leads Count", None), ("Qualified Leads Count", None),
               ("Qualified Leads Count", "CRM Leads Count"), ("Meetings Scheduled Count", None), ("Amount Spent (INR)", "CRM Leads Count"), ("Amount Spent (INR)", "Qualified Leads Count")]
    brand = df["Brand"].iloc[0]; last = None
    for r in range(17, ws.max_row + 1):
        lab = ws.cell(r, 1).value
        if lab is None: continue
        if str(lab).startswith("Notes"): break
        sub = df if lab in (brand, "Grand Total") else df[df["Campaign"] == lab]
        assert len(sub), (f, lab)
        last = r
        for mi, m in enumerate(MONTHS):
            s = sub[sub["Month"] == m]
            for k, (num, den) in enumerate(metrics):
                got = ws.cell(r, 2 + mi * 12 + k).value; n = s[num].sum()
                exp = n if den is None else (n / s[den].sum() if s[den].sum() > 0 else "–")
                tot += 1
                ok = (got == exp) if isinstance(exp, str) else (isinstance(got, (int, float)) and abs(got - exp) <= 1e-9 * max(1, abs(exp)))
                if not ok: bad += 1; print("DIFF", f.split("/")[-1][:20], lab[:30], m, k, got, exp) if bad - b0 < 4 else None
    # structure: merged cells / formulas inside the pivot range
    z = zipfile.ZipFile(f); wbx = z.read("xl/workbook.xml").decode()
    rid = re.search(r'<sheet [^>]*name="Master Pivot"[^>]*r:id="([^"]+)"', wbx).group(1)
    tgt = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="{rid}"', z.read("xl/_rels/workbook.xml.rels").decode())
    sheet = "xl/" + (tgt.group(1) or tgt.group(2)); sx = z.read(sheet).decode()
    ref = re.search(r'<location ref="([^"]+)"', z.read("xl/pivotTables/pivotTable1.xml").decode()).group(1)
    sys.path.insert(0, "/home/user/Debraj-first-project/pipeline"); import inject_pivot as ip
    ip.check_pivot_range_is_clean(sx, ref)
    assert "<pane " not in sx, "Master Pivot must not have frozen panes (blocks scrolling)"
    assert 'zoomScale="85"' in sx, "Master Pivot zoom should be 85"
    assert ref.endswith(str(last)), (ref, last)
    print(f"{f.split('/')[-1][:30]:30s} pivot ref {ref} | body rows to {last} | clean (no merges/formulas in pivot range)")
print(f"MASTER PIVOT CELL COMPARISONS: {tot:,} | MISMATCHES: {bad}")
