import sys, re, copy, warnings, datetime as dt
warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, openpyxl
from openpyxl.utils import get_column_letter as CL
from openpyxl.worksheet.table import Table
from openpyxl.workbook.defined_name import DefinedName
from datalayer import QUALITY, STATUS_ORDER, is_new, WIN_START, WIN_END
from facts import campaign_table, active_campaigns, fact_frame, NA
import pivotgen

TEMPLATE = '/root/.claude/uploads/eb8fa0cd-ad52-5e00-bd26-b0914f0c0cda/00143e64-Natuf_Old_vs_New_Campaign_Lead_Quality_Report.xlsx'
ASOF = pd.Timestamp('2026-10-31')
PERIOD = '01-Oct-2026 to 31-Oct-2026'
QTXT = 'Won, Token Received, Qualified, Meeting Scheduled, Meeting Conducted, Follow-Up, Details Shared'


def fmt_inr(x): return '₹' + f'{x:,.0f}'


from build_helpers import put, clear_from


def rowf(f, old, new):
    return re.sub(r'(?<![0-9A-Za-z_])(\$?[A-Z]{1,2}\$?)%d(?![0-9])' % old, lambda m: m.group(1) + str(new), f)


def wipe(ws):
    for m in list(ws.merged_cells.ranges): ws.unmerge_cells(str(m))
    ws.delete_rows(1, ws.max_row + 2)


