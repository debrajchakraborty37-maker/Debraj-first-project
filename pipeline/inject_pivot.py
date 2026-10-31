#!/usr/bin/env python3
"""Add a real Excel PivotTable (+ slicers) to the 'Master Pivot' sheet of a recalculated brand workbook.

usage: inject_pivot.py <in.xlsx> <out.xlsx>
openpyxl cannot author PivotTables / slicers and the LibreOffice recalculation drops them, so this runs LAST and edits the xlsx
zip directly. The XML is modelled on an Excel-produced exemplar (Master Pivot of the Natuf FinalReport): same cache / pivotTable /
slicerCache / slicer / drawing structure, refreshOnLoad="1" so Excel rebuilds the table from Pivot_Data when the file is opened.
"""
import re, sys, zipfile, warnings
from xml.sax.saxutils import escape, quoteattr
import openpyxl

warnings.filterwarnings("ignore")
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
CACHE_ID_X14 = 1618273645
PIVOT_NAME = "MasterPivot"
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_config as rc
MONTHS = [rc.MLAB[m] for m in rc.MONTHS]

NUM_FIELDS = ["Amount Spent (INR)", "Impressions Delivered", "Total Clicks (all)", "Link Clicks (Meta)", "Meta Platform Leads",
              "CRM Leads Count", "Qualified Leads Count", "Meetings Scheduled Count", "Contacted Leads Count", "Not Contacted Leads Count"]
STR_FIELDS = ["Month", "Brand", "Campaign", "Delivery", "Lead attribution"]
CALC = [("Link CTR ratio", "'Link Clicks (Meta)'/'Impressions Delivered'"),
        ("CPM ratio", "'Amount Spent (INR)'/'Impressions Delivered'*1000"),
        ("Link CPC ratio", "'Amount Spent (INR)'/'Link Clicks (Meta)'"),
        ("CPL Meta ratio", "'Amount Spent (INR)'/'Meta Platform Leads'"),
        ("CPL CRM ratio", "'Amount Spent (INR)'/'CRM Leads Count'"),
        ("CPQL ratio", "'Amount Spent (INR)'/'Qualified Leads Count'"),
        ("Cost per Meeting ratio", "'Amount Spent (INR)'/'Meetings Scheduled Count'"),
        ("Qualified pct ratio", "'Qualified Leads Count'/'CRM Leads Count'"),
        ("Meeting pct ratio", "'Meetings Scheduled Count'/'CRM Leads Count'"),
        ("Contacted pct ratio", "'Contacted Leads Count'/'CRM Leads Count'")]
# (caption, field index, numFmt key)   field idx: 0 Month 1 Brand 2 Campaign 3 Delivery 4 Attr 5..14 numeric 15..24 calculated
DATA_FIELDS = [("Spend (₹)", 5, "cost"), ("Impressions", 6, 3), ("Link Clicks", 8, 3), ("Link CTR", 15, "pct"), ("Meta Leads", 9, 3),
               ("CPL – Meta (₹)", 18, "cost"), ("CRM Leads", 10, 3), ("Qualified", 11, 3), ("Qualified %", 22, "pct"), ("Meetings", 12, 3),
               ("CPL – CRM (₹)", 19, "cost"), ("CPQL (₹)", 20, "cost")]
SLICERS = [("Month", 0, "Slicer_Month"), ("Lead attribution", 4, "Slicer_Lead_attribution"), ("Delivery", 3, "Slicer_Delivery"),
           ("Campaign", 2, "Slicer_Campaign")]
COL_FIELD, ROW_FIELDS = 0, (1, 2)                 # pivot columns = Month; rows = Brand > Campaign (indices into STR_FIELDS)
ROW_CAPTION, COL_CAPTION = "Brand  ›  Campaign", "Month"
SLICER_LAYOUT = [(95250, 1450000), (1600000, 3300000), (4950000, 1500000), (6550000, 4200000)]   # (x offset, width) in EMU per slicer
_DEFAULTS = {k: globals()[k] for k in ("MONTHS", "NUM_FIELDS", "STR_FIELDS", "CALC", "DATA_FIELDS", "SLICERS", "COL_FIELD", "ROW_FIELDS", "ROW_CAPTION", "COL_CAPTION", "SLICER_LAYOUT")}


