# E08 — Statistical Comparison

**Status:** `completed`  
**Runtime:** 0.41 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_tests` | 18 |
| `n_primary_family_tests` | 15 |
| `alpha` | 0.05 |
| `correction` | holm (within primary family tests) |
| `closed_vs_open_hha_1kHz_mean_difference_db` | 12.452558966594328 |
| `closed_vs_open_hha_1kHz_p_value` | 8.368493225391848e-09 |
| `probe_bias_1kHz_mean_db` | -0.5754651922840883 |
| `probe_bias_1kHz_p_value` | 0.19686251067308272 |
| `note` | Differences are a − b. Positive ΔREOIG means more leakage; negative ΔHha/ΔT mean reduced driver output. |

## Summary

All probe-tube presence effects are tested at the subject level with paired designs and interpreted against effect sizes and 95 % confidence intervals rather than p-values alone. Holm correction controls the family-wise error rate across the family-level tests. The closed-vs-open comparison quantifies the large acoustic difference between occluding and open couplings, while the probe-bias test shows whether the two probe microphones differ systematically.

## Warnings

- Shapiro–Wilk indicates non-normal paired differences in at least one test; Wilcoxon p-values are reported alongside the t-tests.

## Tables

### `paired_tests` (18 rows)

| test_id                             | metric      | family           | comparison                 |   n |       mean_a |   mean_b |    mean_diff |     ci_low |   ci_high |   bootstrap_ci_low |   bootstrap_ci_high |            t |   df |     p_value |   p_wilcoxon |     cohen_dz |   rank_biserial |   shapiro_p | holm_family   |       p_holm | significant_holm   |
|:------------------------------------|:------------|:-----------------|:---------------------------|----:|-------------:|---------:|-------------:|-----------:|----------:|-------------------:|--------------------:|-------------:|-----:|------------:|-------------:|-------------:|----------------:|------------:|:--------------|-------------:|:-------------------|
| hha_1kHz_closed_vs_open             | Hha@1kHz    | closed_vs_open   | closed earmold − open dome |  14 | 76.1541      |  63.7016 | 12.4526      |  10.3745   | 14.5306   |          10.63     |           14.2216   | 12.9459      |   13 | 8.36849e-09 |  0.00012207  |  3.45994     |        1        | 0.0588462   | contrast      | nan          | False              |
| ptpe_hha_125Hz_closed_earmold       | ΔHha@125Hz  | closed_earmold   | PTPE vs 0                  |  14 | -2.76278     |   0      | -2.76278     |  -4.61732  | -0.908245 |          -4.43872  |           -1.19862  | -3.21839     |   13 | 0.00672522  |  0.00524902  | -0.860151    |       -0.809524 | 0.15305     | primary       |   0.060527   | False              |
| ptpe_hha_125Hz_vented_earmold       | ΔHha@125Hz  | vented_earmold   | PTPE vs 0                  |  14 |  0.497796    |   0      |  0.497796    |  -5.00226  |  5.99785  |          -2.98578  |            5.936    |  0.19553     |   13 | 0.848001    |  0.0494385   |  0.0522575   |       -0.6      | 1.16174e-05 | primary       |   1          | False              |
| ptpe_hha_125Hz_nugget_earmold       | ΔHha@125Hz  | nugget_earmold   | PTPE vs 0                  |  14 | -9.01127     |   0      | -9.01127     | -14.3997   | -3.62281  |         -13.8613   |           -4.49033  | -3.61285     |   13 | 0.00315344  |  0.00231934  | -0.965574    |       -0.866667 | 0.35983     | primary       |   0.0380839  | True               |
| ptpe_hha_125Hz_silicone_earmold     | ΔHha@125Hz  | silicone_earmold | PTPE vs 0                  |  14 | -4.24847     |   0      | -4.24847     |  -6.78587  | -1.71106  |          -6.47789  |           -2.07052  | -3.61718     |   13 | 0.0031274   |  0.00671387  | -0.966733    |       -0.790476 | 0.895878    | primary       |   0.0380839  | True               |
| ptpe_reoig_1kHz_closed_earmold      | ΔREOIG@1kHz | closed_earmold   | PTPE vs 0                  |  14 |  4.18519     |   0      |  4.18519     |   1.80282  |  6.56757  |           2.34125  |            6.46748  |  3.79519     |   13 | 0.00222759  |  0.000610352 |  1.01431     |        0.942857 | 0.071896    | primary       |   0.0311863  | True               |
| ptpe_reoig_1kHz_vented_earmold      | ΔREOIG@1kHz | vented_earmold   | PTPE vs 0                  |  14 |  2.76075     |   0      |  2.76075     |  -2.45512  |  7.97661  |          -0.143387 |            7.84136  |  1.14348     |   13 | 0.273461    |  0.357544    |  0.305607    |        0.295238 | 1.7721e-06  | primary       |   1          | False              |
| ptpe_reoig_1kHz_nugget_earmold      | ΔREOIG@1kHz | nugget_earmold   | PTPE vs 0                  |  14 |  6.74506     |   0      |  6.74506     |   3.94091  |  9.54921  |           4.17334  |            9.04011  |  5.19652     |   13 | 0.000172131 |  0.000854492 |  1.38883     |        0.92381  | 0.13846     | primary       |   0.00258197 | True               |
| ptpe_reoig_1kHz_silicone_earmold    | ΔREOIG@1kHz | silicone_earmold | PTPE vs 0                  |  14 |  3.29565     |   0      |  3.29565     |   0.392416 |  6.19888  |           0.892698 |            5.91337  |  2.45238     |   13 | 0.0290829   |  0.0418701   |  0.655425    |        0.619048 | 0.358692    | primary       |   0.232663   | False              |
| ptpe_threshold_125Hz_closed_earmold | ΔT@125Hz    | closed_earmold   | PTPE vs 0                  |  14 | -3.89286     |   0      | -3.89286     |  -6.19609  | -1.58962  |          -5.95238  |           -1.82113  | -3.65139     |   13 | 0.00292953  |  0.00758571  | -0.975876    |       -0.809524 | 0.662565    | primary       |   0.0380839  | True               |
| ptpe_threshold_125Hz_vented_earmold | ΔT@125Hz    | vented_earmold   | PTPE vs 0                  |  14 | -3.17207e-17 |   0      | -3.17207e-17 |  -2.44176  |  2.44176  |          -1.7619   |            2.44048  | -2.80651e-17 |   13 | 1           |  0.283377    | -7.50071e-18 |       -0.32381  | 0.000336817 | primary       |   1          | False              |
| ptpe_threshold_125Hz_nugget_earmold | ΔT@125Hz    | nugget_earmold   | PTPE vs 0                  |  14 | -5.95238     |   0      | -5.95238     | -12.6511   |  0.746364 |         -11.786    |           -0.106845 | -1.91966     |   13 | 0.0771159   |  0.0418701   | -0.513052    |       -0.619048 | 0.62211     | primary       |   0.539811   | False              |

### `subject_level_data` (252 rows)

| test_id                 | metric   | family         |   subject |       a |       b |   difference |
|:------------------------|:---------|:---------------|----------:|--------:|--------:|-------------:|
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         1 | 76.7112 | 59.9406 |     16.7706  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         2 | 78.2198 | 68.3344 |      9.88542 |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         3 | 77.4673 | 67.9246 |      9.5427  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         4 | 79.3439 | 65.7097 |     13.6343  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         5 | 75.8756 | 60.1826 |     15.693   |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         6 | 78.4928 | 62.3926 |     16.1001  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         7 | 74.749  | 66.5362 |      8.21275 |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         8 | 74.9084 | 60.0911 |     14.8174  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |         9 | 75.7188 | 61.4483 |     14.2705  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |        10 | 77.7626 | 63.1488 |     14.6138  |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |        11 | 74.9192 | 68.1021 |      6.81718 |
| hha_1kHz_closed_vs_open | Hha@1kHz | closed_vs_open |        12 | 77.6218 | 61.0957 |     16.5261  |

## Artefacts

- tables: `paired_tests.csv`, `subject_level_data.csv`
- figures: `forest_effects.png`, `closed_vs_open_scatter.png`, `paired_differences.png`

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
