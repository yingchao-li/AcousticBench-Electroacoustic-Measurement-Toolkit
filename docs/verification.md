# Verification record

This page records **what was actually executed** in the environment where this
repository was built (macOS arm64, Python 3.12.16) and what was not. It is the
audit trail behind the status claims in the README.

## 1. Environment

| Item | Value |
|---|---|
| OS / CPU | macOS 26.6.2, arm64, 10 cores, 16 GB RAM |
| Python | 3.12.16 (`.venv`) |
| NumPy / SciPy / Pandas | 2.5.5 / 1.18.1 / 3.1.1 |
| Matplotlib / Plotly / Streamlit | 3.11.2 / 7.1.0 / 1.67.0 |
| ReportLab / openpyxl / xlsxwriter | 5.1.0 / 3.1.5 / 3.3.1 |
| MATLAB | **not installed** (no licence) |
| GNU Octave | **not available** (Homebrew install failed: `/opt/homebrew` not writable) |
| Dataset | `Data.mat`, 86.1 MiB, SHA-256 `45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48` |

## 2. Dataset audit

Command: `acb audit` (or `PYTHONPATH=src .venv/bin/python -m acousticbench.cli audit`).

Result: **0 errors, 0 warnings**; 15 checks recorded in
`results/audit/checks.csv`. Highlights:

* schema/shape/dtype validation passed;
* 18 invalid transfer-function sessions, 19 invalid threshold sessions, whole
  sessions only, identical NaN mask across the five transfer containers;
* structural validity confirmed empirically (loose MPT 44.9–62.4 dB below in-ear
  level; no RPT for domes with a 59.2 dB signature; free-field across-device SD
  0.34–0.53 dB);
* unit sanity (Hha 82.8 dB SPL median 0.5–4 kHz; REOIG closed −10.9 dB / open
  +0.5 dB at 1 kHz; REUG +0.6/+14.0/+15.7 dB at 1/2/4 kHz);
* expected PTPE signs reproduced;
* reinsertion SD median 0.38 dB (p95 1.47 dB);
* interpretation caveats recorded (absolute loudspeaker scaling, no reference
  probe for domes, no imputation).

## 3. Experiments E01–E16

Command: `bash scripts/run_experiments.sh` (or `acb experiments`).
Result: **16/16 completed**; total wall-clock ≈ 20 s of analysis plus data
loading. Artefacts in `results/experiments/`; index in
`results/experiments/experiment_index.{json,csv}`.

Key executed numbers:

| Experiment | Verified result |
|---|---|
| E01 | Hha 1 kHz closed 76.1 dB SPL, open dome 62.7 dB SPL |
| E02 | MPT−RPT bias median \|Δ\| 1.74 dB; ΔHha(100 Hz) nugget −8.6 dB; ΔREOIG(1 kHz) nugget +6.1 dB; ΔT(125 Hz) closed −3.9 dB |
| E03 | reinsertion SD median 0.38 dB; RC 0.71–1.28 dB; ICC(2,1) 0.77–0.98 |
| E04 | between-subject SD 1.37–2.20 dB; ICC(1,1) 0.77–0.98 |
| E05 | Hfb 1 kHz closed 8.3 vs open 20.2 dB SPL; ΔHfb nugget +5.8 dB |
| E06 | REUG 1/2/4 kHz +0.6/+14.0/+15.7 dB; REOIG closed −10.7 dB |
| E07 | threshold 125 Hz −71.0 vs −37.5 dBV; ΔT ↔ ΔHha r = 0.56 (n = 56) |
| E08 | closed vs open Hha +12.45 dB, p = 8.4 × 10⁻⁹; 6/15 Holm-significant family tests |
| E09 | gain max \|error\| 5.3 × 10⁻¹⁵ dB (100 reference cases) |
| E10 | THD max \|error\| 3.5 × 10⁻¹³ pp (100 reference cases) |
| E11 | SNR residual max \|error\| 0.0105 dB (100 reference cases); PSD white max 0.055 dB |
| E12 | FR MAE median 0.016 dB, max 0.069 dB (100 reference cases) |
| E13 | measured ratio 3.00 vs configured 3.0; static error 0.015 dB; attack settling 2.94 ms, release 237 ms |
| E14 | 6/6 faults detected; mean relative error 0.001 %; deterministic ×10 |
| E15 | port-vs-production max \|Δ\|: 0.0 dB Hha bands, 5.3 × 10⁻¹⁵ dB REOIG, 1.1 × 10⁻¹⁴ dB PTPE, 2.7 × 10⁻¹⁵ dB gain, 0.0085 dB SNR, 1.5 × 10⁻¹² pp THD. **MATLAB status: not_run.** |
| E16 | 14 operations, 304 ms total; data load 222 ms; no MATLAB timing |

