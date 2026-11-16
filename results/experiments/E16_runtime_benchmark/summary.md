# E16 — Runtime Benchmark

**Status:** `completed`  
**Runtime:** 0.90 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_operations` | 14 |
| `repeats` | 3 |
| `total_median_ms` | 276.8542915582657 |
| `slowest_operation` | load_mat (no hash) |
| `slowest_median_ms` | 204.85700014978647 |
| `fastest_operation` | design_fir (101 taps) |
| `fastest_median_ms` | 0.04254188388586044 |
| `matlab_benchmark` | not_run (MATLAB unavailable in this environment) |
| `note` | Times are wall-clock medians; they include Python overhead and are intended as a relative regression baseline, not as hard real-time guarantees. |

## Summary

The complete benchmark (14 operations) runs in 0.28 s. The slowest operation is load_mat (no hash) (204.9 ms). FFT/PSD/STFT operations are dominated by the 4 s signal length; the estimators and the virtual device are cheap relative to data loading. No MATLAB timing is reported because MATLAB is unavailable.

## Tables

### `runtime_benchmark` (14 rows)

| operation                | category   |   repeats |   median_ms |     min_ms |    max_ms |   throughput_4s_per_s |
|:-------------------------|:-----------|----------:|------------:|-----------:|----------:|----------------------:|
| load_mat (no hash)       | I/O        |         3 |  204.857    | 204.398    | 221.51    |               19.5258 |
| estimate_thd             | estimator  |         3 |   24.5094   |  24.4485   |  24.6105  |              163.203  |
| estimate_filter_response | estimator  |         3 |   12.4205   |  12.3201   |  12.6813  |              322.049  |
| estimate_gain_db         | estimator  |         3 |    8.17338  |   8.17321  |   8.26879 |              489.394  |
| virtual_ha process (4 s) | virtual HA |         3 |    7.56779  |   7.46842  |   7.6085  |              528.556  |
| fft_spectrum (4 s)       | spectral   |         3 |    6.28367  |   6.16913  |   6.53121 |              636.571  |
| estimate_snr_db          | estimator  |         3 |    5.907    |   5.88167  |   5.98421 |              677.163  |
| apply_filter FIR (4 s)   | filtering  |         3 |    2.70846  |   2.70308  |   2.73946 |             1476.86   |
| welch_psd (4 s)          | spectral   |         3 |    1.80987  |   1.78933  |   1.88467 |             2210.1    |
| synthetic render_case    | synthetic  |         3 |    1.03738  |   1.02117  |   1.09013 |             3855.89   |
| stft (4 s)               | spectral   |         3 |    0.743458 |   0.723    |   1.75512 |             5380.26   |
| apply_filter IIR (4 s)   | filtering  |         3 |    0.637708 |   0.633959 |   0.90525 |             6272.46   |

## Artefacts

- tables: `runtime_benchmark.csv`
- figures: `runtime_benchmark.png`, `runtime_by_category.png`

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
