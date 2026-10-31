"""Post-process the openpyxl stage-1 workbook: native pivot parts, slicers, template charts/drawings, then inject cached values."""
import re, sys, zipfile, shutil, subprocess, os, warnings
import pandas as pd
sys.path.insert(0, '/tmp/claude-0/work')
warnings.filterwarnings('ignore')
import pivotgen
from pivotgen import TN

NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def rd(p): return open(TN + p, encoding='utf-8').read()


def stage2(brand, d, info, src, dst):
    f, lay = info['f'], info['lay']
    od = lay['od']
    z = zipfile.ZipFile(src)
    P = {n: z.read(n) for n in z.namelist()}
    T = lambda n: P[n].decode('utf-8')
    # ---- pivot cache
    tdef = rd('pivotCache/pivotCacheDefinition1.xml')
    P['xl/pivotCache/pivotCacheDefinition1.xml'] = pivotgen.cache_def(f, od, tdef).encode('utf-8')
    P['xl/pivotCache/pivotCacheRecords1.xml'] = pivotgen.cache_records(f, od).encode('utf-8')
    pts = pivotgen.pivot_tables(f, od, lay)    # template numbering: 1 pct, 2 camp, 3 head, 4 status
    byname = {'pvtStatusPct': 1, 'pvtCampaign': 2, 'pvtHeadline': 3, 'pvtStatus': 4}
    for i in range(1, 5):
        nm = re.search(r'name="(\w+)"', T(f'xl/pivotTables/pivotTable{i}.xml')).group(1)
        P[f'xl/pivotTables/pivotTable{i}.xml'] = pts[byname[nm]].encode('utf-8')
    # check cache rels id
    crel = T('xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels')
    rid = re.search(r'Id="(\w+)"', crel).group(1)
    cd = T('xl/pivotCache/pivotCacheDefinition1.xml') if False else P['xl/pivotCache/pivotCacheDefinition1.xml'].decode()
    cd = re.sub(r'r:id="\w+"', f'r:id="{rid}"', cd, count=1)
    P['xl/pivotCache/pivotCacheDefinition1.xml'] = cd.encode()
    # ---- charts: template charts with updated refs, caches stripped
    r0, r1, r2, r3 = info['chart_rows']
    nstat_extra = len(sorted(set(d['L'].status) - set(pivotgen.STATUS_ORDER)))
    for i in range(1, 7):
        c = rd(f'charts/chart{i}.xml')
        if i == 4: c = c.replace('$A$98:$A$101', f'$A${r0}:$A${r0 + 3}').replace('$B$98:$B$101', f'$B${r0}:$B${r0 + 3}').replace('$C$98:$C$101', f'$C${r0}:$C${r0 + 3}')
        if i == 5: c = c.replace('$A$104:$A$105', f'$A${r2}:$A${r3}').replace('$B$104:$B$105', f'$B${r2}:$B${r3}').replace('$C$104:$C$105', f'$C${r2}:$C${r3}')
        if i == 6 and nstat_extra:
            for col in 'ADE': c = c.replace(f'${col}$46:${col}$62', f'${col}$46:${col}${62 + nstat_extra}')
        c = re.sub(r'<c:numCache>.*?</c:numCache>', '', c, flags=re.S)
        c = re.sub(r'<c:strCache>.*?</c:strCache>', '', c, flags=re.S)
        P[f'xl/charts/chart{i}.xml'] = c.encode('utf-8')
    # ---- drawings
    P['xl/drawings/drawing1.xml'] = rd('drawings/drawing1.xml').encode('utf-8')
    P['xl/drawings/drawing2.xml'] = rd('drawings/drawing3.xml').encode('utf-8')
    P['xl/drawings/_rels/drawing1.xml.rels'] = rd('drawings/_rels/drawing1.xml.rels').encode('utf-8')
    P['xl/drawings/_rels/drawing2.xml.rels'] = rd('drawings/_rels/drawing3.xml.rels').encode('utf-8')
    P['xl/drawings/drawing3.xml'] = rd('drawings/drawing2.xml').encode('utf-8')   # slicer drawing for Master Pivot
    # ---- slicers
    P['xl/slicers/slicer1.xml'] = rd('slicers/slicer1.xml').encode('utf-8')
    sc = pivotgen.slicer_caches(od, None)
    for n, x in sc.items(): P[f'xl/slicerCaches/slicerCache{n}.xml'] = x.encode('utf-8')
    # sheet2 rels + xml
    rel = T('xl/worksheets/_rels/sheet2.xml.rels')
    rel = rel.replace('</Relationships>',
                      '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="/xl/drawings/drawing3.xml" Id="rId90"/>'
                      '<Relationship Type="http://schemas.microsoft.com/office/2007/relationships/slicer" Target="/xl/slicers/slicer1.xml" Id="rId91"/></Relationships>')
    P['xl/worksheets/_rels/sheet2.xml.rels'] = rel.encode()
    sx = T('xl/worksheets/sheet2.xml')
    ext = ('<extLst><ext xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" uri="{A8765BA9-456A-4dab-B4F3-ACF838C121DE}">'
           '<x14:slicerList><x14:slicer r:id="rId91"/></x14:slicerList></ext></extLst>')
    assert '<drawing' not in sx and '<extLst' not in sx
    ext = ext.replace('<ext ', f'<ext xmlns:r="{NS_R}" ', 1)
    sx = sx.replace('</worksheet>', f'<drawing xmlns:r="{NS_R}" r:id="rId90"/>' + ext + '</worksheet>')
    P['xl/worksheets/sheet2.xml'] = sx.encode()
    # workbook rels / workbook xml
    wr = T('xl/_rels/workbook.xml.rels')
    add = ''.join(f'<Relationship Type="http://schemas.microsoft.com/office/2007/relationships/slicerCache" Target="/xl/slicerCaches/slicerCache{n}.xml" Id="rId{100 + n}"/>' for n in range(1, 6))
    P['xl/_rels/workbook.xml.rels'] = wr.replace('</Relationships>', add + '</Relationships>').encode()
    wx = T('xl/workbook.xml')
    names = ''.join(f'<definedName name="{n}">#N/A</definedName>' for n in ['Slicer_Campaign', 'Slicer_Campaign_Type', 'Slicer_Lead_Month', 'Slicer_Lead_Status', 'Slicer_Lead_Week'])
    wx = wx.replace('</definedNames>', names + '</definedNames>')
    caches = ''.join(f'<x14:slicerCache r:id="rId{100 + n}"/>' for n in range(1, 6))
    wext = ('<extLst><ext xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" uri="{BBE1A952-AA13-448e-AADC-164F8A28A991}">'
            f'<x14:slicerCaches>{caches}</x14:slicerCaches></ext></extLst>')
    wext = wext.replace('<ext ', f'<ext xmlns:r="{NS_R}" ', 1)
    wx = wx.replace('</workbook>', wext + '</workbook>')
    P['xl/workbook.xml'] = wx.encode()
    # content types
    ct = T('[Content_Types].xml')
    add = ('<Override PartName="/xl/drawings/drawing3.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
           '<Override PartName="/xl/slicers/slicer1.xml" ContentType="application/vnd.ms-excel.slicer+xml"/>' +
           ''.join(f'<Override PartName="/xl/slicerCaches/slicerCache{n}.xml" ContentType="application/vnd.ms-excel.slicerCache+xml"/>' for n in range(1, 6)))
    P['[Content_Types].xml'] = ct.replace('</Types>', add + '</Types>').encode()
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
        zo.writestr('[Content_Types].xml', P.pop('[Content_Types].xml'))
        for n, b in P.items(): zo.writestr(n, b)


