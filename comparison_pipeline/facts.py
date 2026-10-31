"""Builds the Fact table (pandas) + helper aggregates shared by workbook builder, pivot generator and verifier."""
import pandas as pd, numpy as np
from datalayer import QUALITY, STATUS_ORDER, is_new

FACT_COLS = ['Record Type', 'Campaign Type', 'Campaign', 'Ad Set', 'Ad', 'CRM Brand', 'Lead Status', 'Lead Quality', 'Lead Month',
             'Lead Week', 'Team Manager', 'Lead Source', 'Attribution Method', 'Lead ID', 'Lead Count', 'Quality Count',
             'Contacted Count', 'Lost Count', 'Calls Count', 'Connected Calls', 'Spend INR', 'Impressions', 'Link Clicks',
             'Meta Results Count', 'Costed Lead Count', 'Costed Quality Count']
NA = '(n/a - spend)'


def lead_type_results(r):
    ind = r['Result indicator']
    if isinstance(ind, str) and 'landing_page_view' in ind:
        return 0
    return 0 if pd.isna(r['Results']) else float(r['Results'])


def campaign_table(d):
    """One row per campaign in Campaign_Master order: Meta campaigns (file order) + CRM-only campaigns + (Unattributed)."""
    camp, L = d['camp'], d['L']
    rows = []
    for _, r in camp.iterrows():
        rows.append(dict(name=r['Campaign name'], in_meta=True, delivery=r['Campaign delivery'], ind=r['Result indicator'],
                         budget=r['Ad set budget'], spend=float(r['Amount spent (INR)']), impr=int(r['Impressions']),
                         clicks=0 if pd.isna(r['Link clicks']) else float(r['Link clicks']),
                         meta=lead_type_results(r)))
    for n in d['extra']:
        rows.append(dict(name=n, in_meta=False, delivery='not in Meta export', ind=None, budget=None, spend=0.0, impr=0, clicks=0, meta=0))
    ct = pd.DataFrame(rows)
    # duplicate campaign names in the Meta export (same name, separate rows): aggregate
    ct = ct.groupby('name', sort=False).agg(in_meta=('in_meta', 'max'), delivery=('delivery', 'first'), ind=('ind', lambda x: next((v for v in x if isinstance(v, str)), None)),
                                           budget=('budget', 'first'), spend=('spend', 'sum'), impr=('impr', 'sum'), clicks=('clicks', 'sum'), meta=('meta', 'sum')).reset_index()
    ct['type'] = ct['name'].map(lambda c: 'New' if is_new(c) else 'Old')
    cnt = L.groupby('campaign').agg(leads=('qual', 'size'), qual=('qual', 'sum'))
    ct['leads'] = ct['name'].map(cnt['leads']).fillna(0).astype(int)
    ct['qual'] = ct['name'].map(cnt['qual']).fillna(0).astype(int)
    un = dict(name='(Unattributed)', in_meta=False, delivery='n/a', ind=None, budget=None, spend=0.0, impr=0, clicks=0, meta=0, type='Unattributed',
              leads=int((L.campaign == '(Unattributed)').sum()), qual=int(L[L.campaign == '(Unattributed)'].qual.sum()))
    ct = pd.concat([ct, pd.DataFrame([un])], ignore_index=True)
    return ct


def active_campaigns(ct):
    """Campaigns shown on dashboards: any spend or leads. Old first (spend desc), New (spend desc), Unattributed last."""
    a = ct[(ct.spend > 0) | (ct.leads > 0)].copy()
    order = {'Old': 0, 'New': 1, 'Unattributed': 2}
    a['o'] = a['type'].map(order)
    return a.sort_values(['o', 'spend', 'leads'], ascending=[True, False, False]).reset_index(drop=True)


def fact_frame(d, ct):
    L = d['L']
    n = len(L)
    f = pd.DataFrame({
        'Record Type': 'Lead', 'Campaign Type': L['ctype'].values, 'Campaign': L['campaign'].values,
        'Ad Set': L['Facebook Ad Set Name'].fillna('_').values, 'Ad': L['Facebook Ad'].fillna('_').values,
        'CRM Brand': L['Brand'].values, 'Lead Status': L['status'].values,
        'Lead Quality': np.where(L['qual'], 'Quality Lead', 'Non-Quality Lead'), 'Lead Month': L['month'].values,
        'Lead Week': L['week'].values, 'Team Manager': L['tm'].values, 'Lead Source': L['Lead Source'].values,
        'Attribution Method': L['method'].values, 'Lead ID': L['Lead id'].values, 'Lead Count': 1,
        'Quality Count': L['qual'].astype(int).values, 'Contacted Count': (L['status'] != 'New Lead').astype(int).values,
        'Lost Count': (L['status'] == 'Lost').astype(int).values, 'Calls Count': L['calls'].values, 'Connected Calls': L['conn'].values,
        'Spend INR': 0.0, 'Impressions': 0, 'Link Clicks': 0, 'Meta Results Count': 0})
    meta_set = set(d['meta_names'])
    f['Costed Lead Count'] = f['Campaign'].isin(meta_set).astype(int)
    f['Costed Quality Count'] = f['Costed Lead Count'] * f['Quality Count']
    sp = ct[(ct.spend > 0) | (ct.impr > 0)]
    srows = []
    for _, r in sp.iterrows():
        srows.append({'Record Type': 'Spend', 'Campaign Type': r['type'], 'Campaign': r['name'], 'Ad Set': '(campaign level)', 'Ad': NA, 'CRM Brand': NA,
                      'Lead Status': NA, 'Lead Quality': NA, 'Lead Month': NA, 'Lead Week': NA, 'Team Manager': NA, 'Lead Source': NA,
                      'Attribution Method': NA, 'Lead ID': NA, 'Lead Count': 0, 'Quality Count': 0, 'Contacted Count': 0, 'Lost Count': 0,
                      'Calls Count': 0, 'Connected Calls': 0, 'Spend INR': r['spend'], 'Impressions': r['impr'], 'Link Clicks': r['clicks'],
                      'Meta Results Count': r['meta'], 'Costed Lead Count': 0, 'Costed Quality Count': 0})
    return pd.concat([f, pd.DataFrame(srows)], ignore_index=True)[FACT_COLS]