def configure(spec=None):
    """Override the pivot layout (fields, measures, slicers, hierarchy). spec=None restores the per-brand report defaults."""
    for k, v in _DEFAULTS.items(): globals()[k] = v
    for k, v in (spec or {}).items():
        assert k in _DEFAULTS, k
        globals()[k] = v


def col_letter(n):
    s = ""
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def read_pivot_data(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["Pivot_Data"]
    rows = [list(r) for r in ws.iter_rows(min_row=1, values_only=True)]
    wb.close()
    nb = len(STR_FIELDS) + len(NUM_FIELDS)
    head = rows[0][:nb]
    assert head == STR_FIELDS + NUM_FIELDS, head
    data = [r[:nb] for r in rows[1:] if r[0] is not None]
    return data


def build_parts(data, sheet_name):
    n = len(data)
    NS, NN, NC = len(STR_FIELDS), len(NUM_FIELDS), len(CALC)
    shared = []  # per string field: ordered unique values
    for f in range(NS):
        seen = list(dict.fromkeys(r[f] for r in data))
        if f == COL_FIELD: seen = [m for m in MONTHS if m in seen]
        shared.append(seen)
    # ---- cache definition
    cf = []
    for f, name in enumerate(STR_FIELDS):
        items = "".join(f"<s v={quoteattr(v)}/>" for v in shared[f])
        cf.append(f'<cacheField name={quoteattr(name)} numFmtId="0"><sharedItems count="{len(shared[f])}">{items}</sharedItems></cacheField>')
    for j, name in enumerate(NUM_FIELDS):
        vals = [float(r[NS + j] or 0) for r in data]
        isint = all(abs(v - round(v)) < 1e-9 for v in vals)
        mn, mx = min(vals), max(vals)
        fmt = "300" if j == 0 else "3"
        cf.append(f'<cacheField name={quoteattr(name)} numFmtId="{fmt}"><sharedItems containsSemiMixedTypes="0" containsString="0" containsNumber="1"'
                  f'{" containsInteger=\"1\"" if isint else ""} minValue="{mn:g}" maxValue="{mx:.10g}"/></cacheField>')
    for name, formula in CALC:
        cf.append(f'<cacheField name={quoteattr(name)} numFmtId="0" formula={quoteattr(formula)} databaseField="0"/>')
    cache_def = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotCacheDefinition xmlns="{NS_MAIN}" xmlns:r="{NS_R}" r:id="rId1" refreshOnLoad="1" '
                 f'refreshedBy="Claude" refreshedDate="46325.5" createdVersion="8" refreshedVersion="6" minRefreshableVersion="3" recordCount="{n}">'
                 f'<cacheSource type="worksheet"><worksheetSource ref="A1:{col_letter(NS + NN)}{n + 1}" sheet="Pivot_Data"/></cacheSource>'
                 f'<cacheFields count="{len(cf)}">{"".join(cf)}</cacheFields>'
                 f'<extLst><ext uri="{{725AE2AE-9491-48be-B2B4-4EB974FC3084}}" xmlns:x14="{NS_X14}"><x14:pivotCacheDefinition pivotCacheId="{CACHE_ID_X14}"/></ext></extLst>'
                 f'</pivotCacheDefinition>')
    # ---- records
    recs = []
    for r in data:
        x = "".join(f'<x v="{shared[f].index(r[f])}"/>' for f in range(NS))
        v = "".join(f'<n v="{float(r[NS + j] or 0):.10g}"/>' for j in range(NN))
        recs.append(f"<r>{x}{v}</r>")
    cache_rec = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotCacheRecords xmlns="{NS_MAIN}" xmlns:r="{NS_R}" count="{n}">{"".join(recs)}</pivotCacheRecords>'
    # ---- pivot table definition
    pf = []
    for f in range(NS):
        k = len(shared[f])
        items = "".join(f'<item x="{i}"/>' for i in range(k)) + '<item t="default"/>'
        if f == COL_FIELD:
            pf.append(f'<pivotField axis="axisCol" showAll="0" defaultSubtotal="0"><items count="{k}">{"".join(f"<item x=\"{i}\"/>" for i in range(k))}</items></pivotField>')
        elif f in ROW_FIELDS:
            pf.append(f'<pivotField axis="axisRow" showAll="0"><items count="{k + 1}">{items}</items></pivotField>')
        else:
            pf.append(f'<pivotField showAll="0"><items count="{k + 1}">{items}</items></pivotField>')
    used = {d[1] for d in DATA_FIELDS}
    for j in range(NN):
        pf.append(f'<pivotField{" dataField=\"1\"" if NS + j in used else ""} showAll="0"/>')
    for j in range(NC):
        pf.append(f'<pivotField{" dataField=\"1\"" if NS + NN + j in used else ""} dragToRow="0" dragToCol="0" dragToPage="0" showAll="0" defaultSubtotal="0"/>')
    # hierarchical row items: each outer item followed by its inner items (inner shared-item order)
    fo, fi = ROW_FIELDS
    kids = {o: sorted({shared[fi].index(r[fi]) for r in data if shared[fo].index(r[fo]) == o}) for o in range(len(shared[fo]))}
    xv = lambda k: "<x/>" if k == 0 else f'<x v="{k}"/>'
    row_items = "".join(f'<i>{xv(o)}</i>' + "".join(f'<i r="1">{xv(k)}</i>' for k in kids[o]) for o in range(len(shared[fo]))) + '<i t="grand"><x/></i>'
    nrow_items = len(shared[fo]) + sum(len(v) for v in kids.values()) + 1
    col_items = ""
    for m in range(len(shared[0])):
        col_items += f'<i><x{"" if m == 0 else f" v=\"{m}\""}/><x/></i>'
        col_items += "".join(f'<i r="1" i="{k}"><x v="{k}"/></i>' for k in range(1, len(DATA_FIELDS)))
    nm = len(shared[0])
    last_col = col_letter(1 + nm * len(DATA_FIELDS))
    last_row = 16 + nrow_items
    fmt = {"cost": 300, "pct": 301}
    dfs = "".join(f'<dataField name={quoteattr(cap)} fld="{fld}" baseField="0" baseItem="0" numFmtId="{fmt.get(nf, nf)}"/>' for cap, fld, nf in DATA_FIELDS)
    pivot = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotTableDefinition xmlns="{NS_MAIN}" name="{PIVOT_NAME}" cacheId="1" '
             f'applyNumberFormats="0" applyBorderFormats="0" applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" '
             f'dataCaption="Values" errorCaption="–" showError="1" missingCaption="–" updatedVersion="6" minRefreshableVersion="3" colGrandTotals="0" '
             f'itemPrintTitles="1" createdVersion="8" outline="1" outlineData="1" multipleFieldFilters="0" rowHeaderCaption={quoteattr(ROW_CAPTION)} colHeaderCaption={quoteattr(COL_CAPTION)} '
             f'fieldListSortAscending="1"><location ref="A14:{last_col}{last_row}" firstHeaderRow="1" firstDataRow="3" firstDataCol="1"/>'
             f'<pivotFields count="{len(pf)}">{"".join(pf)}</pivotFields><rowFields count="2"><field x="{fo}"/><field x="{fi}"/></rowFields>'
             f'<rowItems count="{nrow_items}">{row_items}</rowItems><colFields count="2"><field x="{COL_FIELD}"/><field x="-2"/></colFields>'
             f'<colItems count="{nm * len(DATA_FIELDS)}">{col_items}</colItems><dataFields count="{len(DATA_FIELDS)}">{dfs}</dataFields>'
             f'<pivotTableStyleInfo name="PivotStyleMedium9" showRowHeaders="1" showColHeaders="1" showRowStripes="0" showColStripes="0" showLastColumn="1"/>'
             f'</pivotTableDefinition>')
    return shared, cache_def, cache_rec, pivot