def recalc(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(['soffice', '--headless', '--calc', '--convert-to', 'xlsx:Calc MS Excel 2007 XML', '--outdir', outdir, src], check=True, capture_output=True, timeout=900)
    return os.path.join(outdir, os.path.basename(src))


def inject_values(src, calc, dst):
    """copy cached values from LibreOffice-recalculated workbook into formula cells of src"""
    import openpyxl
    from lxml import etree
    wbv = openpyxl.load_workbook(calc, data_only=True)
    z = zipfile.ZipFile(src)
    wbx = z.read('xl/workbook.xml').decode()
    rels = z.read('xl/_rels/workbook.xml.rels').decode()
    sheets = re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="(\w+)"', wbx)
    relmap = dict((m[1], m[0]) for m in re.findall(r'Target="/?(?:xl/)?([^"]+)" Id="(\w+)"', rels))
    out = {}
    M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    nform = 0
    for name, rid in sheets:
        path = 'xl/' + relmap[rid].replace('xl/', '')
        name = name.replace('&amp;', '&')
        wsv = wbv[name]
        root = etree.fromstring(z.read(path))
        for c in root.iter('{%s}c' % M):
            fe = c.find('{%s}f' % M)
            if fe is None: continue
            nform += 1
            v = wsv[c.get('r')].value
            for old in c.findall('{%s}v' % M): c.remove(old)
            if v is None:
                if 't' in c.attrib: del c.attrib['t']
                continue
            ve = etree.SubElement(c, '{%s}v' % M)
            if isinstance(v, bool):
                c.set('t', 'b'); ve.text = '1' if v else '0'
            elif isinstance(v, (int, float)):
                if 't' in c.attrib: del c.attrib['t']
                ve.text = repr(float(v)) if isinstance(v, float) else str(v)
            elif isinstance(v, str) and v.startswith('#'):
                c.set('t', 'e'); ve.text = v
            elif hasattr(v, 'isoformat'):
                from openpyxl.utils.datetime import to_excel
                if 't' in c.attrib: del c.attrib['t']
                ve.text = repr(float(to_excel(v)))
            else:
                c.set('t', 'str'); ve.text = str(v)
        out[path] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n in z.namelist():
            zo.writestr(n, out.get(n, z.read(n)))
    return nform
