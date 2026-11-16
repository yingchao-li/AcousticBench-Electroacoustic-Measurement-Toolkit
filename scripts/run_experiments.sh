#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AcousticBench — run the reproducible experiments E01–E16.
#
# Usage:
#   bash scripts/run_experiments.sh                          # all enabled experiments
#   bash scripts/run_experiments.sh --codes E01,E02          # subset (comma or space separated)
#   bash scripts/run_experiments.sh --codes "E01 E02"
#
# Artefacts are written to results/experiments/<CODE>_<slug>/ and the index is
# refreshed as results/experiments/experiment_index.{csv,json}.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${ROOT_DIR}/.cache/matplotlib}"

CODES=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --codes)
            if [ "$#" -lt 2 ]; then
                echo "ERROR: --codes requires a value (e.g. --codes E01,E02)." >&2
                exit 2
            fi
            CODES="$2"
            shift 2
            ;;
        --codes=*)
            CODES="${1#--codes=}"
            shift
            ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument '$1'." >&2
            exit 2
            ;;
    esac
done

if [ ! -x ".venv/bin/python" ]; then
    echo "ERROR: .venv not found. Run 'bash scripts/install.sh' first." >&2
    exit 1
fi
if [ ! -f "Data.mat" ]; then
    echo "ERROR: Data.mat not found. Run '.venv/bin/python scripts/fetch_data.py'." >&2
    exit 1
fi

CLI_ARGS=(experiments)
if [ -n "${CODES}" ]; then
    # Accept comma- and/or space-separated codes.
    normalized="${CODES//,/ }"
    read -r -a code_list <<< "${normalized}"
    if [ "${#code_list[@]}" -eq 0 ]; then
        echo "ERROR: --codes did not contain any experiment code." >&2
        exit 2
    fi
    CLI_ARGS+=(--codes "${code_list[@]}")
    echo "Running experiments: ${code_list[*]}"
else
    echo "Running all enabled experiments ..."
fi

.venv/bin/python -m acousticbench.cli "${CLI_ARGS[@]}"

# --- summary ---------------------------------------------------------------
SUMMARY_DIR="${ROOT_DIR}/results/experiments"
if [ -f "${SUMMARY_DIR}/experiment_index.csv" ]; then
    echo ""
    echo "Summary (${SUMMARY_DIR}/experiment_index.csv):"
    .venv/bin/python - "${SUMMARY_DIR}/experiment_index.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
completed = sum(1 for row in rows if row.get("status") == "completed")
print(f"  experiments in index : {len(rows)}")
print(f"  completed            : {completed}")
print(f"  failed               : {len(rows) - completed}")
for row in rows:
    print(
        f"  {row['code']}  {row['status']:9s}  {row['duration_s']:>7s} s  "
        f"{row['n_tables']} tables / {row['n_figures']} figures"
    )
    if row.get("error"):
        print(f"      error: {row['error']}")
if completed != len(rows):
    sys.exit(1)
PY
fi
