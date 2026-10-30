"""Pivot_Data, Master Pivot (pre-rendered grid) and Master Dashboard sheets for one brand workbook.
The real PivotTable + slicers are injected afterwards by inject_pivot.py (openpyxl cannot author them)."""
import os
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.formatting.rule import CellIsRule

MONTHS = ["Jul", "Aug", "Sep", "Oct"]
MLAB = {"Jul": "Jul 2026", "Aug": "Aug 2026", "Sep": "Sep 2026", "Oct": "Oct 2026 (partial)"}
ATTR_OK, ATTR_NOCAP, ATTR_NOTIN = "Campaign in Meta export", "Campaign not determinable", "Campaign outside Meta export"
NAVY, BLUE, TEAL, GREY, LIGHT = "1F3864", "2E5090", "0E7C7B", "7F7F7F", "E8EEF7"
PD_HEAD = ["Month", "Brand", "Campaign", "Delivery", "Lead attribution", "Amount Spent (INR)", "Impressions Delivered", "Total Clicks (all)",
           "Link Clicks (Meta)", "Meta Platform Leads", "CRM Leads Count", "Qualified Leads Count", "Meetings Scheduled Count",
           "Contacted Leads Count", "Not Contacted Leads Count"]
PD_SRC = ["spend", "impr", "clicks", "lclicks", "mleads", "crm", "qual", "meet", "cont", "ncont"]  # keys feeding columns F..O


def fill(h): return PatternFill("solid", fgColor=h)
def font(b=False, c="000000", sz=10): return Font(name="Calibri", size=sz, bold=b, color=c)


def add_pivot_data(wb, brand, rows, colof, cw_title="Campaign-Wise"):
    """rows: list of dict(camp, deliv, row, attr). One Pivot_Data row per campaign line x month, linked by formula to Campaign-Wise."""
    ws = wb.create_sheet("Pivot_Data")
    ws.append(PD_HEAD)
    for c in ws[1]:
        c.font = font(True, "FFFFFF", 10); c.fill = fill(NAVY); c.alignment = Alignment(wrap_text=True, vertical="center")
    r = 2
    for rw in rows:
        for bi, m in enumerate(MONTHS):
            ws.cell(r, 1, MLAB[m]); ws.cell(r, 2, brand); ws.cell(r, 3, rw["camp"]); ws.cell(r, 4, rw["deliv"] or "n/a"); ws.cell(r, 5, rw["attr"])
            for j, k in enumerate(PD_SRC):
                src = f"'{cw_title}'!{colof(bi, k)}{rw['row']}"
                ws.cell(r, 6 + j, f"=IF(ISNUMBER({src}),{src},0)")
            r += 1
    ws.freeze_panes = "A2"
    for i, w in enumerate([18, 22, 60, 12, 28] + [15] * 10, 1): ws.column_dimensions[L(i)].width = w
    ws.sheet_properties.tabColor = GREY
    return {"n": r - 1, "last": r - 1}


def _rng(n, col): return f"Pivot_Data!${col}$2:${col}${n}"


