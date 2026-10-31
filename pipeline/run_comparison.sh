#!/usr/bin/env bash
# One command for the Brand Comparison report: build -> LibreOffice recalc -> inject PivotTable+slicers -> independent verification.
# usage: pipeline/run_comparison.sh <leads_dir> <meta_experts_dir> <comp_dir> <out_dir>
# Exits non-zero if the independent verifier finds any mismatch. Config: config/comparison_config.json (months, brands, sources).
set -euo pipefail
LEADS="$1"; METAX="$2"; COMP="$3"; OUT="$4"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "== 1/2 build + recalc + inject pivot"; python3 -I "$HERE/build_comparison_report.py" "$LEADS" "$METAX" "$COMP" "$OUT"
echo "== 2/2 independent verification against the raw files"; python3 -I "$HERE/verify_comparison.py" "$LEADS" "$METAX" "$COMP" "$OUT/Brand_Comparison_Sep-Oct2026.xlsx"
echo "ALL CHECKS PASSED -> $OUT/Brand_Comparison_Sep-Oct2026.xlsx"
