import pandas as pd, numpy as np, re
from scipy.optimize import milp, LinearConstraint, Bounds
S='Amount spent (INR)'
def norm(s): return re.sub(r'[^a-z0-9]','',str(s).lower())
def solve(a,c,crm_pairs):
    """a: adsets df, c: campaigns df, crm_pairs: Counter {(campaign, adset_name): n}"""
    act=a[(a[S]>0)|(a['Impressions']>0)|(a['Results'].fillna(0)>0)|(a['Link clicks'].fillna(0)>0)].copy()
    camps=c[(c[S]>0)|(c['Impressions']>0)].reset_index(drop=True)
    n,m=len(act),len(camps)
    # affinity
    aff=np.zeros((n,m))
    for i,(ix,r) in enumerate(act.iterrows()):
        for j,cr in camps.iterrows():
            v=0
            k=crm_pairs.get((cr['Campaign name'],r['Ad set name']),0)
            v+=min(k,50)  # CRM evidence
            if norm(cr['Campaign name'])[:12] and norm(r['Ad set name']).startswith(norm(cr['Campaign name'])[:14]): v+=100
            aff[i,j]=v
    # variables x[i,j]
    nv=n*m
    cons=[];lo=[];hi=[]
    A=np.zeros((n,nv))
    for i in range(n): A[i,i*m:(i+1)*m]=1
    cons.append(A);lo+= [1]*n;hi+=[1]*n
    def eq(vals,tgt_fn,name):
        M=np.zeros((m,nv)); t=[]
        for j,cr in camps.iterrows():
            for i in range(n): M[j,i*m+j]=vals[i]
            t.append(tgt_fn(cr))
        cons.append(M);lo.extend(t);hi.extend(t)
    eq(np.round(act[S].values*100).astype(np.int64).astype(float),lambda cr:round(cr[S]*100),'spend')
    eq(act['Impressions'].values.astype(float),lambda cr:cr['Impressions'],'impr')
    pass
    eq(act['Results'].fillna(0).values.astype(float),lambda cr:0 if pd.isna(cr['Results']) else cr['Results'],'res')
    res=milp(c=-aff.flatten(),constraints=[LinearConstraint(np.vstack(cons),lo,hi)],integrality=np.ones(nv),bounds=Bounds(0,1))
    return act,camps,res,aff
def run(pre,brand_leads):
    a=pd.read_csv(f'raw/COMPARISON/{pre}-Ad-sets-1-Oct-2026-31-Oct-2026.csv')
    c=pd.read_csv(f'raw/COMPARISON/{pre}-Campaigns-1-Oct-2026-31-Oct-2026.csv')
    from collections import Counter
    cp=Counter(zip(brand_leads['Facebook Campaign Name'],brand_leads['Facebook Ad Set Name']))
    act,camps,res,aff=solve(a,c,cp)
    print(res.status,res.message)
    if res.x is None: return
    x=res.x.reshape(len(act),len(camps)).round().astype(int)
    act['camp']=[camps.loc[x[i].argmax(),'Campaign name'] for i in range(len(act))]
    act['aff']=[aff[i,x[i].argmax()] for i in range(len(act))]
    return act
if __name__=='__main__':
    df=pd.read_pickle('lead.pkl')
    pd.set_option('display.width',250); pd.set_option('display.max_colwidth',70); pd.set_option('display.max_rows',500)
    for pre,pat in [('Natuf-x-Gen-Y-(Current-Kustard)','natuf'),('Kustard-__-Carlton-(New)','carlton|\\| CW')]:
        bl=df[df['Facebook Campaign Name'].fillna('').str.contains(pat,case=False)]
        act=run(pre,bl)
        print(act[['Ad set name','camp','aff',S,'Results']].to_string())