def add_master_pivot(wb, brand, rows, n):
    ws = wb.create_sheet("Master Pivot")
    ws.sheet_properties.tabColor = TEAL
    ws.sheet_view.showGridLines = False
    ncol = 1 + 12 * 4
    ws["A1"] = f"MASTER PIVOT  —  {brand.upper()}  ·  Campaign Performance"
    ws["A2"] = ("Interactive PivotTable  ·  Jul · Aug · Sep · Oct 2026 (October is partial, data to 30 Oct)  ·  Meta spend & delivery + Facebook-sourced CRM leads. "
                "Use the slicers to filter by Month, Delivery, Lead attribution and Campaign; drag fields in the PivotTable Field List to re-cut. "
                "Cost metrics show “–” where spend or leads are zero (never a fake 0).")
    for rr, (sz, b) in ((1, (16, True)), (2, (10, False))):
        for ci in range(1, ncol + 1):
            ws.cell(rr, ci).fill = fill(NAVY); ws.cell(rr, ci).font = font(b, "FFFFFF", sz)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=25); ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=25)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top"); ws.row_dimensions[2].height = 44
    ws["A13"] = "▸  Click any slicer item to filter (Ctrl+click = several, ✕ = clear). Right-click ▸ Refresh if you change the source in Pivot_Data."
    ws.merge_cells("A13:Y13")
    for ci in range(1, 26):
        ws.cell(13, ci).fill = fill(LIGHT); ws.cell(13, ci).font = font(True, NAVY, 9)
    ws.column_dimensions["A"].width = 58
    for ci in range(2, ncol + 1): ws.column_dimensions[L(ci)].width = 14
    for r_ in range(4, 12): ws.row_dimensions[r_].height = 20
    metrics = [("Spend (₹)", "F", None, "₹#,##0.00"), ("Impressions", "G", None, "#,##0"), ("Link Clicks", "I", None, "#,##0"),
               ("Link CTR", "I", "G", "0.00%"), ("Meta Leads", "J", None, "#,##0"), ("CPL – Meta (₹)", "F", "J", "₹#,##0.00"),
               ("CRM Leads", "K", None, "#,##0"), ("Qualified", "L", None, "#,##0"), ("Qualified %", "L", "K", "0.00%"),
               ("Meetings", "M", None, "#,##0"), ("CPL – CRM (₹)", "F", "K", "₹#,##0.00"), ("CPQL (₹)", "F", "L", "₹#,##0.00")]
    ws["B14"] = "Month"; ws["B14"].font = font(True, "FFFFFF", 10)
    for ci in range(1, ncol + 1):
        for rr in (14, 15, 16):
            ws.cell(rr, ci).fill = fill(NAVY if rr < 16 else BLUE); ws.cell(rr, ci).font = font(True, "FFFFFF", 9)
    ws["A16"] = "Brand  ›  Campaign"
    for mi, m in enumerate(MONTHS):
        c0 = 2 + mi * 12
        ws.cell(15, c0, MLAB[m]); ws.merge_cells(start_row=15, start_column=c0, end_row=15, end_column=c0 + 11)
        ws.cell(15, c0).alignment = Alignment(horizontal="center")
        for k, (cap, num, den, fmt) in enumerate(metrics):
            c = ws.cell(16, c0 + k, cap); c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    ws.row_dimensions[16].height = 30
    pr = 17

    def cells(r, crit_col, crit_val):
        for mi, m in enumerate(MONTHS):
            c0 = 2 + mi * 12
            crit = f'{_rng(n, "A")},"{MLAB[m]}"' + (f',{_rng(n, crit_col)},{crit_val}' if crit_col else "")
            sums = {x: f"SUMIFS({_rng(n, x)},{crit})" for x in "FGIJKLM"}
            for k, (cap, num, den, fmt) in enumerate(metrics):
                c = ws.cell(r, c0 + k)
                if den is None: c.value = "=" + sums[num]
                else:
                    c.value = f'=IFERROR(IF({sums[den]}>0,{sums[num]}/{sums[den]},"–"),"–")'
                c.number_format = fmt; c.alignment = Alignment(horizontal="right")

    ws.cell(pr, 1, brand)
    cells(pr, "B", f"$A{pr}")
    for ci in range(1, ncol + 1): ws.cell(pr, ci).font = font(True, NAVY, 9); ws.cell(pr, ci).fill = fill(LIGHT)
    r = pr + 1
    for rw in rows:
        ws.cell(r, 1, rw["camp"]).alignment = Alignment(indent=1)
        cells(r, "C", f"$A{r}")
        for ci in range(1, ncol + 1): ws.cell(r, ci).font = font(False, "000000", 9)
        r += 1
    ws.cell(r, 1, "Grand Total")
    cells(r, None, None)
    for ci in range(1, ncol + 1): ws.cell(r, ci).font = font(True, "FFFFFF", 9); ws.cell(r, ci).fill = fill(NAVY)
    grand = r
    ws.cell(r + 2, 1, "Notes: figures are exact sums of the Pivot_Data sheet (one row per campaign line × month, linked to Campaign-Wise). Lead lines "
                      "‘Campaign not determinable’ / ‘Campaign outside Meta export’ carry CRM leads but no Meta spend, so their cost metrics show “–”. "
                      "October 2026 is a partial month. Reach is not additive and is therefore not in the pivot.")
    ws.merge_cells(start_row=r + 2, start_column=1, end_row=r + 2, end_column=25)
    ws.cell(r + 2, 1).alignment = Alignment(wrap_text=True, vertical="top"); ws.cell(r + 2, 1).font = font(False, "404040", 9)
    ws.row_dimensions[r + 2].height = 40
    ws.freeze_panes = "B17"
    return {"grand": grand, "first": pr + 1, "last": grand - 1, "pivot_ref_last_row": grand}