def slicer_parts(shared, tab_id):
    caches, names = [], []
    for cap, fld, cname in SLICERS:
        items = "".join(f'<i x="{i}" s="1"/>' for i in range(len(shared[fld])))
        caches.append((cname, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<slicerCacheDefinition xmlns="{NS_X14}" '
                       f'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="x" xmlns:x="{NS_MAIN}" name="{cname}" sourceName={quoteattr(cap)}>'
                       f'<pivotTables><pivotTable tabId="{tab_id}" name="{PIVOT_NAME}"/></pivotTables><data><tabular pivotCacheId="{CACHE_ID_X14}"><items count="{len(shared[fld])}">{items}</items></tabular></data>'
                       f'<extLst><x:ext uri="{{470722E0-AACD-4C17-9CDC-17EF765DBC7E}}" xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main"><x15:slicerCacheHideItemsWithNoData/></x:ext></extLst>'
                       f'</slicerCacheDefinition>'))
    sl = "".join(f'<slicer name={quoteattr(cap)} cache="{cname}" caption={quoteattr(cap)} style="SlicerStyleLight5" rowHeight="241300"/>' for cap, fld, cname in SLICERS)
    slicers = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<slicers xmlns="{NS_X14}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
               f'mc:Ignorable="x" xmlns:x="{NS_MAIN}">{sl}</slicers>')
    return caches, slicers


