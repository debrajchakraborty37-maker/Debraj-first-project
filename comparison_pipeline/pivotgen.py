"""Generate pivot cache / pivot tables / slicer caches consistent with the new Fact table (based on the template XML)."""
import re
from xml.sax.saxutils import escape, quoteattr
import pandas as pd
from facts import FACT_COLS, NA
from datalayer import STATUS_ORDER

TN = '/tmp/claude-0/work/tn/xl/'
SHARED = {0: 'Record Type', 1: 'Campaign Type', 2: 'Campaign', 6: 'Lead Status', 8: 'Lead Month', 9: 'Lead Week'}
NUMF = {14: '0', 15: '3', 16: '3', 17: '3', 18: '0', 19: '0', 20: '0', 21: '0', 22: '0', 23: '0', 24: '3', 25: '3'}
CALC = [('Quality Pct', "'Quality Count'/'Lead Count'"), ('Contacted Pct', "'Contacted Count'/'Lead Count'"),
        ('QoC Pct', "'Quality Count'/'Contacted Count'"), ('Lost Pct', "'Lost Count'/'Lead Count'"),
        ('CPL', "'Spend INR'/'Costed Lead Count'"), ('CPQL', "'Spend INR'/'Costed Quality Count'"),
        ('CTR', "'Link Clicks'/Impressions"), ('Capture Pct', "'Costed Lead Count'/'Meta Results Count'"),
        ('Call Connect Pct', "'Connected Calls'/'Calls Count'"), ('Calls per Lead', "'Calls Count'/'Lead Count'")]
MAP_OLD2NEW = lambda n: n + 2 if n >= 24 else n   # template field index -> new index


def orders(f, ct_active_names):
    """display (= shared item) order for the six shared-item fields"""
    st = list(f['Lead Status'].unique())
    ordered = [s for s in STATUS_ORDER if s in st] + sorted(s for s in st if s not in STATUS_ORDER and s != NA) + ([NA] if NA in st else [])
    weeks = sorted(w for w in f['Lead Week'].unique() if w != NA)
    months = sorted(m for m in f['Lead Month'].unique() if m != NA)
    camps = [c for c in ct_active_names if c in set(f['Campaign'])]
    for c in f['Campaign'].unique():
        if c not in camps: camps.append(c)
    types = [t for t in ['Old', 'New', 'Unattributed'] if t in set(f['Campaign Type'])]
    return {0: ['Lead', 'Spend'], 1: types, 2: camps, 6: ordered, 8: months + [NA], 9: weeks + [NA]}


def cache_def(f, od, tmpl_def):
    head = tmpl_def[:tmpl_def.index('<cacheFields')]
    head = re.sub(r'recordCount="\d+"', f'recordCount="{len(f)}"', head)
    parts = []
    for i, name in enumerate(FACT_COLS):
        nf = NUMF.get(i)
        if i in SHARED:
            items = ''.join(f'<s v={quoteattr(v)}/>' for v in od[i])
            parts.append(f'<cacheField name="{name}" numFmtId="0"><sharedItems count="{len(od[i])}">{items}</sharedItems></cacheField>')
        elif nf is not None:
            s = f[name]
            integer = all(float(x).is_integer() for x in s)
            attrs = 'containsSemiMixedTypes="0" containsString="0" containsNumber="1"' + (' containsInteger="1"' if integer else '')
            mn, mx = s.min(), s.max()
            fmt = lambda x: repr(int(x)) if integer else repr(float(x))
            parts.append(f'<cacheField name="{name}" numFmtId="{nf}"><sharedItems {attrs} minValue="{fmt(mn)}" maxValue="{fmt(mx)}"/></cacheField>')
        else:
            parts.append(f'<cacheField name="{name}" numFmtId="0"><sharedItems/></cacheField>')
    for k, (n, fm) in enumerate(CALC):
        parts.append(f'<cacheField name="{n}" numFmtId="0" formula="{fm}" databaseField="0"/>')
    tail = '<extLst>' + tmpl_def.split('<extLst>')[1]
    return head + f'<cacheFields count="{len(parts)}">' + ''.join(parts) + '</cacheFields>' + tail


def cache_records(f, od):
    idx = {i: {v: k for k, v in enumerate(od[i])} for i in SHARED}
    head = open(TN + 'pivotCache/pivotCacheRecords1.xml').read()
    head = head[:head.index('<r>')]
    head = re.sub(r'count="\d+"', f'count="{len(f)}"', head, count=1)
    out = [head]
    cols = list(f.columns)
    arr = f.to_numpy(dtype=object)
    for row in arr:
        r = []
        for i, v in enumerate(row):
            if i in SHARED: r.append(f'<x v="{idx[i][v]}"/>')
            elif i in NUMF: r.append(f'<n v="{repr(int(v)) if float(v).is_integer() else repr(float(v))}"/>')
            else: r.append(f'<s v={quoteattr(str(v))}/>')
        out.append('<r>' + ''.join(r) + '</r>')
    out.append('</pivotCacheRecords>')
    return ''.join(out)