def add_dashboard(wb, brand, rows, n, mp, colof, cw_total_row, notes):
    """Master Dashboard (+ Dashboard_Data helper). rows: campaign lines. notes: dict of caveat facts."""
    wd = wb.create_sheet("Dashboard_Data"); wd.sheet_properties.tabColor = GREY
    ws = wb.create_sheet("Master Dashboard"); ws.sheet_properties.tabColor = NAVY
    ws.sheet_view.showGridLines = False; ws.sheet_view.zoomScale = 90
    SEL = "'Master Dashboard'!$C$4"
    labels = ["All months"] + [MLAB[m] for m in MONTHS]
    # ---------------- helper sheet
    wd["A1"] = "Dashboard helper tables (formulas only — feeds the Master Dashboard). Do not edit."
    wd["A1"].font = font(True, NAVY, 11)
    wd["A3"] = "Selected view key"; wd["B3"] = f'=IF({SEL}="All months","*",{SEL})'
    wd["A4"] = "Selected view index (0 = all)"; wd["B4"] = f'=IFERROR(MATCH({SEL},$A$8:$A$11,0),0)'
    heads = ["Month", "Spend", "Impressions", "Link clicks", "Meta leads", "CRM leads", "Qualified", "Meetings", "Contacted",
             "Cost per lead (CRM)", "Cost per qualified", "Cost per meeting", "Qualified %", "Contacted %", "Cost per lead (Meta)"]
    for i, h in enumerate(heads, 1):
        c = wd.cell(7, i, h); c.font = font(True, "FFFFFF", 9); c.fill = fill(NAVY); c.alignment = Alignment(wrap_text=True)
    pcol = {"Spend": "F", "Impressions": "G", "Link clicks": "I", "Meta leads": "J", "CRM leads": "K", "Qualified": "L", "Meetings": "M", "Contacted": "N"}
    for i, m in enumerate(MONTHS):
        r = 8 + i
        wd.cell(r, 1, MLAB[m])
        for j, h in enumerate(heads[1:9], 2):
            wd.cell(r, j, f'=SUMIFS({_rng(n, pcol[h])},{_rng(n, "A")},$A{r})')
    # derived (cols J..O) for monthly rows 8..11 and selected row 12
    wd.cell(12, 1, "Selected view")
    for j, h in enumerate(heads[1:9], 2):
        wd.cell(12, j, f'=SUMIFS({_rng(n, pcol[h])},{_rng(n, "A")},$B$3)')
    wd.cell(13, 1, "Previous month (for tile comparison)")
    for j in range(2, 10):
        cl = L(j)
        wd.cell(13, j, f'=IF($B$4<=1,"",INDEX({cl}$8:{cl}$11,$B$4-1))')
    for r in range(8, 14):
        sp, crm, q, mt, ct, ml = (f"B{r}", f"F{r}", f"G{r}", f"H{r}", f"I{r}", f"E{r}")
        wd.cell(r, 10, f'=IFERROR(IF(AND(ISNUMBER({crm}),{crm}>0,{sp}>0),{sp}/{crm},"N/A"),"N/A")')
        wd.cell(r, 11, f'=IFERROR(IF(AND(ISNUMBER({q}),{q}>0,{sp}>0),{sp}/{q},"N/A"),"N/A")')
        wd.cell(r, 12, f'=IFERROR(IF(AND(ISNUMBER({mt}),{mt}>0,{sp}>0),{sp}/{mt},"N/A"),"N/A")')
        wd.cell(r, 13, f'=IFERROR(IF(AND(ISNUMBER({crm}),{crm}>0),{q}/{crm},"N/A"),"N/A")')
        wd.cell(r, 14, f'=IFERROR(IF(AND(ISNUMBER({crm}),{crm}>0),{ct}/{crm},"N/A"),"N/A")')
        wd.cell(r, 15, f'=IFERROR(IF(AND(ISNUMBER({ml}),{ml}>0,{sp}>0),{sp}/{ml},"N/A"),"N/A")')
    wd.cell(14, 1, "Jul–Oct total")
    for j in range(2, 10): wd.cell(14, j, f"=SUM({L(j)}8:{L(j)}11)")
    sp, crm, q, mt, ct, ml = "B14", "F14", "G14", "H14", "I14", "E14"
    wd.cell(14, 10, f'=IFERROR(IF(AND({crm}>0,{sp}>0),{sp}/{crm},"N/A"),"N/A")'); wd.cell(14, 11, f'=IFERROR(IF(AND({q}>0,{sp}>0),{sp}/{q},"N/A"),"N/A")')
    wd.cell(14, 12, f'=IFERROR(IF(AND({mt}>0,{sp}>0),{sp}/{mt},"N/A"),"N/A")'); wd.cell(14, 13, f'=IFERROR(IF({crm}>0,{q}/{crm},"N/A"),"N/A")')
    wd.cell(14, 14, f'=IFERROR(IF({crm}>0,{ct}/{crm},"N/A"),"N/A")'); wd.cell(14, 15, f'=IFERROR(IF(AND({ml}>0,{sp}>0),{sp}/{ml},"N/A"),"N/A")')
    # campaign helper (Meta-export campaigns only)
    camp = [r_ for r_ in rows if r_["attr"] == ATTR_OK]
    h0 = 18
    for i, h in enumerate(["Campaign", "Spend (selected)", "Qualified (selected)", "Rank key spend", "Rank key qualified", "CRM leads (selected)"], 1):
        c = wd.cell(h0, i, h); c.font = font(True, "FFFFFF", 9); c.fill = fill(NAVY)
    for i, rw in enumerate(camp):
        r = h0 + 1 + i
        wd.cell(r, 1, rw["camp"])
        wd.cell(r, 2, f'=SUMIFS({_rng(n, "F")},{_rng(n, "C")},$A{r},{_rng(n, "A")},$B$3)')
        wd.cell(r, 3, f'=SUMIFS({_rng(n, "L")},{_rng(n, "C")},$A{r},{_rng(n, "A")},$B$3)')
        wd.cell(r, 4, f"=B{r}+(1000-ROW())/1000000000")
        wd.cell(r, 5, f"=C{r}+(1000-ROW())/1000000000")
        wd.cell(r, 6, f'=SUMIFS({_rng(n, "K")},{_rng(n, "C")},$A{r},{_rng(n, "A")},$B$3)')
    c1, c2 = h0 + 1, h0 + len(camp)
    t0 = 8
    wd.cell(5, 8, "Top 10 helper"); wd.cell(6, 8, "")
    for i, h in enumerate(["#", "Top spend campaign", "Spend", "Top qualified campaign", "Qualified"], 1):
        c = wd.cell(t0 - 1 + 0, 17 + i - 1, h); c.font = font(True, "FFFFFF", 9); c.fill = fill(NAVY)
    for k in range(1, 11):
        r = t0 + k - 1
        wd.cell(r, 17, k)
        wd.cell(r, 18, f'=IF(LARGE($D${c1}:$D${c2},Q{r})>=1,INDEX($A${c1}:$A${c2},MATCH(LARGE($D${c1}:$D${c2},Q{r}),$D${c1}:$D${c2},0)),"")')
        wd.cell(r, 19, f'=IF(R{r}="","",INDEX($B${c1}:$B${c2},MATCH(R{r},$A${c1}:$A${c2},0)))')
        wd.cell(r, 20, f'=IF(LARGE($E${c1}:$E${c2},Q{r})>=1,INDEX($A${c1}:$A${c2},MATCH(LARGE($E${c1}:$E${c2},Q{r}),$E${c1}:$E${c2},0)),"")')
        wd.cell(r, 21, f'=IF(T{r}="","",INDEX($C${c1}:$C${c2},MATCH(T{r},$A${c1}:$A${c2},0)))')
    # attribution split (selected view)
    wd.cell(21, 8, "Facebook lead attribution (selected view)")
    for i, a in enumerate([ATTR_OK, ATTR_NOCAP, ATTR_NOTIN]):
        wd.cell(22 + i, 8, a); wd.cell(22 + i, 9, f'=SUMIFS({_rng(n, "K")},{_rng(n, "E")},H{22 + i},{_rng(n, "A")},$B$3)')
    wd.cell(25, 8, "Total"); wd.cell(25, 9, "=SUM(I22:I24)")
    for j, w in enumerate([34, 14, 14, 14, 14, 14, 14, 14, 30, 14, 14, 14, 14, 14, 14, 3, 5, 50, 14, 50, 12], 1): wd.column_dimensions[L(j)].width = w
    for r in range(8, 15):
        for j in (2, 10, 11, 12, 15): wd.cell(r, j).number_format = "#,##0.00"
        for j in (13, 14): wd.cell(r, j).number_format = "0.00%"
    # ---------------- dashboard sheet
    widths = [2, 24, 17, 17, 17, 17, 17, 17, 17, 17, 17, 2]
    for i, w in enumerate(widths, 1): ws.column_dimensions[L(i)].width = w
    for ci in range(1, 13):
        for rr in (1, 2):
            ws.cell(rr, ci).fill = fill(NAVY)
    ws["B1"] = f"MASTER DASHBOARD  —  {brand.upper()}"; ws["B1"].font = font(True, "FFFFFF", 20)
    ws["B2"] = ("Meta Ads spend → leads → qualified leads → meetings  ·  Jul–Oct 2026  ·  October is a PARTIAL month (data to 30 Oct)")
    ws["B2"].font = font(False, "FFFFFF", 11); ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 20
    ws["B4"] = "SHOW ME  ▶"; ws["B4"].font = font(True, NAVY, 12); ws["B4"].alignment = Alignment(horizontal="right", vertical="center")
    ws["C4"] = os.environ.get("DASH_SEL", "All months")  # env override is for testing only
    ws.merge_cells("C4:D4")
    ws["C4"].font = font(True, "FFFFFF", 12); ws["C4"].fill = fill(TEAL); ws["C4"].alignment = Alignment(horizontal="center", vertical="center")
    ws["D4"].fill = fill(TEAL)
    ws["E4"] = "◀ click the cell and choose a month (or All months) — every tile and the Top-10 charts update"
    ws["E4"].font = font(False, GREY, 9); ws.row_dimensions[4].height = 26
    dv = DataValidation(type="list", formula1='"' + ",".join(labels) + '"', allow_blank=False, showDropDown=False)
    dv.error = "Please pick a month from the list"; dv.prompt = "Choose a month or All months"; dv.promptTitle = "Month"
    ws.add_data_validation(dv); dv.add("C4")
    ws["B5"] = '="Showing: "&C4&IF(C4="All months","  (Jul–Oct 2026 total)","")'
    ws["B5"].font = font(True, TEAL, 11)
    tiles = [("Meta Ad Spend", "B", "₹#,##0", False, "Money spent on Meta ads"),
             ("Leads from Meta forms", "E", "#,##0", False, "Lead-form results reported by Meta"),
             ("Leads in CRM", "F", "#,##0", False, "Facebook-sourced leads that reached the CRM"),
             ("Qualified Leads", "G", "#,##0", False, "Serious prospects (qualified or beyond)"),
             ("Meetings", "H", "#,##0", False, "Meetings scheduled / held"),
             ("Cost per CRM Lead", "J", "₹#,##0", True, "Spend ÷ CRM leads — lower is better"),
             ("Cost per Qualified Lead", "K", "₹#,##0", True, "Spend ÷ qualified leads — lower is better"),
             ("Cost per Meeting", "L", "₹#,##0", True, "Spend ÷ meetings — lower is better"),
             ("Qualified Rate", "M", "0.0%", False, "Qualified ÷ CRM leads"),
             ("Contacted Rate", "N", "0.0%", False, "Share of leads the team has contacted")]
    tile_cols = [2, 4, 6, 8, 10]  # B..J, each tile 2 cols wide (B-C, D-E, F-G, H-I, J-K)
    for ti, (lab, dcol, fmt, lower_better, sub) in enumerate(tiles):
        row0 = 7 + (ti // 5) * 5
        c0 = tile_cols[ti % 5]
        for rr in range(row0, row0 + 4):
            for cc in (c0, c0 + 1):
                ws.cell(rr, cc).fill = fill("F4F7FB")
        ws.merge_cells(start_row=row0, start_column=c0, end_row=row0, end_column=c0 + 1)
        ws.merge_cells(start_row=row0 + 1, start_column=c0, end_row=row0 + 1, end_column=c0 + 1)
        ws.merge_cells(start_row=row0 + 2, start_column=c0, end_row=row0 + 2, end_column=c0 + 1)
        ws.merge_cells(start_row=row0 + 3, start_column=c0, end_row=row0 + 3, end_column=c0 + 1)
        a = ws.cell(row0, c0, lab); a.font = font(True, "FFFFFF", 10); a.alignment = Alignment(horizontal="center")
        for cc in (c0, c0 + 1): ws.cell(row0, cc).fill = fill(BLUE if ti < 5 else TEAL)
        v = ws.cell(row0 + 1, c0, f"=Dashboard_Data!{dcol}12")
        v.number_format = fmt; v.font = font(True, NAVY, 20); v.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row0 + 1].height = 34
        s = ws.cell(row0 + 2, c0, f'=IF(Dashboard_Data!$B$4<=1,IF(Dashboard_Data!$B$4=0,"Jul–Oct total","First month of the period"),'
                                   f'IFERROR(IF(OR(NOT(ISNUMBER(Dashboard_Data!{dcol}12)),NOT(ISNUMBER(Dashboard_Data!{dcol}13))),"vs previous month: n/a",'
                                   f'IF(Dashboard_Data!{dcol}13=0,"vs previous month: n/a",'
                                   f'IF(Dashboard_Data!{dcol}12>=Dashboard_Data!{dcol}13,"▲ ","▼ ")&TEXT(ABS(Dashboard_Data!{dcol}12/Dashboard_Data!{dcol}13-1),"0.0%")&" vs previous month")),"vs previous month: n/a"))')
        s.font = font(True, GREY, 9); s.alignment = Alignment(horizontal="center")
        d = ws.cell(row0 + 3, c0, sub); d.font = font(False, GREY, 8); d.alignment = Alignment(horizontal="center")
        # colour the change line
        from openpyxl.formatting.rule import FormulaRule
        cell = ws.cell(row0 + 2, c0).coordinate
        good, bad = ("00803C", "C00000") if not lower_better else ("C00000", "00803C")
        ws.conditional_formatting.add(cell, FormulaRule(formula=[f'LEFT({cell},1)="▲"'], font=Font(color=good, bold=True)))
        ws.conditional_formatting.add(cell, FormulaRule(formula=[f'LEFT({cell},1)="▼"'], font=Font(color=bad, bold=True)))
    # ----- month-to-month table (always all months)
    r0 = 18
    ws.cell(r0, 2, "MONTH-TO-MONTH PERFORMANCE").font = font(True, "FFFFFF", 11)
    for cc in range(2, 12): ws.cell(r0, cc).fill = fill(NAVY)
    th = ["Month", "Spend (₹)", "Leads from Meta forms", "Leads in CRM", "Qualified leads", "Meetings", "Cost per CRM lead (₹)", "Cost per qualified lead (₹)", "Qualified rate", "Contacted rate"]
    srcc = ["A", "B", "E", "F", "G", "H", "J", "K", "M", "N"]
    fmts = [None, "₹#,##0", "#,##0", "#,##0", "#,##0", "#,##0", "₹#,##0", "₹#,##0", "0.0%", "0.0%"]
    for i, h in enumerate(th):
        c = ws.cell(r0 + 1, 2 + i, h); c.font = font(True, NAVY, 9); c.fill = fill(LIGHT); c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[r0 + 1].height = 32
    for k in range(5):
        r = r0 + 2 + k
        for i, sc in enumerate(srcc):
            c = ws.cell(r, 2 + i, f"=Dashboard_Data!{sc}{14 if k == 4 else 8 + k}")
            if fmts[i]: c.number_format = fmts[i]
            c.alignment = Alignment(horizontal="left" if i == 0 else "right"); c.font = font(k == 4, "000000", 10)
            if k == 4: c.fill = fill(LIGHT)
    # change row
    r = r0 + 7
    ws.cell(r, 2, "Change Sep → Oct is NOT like-for-like (October is partial)").font = font(False, GREY, 8)
    # ----- charts
    def style(ch, title, w=15.5, h=7.2):
        ch.title = title; ch.width = w; ch.height = h; ch.legend.position = "b"
        ch.x_axis.delete = False; ch.y_axis.delete = False
        return ch
    cat = Reference(wd, min_col=1, min_row=8, max_row=11)
    c1_ = BarChart(); c1_.type = "col"; style(c1_, "Spend (bars) and leads in CRM (line) by month")
    c1_.add_data(Reference(wd, min_col=2, min_row=7, max_row=11), titles_from_data=True); c1_.set_categories(cat)
    c1_.series[0].graphicalProperties.solidFill = BLUE
    c1_.y_axis.title = "Spend (₹)"; c1_.y_axis.majorGridlines = None
    l1 = LineChart(); l1.add_data(Reference(wd, min_col=6, min_row=7, max_row=11), titles_from_data=True)
    l1.series[0].graphicalProperties.line.solidFill = "E07B00"; l1.series[0].graphicalProperties.line.width = 28000
    l1.series[0].smooth = False; l1.y_axis.delete = False; l1.y_axis.axId = 200; l1.y_axis.title = "Leads in CRM"; l1.y_axis.crosses = "max"
    c1_ += l1
    ws.add_chart(c1_, f"B{r0 + 10}")
    c2_ = LineChart(); style(c2_, "Cost per CRM lead and per qualified lead (₹)")
    c2_.add_data(Reference(wd, min_col=10, min_row=7, max_row=11), titles_from_data=True)
    c2_.add_data(Reference(wd, min_col=11, min_row=7, max_row=11), titles_from_data=True); c2_.set_categories(cat)
    c2_.series[0].smooth = False; c2_.series[1].smooth = False; c2_.series[0].graphicalProperties.line.solidFill = TEAL; c2_.series[1].graphicalProperties.line.solidFill = "C00000"
    ws.add_chart(c2_, f"G{r0 + 10}")
    c3_ = BarChart(); c3_.type = "bar"; style(c3_, "Lead funnel — selected view (Meta forms → CRM → Qualified → Meetings)")
    # funnel data block in helper sheet
    wd.cell(28, 8, "Funnel (selected view)")
    for i, (lab, src_) in enumerate([("Leads from Meta forms", "E12"), ("Leads in CRM", "F12"), ("Qualified leads", "G12"), ("Meetings", "H12")]):
        wd.cell(29 + i, 8, lab); wd.cell(29 + i, 9, f"={src_}")
    c3_.add_data(Reference(wd, min_col=9, min_row=29, max_row=32), titles_from_data=False); c3_.set_categories(Reference(wd, min_col=8, min_row=29, max_row=32))
    c3_.series[0].graphicalProperties.solidFill = TEAL; c3_.legend = None; c3_.x_axis.scaling.orientation = "maxMin"
    c3_.dataLabels = DataLabelList(); c3_.dataLabels.showVal = True; c3_.dataLabels.showSerName = False; c3_.dataLabels.showCatName = False; c3_.dataLabels.showLegendKey = False; c3_.dataLabels.showPercent = False
    ws.add_chart(c3_, f"B{r0 + 26}")
    c4_ = BarChart(); c4_.type = "bar"; style(c4_, "Top 10 campaigns by spend — selected view (₹)", h=10)
    c4_.add_data(Reference(wd, min_col=19, min_row=8, max_row=17), titles_from_data=False); c4_.set_categories(Reference(wd, min_col=18, min_row=8, max_row=17))
    c4_.series[0].graphicalProperties.solidFill = BLUE; c4_.legend = None; c4_.x_axis.scaling.orientation = "maxMin"
    ws.add_chart(c4_, f"G{r0 + 26}")
    c5_ = BarChart(); c5_.type = "bar"; style(c5_, "Top 10 campaigns by qualified leads — selected view", h=10)
    c5_.add_data(Reference(wd, min_col=21, min_row=8, max_row=17), titles_from_data=False); c5_.set_categories(Reference(wd, min_col=20, min_row=8, max_row=17))
    c5_.series[0].graphicalProperties.solidFill = TEAL; c5_.legend = None; c5_.x_axis.scaling.orientation = "maxMin"; c5_.x_axis.tickLblSkip = 1; c4_.x_axis.tickLblSkip = 1
    ws.add_chart(c5_, f"B{r0 + 44}")
    # ----- key highlights
    hr = r0 + 63
    ws.cell(hr, 2, "KEY HIGHLIGHTS (update automatically)").font = font(True, "FFFFFF", 11)
    for cc in range(2, 12): ws.cell(hr, cc).fill = fill(TEAL)
    D = "Dashboard_Data!"
    hl = [
        f'="• Over Jul–Oct 2026 the brand spent ₹"&TEXT({D}B14,"#,##0")&" on Meta ads, which brought "&TEXT({D}F14,"#,##0")&" leads into the CRM; "&TEXT({D}G14,"#,##0")&" ("&TEXT({D}M14,"0.0%")&") were qualified and "&TEXT({D}H14,"#,##0")&" reached the meeting stage."',
        f'=IFERROR("• Cheapest month for a CRM lead: "&INDEX({D}A8:A11,MATCH(MIN({D}J8:J11),{D}J8:J11,0))&" (₹"&TEXT(MIN({D}J8:J11),"#,##0")&"); costliest: "&INDEX({D}A8:A11,MATCH(MAX({D}J8:J11),{D}J8:J11,0))&" (₹"&TEXT(MAX({D}J8:J11),"#,##0")&").","• Cost per CRM lead could not be calculated for the months shown.")',
        f'=IFERROR("• Best qualified rate: "&INDEX({D}A8:A11,MATCH(MAX({D}M8:M11),{D}M8:M11,0))&" ("&TEXT(MAX({D}M8:M11),"0.0%")&"); weakest: "&INDEX({D}A8:A11,MATCH(MIN({D}M8:M11),{D}M8:M11,0))&" ("&TEXT(MIN({D}M8:M11),"0.0%")&").","• Qualified rate could not be calculated.")',
        f'=IFERROR("• Biggest spend in the selected view: "&{D}R8&" — ₹"&TEXT({D}S8,"#,##0")&" ("&TEXT({D}S8/{D}B12,"0.0%")&" of spend).","• No campaign spend in the selected view.")',
        f'=IFERROR("• "&TEXT({D}I23/{D}I25,"0.0%")&" of CRM leads in the selected view could not be tied to a campaign (no campaign name and ad set not mappable) and "&TEXT({D}I24/{D}I25,"0.0%")&" belong to campaigns outside the supplied Meta export — their cost is not included.","• Lead attribution not available.")',
    ]
    for i, f_ in enumerate(hl):
        c = ws.cell(hr + 1 + i, 2, f_); c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = font(False, "000000", 10)
        ws.merge_cells(start_row=hr + 1 + i, start_column=2, end_row=hr + 1 + i, end_column=11); ws.row_dimensions[hr + 1 + i].height = 32
    cr = hr + 8
    ws.cell(cr, 2, "HOW TO READ THIS PAGE").font = font(True, "FFFFFF", 11)
    for cc in range(2, 12): ws.cell(cr, cc).fill = fill(GREY)
    cav = [
        "• Spend and form-leads come from Meta Ads Manager; CRM leads, qualified leads and meetings come from the Lead Module (leads counted in the month they were created).",
        "• Qualified = lead has reached Qualified, Follow-Up, Details Shared, Meeting Scheduled or Meeting Conducted. Meetings = Follow-Up, Meeting Scheduled or Meeting Conducted.",
        "• Cost per lead / qualified lead / meeting = Meta spend ÷ the count. “N/A” means it cannot be calculated (for example no spend that month) — it is never shown as zero.",
        f"• October 2026 is a partial month (data to 30 Oct), so compare it with full months carefully. FW is a separate brand and is excluded.",
        notes.get("attr", ""),
        "• Detailed tabs: Master Pivot (interactive, with slicers), Month-on-Month, Brand-Wise, Campaign-Wise, Data Quality Log and Validation.",
    ]
    for i, t in enumerate(cav):
        c = ws.cell(cr + 1 + i, 2, t); c.alignment = Alignment(wrap_text=True, vertical="top"); c.font = font(False, "404040", 9)
        ws.merge_cells(start_row=cr + 1 + i, start_column=2, end_row=cr + 1 + i, end_column=11); ws.row_dimensions[cr + 1 + i].height = 28
    ws.page_setup.orientation = "portrait"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return {"hl_row": hr, "tile_rows": (7, 12)}