Synthetic target compliance (reference conditions only): gain, SNR, THD and
frequency response **all within target** (see `docs/experiments.md`).

## 4. MATLAB

* All 46 `.m` files (6,571 lines) were **statically reviewed** with a custom
  checker (ASCII safety, function/file-name consistency, block/delimiter
  balance, no toolbox calls, no Python-isms) — 0 problems after fixing issues
  found during review.
* The E15 dataset reference definitions were re-implemented in Python and
  cross-checked against the MATLAB formulas: **142/142 dataset rows agree to
  ≤ 1.4 × 10⁻¹⁴ dB** (this caught and fixed a band-REOIG definition mismatch).
* **No MATLAB or Octave code was executed.** No MATLAB test result, numerical
  output, GUI screenshot or `matlab_reference.csv` is claimed. See
  [`matlab_status.md`](matlab_status.md).

## 5. Dashboard and reports

* All 20 app/report modules import successfully.
* Streamlit headless: server starts, `/_stcore/health` → `200 ok`, root page
  `200`; server stopped afterwards.
* `streamlit.testing.v1.AppTest`: `app/dashboard.py` and all nine pages run with
  **0 exceptions**, including a missing-data environment (no `Data.mat`,
  no results) and a Report Center end-to-end generation run.
* Reports generated from the persisted artefacts (no analysis re-run):
  PDF ≈ 4.0 MiB, Excel ≈ 0.72 MiB (500-row cap per experiment sheet),
  HTML ≈ 4.6 MiB (embedded figures). MATLAB status is reported as not-run in
  every format.

## 6. Tests

Command:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q
PYTHONPATH=src .venv/bin/python -m pytest tests -q --cov=acousticbench --cov-report=term
```

The suite includes unit tests for config/I/O/data/validity, measurements,
statistics, DSP, virtual HA, synthetic cases, experiments, validation and
reports; integration tests for the analysis pipeline and experiment artefacts;
and real-data regression tests pinned to the values above.

**Result (executed):**

```text
557 passed, 5 warnings in 54.5 s
TOTAL coverage: 91.37 %  (core packages 93.9 %)
```

Module-level coverage is ≥ 90 % for every core package (config 99.3 %, data 96.0 %,
measurements 93.6 %, stats 92.9 %, DSP 90.3 %, virtual HA 92.0 %, synthetic 90.8 %,
validation 94.8 %, experiments core 98.2 %; core aggregate 93.9 %). Lower-coverage modules are
peripheral: `logging_utils` (console/file handler setup), `report/figures.py`
(plotting helpers exercised through generated reports rather than unit-tested
line by line) and some defensive error branches; they are included in the 91 %
total rather than excluded. Tests that need `Data.mat` are marked
`requires_data` and skip cleanly on machines without the dataset.

## 7. Reproducing this record

```bash
bash scripts/install.sh
python scripts/fetch_data.py
python scripts/verify_install.py
acb audit
bash scripts/run_experiments.sh
bash scripts/run_tests.sh
acb report
```

Every step above writes its own machine-readable artefacts; none of the claims
in this document rely on manual transcription.