def _fields(od, axis, datafields, page0=False, lead_only=False):
    """pivotFields xml. axis: dict field_idx -> axis name. datafields: set of NEW indexes used as dataField"""
    out = []
    for i in range(len(FACT_COLS) + len(CALC)):
        if i in SHARED:
            n = len(od[i])
            ax = f' axis="{axis[i]}"' if i in axis else ''
            items = ''.join(f'<item x="{k}"/>' for k in range(n)) + '<item t="default"/>'
            out.append(f'<pivotField{ax} multipleItemSelectionAllowed="1" showAll="0"><items count="{n + 1}">{items}</items></pivotField>')
        elif i >= len(FACT_COLS):
            df = ' dataField="1"' if i in datafields else ''
            out.append(f'<pivotField{df} dragToRow="0" dragToCol="0" dragToPage="0" showAll="0" defaultSubtotal="0"/>')
        else:
            df = ' dataField="1"' if i in datafields else ''
            out.append(f'<pivotField{df} showAll="0"/>')
    return f'<pivotFields count="{len(out)}">' + ''.join(out) + '</pivotFields>'


def pivot_tables(f, od, lay):
    """lay: dict with refs: head, status, pct, camp -> 'B25:F34' etc.  Returns {1..4: xml} using template files as base."""
    res = {}
    lead = f[f['Record Type'] == 'Lead']
    types_present = [t for t in od[1] if t in set(lead['Campaign Type'])]
    t_idx = {t: od[1].index(t) for t in od[1]}
    # statuses present in leads (display order)
    sts = [s for s in od[6] if s in set(lead['Lead Status'])]
    s_idx = [od[6].index(s) for s in sts]

    def base(i):
        return open(TN + f'pivotTables/pivotTable{i}.xml').read()

    def swap(s, tag, new):
        return re.sub(rf'<{tag}\b.*?</{tag}>', lambda m: new, s, count=1, flags=re.S)

    def fix_df(s):
        return re.sub(r'(<dataField [^>]*?fld=")(\d+)(")', lambda m: m.group(1) + str(MAP_OLD2NEW(int(m.group(2)))) + m.group(3), s)

    def colitems(types):
        return f'<colItems count="{len(types) + 1}">' + '<i><x/></i>' + ''.join(f'<i><x v="{k}"/></i>' for k in range(1, len(types))) + '<i t="grand"><x/></i></colItems>'

    # status (4) and status % (1): axisRow field 6, axisCol field 1, axisPage field 0
    for i, key in ((4, 'status'), (1, 'pct')):
        s = base(i)
        s = swap(s, 'pivotFields', _fields(od, {0: 'axisPage', 1: 'axisCol', 6: 'axisRow'}, {14}))
        s = re.sub(r'<location [^>]*/>', lambda m: f'<location ref="{lay[key]}" firstHeaderRow="1" firstDataRow="2" firstDataCol="1" rowPageCount="1" colPageCount="1"/>', s)
        rows = ''.join('<i><x/></i>' if k == 0 else f'<i><x v="{k}"/></i>' for k in range(len(sts)))
        # rowItems index refers to position in the field's items list (= shared index)
        rows = ''.join(('<i><x/></i>' if si == 0 else f'<i><x v="{si}"/></i>') for si in s_idx) + '<i t="grand"><x/></i>'
        s = swap(s, 'rowItems', f'<rowItems count="{len(sts) + 1}">{rows}</rowItems>')
        s = swap(s, 'colItems', colitems(od[1]))
        s = fix_df(s)
        res[i] = s
    # headline (3): axisCol field 1, rows = data fields
    s = base(3)
    s = swap(s, 'pivotFields', _fields(od, {1: 'axisCol'}, {14, 15, 20, 26, 27, 28, 30, 31}))
    s = fix_df(s)
    s = re.sub(r'<location [^>]*/>', lambda m: f'<location ref="{lay["head"]}" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>', s)
    s = swap(s, 'colItems', colitems(od[1]))
    res[3] = s
    # campaign (2): rows = type > campaign
    s = base(2)
    s = swap(s, 'pivotFields', _fields(od, {1: 'axisRow', 2: 'axisRow'}, {14, 15, 20, 26, 30, 31}))
    s = fix_df(s)
    ct_of = f.drop_duplicates('Campaign').set_index('Campaign')['Campaign Type']
    rows = []
    for t in od[1]:
        rows.append('<i><x/></i>' if t_idx[t] == 0 else f'<i><x v="{t_idx[t]}"/></i>')
        for c in od[2]:
            if ct_of.get(c) == t:
                k = od[2].index(c)
                rows.append('<i r="1"><x/></i>' if k == 0 else f'<i r="1"><x v="{k}"/></i>')
    rows.append('<i t="grand"><x/></i>')
    s = swap(s, 'rowItems', f'<rowItems count="{len(rows)}">{"".join(rows)}</rowItems>')
    s = re.sub(r'<location [^>]*/>', lambda m: f'<location ref="{lay["camp"]}" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>', s)
    res[2] = s
    return res


def slicer_caches(od, which):
    """which: {n: (xml_template_path, field)}  -> regenerate <items>"""
    out = {}
    names = {1: 1, 2: 2, 3: 6, 4: 8, 5: 9}
    for n, fld in names.items():
        s = open(TN + f'slicerCaches/slicerCache{n}.xml').read()
        k = len(od[fld])
        items = ''.join(f'<i x="{j}" s="1"/>' for j in range(k))
        s = re.sub(r'<items count="\d+">.*?</items>', f'<items count="{k}">{items}</items>', s, flags=re.S)
        out[n] = s
    return out