def add_validation_rows(wsV, mp, n, cw_total_row, colof, MONTH_KEYS=MONTHS):
    """pivot-data and master-pivot tie-outs appended to the Validation tab."""
    r = wsV.max_row + 1
    wsV.cell(r, 1, "D.  PIVOT DATA / MASTER PIVOT / DASHBOARD");
    for i in range(1, 6): wsV.cell(r, i).fill = fill(BLUE); wsV.cell(r, i).font = font(True, "FFFFFF", 10)
    r += 1
    def tc(k, b=4): return f"'Campaign-Wise'!{colof(b, k)}{cw_total_row}"
    items = [("Pivot_Data spend total vs Campaign-Wise total", f"=SUM({_rng(n, 'F')})", f"={tc('spend')}"),
             ("Pivot_Data Meta leads total vs Campaign-Wise total", f"=SUM({_rng(n, 'J')})", f"={tc('mleads')}"),
             ("Pivot_Data CRM leads total vs Campaign-Wise total", f"=SUM({_rng(n, 'K')})", f"={tc('crm')}"),
             ("Pivot_Data qualified total vs Campaign-Wise total", f"=SUM({_rng(n, 'L')})", f"={tc('qual')}"),
             ("Pivot_Data meetings total vs Campaign-Wise total", f"=SUM({_rng(n, 'M')})", f"={tc('meet')}"),
             ("Master Pivot grand-total spend (4 months) vs Pivot_Data", "=" + "+".join(f"'Master Pivot'!{L(2 + 12 * m)}{mp['grand']}" for m in range(4)), f"=SUM({_rng(n, 'F')})"),
             ("Master Pivot grand-total CRM leads (4 months) vs Pivot_Data", "=" + "+".join(f"'Master Pivot'!{L(8 + 12 * m)}{mp['grand']}" for m in range(4)), f"=SUM({_rng(n, 'K')})"),
             ("Master Dashboard total spend (Jul–Oct) vs Campaign-Wise", "=Dashboard_Data!B14", f"={tc('spend')}")]
    for name, a, b in items:
        wsV.cell(r, 1, name); wsV.cell(r, 2, a); wsV.cell(r, 3, b); wsV.cell(r, 4, f"=ROUND(B{r}-C{r},2)"); wsV.cell(r, 5, f'=IF(D{r}=0,"✔ ties","✘ CHECK")')
        r += 1