def drawing_xml():
    colw = [58] + [14] * (len(MONTHS) * len(DATA_FIELDS) + 12)   # Master Pivot column widths (characters)
    emu = lambda w: (int(w * 7 + 5)) * 9525
    edges = [0]
    for w in colw: edges.append(edges[-1] + emu(w))

    def pos(x):
        for i in range(len(colw)):
            if x < edges[i + 1]: return i, x - edges[i]
        return len(colw) - 1, 0
    layout = SLICER_LAYOUT
    anchors = []
    for i, ((cap, fld, cname), (x0, w)) in enumerate(zip(SLICERS, layout)):
        (c0, o0), (c1, o1) = pos(x0), pos(x0 + w)
        anchors.append(
            f'<xdr:twoCellAnchor><xdr:from><xdr:col>{c0}</xdr:col><xdr:colOff>{o0}</xdr:colOff><xdr:row>3</xdr:row><xdr:rowOff>57150</xdr:rowOff></xdr:from>'
            f'<xdr:to><xdr:col>{c1}</xdr:col><xdr:colOff>{o1}</xdr:colOff><xdr:row>11</xdr:row><xdr:rowOff>219075</xdr:rowOff></xdr:to>'
            f'<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">'
            f'<mc:Choice Requires="a14"><xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="{i + 2}" name={quoteattr(cap)}/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
            f'<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm><a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/drawing/2010/slicer">'
            f'<sle:slicer xmlns:sle="http://schemas.microsoft.com/office/drawing/2010/slicer" name={quoteattr(cap)}/></a:graphicData></a:graphic></xdr:graphicFrame></mc:Choice>'
            f'<mc:Fallback xmlns=""><xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="0" name=""/><xdr:cNvSpPr><a:spLocks noTextEdit="1"/></xdr:cNvSpPr></xdr:nvSpPr>'
            f'<xdr:spPr><a:xfrm><a:off x="{x0}" y="933450"/><a:ext cx="{w}" cy="1900000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:prstClr val="white"/></a:solidFill>'
            f'<a:ln w="1"><a:solidFill><a:prstClr val="green"/></a:solidFill></a:ln></xdr:spPr><xdr:txBody><a:bodyPr vertOverflow="clip" horzOverflow="clip"/><a:lstStyle/>'
            f'<a:p><a:r><a:rPr lang="en-IN" sz="1100"/><a:t>This shape represents a slicer. Slicers are supported in Excel 2010 or later.</a:t></a:r></a:p></xdr:txBody></xdr:sp></mc:Fallback></mc:AlternateContent><xdr:clientData/></xdr:twoCellAnchor>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">' + "".join(anchors) + '</xdr:wsDr>')


def _cell_to_rc(ref):
    m = re.match(r"([A-Z]+)(\d+)$", ref); col = 0
    for ch in m.group(1): col = col * 26 + ord(ch) - 64
    return int(m.group(2)), col


def check_pivot_range_is_clean(sheet_xml, pivot_ref):
    """Excel cannot refresh a PivotTable over merged cells, and the pivot body must be plain values (no formulas)."""
    a, b = pivot_ref.split(":"); (r0, c0), (r1, c1) = _cell_to_rc(a), _cell_to_rc(b)
    for mref in re.findall(r'<mergeCell ref="([^"]+)"', sheet_xml):
        x, y = mref.split(":"); (mr0, mc0), (mr1, mc1) = _cell_to_rc(x), _cell_to_rc(y)
        if not (mr1 < r0 or mr0 > r1 or mc1 < c0 or mc0 > c1):
            raise ValueError(f"merged cells {mref} overlap the pivot range {pivot_ref} — Excel would refuse to refresh the PivotTable")
    for m in re.finditer(r'<c r="([A-Z]+\d+)"[^>]*>(?:(?!</c>).)*?<f[ >]', sheet_xml, re.S):
        r, c = _cell_to_rc(m.group(1))
        if r0 <= r <= r1 and c0 <= c <= c1:
            raise ValueError(f"formula in pivot range cell {m.group(1)} — the pivot body must be plain values")


