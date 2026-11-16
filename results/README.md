# Results

Generated analysis artefacts. Everything here is reproducible from the code and
the public dataset; see the repository README and `config/default.yaml`.

| Directory | Contents |
|---|---|
| `audit/` | Data-quality audit of `Data.mat`: `data_audit.json`, `data_audit.md`, CSV tables, overview figure |
| `experiments/E01_…` … `E16_…` | One directory per experiment: `result.json`, `summary.md`, `config_snapshot.json`, `tables/*.csv`, `figures/*.png` |
| `experiments/experiment_index.json` / `.csv` | Aggregate index of all runs (status, duration, artefact counts) |
| `validation/` | E15 cross-language exchange: `matlab_inputs.mat`, expected values, `cross_language_report.json` (MATLAB side status included) |
| `synthetic/` | Deterministic 1000-case suite manifest (`manifest.csv`, `manifest.json`) |
| `logs/` | Runtime logs (git-ignored) |

## How to regenerate

```bash
python scripts/fetch_data.py
acb audit
bash scripts/run_experiments.sh
```

The exact source dataset is identified by SHA-256
`45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48`.
Note: the dataset is CC BY 4.0 (see `DATA_LICENSE.md`); results derived from it
are shared under the same attribution requirements.

## Status

All 16 experiments completed successfully. MATLAB is unavailable in the build
environment; E15 records `matlab_status = "not_run"` and does **not** claim a
MATLAB verification. Synthetic target compliance (E09–E12) is reported only for
the documented reference conditions.
