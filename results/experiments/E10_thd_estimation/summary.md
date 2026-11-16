# E10 — THD Estimation

**Status:** `completed`  
**Runtime:** 6.06 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_cases` | 250 |
| `n_reference_cases` | 100 |
| `target_percentage_points` | 0.1 |
| `reference_condition` | 1 kHz tone, THD 0.5…5 %, no noise, integer number of periods, Hann-windowed harmonic analysis |
| `target_met_in_reference_condition` | True |
| `note` | THD is estimated from Hann-windowed harmonic projections; the injected harmonic amplitudes are known exactly from the generated waveforms. |

## Summary

Harmonic projection recovers the injected THD to within 3.49e-13 percentage points in the reference condition (target 0.1 pp). The wider range probes distortion up to 10 % and multiple fundamental frequencies; the estimator remains within the target there too, which shows that the method is not tuned to a single case.

## Tables

### `thd_case_results` (250 rows)

| case_id   |   tone_hz |   input_level_dbfs |   thd_percent_true |   thd_percent_estimated |   error_percentage_points |   fundamental_dbfs | is_reference_condition   |
|:----------|----------:|-------------------:|-------------------:|------------------------:|--------------------------:|-------------------:|:-------------------------|
| thd-0000  |      1000 |                -20 |           0.718103 |                0.718103 |              -1.94955e-13 |                -20 | True                     |
| thd-0001  |      1000 |                -20 |           1.14845  |                1.14845  |               2.61124e-13 |                -20 | True                     |
| thd-0002  |      1000 |                -20 |           4.95741  |                4.95741  |               1.62537e-13 |                -20 | True                     |
| thd-0003  |      1000 |                -20 |           4.06554  |                4.06554  |               4.52971e-14 |                -20 | True                     |
| thd-0004  |      1000 |                -20 |           4.8712   |                4.8712   |              -1.83853e-13 |                -20 | True                     |
| thd-0005  |      1000 |                -20 |           3.50132  |                3.50132  |              -9.41469e-14 |                -20 | True                     |
| thd-0006  |      1000 |                -20 |           2.34254  |                2.34254  |               6.88338e-14 |                -20 | True                     |
| thd-0007  |      1000 |                -20 |           0.549685 |                0.549685 |               1.48659e-13 |                -20 | True                     |
| thd-0008  |      1000 |                -20 |           2.49592  |                2.49592  |              -1.74527e-13 |                -20 | True                     |
| thd-0009  |      1000 |                -20 |           1.78939  |                1.78939  |               2.14051e-13 |                -20 | True                     |
| thd-0010  |      1000 |                -20 |           1.19534  |                1.19534  |               1.108e-13   |                -20 | True                     |
| thd-0011  |      1000 |                -20 |           1.61097  |                1.61097  |              -1.94955e-13 |                -20 | True                     |

## Artefacts

- tables: `thd_case_results.csv`
- figures: `thd_scatter.png`, `thd_error_histogram.png`, `thd_error_vs_level.png`

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
