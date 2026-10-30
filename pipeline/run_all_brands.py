#!/usr/bin/env python3
"""Build every brand workbook end to end: openpyxl build -> LibreOffice recalculation -> PivotTable/slicer injection.
usage: run_all_brands.py <lead_dir> <meta_dir> <out_dir> [brand ...]"""
import os, subprocess, sys, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_brand_report as bb, inject_pivot

def run(lead_dir, meta_dir, out_dir, brands=None):
    os.makedirs(out_dir, exist_ok=True)
    for brand in brands or list(bb.BRANDS):
        tmp = tempfile.mkdtemp(prefix="brand_")
        raw = os.path.join(tmp, "raw"); calc = os.path.join(tmp, "calc")
        bb.main(brand, lead_dir, meta_dir, raw)
        fn = os.listdir(raw)[0]
        subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", calc, os.path.join(raw, fn)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        info = inject_pivot.inject(os.path.join(calc, fn), os.path.join(out_dir, fn))
        print("  ->", fn, info)
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:] or None)
