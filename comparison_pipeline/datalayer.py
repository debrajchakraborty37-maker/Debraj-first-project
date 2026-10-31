"""Data layer: clean raw exports -> per-brand tables used to build the workbook, plus independent KPIs."""
import re, glob
import pandas as pd, numpy as np
from collections import Counter
from mapadsets import solve, S

RAW = '/tmp/claude-0/work/raw/COMPARISON/'
QUALITY = ["Won", "Token Received", "Qualified", "Meeting Scheduled", "Meeting Conducted", "Follow-Up", "Details Shared"]
STATUS_ORDER = ["Won", "Token Received", "Qualified", "Meeting Scheduled", "Meeting Conducted", "Follow-Up", "Details Shared",
                "Connected", "Attempt 1", "Attempt 2", "Attempt 3", "Attempt 4", "Attempt 5", "New Lead", "Nurture",
                "Meeting Conducted but NOT QUALIFIED", "Lost"]
CFG = {
    'Natuf': dict(prefix='Natuf-x-Gen-Y-(Current-Kustard)',
                  groups=['In House Natuf', 'Natuf', 'Natuf_MF', 'FW-Natuf', 'FW-Shayreen by Natuf'],
                  kw=re.compile(r'natuf', re.I), alias={}),
    'Carlton': dict(prefix='Kustard-__-Carlton-(New)',
                    groups=['Carlton Salon', 'In House Carlton Salon', 'Carlton Wellness Center', 'In House Carlton Wellness',
                            'Carlton_Salon_MF', 'FW-Carlton Salon', 'FW-Carlton Wellness Center', 'FW-Carlton_Salon_MF', 'FW-Carlon Spa'],
                    kw=re.compile(r'carlton|\bCW\b', re.I),
                    alias={'ABO | CW | WhatsApp | Unit Franchise | India | Oct26 | V2': 'ABO | CW | WhatsApp | Unit Franchise | India | Oct26 | V1'}),
}
WIN_START, WIN_END = pd.Timestamp('2026-10-01'), pd.Timestamp('2026-10-31')


NEW = set()
NEW_SETS = {
    'Natuf': ['EBG - In House | ABO | Natuf | Leads | Unit Franchise | India | Oct26 | V1',
              'Natuf | In House | ABO |  | WhatsApp | Unit Franchise | India | Oct26 | V1'],
    'Carlton': ['EBG - In House | ABO | CW Salon | WhatsApp | Unit Franchise | India | Oct26 | V1',
                'EBG - In House | ABO | CW | Leads | Unit Franchise | India | Oct26 | V2',
                'EBG - In House | ABO | CW Salon | Leads | Unit Franchise | India | Oct26 | V1'],
}


def is_new(name):
    return name in NEW