def next_rid(rels_xml):
    ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels_xml)]
    return max(ids + [0]) + 1


def inject(src, dst, spec=None):
    configure(spec)
    data = read_pivot_data(src)
    z = zipfile.ZipFile(src)
    files = {n: z.read(n) for n in z.namelist()}
    order = z.namelist()
    z.close()
    g = lambda n: files[n].decode("utf-8")
    wbx = g("xl/workbook.xml")
    m = re.search(r'<sheet [^>]*name="Master Pivot"[^>]*/>', wbx)
    assert m, "Master Pivot sheet not found"
    sheet_id = re.search(r'sheetId="(\d+)"', m.group(0)).group(1)
    sheet_rid = re.search(r'r:id="([^"]+)"', m.group(0)).group(1)
    wrels = g("xl/_rels/workbook.xml.rels")
    target = re.search(rf'<Relationship [^>]*Id="{sheet_rid}"[^>]*>', wrels).group(0)
    sheet_path = "xl/" + re.search(r'Target="([^"]+)"', target).group(1).lstrip("/").replace("xl/", "")
    shared, cache_def, cache_rec, pivot = build_parts(data, "Master Pivot")
    caches, slicers = slicer_parts(shared, sheet_id)
    existing_dr = [int(x) for x in re.findall(r"xl/drawings/drawing(\d+)\.xml", " ".join(files))]
    dr_no = max(existing_dr + [0]) + 1
    add = {
        "xl/pivotCache/pivotCacheDefinition1.xml": cache_def,
        "xl/pivotCache/pivotCacheRecords1.xml": cache_rec,
        "xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{NS_R}/pivotCacheRecords" Target="pivotCacheRecords1.xml"/></Relationships>',
        "xl/pivotTables/pivotTable1.xml": pivot,
        "xl/pivotTables/_rels/pivotTable1.xml.rels": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{NS_R}/pivotCacheDefinition" Target="../pivotCache/pivotCacheDefinition1.xml"/></Relationships>',
        "xl/slicers/slicer1.xml": slicers,
        f"xl/drawings/drawing{dr_no}.xml": drawing_xml(),
    }
    for i, (cname, xml) in enumerate(caches, 1): add[f"xl/slicerCaches/slicerCache{i}.xml"] = xml
    # ---- content types
    ct = g("[Content_Types].xml")
    ov = ['<Override PartName="/xl/pivotCache/pivotCacheDefinition1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>',
          '<Override PartName="/xl/pivotCache/pivotCacheRecords1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"/>',
          '<Override PartName="/xl/pivotTables/pivotTable1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>',
          '<Override PartName="/xl/slicers/slicer1.xml" ContentType="application/vnd.ms-excel.slicer+xml"/>',
          f'<Override PartName="/xl/drawings/drawing{dr_no}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>']
    ov += [f'<Override PartName="/xl/slicerCaches/slicerCache{i}.xml" ContentType="application/vnd.ms-excel.slicerCache+xml"/>' for i in range(1, len(caches) + 1)]
    ct = ct.replace("</Types>", "".join(ov) + "</Types>")
    files["[Content_Types].xml"] = ct.encode("utf-8")
    # ---- workbook rels
    rid = next_rid(wrels)
    cache_rid = f"rId{rid}"
    new_rels = f'<Relationship Id="{cache_rid}" Type="{NS_R}/pivotCacheDefinition" Target="pivotCache/pivotCacheDefinition1.xml"/>'
    sl_rids = []
    for i in range(1, len(caches) + 1):
        rid += 1; sl_rids.append(f"rId{rid}")
        new_rels += f'<Relationship Id="rId{rid}" Type="http://schemas.microsoft.com/office/2007/relationships/slicerCache" Target="slicerCaches/slicerCache{i}.xml"/>'
    wrels = wrels.replace("</Relationships>", new_rels + "</Relationships>")
    files["xl/_rels/workbook.xml.rels"] = wrels.encode("utf-8")
    # ---- workbook.xml: definedNames, pivotCaches, x14 slicerCaches
    dn = "".join(f'<definedName name="{c}">#N/A</definedName>' for c, _ in caches)
    if "</definedNames>" in wbx: wbx = wbx.replace("</definedNames>", dn + "</definedNames>", 1)
    else: wbx = wbx.replace("<calcPr", f"<definedNames>{dn}</definedNames><calcPr", 1)
    pc = f'<pivotCaches><pivotCache cacheId="1" r:id="{cache_rid}"/></pivotCaches>'
    cm = re.search(r"<calcPr[^>]*/>", wbx)
    assert cm, "calcPr missing"
    wbx = wbx[:cm.end()] + pc + wbx[cm.end():]
    ext = (f'<ext uri="{{BBE1A952-AA13-448e-AADC-164F8A28A991}}" xmlns:x14="{NS_X14}"><x14:slicerCaches>'
           + "".join(f'<x14:slicerCache r:id="{r_}"/>' for r_ in sl_rids) + '</x14:slicerCaches></ext>')
    if "<extLst>" in wbx: wbx = wbx.replace("<extLst>", "<extLst>" + ext, 1)
    else: wbx = wbx.replace("</workbook>", f"<extLst>{ext}</extLst></workbook>", 1)
    files["xl/workbook.xml"] = wbx.encode("utf-8")
    # ---- sheet rels + sheet xml
    rels_path = sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
    srels = g(rels_path) if rels_path in files else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    r1 = next_rid(srels)
    srels = srels.replace("</Relationships>",
        f'<Relationship Id="rId{r1}" Type="{NS_R}/pivotTable" Target="../pivotTables/pivotTable1.xml"/>'
        f'<Relationship Id="rId{r1 + 1}" Type="{NS_R}/drawing" Target="../drawings/drawing{dr_no}.xml"/>'
        f'<Relationship Id="rId{r1 + 2}" Type="http://schemas.microsoft.com/office/2007/relationships/slicer" Target="../slicers/slicer1.xml"/></Relationships>')
    if rels_path not in files: order.append(rels_path)
    files[rels_path] = srels.encode("utf-8")
    sx = g(sheet_path)
    assert "<drawing " not in sx
    check_pivot_range_is_clean(sx, re.search(r'<location ref="([^"]+)"', pivot).group(1))
    ins = re.search(r"<legacyDrawing|<legacyDrawingHF|<picture|<oleObjects|<controls|<webPublishItems|<tableParts|<extLst|</worksheet>", sx)
    sx = sx[:ins.start()] + f'<drawing r:id="rId{r1 + 1}"/>' + sx[ins.start():]
    sl_ext = f'<ext uri="{{A8765BA9-456A-4dab-B4F3-ACF838C121DE}}" xmlns:x14="{NS_X14}"><x14:slicerList><x14:slicer r:id="rId{r1 + 2}"/></x14:slicerList></ext>'
    if "<extLst>" in sx: sx = sx.replace("<extLst>", "<extLst>" + sl_ext, 1)
    else: sx = sx.replace("</worksheet>", f"<extLst>{sl_ext}</extLst></worksheet>", 1)
    assert 'xmlns:r="' in sx[:2000], "r namespace missing on sheet root"
    files[sheet_path] = sx.encode("utf-8")
    # ---- styles: custom number formats used by the pivot data fields
    st = g("xl/styles.xml")
    nf = ('<numFmt numFmtId="300" formatCode="&quot;₹&quot;#,##0.00;\\-&quot;₹&quot;#,##0.00;&quot;–&quot;"/>'
          '<numFmt numFmtId="301" formatCode="0.00%;\\-0.00%;&quot;–&quot;"/>')
    mm = re.search(r'<numFmts count="(\d+)">', st)
    if mm:
        st = st.replace(mm.group(0), f'<numFmts count="{int(mm.group(1)) + 2}">', 1).replace("</numFmts>", nf + "</numFmts>", 1)
    else:
        st = re.sub(r"(<styleSheet[^>]*>)", r'\1<numFmts count="2">' + nf.replace("\\", "\\\\") + "</numFmts>", st, count=1)
    files["xl/styles.xml"] = st.encode("utf-8")
    for k, v in add.items():
        files[k] = v.encode("utf-8"); order.append(k)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
        for n in order:
            if n in files: out.writestr(n, files[n])
    return {"rows": len(data), "campaigns": len(shared[ROW_FIELDS[1]]), "months": len(shared[COL_FIELD])}


if __name__ == "__main__":
    print(inject(sys.argv[1], sys.argv[2]))
