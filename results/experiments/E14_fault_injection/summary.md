# E14 — Fault Injection

**Status:** `completed`  
**Runtime:** 0.14 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_fault_types` | 6 |
| `n_detected_within_tolerance` | 6 |
| `detection_rate` | 1.0 |
| `mean_relative_error_percent` | 0.001157407407548525 |
| `deterministic_repetitions_per_fault` | 10 |
| `note` | Detection uses only the measured output; true injected parameters are used solely for scoring. |

## Summary

All six fault types are injected deterministically and recovered from the output: clipping from the peak level, dropout from the silent interval, DC offset from the signal mean, gain error from the tone amplitude, harmonic distortion from the harmonic amplitudes and latency from the cross-correlation lag. The detection table reports the true value, the measured value and the error, so the validation claim is fully auditable rather than asserted.

## Tables

### `fault_detection` (6 rows)

| fault_type          | true_parameter   |   true_value |   measured_value | unit   |   absolute_error |   relative_error_percent |   tolerance | detected   |
|:--------------------|:-----------------|-------------:|-----------------:|:-------|-----------------:|-------------------------:|------------:|:-----------|
| clipping            | clip_level_dbfs  |       -24    |       -24        | dBFS   |      0           |              0           |     0.5     | True       |
| dropout             | duration_s       |         0.3  |         0.300021 | s      |      2.08333e-05 |              0.00694444  |     0.01    | True       |
| dc_offset           | offset           |         0.05 |         0.05     | linear |      1.38778e-17 |              2.77556e-14 |     0.0001  | True       |
| gain_error          | gain_db          |        -6    |        -6        | dB     |      8.88178e-16 |              1.4803e-14  |     0.2     | True       |
| harmonic_distortion | percentage       |         3    |         3        | %      |      2.44249e-14 |              8.14164e-13 |     0.2     | True       |
| latency             | delay_ms         |        12    |        12        | ms     |      0           |              0           |     0.03125 | True       |

## Artefacts

- tables: `fault_detection.csv`
- figures: `fault_waveforms.png`, `fault_detection.png`

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