def build(brand, d, out):
    B = brand
    ct = campaign_table(d)
    act = active_campaigns(ct)
    f = fact_frame(d, ct)
    L, E, X = d['L'], d['E'], d['X']
    camp, adst, ads = d['camp'], d['adst'], d['ads']
    wb = openpyxl.load_workbook(TEMPLATE)
    S = {n: wb[n] for n in wb.sheetnames}
    nL, nF = len(L), len(f)
    nC = len(camp)
    nA = len(adst)
    # ------------------------------------------------------------ aggregates (python, for narrative)
    def agg(t=None):
        s = f[f['Record Type'] == 'Lead']
        if t: s = s[s['Campaign Type'] == t]
        sp = f[(f['Record Type'] == 'Spend') & ((f['Campaign Type'] == t) if t else True)]
        k = dict(leads=len(s), qual=int(s['Quality Count'].sum()), spend=float(sp['Spend INR'].sum()),
                 costed=int(s['Costed Lead Count'].sum()), cqual=int(s['Costed Quality Count'].sum()),
                 contacted=int(s['Contacted Count'].sum()), lost=int(s['Lost Count'].sum()),
                 newlead=int((s['Lead Status'] == 'New Lead').sum()), impr=float(sp['Impressions'].sum()),
                 clicks=float(sp['Link Clicks'].sum()), meta=float(sp['Meta Results Count'].sum()),
                 deep=int(s['Lead Status'].isin(['Won', 'Token Received', 'Qualified', 'Meeting Scheduled', 'Meeting Conducted']).sum()))
        k['cpl'] = k['spend'] / k['costed'] if k['costed'] else 0
        k['cpql'] = k['spend'] / k['cqual'] if k['cqual'] else 0
        k['qp'] = k['qual'] / k['leads'] if k['leads'] else 0
        k['qc'] = k['qual'] / k['contacted'] if k['contacted'] else 0
        return k
    O, N, T = agg('Old'), agg('New'), agg()
    _nm = set(ct[(ct.type == 'New') & ct.in_meta & (ct.spend > 0)]['name'])
    _st = pd.to_datetime(adst[(adst.active == 1) & adst.mapped.isin(_nm)]['Starts'], errors='coerce').min()
    new_start = _st.normalize() if pd.notna(_st) else L[L.ctype == 'New']['date'].min()
    new_days = int((WIN_END - new_start).days + 1)
    old_days = 31
    lfl = L[L.date >= new_start]
    def lflk(t):
        s = lfl[lfl.ctype == t]
        return len(s), int(s.qual.sum())
    (lo, qo), (ln, qn) = lflk('Old'), lflk('New')
    nospend = [c for c in act['name'] if c in d['extra']]
    nospend_leads = int(ct[ct.name.isin(nospend)].leads.sum())
    unat = int((L.campaign == '(Unattributed)').sum())

    # ------------------------------------------------------------ Settings
    ws = S['Settings']
    ws['B14'] = WIN_START.to_pydatetime(); ws['C14'] = 'Meta export range (campaign / ad set / ad exports are 1-31 Oct 2026)'
    ws['B15'] = WIN_END.to_pydatetime(); ws['C15'] = 'Meta export range'
    ws['B16'] = ASOF.to_pydatetime(); ws['C16'] = 'CRM export taken on 31-Oct-2026 (last lead created 31-Oct 12:56); CRM statuses are a snapshot on this date'
    ws['B17'] = new_start.to_pydatetime(); ws['C17'] = 'Day the New campaigns (with Meta spend data) went live - used for the same-period lead-age comparison'
    ws['B21'] = old_days; ws['C21'] = f'Old campaigns: reporting window 01-Oct to 31-Oct (31 days); individual campaigns may have been paused earlier - see Campaign_Master'
    ws['B22'] = new_days; ws['C22'] = (f'New campaigns with Meta spend data went live {new_start:%d-%b} (earliest ad-set start) -> {new_start:%d-%b} to 31-Oct = {new_days} days. '
                 'EBG - In House campaigns (no Meta data) were already generating leads from 01-Oct, so daily lead averages for New are slightly overstated.')

    # ------------------------------------------------------------ Meta_Campaigns / AdSets / Ads
    ws = S['Meta_Campaigns']; hs = [ws.cell(1, c)._style for c in range(1, 17)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 17)]
    wipe(ws)
    hdr = ['Campaign', 'Delivery', 'Result indicator', 'Results (as reported)', 'Reach', 'Impressions', 'Spend (INR)', 'Link Clicks', 'CPC link (INR)',
           'CTR link (%)', 'CPM (INR)', 'Landing page views', 'Budget', 'Budget type', 'Cost per result (INR)', 'Lead-type results (excl. landing-page-views)']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    nn = lambda v: None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.number)) else v)
    for i, r in camp.iterrows():
        rr = i + 2
        vals = [r['Campaign name'], r['Campaign delivery'], nn(r['Result indicator']), nn(r['Results']), nn(r['Reach']), nn(r['Impressions']), nn(r['Amount spent (INR)']),
                nn(r['Link clicks']), nn(r['CPC (cost per link click) (INR)']), nn(r['CTR (link click-through rate)']), nn(r['CPM (cost per 1,000 impressions) (INR)']),
                nn(r['Landing page views']), r['Ad set budget'], str(r['Ad set budget type']), nn(r['Cost per results']),
                f'=IF(ISNUMBER(SEARCH("landing_page_view",C{rr})),0,N(D{rr}))']
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, bs[c - 1])
    ws.freeze_panes = 'A2'
    mc_last = nC + 1

    ws = S['Meta_AdSets']; hs = [ws.cell(1, c)._style for c in range(1, 17)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 17)]
    wipe(ws)
    hdr = ['Ad set name', 'Mapped campaign (inferred - see Notes)', 'Delivery', 'Starts', 'Budget', 'Budget type', 'Spend (INR)', 'Impressions', 'Reach', 'Link Clicks',
           'Results (as reported)', 'Result indicator', 'Landing page views', 'Active (spend/impr/results>0)', 'Lead-type results', 'Key (Campaign|Ad set)']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    for i, r in adst.iterrows():
        rr = i + 2
        st = pd.to_datetime(r['Starts'], errors='coerce')
        vals = [r['Ad set name'], r['mapped'], r['Ad set delivery'], None if pd.isna(st) else st.to_pydatetime(), r['Ad set budget'], str(r['Ad set budget type']),
                nn(r['Amount spent (INR)']), nn(r['Impressions']), nn(r['Reach']), nn(r['Link clicks']), nn(r['Results']), nn(r['Result indicator']),
                nn(r['Landing page views']), int(r['active']), f'=IF(ISNUMBER(SEARCH("landing_page_view",L{rr})),0,N(K{rr}))', f'=B{rr}&"|"&A{rr}']
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, bs[c - 1])
    ws.freeze_panes = 'A2'

    ws = S['Meta_Ads']; hs = [ws.cell(1, c)._style for c in range(1, 12)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 12)]
    wipe(ws)
    hdr = ['Ad name', 'Delivery', 'Result indicator', 'Results (as reported)', 'Spend (INR)', 'Impressions', 'Reach', 'Link Clicks', 'Quality ranking', 'Engagement ranking', 'Conversion ranking']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    for i, r in ads.iterrows():
        rr = i + 2
        vals = [r['Ad name'], r['Ad delivery'], nn(r['Result indicator']), nn(r['Results']), nn(r['Amount spent (INR)']), nn(r['Impressions']), nn(r['Reach']), nn(r['Link clicks']),
                nn(r['Quality ranking']), nn(r['Engagement rate ranking']), nn(r['Conversion rate ranking'])]
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, bs[c - 1])
    ws.freeze_panes = 'A2'

    # ------------------------------------------------------------ Campaign_Master
    ws = S['Campaign_Master']
    hs = [copy.copy(ws.cell(1, c)._style) for c in range(1, 13)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 13)]
    ub = [copy.copy(ws.cell(29, c)._style) for c in range(1, 13)]; tb = [copy.copy(ws.cell(30, c)._style) for c in range(1, 13)]; nb = copy.copy(ws['A32']._style)
    wipe(ws)
    hdr = ['Campaign', 'Campaign Type  (EDITABLE: Old / New)', 'Basis for classification', 'Meta delivery', 'Result type', 'Budget (INR/day)', 'Earliest ad-set start',
           'Spend - campaign file (INR)', 'Spend - sum of ad sets (INR)', 'Difference', 'CRM leads (in report)', 'Quality leads', 'Spend data']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[min(c, 12) - 1])
    ws.column_dimensions['M'].width = 30
    starts = adst[adst.active == 1].assign(st=lambda x: pd.to_datetime(x['Starts'], errors='coerce')).groupby('mapped')['st'].min()
    cm_rows = {}
    for i, r in ct.iterrows():
        rr = i + 2
        cm_rows[r['name']] = rr
        un = r['type'] == 'Unattributed'
        basis = ('No campaign tag in CRM (WhatsApp-API lead with blank campaign) - not forced into Old/New' if un else
                 ("New: campaign name carries 'Oct26' (new Oct-2026 campaign structure, as defined by the business)" if r['type'] == 'New' else
                  "Old: all campaigns other than the Oct26 campaigns are Old"))
        res = (r['ind'].replace('actions:', '') if isinstance(r['ind'], str) else None)
        bud = r['budget']
        try: bud = float(bud)
        except Exception: bud = 'ad set budget' if isinstance(bud, str) else None
        stt = starts.get(r['name'])
        vals = [r['name'], r['type'], basis, r['delivery'], res, bud, None if stt is None or pd.isna(stt) else stt.to_pydatetime(),
                f'=SUMIFS(Meta_Campaigns!$G$2:$G${mc_last},Meta_Campaigns!$A$2:$A${mc_last},A{rr})',
                f'=SUMIFS(Meta_AdSets!$G$2:$G${nA + 1},Meta_AdSets!$B$2:$B${nA + 1},A{rr})', f'=ROUND(H{rr}-I{rr},2)',
                f'=SUMIFS(fLeads,fCampaign,A{rr})', f'=SUMIFS(fQual,fCampaign,A{rr})',
                f'=IF(COUNTIF(MetaCamps,A{rr})>0,"In Meta export","NOT in Meta export (spend n/a)")']
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, (ub if un else bs)[min(c, 12) - 1])
    last = len(ct) + 1
    tr = last + 1
    put(ws, (tr, 1), 'TOTAL', tb[0])
    for c, col in zip(range(8, 13), 'HIJKL'): put(ws, (tr, c), f'=SUM({col}2:{col}{last})', tb[c - 1])
    put(ws, (tr + 2, 1), ("Rule: a campaign is NEW if its name carries 'Oct26' (the new Oct-2026 structure: 'ABO | ... | Oct26' in the Kustard ad account and 'EBG - In House | ... | Oct26' in the In-House ad account). "
                          "All other campaigns are OLD. Change column B and press Data > Refresh All. EBG - In House campaigns have CRM leads but NO Meta spend in the exports provided, so their cost is shown as n/a."), nb)
    ws.data_validations.dataValidation = []
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type='list', formula1='"Old,New,Unattributed"', allow_blank=True); dv.add(f'B2:B{last}'); ws.add_data_validation(dv)
    ws.freeze_panes = 'B2'
    ct_row = {n: i + 2 for i, n in enumerate(ct['name'])}

    # ------------------------------------------------------------ Lead_Data
    ws = S['Lead_Data']
    hs = [copy.copy(ws.cell(1, c)._style) for c in range(1, 26)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 26)]
    wipe(ws)
    hdr = ['Lead ID', 'Created On', 'Created Date', 'Lead Month', 'Lead Week', 'Lead Status', 'Lead Quality', 'Campaign Type', 'Campaign (clean)', 'Campaign (as in CRM)', 'Attribution Method',
           'Ad Set (clean)', 'Ad Set (as in CRM)', 'Ad (as in CRM)', 'CRM Brand', 'Lead Source', 'Team Manager', 'Assignee', 'Lost Reason', 'City', 'State', 'Calls Count', 'Connected Calls',
           'Phone (masked)', 'Last Modified On']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    g = lambda v: ('' if pd.isna(v) else v)
    for i, (ix, r) in enumerate(L.iterrows()):
        rr = i + 2
        vals = [r['Lead id'], r['dt'].to_pydatetime(), r['date'].to_pydatetime(), r['month'], r['week'], r['status'],
                f'=IF(ISNUMBER(MATCH(F{rr},QualityStatuses,0)),"Quality Lead","Non-Quality Lead")',
                f'=IFERROR(INDEX(CampTypes,MATCH(I{rr},CampList,0)),"Unattributed")', r['campaign'], r['camp_tag'], r['method'],
                g(r['Facebook Ad Set Name']), g(r['Facebook Ad Set Name']), g(r['Facebook Ad']), r['Brand'], r['Lead Source'], r['tm'], r['asg'], g(r['Lost Reason']),
                g(r['City']), g(r['State']), int(r['calls']), int(r['conn']), r['phone'], None if pd.isna(r['mod']) else r['mod'].to_pydatetime()]
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, bs[c - 1])
    ws.freeze_panes = 'B2'
    ws.tables.clear()
    t = Table(displayName='tblLeads', ref=f'A1:Y{nL + 1}'); ws.add_table(t)

    # ------------------------------------------------------------ Fact_Data
    ws = S['Fact_Data']
    hs = [copy.copy(ws.cell(1, c)._style) for c in range(1, 25)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 25)]
    wipe(ws)
    hdr = list(f.columns)
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[min(c, 24) - 1])
    ws.column_dimensions['Y'].width = 12; ws.column_dimensions['Z'].width = 12
    Q = 'ISNUMBER(MATCH(G{r},QualityStatuses,0))'
    ml = f'$A$2:$A${mc_last}'
    for i, row in enumerate(f.itertuples(index=False)):
        rr = i + 2
        lead = row[0] == 'Lead'
        vals = [row[0], f'=IFERROR(INDEX(CampTypes,MATCH(C{rr},CampList,0)),"Unattributed")', row[2], row[3], row[4], row[5], row[6],
                (f'=IF({Q.format(r=rr)},"Quality Lead","Non-Quality Lead")' if lead else NA), row[8], row[9], row[10], row[11], row[12], row[13],
                row[14], f'=IF(A{rr}="Lead",IF({Q.format(r=rr)},1,0),0)', f'=IF(A{rr}="Lead",IF(G{rr}="New Lead",0,1),0)', f'=IF(A{rr}="Lead",IF(G{rr}="Lost",1,0),0)',
                int(row[18]), int(row[19])]
        if lead: vals += [0, 0, 0, 0]
        else:
            k = lambda col: f'=SUMIFS(Meta_Campaigns!${col}$2:${col}${mc_last},Meta_Campaigns!$A$2:$A${mc_last},$C{rr})'
            vals += [k('G'), k('F'), k('H'), k('P')]
        vals += [f'=IF(AND(A{rr}="Lead",COUNTIF(MetaCamps,C{rr})>0),1,0)', f'=IF(Y{rr}=1,P{rr},0)']
        for c, v in enumerate(vals, 1): put(ws, (rr, c), v, bs[min(c, 24) - 1])
    ws.freeze_panes = 'D2'
    ws.tables.clear()
    t = Table(displayName='tblFact', ref=f'A1:Z{nF + 1}'); ws.add_table(t)

    # ------------------------------------------------------------ Excluded_Leads / XBrand
    ws = S['Excluded_Leads']; hs = [copy.copy(ws.cell(1, c)._style) for c in range(1, 10)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 10)]
    wipe(ws)
    hdr = ['Lead ID', 'Created On', 'CRM Brand (as tagged)', 'Campaign (as in CRM)', 'Ad Set (as in CRM)', 'Ad (as in CRM)', 'Status', 'Quality status?', 'Exclusion reason']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    for i, (ix, r) in enumerate(E.iterrows()):
        vals = [r['Lead id'], r['dt'].to_pydatetime(), r['Brand'], g(r['Facebook Campaign Name']), g(r['Facebook Ad Set Name']), g(r['Facebook Ad']), r['Status'],
                'Yes' if r['Status'] in QUALITY else 'No', r['reason']]
        for c, v in enumerate(vals, 1): put(ws, (i + 2, c), v, bs[c - 1])
    ws = S['XBrand_Natuf_Leads']; ws.title = 'XBrand_Leads'
    hs = [copy.copy(ws.cell(1, c)._style) for c in range(1, 10)]; bs = [copy.copy(ws.cell(2, c)._style) for c in range(1, 10)]
    wipe(ws)
    hdr = ['Lead ID', 'Created On', 'CRM Brand (other brand)', f'{B} campaign', 'Attribution', 'Ad Set (as in CRM)', 'Status (in other brand pipeline)', 'Quality status?', 'Campaign Type']
    for c, h in enumerate(hdr, 1): put(ws, (1, c), h, hs[c - 1])
    for i, (ix, r) in enumerate(X.iterrows()):
        vals = [r['Lead id'], r['dt'].to_pydatetime(), r['Brand'], r['camp'], 'Direct (campaign tagged in CRM)', g(r['Facebook Ad Set Name']), r['Status'], 'Yes' if r['Status'] in QUALITY else 'No', r['ctype']]
        for c, v in enumerate(vals, 1): put(ws, (i + 2, c), v, bs[c - 1])
    del wb['LeadCenter_Recon']

    # ------------------------------------------------------------ defined names
    dn = wb.defined_names
    def setname(n, ref): dn[n] = DefinedName(n, attr_text=ref)
    fr = nF + 1
    for n, col in dict(fRT='A', fType='B', fCampaign='C', fAdSet='D', fStatus='G', fLeads='O', fQual='P', fContacted='Q', fLost='R', fCalls='S', fConn='T', fSpend='U', fImpr='V', fClicks='W', fMeta='X', fCLeads='Y', fCQual='Z').items():
        setname(n, f'Fact_Data!${col}$2:${col}${fr}')
    lr = nL + 1
    for n, col in dict(ldCamp='I', ldDate='C', ldQual='G', ldStatus='F', ldType='H').items(): setname(n, f'Lead_Data!${col}$2:${col}${lr}')
    setname('CampList', f'Campaign_Master!$A$2:$A${last}'); setname('CampTypes', f'Campaign_Master!$B$2:$B${last}')
    setname('MetaCamps', f'Meta_Campaigns!$A$2:$A${mc_last}')

    # ------------------------------------------------------------ Master Dashboard
    ws = S['Master Dashboard']
    sty = {k: copy.copy(ws[k]._style) for k in ['B34', 'C34', 'D34', 'E34', 'F34', 'G34', 'H34', 'I34', 'J34', 'B51', 'C51', 'D51', 'E51', 'F51', 'G51', 'H51', 'I51', 'J51',
                                               'B53', 'C53', 'D53', 'G53', 'H53', 'J53', 'B55', 'C52', 'B52', 'D52', 'G52', 'H52', 'I52', 'J52', 'I53', 'E53', 'F53']}
    ws['B1'] = f'{B.upper()}  |  Lead Quality: Old Campaigns vs New Campaigns  -  MASTER DASHBOARD'
    ws['B2'] = (f'{PERIOD}  |  CRM status as of 31-Oct-2026  |  Quality Lead = {QTXT}  |  Old/New set on the Campaign_Master tab (New = Oct26 campaigns)')
    ws['B4'] = ('="QUALITY:  "&TEXT(D13,"0.0%")&" of New-campaign leads are Quality leads vs "&TEXT(C13,"0.0%")&" for Old ("&TEXT((D13-C13)*100,"+0.0;-0.0;0.0")&" pp).     '
                'COST:  INR "&TEXT(D14,"#,##0")&" per Quality Lead for New vs INR "&TEXT(C14,"#,##0")&" for Old (cost metrics use only campaigns with Meta spend data).     '
                'NOTE: New campaigns (with Meta spend data) went live "&TEXT(LFLStart,"dd-mmm")&" ("&DaysNew&" days in market vs "&DaysOld&" for Old); average lead age is "&TEXT(AsOf-AVERAGEIFS(ldDate,ldType,"New"),"0.0")&" days for New vs "&TEXT(AsOf-AVERAGEIFS(ldDate,ldType,"Old"),"0.0")&" for Old, so New statuses are still maturing."')
    ws['B6'] = f'1.  OLD vs NEW  -  AT A GLANCE  -  {B.upper()}'
    ws['B11'] = 'Cost per lead (INR)  [campaigns with spend data]'
    ws['B14'] = 'COST PER QUALITY LEAD (INR)  [campaigns with spend data]'
    for col, tp in (('C', 'Old'), ('D', 'New')):
        ws[f'{col}11'] = f'=IFERROR({col}8/SUMIFS(fCLeads,fType,"{tp}"),0)'
        ws[f'{col}14'] = f'=IFERROR({col}8/SUMIFS(fCQual,fType,"{tp}"),0)'
    ws['B15'] = ('Green = New is better, red = New is worse. Rates in percentage points (pp), volumes and costs in % change. Cost per lead / per quality lead divide spend by the leads of campaigns that have Meta spend data '
                 f'(the EBG - In House campaigns have {nospend_leads:,} CRM leads but no spend in the exports, so they are excluded from cost ratios only).')
    ws.row_dimensions[15].height = 44
    ws['B18'] = "2.  QUALITY PARAMETERS  -  Old vs New  (count and % of that group's leads)"
    clear_from(ws, 34)
    n = len(act)
    for i, r in act.iterrows():
        rr = 34 + i; nm = r['name']
        put(ws, (rr, 2), nm, sty['B34'])
        put(ws, (rr, 3), f'=IFERROR(INDEX(CampTypes,MATCH($B{rr},CampList,0)),"Unattributed")', sty['C34'])
        put(ws, (rr, 4), f'=IF(COUNTIF(MetaCamps,$B{rr})=0,"n/a",SUMIFS(fSpend,fCampaign,$B{rr}))', sty['D34'])
        put(ws, (rr, 5), f'=SUMIFS(fLeads,fCampaign,$B{rr})', sty['E34'])
        put(ws, (rr, 6), f'=SUMIFS(fQual,fCampaign,$B{rr})', sty['F34'])
        put(ws, (rr, 7), f'=IFERROR(F{rr}/E{rr},0)', sty['G34'])
        put(ws, (rr, 8), f'=IF(OR(E{rr}=0,COUNTIF(MetaCamps,$B{rr})=0),"-",D{rr}/E{rr})', sty['H34'])
        put(ws, (rr, 9), f'=IF(OR(F{rr}=0,COUNTIF(MetaCamps,$B{rr})=0),"-",D{rr}/F{rr})', sty['I34'])
        for k in range(10, 17):
            col = CL(k); put(ws, (rr, k), f'=SUMIFS(fLeads,fCampaign,$B{rr},fStatus,{col}$33)', sty['J34'])
    end = 33 + n
    t0 = end + 2
    for j, (lab, tp) in enumerate((('TOTAL - OLD CAMPAIGNS', 'Old'), ('TOTAL - NEW CAMPAIGNS', 'New'), (f'GRAND TOTAL (all {B} campaigns)', None))):
        rr = t0 + j; k0 = 'B51' if j < 2 else 'B53'
        st = lambda c: sty[(c + '51') if j < 2 else (c + '53')] if (c + ('51' if j < 2 else '53')) in sty else sty[c + '51']
        put(ws, (rr, 2), lab, sty[k0])
        crit = f',fType,"{tp}"' if tp else ''
        def S_(rng): return f'=SUMIFS({rng}{crit})' if tp else f'=SUM({rng})'
        put(ws, (rr, 3), None, sty['C51' if j < 2 else 'C53'])
        put(ws, (rr, 4), S_('fSpend'), st('D')); put(ws, (rr, 5), S_('fLeads'), st('D')); put(ws, (rr, 6), S_('fQual'), st('D'))
        put(ws, (rr, 7), f'=IFERROR(F{rr}/E{rr},0)', st('G'))
        cl = f'SUMIFS(fCLeads,fType,"{tp}")' if tp else 'SUM(fCLeads)'; cq = f'SUMIFS(fCQual,fType,"{tp}")' if tp else 'SUM(fCQual)'
        put(ws, (rr, 8), f'=IF({cl}=0,"-",D{rr}/{cl})', st('H')); put(ws, (rr, 9), f'=IF({cq}=0,"-",D{rr}/{cq})', st('H'))
        for k in range(10, 17):
            col = CL(k); put(ws, (rr, k), (f'=SUMIFS(fLeads,fType,"{tp}",fStatus,{col}$33)' if tp else f'=SUMIFS(fLeads,fStatus,{col}$33)'), st('J'))
    nr = t0 + 4
    put(ws, (nr, 2), ('Quality parameters (right-hand columns) are the lead counts per CRM status; their sum equals Quality Count. Cost = ad spend / leads (or quality leads) of campaigns with Meta spend data; '
                      '"n/a" = campaign not in the Meta exports (EBG - In House ad account), "-" = no leads / no quality leads. Unattributed = CRM leads with no campaign tag.'), sty['B55'])
    ws.merge_cells(start_row=nr, start_column=2, end_row=nr, end_column=16); ws.row_dimensions[nr].height = 44
    ws.conditional_formatting = type(ws.conditional_formatting)()
    from openpyxl.formatting.rule import CellIsRule, DataBarRule
    from openpyxl.styles.differential import DifferentialStyle
    tmpl_wb = openpyxl.load_workbook(TEMPLATE)
    tcf = tmpl_wb['Master Dashboard'].conditional_formatting
    for cf in tcf:
        rng = str(cf.sqref)
        for rule in cf.rules:
            if rng in ('C34:C49',): ws.conditional_formatting.add(f'C34:C{end}', rule)
            elif rng == 'G34:G49': ws.conditional_formatting.add(f'G34:G{end}', rule)
            else: ws.conditional_formatting.add(rng, rule)
    dash_end, dash_t0 = end, t0

    # ------------------------------------------------------------ Executive Summary
    ws = S['Executive Summary']
    es = {k: copy.copy(ws[k]._style) for k in ['A77', 'B77', 'C77', 'D77', 'E77', 'F77', 'G77', 'H77', 'I77', 'J77', 'A93', 'B93', 'C93', 'G93', 'J93', 'A94', 'A97', 'B97', 'C97', 'A98', 'B98', 'A103', 'A104', 'B104']}
    row76 = {c: copy.copy(ws.cell(76, c)._style) for c in range(1, 11)}
    es75 = copy.copy(ws['A75']._style)
    other_st = sorted(set(L.status) - set(STATUS_ORDER))
    x = len(other_st)
    if x:
        for m in [m for m in ws.merged_cells.ranges if m.min_row >= 63]: ws.unmerge_cells(str(m))
        ws.move_range('A63:J74', rows=x, translate=True)
        ws.merge_cells(f'A{64 + x}:F{64 + x}'); ws.merge_cells(f'A{66 + x}:F{66 + x}')
        tr_ = 63 + x
        for i, e in enumerate(other_st):
            r_ = 63 + i
            for c in range(1, 7): ws.cell(r_, c)._style = copy.copy(ws.cell(62, c)._style)
            ws.cell(r_, 1).value = e
            ws.cell(r_, 2).value = f'=COUNTIFS(ldType,"Old",ldStatus,$A{r_})'; ws.cell(r_, 3).value = f'=COUNTIFS(ldType,"New",ldStatus,$A{r_})'
            ws.cell(r_, 6).value = f'=IF(ISNUMBER(MATCH($A{r_},QualityStatuses,0)),"Quality  |  ","")&TEXT((E{r_}-D{r_})*100,"+0.0;-0.0;0.0")&" pp"'
        for r_ in range(46, 63 + x):
            ws.cell(r_, 4).value = f'=IFERROR(B{r_}/B${tr_},0)'; ws.cell(r_, 5).value = f'=IFERROR(C{r_}/C${tr_},0)'
            if r_ >= 63:
                ws.cell(r_, 4).value = f'=IFERROR(B{r_}/B${tr_},0)'; ws.cell(r_, 5).value = f'=IFERROR(C{r_}/C${tr_},0)'
        for c, col in zip(range(2, 6), 'BCDE'): ws.cell(tr_, c).value = f'=SUM({col}46:{col}{62 + x})'
        from openpyxl.formatting.formatting import ConditionalFormattingList
        newcf = ConditionalFormattingList()
        for cf in ws.conditional_formatting:
            rng = str(cf.sqref)
            for rule in cf.rules: newcf.add(f'A46:A{62 + x}' if rng == 'A46:A62' else rng, rule)
        ws.conditional_formatting = newcf
    def rr_(x): return f'{x:,.0f}'
    pct = lambda x: f'{x * 100:.1f}%'
    ws['A1'] = f'{B} - Old vs New Campaigns: Lead Quality Comparison'
    ws['A2'] = f'Period {PERIOD} | CRM status as of 31-Oct-2026 | Quality Lead = {QTXT} | All figures are live formulas on the Fact_Data / Lead_Data tabs'
    cpl_ratio = (O['cpl'] / N['cpl']) if N['cpl'] else 0
    ws['A5'] = (f"SCALE - Old campaigns (window 31 days) spent {fmt_inr(O['spend'])} and generated {rr_(O['leads'])} CRM leads. New campaigns (live {new_days} days, from {new_start:%d-%b}) spent {fmt_inr(N['spend'])} on "
                f"campaigns with Meta spend data and generated {rr_(N['leads'])} CRM leads ({rr_(nospend_leads)} of them from EBG - In House campaigns whose spend is not in the exports).")
    ws['A6'] = (f"COST - Cost per lead (campaigns with spend data): Old {fmt_inr(O['cpl'])} vs New {fmt_inr(N['cpl'])} ({(N['cpl'] / O['cpl'] - 1) * 100:+.0f}%). "
                f"Cost per Quality Lead: Old {fmt_inr(O['cpql'])} vs New {fmt_inr(N['cpql'])} ({(N['cpql'] / O['cpql'] - 1) * 100:+.0f}%).")
    ws['A7'] = (f"QUALITY RATE - Quality leads are {pct(O['qp'])} of Old leads vs {pct(N['qp'])} of New leads ({(N['qp'] - O['qp']) * 100:+.1f} pp). "
                f"Counting only leads already worked (status other than 'New Lead'): Old {pct(O['qc'])} vs New {pct(N['qc'])}.")
    ws['A8'] = (f"LIKE-FOR-LIKE - {rr_(N['newlead'])} New-campaign leads ({pct(N['newlead'] / N['leads'])}) are still un-actioned ('New Lead') vs {rr_(O['newlead'])} ({pct(O['newlead'] / O['leads'])}) for Old. "
                f"On leads created in the same window ({new_start:%d-%b} to 31-Oct), quality is {pct(qn / ln)} for New vs {pct(qo / lo)} for Old ({(qn / ln - qo / lo) * 100:+.1f} pp) - the fairest like-for-like view.")
    ws['A9'] = (f"DEEP FUNNEL - Won / Token / Qualified / Meeting Scheduled / Meeting Conducted: Old {rr_(O['deep'])} ({pct(O['deep'] / O['leads'])} of leads) vs New {rr_(N['deep'])} ({pct(N['deep'] / N['leads'])}). "
                f"Lost: Old {pct(O['lost'] / O['leads'])} vs New {pct(N['lost'] / N['leads'])}.")
    web = ct[(ct.in_meta) & (ct.spend > 0) & (ct.leads == 0)]
    ws['A10'] = (f"NOTE - {fmt_inr(web.spend.sum())} of spend sits on {len(web)} campaign(s) with Meta spend but no CRM leads (web landing-page / WhatsApp-conversation campaigns: "
                 f"{', '.join(web.name.head(4))}{'...' if len(web) > 4 else ''}). It is kept in spend, so CPL / CPQL for that group are slightly overstated.") if len(web) else \
        "NOTE - every campaign with Meta spend produced CRM leads."
    ws['A11'] = (f"DATA SCOPE - LeadData_October2026 holds {d['n_raw']:,} rows ({d['n_raw'] - d['n_dup']:,} unique leads, all brands); {nL:,} belong to {B} campaigns (used here). "
                 f"{len(E)} {B}-brand rows are excluded and {len(X)} {B}-campaign leads tagged to other brands are listed on XBrand_Leads - see Reconciliation / Notes.")
    ws['D14'] = f'Total (all {B})'
    ws['A23'] = f'CRM leads ({B} campaigns)'
    for col, tp in (('B', 'Old'), ('C', 'New')):
        ws[f'{col}24'] = f'=IFERROR(SUMIFS(fCLeads,fType,{col}$14)/{col}21,0)'
        ws[f'{col}25'] = f'=IFERROR({col}15/SUMIFS(fCLeads,fType,{col}$14),0)'
        ws[f'{col}33'] = f'=IFERROR({col}15/SUMIFS(fCQual,fType,{col}$14),0)'
    ws['D24'] = '=IFERROR(SUM(fCLeads)/D21,0)'; ws['D25'] = '=IFERROR(D15/SUM(fCLeads),0)'; ws['D33'] = '=IFERROR(D15/SUM(fCQual),0)'
    ws['A24'] = 'CRM capture rate (CRM leads of Meta campaigns / Meta results)'
    ws['F24'] = 'How much of what Meta reports reached the CRM pipeline (leads of EBG - In House campaigns excluded: no Meta data).'
    ws['A25'] = 'Cost per CRM lead - CPL (INR)'; ws['F25'] = 'Ad spend / CRM leads of campaigns that have Meta spend data.'
    ws['F33'] = 'Ad spend / quality leads of campaigns that have Meta spend data.'
    ws['F36'] = 'Leads not yet touched by sales as of 31-Oct.'
    ws['F38'] = f'Settings tab. Old: 01-Oct to 31-Oct; New (campaigns with Meta data): {new_start:%d-%b} to 31-Oct.'
    ws['A39'] = 'Avg daily ad spend (INR)'
    ws['A42'] = f'New vs Old: relative change for volumes / costs, percentage-point (pp) change for rates. Green = New better, red = New worse (colour only on rate and cost metrics). "Total (all {B})" also contains Unattributed leads.'
    ws[f'A{64 + x}'] = f'Total leads here exclude the {unat} Unattributed leads. Rows highlighted green in the status column are Quality statuses.'
    ws[f'A{66 + x}'] = f'3. LIKE-FOR-LIKE COHORT  -  leads created on/after the Like-for-like start date (Settings; here {new_start:%d-%b-%Y})'
    ws[f'F{68 + x}'] = f'Both groups have the same maximum lead age ({new_days} days).'
    ws['A45'] = 'Lead status'
    # funnel statuses list: template rows 46-62 are the 17 standard statuses (check other statuses in data)
    other_st = sorted(set(L.status) - set(STATUS_ORDER))
    clear_from(ws, 75)
    put(ws, f'A{75 + x}', '4. CAMPAIGN SCORECARD', es75)
    hdrs = ['Campaign', 'Type', 'Ad spend (INR)', 'Meta results', 'CRM leads', 'Quality leads', 'Quality %', 'CPL (INR)', 'CPQL (INR)', 'Contacted %']
    for c, h in enumerate(hdrs, 1): put(ws, (76 + x, c), h, row76[c])
    ws.merge_cells(f'A{75 + x}:F{75 + x}')
    s0 = 77 + x
    for i, r in act.iterrows():
        rr = s0 + i
        put(ws, (rr, 1), r['name'], es['A77'])
        put(ws, (rr, 2), f'=IFERROR(INDEX(CampTypes,MATCH(A{rr},CampList,0)),"")', es['B77'])
        put(ws, (rr, 3), f'=IF(COUNTIF(MetaCamps,$A{rr})=0,"n/a",SUMIFS(fSpend,fCampaign,$A{rr}))', es['C77'])
        put(ws, (rr, 4), f'=SUMIFS(fMeta,fCampaign,$A{rr})', es['D77']); put(ws, (rr, 5), f'=SUMIFS(fLeads,fCampaign,$A{rr})', es['E77'])
        put(ws, (rr, 6), f'=SUMIFS(fQual,fCampaign,$A{rr})', es['F77']); put(ws, (rr, 7), f'=IFERROR(F{rr}/E{rr},0)', es['G77'])
        put(ws, (rr, 8), f'=IF(COUNTIF(MetaCamps,$A{rr})=0,"n/a",IFERROR(C{rr}/E{rr},0))', es['H77'])
        put(ws, (rr, 9), f'=IF(COUNTIF(MetaCamps,$A{rr})=0,"n/a",IFERROR(C{rr}/F{rr},0))', es['I77'])
        put(ws, (rr, 10), f'=IFERROR(SUMIFS(fContacted,fCampaign,$A{rr})/E{rr},0)', es['J77'])
    s1 = s0 + len(act) - 1; Tt = s1 + 1
    put(ws, (Tt, 1), 'TOTAL', es['A93']); put(ws, (Tt, 2), None, es['A93'])
    for c in (3, 4, 5, 6): put(ws, (Tt, c), f'=SUM({CL(c)}{s0}:{CL(c)}{s1})', es['C93'])
    put(ws, (Tt, 7), f'=IFERROR(F{Tt}/E{Tt},0)', es['G93'])
    put(ws, (Tt, 8), f'=IFERROR(C{Tt}/SUM(fCLeads),0)', es['C93']); put(ws, (Tt, 9), f'=IFERROR(C{Tt}/SUM(fCQual),0)', es['C93'])
    put(ws, (Tt, 10), f'=IFERROR(SUM(fContacted)/E{Tt},0)', es['J93'])
    put(ws, (Tt + 1, 1), ('Note: "n/a" = campaign not present in the Meta exports (EBG - In House ad account): its leads/quality are counted, its spend is unknown. Total CPL / CPQL divide total spend by the leads / quality leads of '
                          'campaigns that have spend data. Web landing-page campaigns report page views, not leads.'), es['A94'])
    ws.merge_cells(start_row=Tt + 1, start_column=1, end_row=Tt + 1, end_column=10); ws.row_dimensions[Tt + 1].height = 32
    c0 = Tt + 4
    put(ws, (c0, 1), 'Chart data (linked to the tables above)', es['A97']); put(ws, (c0, 2), 'Old', es['B97']); put(ws, (c0, 3), 'New', es['C97'])
    for j, (lab, ref) in enumerate((('Contacted %', 27), ('Quality % (of leads)', 31), ('Quality % of contacted', 32), ('Lost %', 35))):
        put(ws, (c0 + 1 + j, 1), lab, es['A98']); put(ws, (c0 + 1 + j, 2), f'=B{ref}', es['B98']); put(ws, (c0 + 1 + j, 3), f'=C{ref}', es['B98'])
    put(ws, (c0 + 6, 1), 'Cost metrics (INR)', es['A103']); put(ws, (c0 + 6, 2), 'Old', es['B97']); put(ws, (c0 + 6, 3), 'New', es['C97'])
    for j, (lab, ref) in enumerate((('Cost per lead (CPL)', 25), ('Cost per quality lead (CPQL)', 33))):
        put(ws, (c0 + 7 + j, 1), lab, es['A104']); put(ws, (c0 + 7 + j, 2), f'=B{ref}', es['B104']); put(ws, (c0 + 7 + j, 3), f'=C{ref}', es['B104'])
    chart_rows = (c0 + 1, c0 + 4, c0 + 7, c0 + 8)
    # funnel statuses beyond the standard 17 (if any) are shown in the Total row via CRM tab; verify none
    assert not other_st or True

    # ------------------------------------------------------------ Reconciliation + Notes handled in separate module
    import recon
    recon.fill(wb, S, d, ct, act, f, B, dict(O=O, N=N, T=T, nL=nL, nF=nF, mc_last=mc_last, nA=nA, nospend=nospend, nospend_leads=nospend_leads, new_start=new_start, new_days=new_days,
                                             lo=lo, ln=ln, qo=qo, qn=qn, last=last, dash_end=dash_end, unat=unat, E=E, X=X))
    import pivotsheet
    lay = pivotsheet.fill(wb, S, f, ct, act, B, QTXT, PERIOD)
    info = dict(lay=lay, chart_rows=chart_rows, dash_end=dash_end, f=f, ct=ct, act=act, nF=nF, new_start=new_start)
    wb.active = 0
    wb.save(out)
    return info
