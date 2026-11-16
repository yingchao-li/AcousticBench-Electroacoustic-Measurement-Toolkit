#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AcousticBench — run the test suite.
#
# Usage: bash scripts/run_tests.sh [pytest arguments ...]
#   bash scripts/run_tests.sh                         # full suite
#   bash scripts/run_tests.sh -m "not requires_data"  # data-free subset
#   bash scripts/run_tests.sh -q --cov=acousticbench
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -x ".venv/bin/python" ]; then
    echo "ERROR: .venv not found. Run 'bash scripts/install.sh' first." >&2
    exit 1
fi

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${ROOT_DIR}/.cache/matplotlib}"

echo "Running: .venv/bin/python -m pytest tests $*"
exec .venv/bin/python -m pytest tests "$@"
