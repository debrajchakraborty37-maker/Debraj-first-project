import copy
import pandas as pd
from openpyxl.utils import get_column_letter as CL
from build_helpers import put, clear_from
from pivotgen import orders
from datalayer import STATUS_ORDER

NA = '(n/a - spend)'


def ratio(a, b):
    return a / b if b else '-'


def fill(wb, S, f, ct, act, B, QTXT, PERIOD):
    ws = S['Master Pivot']
    T = lambda ref: copy.copy(ws[ref]._style)
    st = {k: T(k) for k in ['B24', 'B25', 'C25', 'B26', 'C26', 'B27', 'C27', 'C30', 'B39', 'C39', 'B41', 'C41', 'B42', 'C42', 'B43', 'C43', 'B59', 'C59', 'C68', 'B89', 'C89', 'B90', 'C90',
                            'B91', 'C91', 'D91', 'E91', 'G91', 'B92', 'C92', 'D92', 'E92', 'G92', 'B110', 'C110', 'E110', 'G110', 'B114', 'B115', 'C115', 'B116', 'C116', 'D116', 'E116',
                            'F116', 'G116', 'H116', 'D123', 'E123', 'B237']}
    st_tot = {c: T(f'{c}123') for c in 'BCDEFGH'}
    ws['B1'] = f'{B.upper()}  |  Lead Quality: Old Campaigns vs New Campaigns  -  MASTER PIVOT (interactive)'
    ws['B2'] = (f'{PERIOD}  |  CRM status as of 31-Oct-2026  |  Quality Lead = {QTXT}  |  Click any slicer button to filter every table (Ctrl+click = multi-select)')
    ws['B4'] = ('FILTERS (slicers)  -  click a button to filter the three pivot tables below; Ctrl+click = multi-select. Spend cannot be split by status / month / week, so it shows "-" when those are used. '
                'Cost per lead / per quality lead use only campaigns with Meta spend data (EBG - In House campaigns have no spend in the exports).')
    clear_from(ws, 24)
    od = orders(f, list(act['name']))
    types = od[1]
    lead = f[f['Record Type'] == 'Lead']
    ncol = len(types) + 1  # data columns incl grand
    lastcol = CL(2 + ncol)

    def block(df):
        sp = df['Spend INR'].sum(); ld = df['Lead Count'].sum(); q = df['Quality Count'].sum(); co = df['Contacted Count'].sum()
        cl = df['Costed Lead Count'].sum(); cq = df['Costed Quality Count'].sum()
        return dict(spend=float(sp), leads=int(ld), cpl=ratio(sp, cl), cont=ratio(co, ld), qual=int(q), qp=ratio(q, ld), qc=ratio(q, co), cpql=ratio(sp, cq))

    cols = [f[f['Campaign Type'] == t] for t in types] + [f]
    # ---- 1. headline
    put(ws, 'B24', '1.  HEADLINE  -  Old vs New campaigns (all key metrics)', st['B24']); ws.merge_cells('B24:N24')
    put(ws, 'C25', 'Campaign Type', st['C25'])
    put(ws, 'B26', 'Values', st['B26'])
    for j, t in enumerate(types + ['Grand Total']): put(ws, (26, 3 + j), t, st['C26'])
    labels = [('Spend (₹)', 'spend', 'C27'), ('Leads', 'leads', 'C27'), ('Cost per Lead (₹)', 'cpl', 'C27'), ('Contacted %', 'cont', 'C30'), ('Quality Leads', 'qual', 'C27'),
              ('Quality %', 'qp', 'C30'), ('Quality % of Contacted', 'qc', 'C30'), ('Cost per Quality Lead (₹)', 'cpql', 'C27')]
    blocks = [block(c) for c in cols]
    for i, (lab, key, sk) in enumerate(labels):
        put(ws, (27 + i, 2), lab, st['B27'])
        for j, b in enumerate(blocks): put(ws, (27 + i, 3 + j), b[key], st[sk])
    head_ref = f'B25:{lastcol}34'
    # ---- 2. status counts
    put(ws, 'B38', '2.  LEAD STATUS FUNNEL  -  number of leads by status', st['B24']); ws.merge_cells('B38:N38')
    put(ws, 'B39', 'Record Type', st['B39']); put(ws, 'C39', 'Lead', st['C39'])
    sts = [s for s in od[6] if s in set(lead['Lead Status'])]
    put(ws, 'B41', 'Leads', st['B41']); put(ws, 'C41', 'Campaign Type', st['C41'])
    put(ws, 'B42', 'Lead Status', st['B42'])
    for j, t in enumerate(types + ['Grand Total']): put(ws, (42, 3 + j), t, st['C42'])
    cnt = lead.groupby(['Lead Status', 'Campaign Type']).size()
    for i, s in enumerate(sts):
        put(ws, (43 + i, 2), s, st['B43'])
        for j, t in enumerate(types):
            v = int(cnt.get((s, t), 0)); put(ws, (43 + i, 3 + j), v if v else None, st['C43'])
        put(ws, (43 + i, 3 + len(types)), int(sum(cnt.get((s, t), 0) for t in types)), st['C43'])
    g1 = 43 + len(sts)
    put(ws, (g1, 2), 'Grand Total', st['B59'])
    tot = lead.groupby('Campaign Type').size()
    for j, t in enumerate(types): put(ws, (g1, 3 + j), int(tot.get(t, 0)), st['C59'])
    put(ws, (g1, 3 + len(types)), len(lead), st['C59'])
    status_ref = f'B41:{lastcol}{g1}'
    # ---- 3. status %
    T2 = g1 + 4
    put(ws, (T2, 2), "3.  LEAD STATUS FUNNEL  -  % of each campaign type's leads", st['B24']); ws.merge_cells(start_row=T2, start_column=2, end_row=T2, end_column=14)
    put(ws, (T2 + 1, 2), 'Record Type', st['B39']); put(ws, (T2 + 1, 3), 'Lead', st['C39'])
    p0 = T2 + 3
    put(ws, (p0, 2), 'Leads', st['B41']); put(ws, (p0, 3), 'Campaign Type', st['C41']); put(ws, (p0 + 1, 2), 'Lead Status', st['B42'])
    for j, t in enumerate(types + ['Grand Total']): put(ws, (p0 + 1, 3 + j), t, st['C42'])
    for i, s in enumerate(sts):
        put(ws, (p0 + 2 + i, 2), s, st['B43'])
        for j, t in enumerate(types):
            put(ws, (p0 + 2 + i, 3 + j), cnt.get((s, t), 0) / tot[t], st['C68'])
        put(ws, (p0 + 2 + i, 3 + len(types)), sum(cnt.get((s, t), 0) for t in types) / len(lead), st['C68'])
    g2 = p0 + 2 + len(sts)
    put(ws, (g2, 2), 'Grand Total', st['B59'])
    for j in range(len(types) + 1): put(ws, (g2, 3 + j), 1, st['C68'])
    pct_ref = f'B{p0}:{lastcol}{g2}'
    # ---- campaign pivot
    T3 = g2 + 4
    put(ws, (T3, 2), '3.  CAMPAIGN WISE  -  spend, leads and lead quality', st['B24']); ws.merge_cells(start_row=T3, start_column=2, end_row=T3, end_column=14)
    top = T3 + 1
    put(ws, (top, 3), 'Values', st['C89'])
    hdr = ['Campaign Type / Campaign', 'Spend (₹)', 'Leads', 'Cost per Lead (₹)', 'Quality Leads', 'Quality %', 'Cost per Quality Lead (₹)']
    for c, h in enumerate(hdr): put(ws, (top + 1, 2 + c), h, st['B90'] if c == 0 else st['C90'])
    r = top + 2
    ct_of = f.drop_duplicates('Campaign').set_index('Campaign')['Campaign Type']

    def rowvals(df):
        b = block(df)
        return [b['spend'], b['leads'], b['cpl'], b['qual'], b['qp'], b['cpql']]
    for t in types:
        put(ws, (r, 2), t, st['B91'])
        for c, v in enumerate(rowvals(f[f['Campaign Type'] == t])): put(ws, (r, 3 + c), v, st['C91'] if c not in (4,) else st['G91'])
        r += 1
        for cmp_ in od[2]:
            if ct_of.get(cmp_) != t: continue
            put(ws, (r, 2), cmp_, st['B92'])
            for c, v in enumerate(rowvals(f[f['Campaign'] == cmp_])): put(ws, (r, 3 + c), v, st['C92'] if c not in (4,) else st['G92'])
            r += 1
    put(ws, (r, 2), 'Grand Total', st['B110'])
    for c, v in enumerate(rowvals(f)): put(ws, (r, 3 + c), v, st['C110'] if c not in (4,) else st['G110'])
    camp_ref = f'B{top}:H{r}'
    # ---- 4. quality table
    T4 = r + 4
    put(ws, (T4, 2), '4.  QUALITY TABLE  -  Campaign Name, Campaign Type, Quality Parameter, Quality % and Quality Count', st['B114']); ws.merge_cells(start_row=T4, start_column=2, end_row=T4, end_column=9)
    h = T4 + 1
    for c, t in enumerate(['Campaign Name', 'Campaign Type (Old / New)', 'Quality Parameter', 'Quality %', 'Quality Count', 'Campaign Leads', 'Campaign Spend (INR)']):
        put(ws, (h, 2 + c), t, st['B115'] if c == 0 else st['C115'])
    groups = [('ALL OLD CAMPAIGNS (combined)', 'Old', True), ('ALL NEW CAMPAIGNS (combined)', 'New', True)] + [(n, None, False) for n in act[act.leads > 0]['name']]
    r = h + 1
    for name, tp, isT in groups:
        for p in range(8):
            q = p == 7
            put(ws, (r, 2), name, st['B116'])
            if isT: put(ws, (r, 3), tp, st['C116'])
            else: put(ws, (r, 3), f'=IFERROR(INDEX(CampTypes,MATCH($B{r},CampList,0)),"Unattributed")', st['C116'])
            put(ws, (r, 4), 'TOTAL QUALITY LEADS' if q else f'=Settings!$A${4 + p}', st['D116'])
            put(ws, (r, 5), f'=IFERROR(F{r}/G{r},0)', st['E116'])
            key, crit = ('fType', f'$C{r}') if isT else ('fCampaign', f'$B{r}')
            put(ws, (r, 6), (f'=SUMIFS(fQual,{key},{crit})' if q else f'=SUMIFS(fLeads,{key},{crit},fStatus,$D{r})'), st['F116'])
            put(ws, (r, 7), f'=SUMIFS(fLeads,{key},{crit})', st['G116'])
            put(ws, (r, 8), (f'=SUMIFS(fSpend,{key},{crit})' if isT else f'=IF(COUNTIF(MetaCamps,$B{r})=0,"n/a",SUMIFS(fSpend,{key},{crit}))'), st['H116'])
            if q:
                for c in range(2, 9): ws.cell(r, c)._style = copy.copy(st_tot['BCDEFGH'[c - 2]])
            r += 1
    last = r - 1
    ws.auto_filter.ref = f'B{h}:H{last}'
    put(ws, (last + 2, 2), ('Quality % = Quality Count / all leads of that campaign. Use the filter arrows on the header row to pick a campaign, type or quality parameter. (This table is formula-based: it responds to the '
                           'Campaign_Master Old/New mapping, not to the slicers.) Campaign Spend "n/a" = campaign not in the Meta exports (EBG - In House).'), st['B237'])
    # hyperlinks
    for hl in ws._hyperlinks:
        loc = {'C3': 24, 'D3': 38, 'E3': T3, 'F3': T4}.get(hl.ref)
        if loc: hl.location = f"'Master Pivot'!B{loc}"
    return dict(head=head_ref, status=status_ref, pct=pct_ref, camp=camp_ref, od=od, qt_hdr=h, qt_last=last)