def load_leads():
    df = pd.read_csv(RAW + 'LeadData_October2026.csv', dtype=str, encoding='utf-8-sig', low_memory=False)
    n_raw = len(df)
    df['dt'] = pd.to_datetime(df['Created On'], format='%d/%m/%Y %H:%M:%S')
    df['mod'] = pd.to_datetime(df['Modified On'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    dups = df[df['Lead id'].duplicated(keep='first')]
    df = df.drop_duplicates('Lead id', keep='first').copy()
    return df, n_raw, len(dups)


def blank(x):
    return pd.isna(x) or str(x).strip() in ('', '_', '-')


def build(brand):
    cfg = CFG[brand]
    NEW.clear(); NEW.update(NEW_SETS[brand])
    df, n_raw, n_dup = load_leads()
    camp = pd.read_csv(RAW + f"{cfg['prefix']}-Campaigns-1-Oct-2026-31-Oct-2026.csv")
    adst = pd.read_csv(RAW + f"{cfg['prefix']}-Ad-sets-1-Oct-2026-31-Oct-2026.csv")
    ads = pd.read_csv(RAW + f"{cfg['prefix']}-Ads-1-Oct-2026-31-Oct-2026.csv")
    meta_names = list(camp['Campaign name'])
    U = set(meta_names)
    ingroup = df['Brand'].isin(cfg['groups'])
    # extra (CRM-only) campaigns of this brand: tags on in-group rows that carry brand keyword and are not in Meta
    tags = df.loc[ingroup, 'Facebook Campaign Name'].fillna('_')
    extra = sorted({t for t in tags if t not in U and not blank(t) and (cfg['kw'].search(t)) and t not in cfg['alias']})
    # which extras are really this brand: must contain Oct26-style structure or keyword; others (e.g. AAC, Nonstop) are excluded by kw
    extra = sorted(set(extra) | set(NEW_SETS[brand]) - U)
    universe = U | set(extra)

    def resolve(tag):
        t = cfg['alias'].get(tag, tag)
        return t if t in universe else None

    df['camp_tag'] = df['Facebook Campaign Name'].fillna('_')
    df['camp_res'] = df['camp_tag'].map(resolve)
    df['alias_used'] = df['camp_tag'].isin(cfg['alias'])
    rows_in, excl, xb = [], [], []
    for ix, r in df.iterrows():
        tag_ok = isinstance(r['camp_res'], str)
        if r['Brand'] in cfg['groups']:
            if tag_ok:
                rows_in.append((ix, r['camp_res'], 'Alias (CRM campaign name differs from Meta name)' if r['alias_used'] else 'Direct (campaign tagged in CRM)'))
            elif blank(r['camp_tag']):
                if r['Lead Source'] in ('Facebook', 'Whatsapp Cloud API'):
                    rows_in.append((ix, '(Unattributed)', 'No campaign tag in CRM (paid/WhatsApp lead, campaign blank)'))
                else:
                    excl.append((ix, f"No campaign and no ad set in CRM; lead source = {r['Lead Source']} (bulk/manual upload, not a campaign lead)"))
            else:
                excl.append((ix, "Tagged to a " + brand + " brand in CRM but the campaign belongs to another brand / is not a " + brand + " campaign"))
        elif tag_ok:
            xb.append((ix, r['camp_res']))
    inx = pd.DataFrame(rows_in, columns=['ix', 'campaign', 'method']).set_index('ix')
    L = df.loc[inx.index].copy()
    L['campaign'] = inx['campaign']
    L['method'] = inx['method']
    L['ctype'] = L['campaign'].map(lambda c: 'Unattributed' if c == '(Unattributed)' else ('New' if is_new(c) else 'Old'))
    L['status'] = L['Status']
    L['qual'] = L['status'].isin(QUALITY)
    L['date'] = L['dt'].dt.normalize()
    L['month'] = L['dt'].dt.strftime('%Y-%m')
    L['week'] = (L['date'] - pd.to_timedelta(L['dt'].dt.weekday, unit='D')).dt.strftime('Wk of %Y-%m-%d')
    L['tm'] = L['Assignee Manager name'].map(lambda x: '(Unassigned)' if blank(x) else x)
    L['asg'] = L['Assignee name'].map(lambda x: '(Unassigned)' if blank(x) else x)
    L['phone'] = L['Phone'].map(lambda p: 'XXXXXX' + re.sub(r'\D', '', str(p))[-4:] if isinstance(p, str) else '')
    L['calls'] = pd.to_numeric(L['Calls Count'], errors='coerce').fillna(0).astype(int)
    L['conn'] = pd.to_numeric(L['Connected Call Count'], errors='coerce').fillna(0).astype(int)
    L = L.sort_values('dt', ascending=False)
    E = df.loc[[i for i, _ in excl]].copy()
    E['reason'] = [r for _, r in excl]
    E = E.sort_values('dt', ascending=False)
    X = df.loc[[i for i, _ in xb]].copy()
    X['camp'] = [c for _, c in xb]
    X['ctype'] = X['camp'].map(lambda c: 'New' if is_new(c) else 'Old')
    X = X.sort_values('dt', ascending=False)
    # ad set -> campaign mapping (exact-sum ILP)
    pairs = Counter(zip(L['campaign'], L['Facebook Ad Set Name']))
    act, camps_nz, res, aff = solve(adst, camp, pairs)
    assert res.x is not None, 'ad set mapping infeasible'
    x = res.x.reshape(len(act), len(camps_nz)).round().astype(int)
    adst['mapped'] = None
    for i, ix in enumerate(act.index):
        adst.loc[ix, 'mapped'] = camps_nz.loc[x[i].argmax(), 'Campaign name']
    adst['active'] = adst.index.isin(act.index).astype(int)
    for ix in adst.index[adst['active'] == 0]:
        nm = re.sub(r'[^a-z0-9]', '', adst.loc[ix, 'Ad set name'].lower())
        cand = [c for c in meta_names if nm.startswith(re.sub(r'[^a-z0-9]', '', c.lower())[:16]) and len(c) > 8]
        adst.loc[ix, 'mapped'] = cand[0] if cand else '(inactive - not mapped)'
    return dict(brand=brand, cfg=cfg, camp=camp, adst=adst, ads=ads, L=L, E=E, X=X, meta_names=meta_names,
                extra=extra, universe=universe, n_raw=n_raw, n_dup=n_dup, df=df)


def kpis(d):
    """Independent pandas KPIs for verification."""
    L, camp = d['L'], d['camp']
    sp = camp.groupby(camp['Campaign name'].map(lambda c: 'New' if is_new(c) else 'Old'))['Amount spent (INR)'].sum()
    out = {}
    for t in ['Old', 'New', 'Unattributed']:
        s = L[L.ctype == t]
        out[t] = dict(spend=float(round(sp.get(t, 0), 2)), leads=len(s), qual=int(s.qual.sum()),
                      newlead=int((s.status == 'New Lead').sum()), contacted=int((s.status != 'New Lead').sum()),
                      lost=int((s.status == 'Lost').sum()))
    return out


if __name__ == '__main__':
    import sys
    for b in ['Natuf', 'Carlton']:
        d = build(b)
        print('=====', b, 'raw', d['n_raw'], 'dups', d['n_dup'], 'in-scope', len(d['L']), 'excluded', len(d['E']), 'xbrand', len(d['X']))
        print('extra campaigns:', d['extra'])
        print(d['L'].method.value_counts().to_dict())
        k = kpis(d)
        for t, v in k.items(): print(t, v, 'q%', round(v['qual'] / v['leads'] * 100, 1) if v['leads'] else 0)
        print(d['E'].reason.value_counts().to_dict())
        print(d['L'].groupby(['campaign', 'ctype']).size().to_string())
        pd.to_pickle(d, f'/tmp/claude-0/work/{b}.pkl')
