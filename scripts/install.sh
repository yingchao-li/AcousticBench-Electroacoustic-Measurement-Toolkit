#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AcousticBench — one-click installation
#
# Creates a local virtual environment (Python >= 3.10), installs the package
# in editable mode with the development extras, and prints the next steps.
# The dataset is NOT downloaded silently; pass --with-data to fetch it from
# Zenodo (with SHA-256 verification).
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

WITH_DATA=0

usage() {
    cat <<'EOF'
Usage: bash scripts/install.sh [--with-data]

Creates .venv (Python 3.10+), upgrades pip, installs the package in editable
mode with the [dev] extras, and prints the next steps.

Options:
  --with-data   Also download Data.mat / Documentation.pdf from Zenodo
                (SHA-256 verified). Requires network access.
  -h, --help    Show this help and exit.

Environment:
  PYTHON        Python interpreter to use for the virtual environment
                (default: python3.12, then python3, then python).
EOF
}

for argument in "$@"; do
    case "${argument}" in
        --with-data)
            WITH_DATA=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: ${argument}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# --- pick a Python interpreter ---------------------------------------------
PYTHON_BIN="${PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
    for candidate in python3.12 python3 python; do
        if command -v "${candidate}" >/dev/null 2>&1; then
            PYTHON_BIN="${candidate}"
            break
        fi
    done
fi
if [ -z "${PYTHON_BIN}" ]; then
    echo "ERROR: no Python interpreter found (tried python3.12, python3, python)." >&2
    exit 1
fi
if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "ERROR: Python >= 3.10 is required; ${PYTHON_BIN} is too old." >&2
    exit 1
fi
echo "Using Python: $("${PYTHON_BIN}" -c 'import sys; print(sys.executable)') ($("${PYTHON_BIN}" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'))"

# --- create the virtual environment ----------------------------------------
if [ ! -x ".venv/bin/python" ]; then
    echo "Creating virtual environment in .venv ..."
    "${PYTHON_BIN}" -m venv .venv
else
    echo "Reusing existing virtual environment .venv"
fi

echo "Upgrading pip ..."
.venv/bin/python -m pip install --upgrade pip >/dev/null

echo "Installing AcousticBench with development extras ..."
.venv/bin/python -m pip install -e ".[dev]"

if [ "${WITH_DATA}" -eq 1 ]; then
    echo "Downloading the Zenodo dataset (SHA-256 verified) ..."
    .venv/bin/python scripts/fetch_data.py
fi

# --- next steps -------------------------------------------------------------
cat <<'EOF'

Installation completed.

Next steps:
  bash scripts/run_tests.sh                      # run the test suite
  bash scripts/run_experiments.sh                # run all 16 experiments
  bash scripts/start_dashboard.sh                # launch the Streamlit dashboard
  .venv/bin/python scripts/verify_install.py     # verify environment + data

If the dataset is not present yet:
  .venv/bin/python scripts/fetch_data.py         # download from Zenodo (SHA-256 verified)

The raw dataset (Data.mat, Documentation.pdf) is licensed CC BY 4.0; see
DATA_LICENSE.md for citation requirements.
EOF
