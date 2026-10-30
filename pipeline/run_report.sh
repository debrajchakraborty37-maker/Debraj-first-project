#!/usr/bin/env bash
# One command: build every brand workbook -> LibreOffice recalc -> inject PivotTable+slicers -> run ALL independent verifiers -> zip.
# usage: pipeline/run_report.sh <lead_dir> <meta_dir> <out_dir> [brand ...]
#   lead_dir  folder with the monthly lead files (names per config/report_config.json)
#   meta_dir  folder with the monthly Meta *Campaigns* CSV exports
# Set REPORT_CONFIG=/path/to/other_config.json to use a different period / brand list. Exits non-zero if any check fails.
set -euo pipefail
LEADS="$1"; META="$2"; OUT="$3"; shift 3 || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="python3 -I"
echo "== 1/4 build + recalc + inject pivot"; $PY "$HERE/run_all_brands.py" "$LEADS" "$META" "$OUT" "$@"
echo "== 2/4 independent check of every report cell against the raw files"; $PY "$HERE/verify_reports.py" "$LEADS" "$META" "$OUT"
echo "== 3/4 Master Pivot (values, structure, no merged cells / formulas / frozen panes)"; $PY "$HERE/verify_masterpivot.py" "$OUT"/*.xlsx
echo "== 4/4 Master Dashboard tiles/tables/top-10 (default selection 'All months')"
for f in "$OUT"/*.xlsx; do $PY "$HERE/verify_dashboard.py" "$f" "All months"; done
cd "$OUT" && rm -f Brand_Reports.zip && zip -q -j Brand_Reports.zip ./*_FinalReport_*.xlsx && unzip -tq Brand_Reports.zip
echo "ALL CHECKS PASSED -> $OUT/Brand_Reports.zip"
