#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AcousticBench — launch the Streamlit dashboard.
#
# Usage:
#   bash scripts/start_dashboard.sh               # http://localhost:8501
#   PORT=9000 bash scripts/start_dashboard.sh     # custom port
#   bash scripts/start_dashboard.sh --server.headless true
#
# Any extra arguments are forwarded to `streamlit run`.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -x ".venv/bin/python" ]; then
    echo "ERROR: .venv not found. Run 'bash scripts/install.sh' first." >&2
    exit 1
fi
if [ ! -f "app/dashboard.py" ]; then
    echo "ERROR: app/dashboard.py not found (run from the repository)." >&2
    exit 1
fi

PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONPATH
export MPLCONFIGDIR="${MPLCONFIGDIR:-${ROOT_DIR}/.cache/matplotlib}"
PORT="${PORT:-8501}"

exec .venv/bin/python -m streamlit run app/dashboard.py \
    --server.port "${PORT}" \
    "$@"
