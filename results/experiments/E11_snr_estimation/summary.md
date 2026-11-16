# E11 — SNR Estimation

**Status:** `completed`  
**Runtime:** 3.45 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_cases` | 250 |
| `n_reference_cases` | 100 |
| `target_db` | 0.5 |
| `reference_condition` | 1 kHz tone in additive white Gaussian noise, SNR 10…40 dB, 4 s Hann-windowed PSD estimate |
| `target_met_in_reference_condition` | True |
| `psd_target_met_in_reference_condition` | True |
| `note` | The residual estimator is primary; the PSD estimator is reported to expose the expected bias for non-flat (pink) noise. |

## Summary

Using the exact noise waveform as ground truth, the residual estimator recovers the SNR to within 0.0105 dB in the reference condition (target 0.5 dB), whereas the PSD estimator is accurate for white noise but biased for pink noise. Reporting both makes the estimator's validity domain explicit rather than hiding it.

## Tables

### `snr_case_results` (250 rows)

| case_id   |   tone_hz | noise_color   |   input_level_dbfs |   snr_db_true |   snr_db_estimated_residual |   error_residual_db |   snr_db_estimated_psd |   error_psd_db | is_reference_condition   |
|:----------|----------:|:--------------|-------------------:|--------------:|----------------------------:|--------------------:|-----------------------:|---------------:|:-------------------------|
| snr-0000  |      1000 | white         |                -20 |       10.1137 |                     10.1111 |        -0.00259946  |                10.147  |      0.0332997 | True                     |
| snr-0001  |      1000 | white         |                -20 |       14.2373 |                     14.2466 |         0.00925792  |                14.2812 |      0.0438658 | True                     |
| snr-0002  |      1000 | white         |                -20 |       33.6775 |                     33.6778 |         0.00033408  |                33.7074 |      0.0299449 | True                     |
| snr-0003  |      1000 | white         |                -20 |       17.0747 |                     17.0779 |         0.0032399   |                17.1145 |      0.0397883 | True                     |
| snr-0004  |      1000 | white         |                -20 |       30.1604 |                     30.1596 |        -0.000874723 |                30.1947 |      0.0342867 | True                     |
| snr-0005  |      1000 | white         |                -20 |       27.9318 |                     27.9313 |        -0.000470636 |                27.967  |      0.0351695 | True                     |
| snr-0006  |      1000 | white         |                -20 |       24.3153 |                     24.3161 |         0.000759843 |                24.3529 |      0.0376203 | True                     |
| snr-0007  |      1000 | white         |                -20 |       16.4471 |                     16.4573 |         0.0102236   |                16.5023 |      0.055272  | True                     |
| snr-0008  |      1000 | white         |                -20 |       39.4626 |                     39.4629 |         0.000258701 |                39.4774 |      0.0148173 | True                     |
| snr-0009  |      1000 | white         |                -20 |       18.5292 |                     18.5318 |         0.00258343  |                18.5647 |      0.0354507 | True                     |
| snr-0010  |      1000 | white         |                -20 |       19.2418 |                     19.2438 |         0.0019685   |                19.2779 |      0.0360509 | True                     |
| snr-0011  |      1000 | white         |                -20 |       28.405  |                     28.4058 |         0.000851105 |                28.4396 |      0.0346537 | True                     |

## Artefacts

- tables: `snr_case_results.csv`
- figures: `snr_scatter.png`, `snr_psd_by_color.png`, `snr_error_histogram.png`

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
