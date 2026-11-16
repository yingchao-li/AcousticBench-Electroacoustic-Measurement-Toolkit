# E15 — MATLAB-Python Agreement

**Status:** `completed`  
**Runtime:** 5.08 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `matlab_available` | False |
| `matlab_executable` | None |
| `matlab_status` | not_run |
| `matlab_error` | MATLAB is not installed in this environment. The MATLAB implementation, GUI and tests are provided (matlab/) but are explicitly NOT executed/verified here; see docs/matlab_status.md. |
| `port_agreement_passed` | True |
| `port_n_comparisons` | 6 |
| `matlab_agreement_passed` | None |
| `matlab_n_comparisons` | 0 |
| `matlab_matched_test_ids` | 0 |
| `expected_test_ids` | 167 |
| `matlab_inputs_mat` | /Users/ingchaolee/PycharmProjects/AcousticBench/results/validation/matlab_inputs.mat |
| `matlab_reference_csv` | None |
| `verification_statement` | Port-vs-production agreement executed in Python. MATLAB execution NOT performed: MATLAB is absent from this environment. |

## Summary

The production Python implementation and an independently written MATLAB-transcribed Python port agree to numerical precision on real data (band levels, REOIG, PTPE) and on synthetic gain/SNR/THD signals. The MATLAB input file and the exact CSV contract are generated so that `matlab/run_cross_language_export.m` can be run on a machine with MATLAB; here that step is marked NOT RUN because MATLAB is unavailable. This distinction is deliberate: port agreement demonstrates algorithmic consistency, not execution of the MATLAB code.

## Warnings

- MATLAB is not installed: the MATLAB-side numerical agreement was NOT executed. MATLAB code, GUI and tests are provided but unverified (docs/matlab_status.md). The MATLAB input file and CSV contract are nevertheless generated under results/validation/ so the comparison can be run elsewhere.

## Tables

### `port_comparisons` (6 rows)

| name                             | unit   |   n |   max_abs_diff |   median_abs_diff |   tolerance | passed   |
|:---------------------------------|:-------|----:|---------------:|------------------:|------------:|:---------|
| hha_band_db (port vs production) | dB     |  36 |    0           |       0           |        0.01 | True     |
| reoig_db (port vs production)    | dB     |  63 |    5.32907e-15 |       1.77636e-15 |        0.01 | True     |
| ptpe_hha_db (port vs production) | dB     |  36 |    1.09912e-14 |       2.52576e-15 |        0.01 | True     |
| gain_db (port vs production)     | dB     |   7 |    2.66454e-15 |       0           |        0.01 | True     |
| snr_db (port vs production)      | dB     |   7 |    0.00851507  |       0.00231599  |        0.05 | True     |
| thd_percent (port vs production) | pp     |   7 |    1.45661e-12 |       8.52651e-14 |        0.01 | True     |

### `matlab_comparisons` (0 rows)



### `expected_dataset_values` (142 rows)

| test_id          | quantity    | unit   |   expected_python |
|:-----------------|:------------|:-------|------------------:|
| hha_band:2:63    | hha_band_db | dB     |           48.1212 |
| hha_band:2:125   | hha_band_db | dB     |           58.5992 |
| hha_band:2:250   | hha_band_db | dB     |           69.0371 |
| hha_band:2:500   | hha_band_db | dB     |           74.8429 |
| hha_band:2:1000  | hha_band_db | dB     |           79.0422 |
| hha_band:2:2000  | hha_band_db | dB     |           87.813  |
| hha_band:2:4000  | hha_band_db | dB     |           83.148  |
| hha_band:2:8000  | hha_band_db | dB     |           72.7304 |
| hha_band:2:16000 | hha_band_db | dB     |           53.7277 |
| hha_band:4:63    | hha_band_db | dB     |           32.758  |
| hha_band:4:125   | hha_band_db | dB     |           48.1112 |
| hha_band:4:250   | hha_band_db | dB     |           62.3732 |

## Artefacts

- tables: `port_comparisons.csv`, `matlab_comparisons.csv`, `expected_dataset_values.csv`
- figures: `port_agreement.png`

## Data provenance

```json
{
  "dataset_path": "Data.mat",
  "sha256": "45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48",
  "mat_format": "v5",
  "n_frequencies": 2049,
  "n_subjects": 14,
  "n_reinsertions": 3,
  "n_devices": 14,
  "invalid_policy": "exclude"
}
```
