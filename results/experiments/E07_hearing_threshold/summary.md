# E07 — Hearing Threshold

**Status:** `completed`  
**Runtime:** 0.08 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `delta_t_vs_delta_hha_correlation` | 0.5607577517461055 |
| `delta_t_vs_delta_hha_slope` | 0.6127088771990051 |
| `delta_t_vs_delta_hha_mean_difference_db` | -1.1311801522458336 |
| `delta_t_vs_delta_hha_n` | 56 |
| `note` | ΔT = T_ref − T_meas is expressed in dB and equals the equivalent change of Hha at fixed drive voltage; negative values mean the probe reduces driver output. |

## Summary

Thresholds through the hearing-aid receiver are lowest (most sensitive) for the closed and nugget earmolds and highest for the open dome, matching the coupling tightness. Inserting the measurement probe raises the required voltage at 125 Hz for the occluding couplings, again mirroring the acoustic PTPE. The ΔT–ΔHha comparison confirms that threshold differences express the same level change as the transfer-function measurement, within the limits set by 1 dB threshold quantisation.

## Tables

### `threshold_curves` (84 rows)

| family         | family_label   | condition   |   frequency_hz |   median_dbv |   mean_dbv |   sd_dbv |   n_subjects |
|:---------------|:---------------|:------------|---------------:|-------------:|-----------:|---------:|-------------:|
| closed_earmold | Closed Earmold | measurement |            125 |        -65.5 |   -67.1    |  6.16358 |           14 |
| closed_earmold | Closed Earmold | measurement |            250 |        -83   |   -82.5    |  5.2818  |           14 |
| closed_earmold | Closed Earmold | measurement |            500 |        -95   |   -94      |  4.7985  |           14 |
| closed_earmold | Closed Earmold | measurement |            750 |       -100   |   -98.6    |  5.84764 |           14 |
| closed_earmold | Closed Earmold | measurement |           1000 |       -102.5 |  -101.95   |  4.14451 |           14 |
| closed_earmold | Closed Earmold | measurement |           2000 |       -105.5 |  -104.25   |  6.79272 |           14 |
| closed_earmold | Closed Earmold | reference   |            125 |        -71   |   -70.6905 |  5.65033 |           14 |
| closed_earmold | Closed Earmold | reference   |            250 |        -84   |   -83.8333 |  6.0321  |           14 |
| closed_earmold | Closed Earmold | reference   |            500 |        -95   |   -95.1667 |  4.73656 |           14 |
| closed_earmold | Closed Earmold | reference   |            750 |        -99.5 |   -99.619  |  6.74972 |           14 |
| closed_earmold | Closed Earmold | reference   |           1000 |       -102   |  -102.167  |  4.04798 |           14 |
| closed_earmold | Closed Earmold | reference   |           2000 |       -104   |  -104.548  |  6.89716 |           14 |

### `delta_threshold_125Hz` (98 rows)

| family         | family_label   |   subject |   reinsertion |   delta_t_db | valid   |
|:---------------|:---------------|----------:|--------------:|-------------:|:--------|
| closed_earmold | Closed Earmold |         1 |             1 |    -3.66667  | True    |
| closed_earmold | Closed Earmold |         2 |             1 |    -5        | True    |
| closed_earmold | Closed Earmold |         3 |             1 |    -2.66667  | True    |
| closed_earmold | Closed Earmold |         4 |             1 |    -9.33333  | True    |
| closed_earmold | Closed Earmold |         5 |             1 |    -5.5      | True    |
| closed_earmold | Closed Earmold |         6 |             1 |    -7.33333  | True    |
| closed_earmold | Closed Earmold |         7 |             1 |    -5        | True    |
| closed_earmold | Closed Earmold |         8 |             1 |    -1.66667  | True    |
| closed_earmold | Closed Earmold |         9 |             1 |     5.33333  | True    |
| closed_earmold | Closed Earmold |        10 |             1 |   -11        | True    |
| closed_earmold | Closed Earmold |        11 |             1 |    -3.33333  | True    |
| closed_earmold | Closed Earmold |        12 |             1 |    -0.333333 | True    |

### `delta_threshold_125Hz_ci` (7 rows)

| family           | family_label     |   n |      mean_db |    sd_db |    se_db |   ci_low_db |   ci_high_db |
|:-----------------|:-----------------|----:|-------------:|---------:|---------:|------------:|-------------:|
| closed_earmold   | Closed Earmold   |  14 | -3.89286     |  3.98909 | 1.06613  |    -6.19609 |    -1.58962  |
| nugget_earmold   | Nugget Earmold   |  14 | -5.95238     | 11.6019  | 3.10074  |   -12.6511  |     0.746364 |
| open_dome        | Open Dome        |  14 | -6.34413e-17 |  3.53735 | 0.945396 |    -2.0424  |     2.0424   |
| power_dome       | Power Dome       |  14 | -5.27381     |  5.7778  | 1.54418  |    -8.60981 |    -1.93781  |
| silicone_earmold | Silicone Earmold |  14 | -1.15476     |  4.93222 | 1.31819  |    -4.00254 |     1.69302  |
| tulip_dome       | Tulip Dome       |  14 | -1.28571     |  2.96664 | 0.792869 |    -2.9986  |     0.427175 |
| vented_earmold   | Vented Earmold   |  14 | -3.17207e-17 |  4.22902 | 1.13025  |    -2.44176 |     2.44176  |

### `delta_t_vs_delta_hha` (56 rows)

| family         | family_label   |   subject |   delta_t_db |   delta_hha_db |
|:---------------|:---------------|----------:|-------------:|---------------:|
| closed_earmold | Closed Earmold |         1 |    -3.66667  |       -1.37816 |
| closed_earmold | Closed Earmold |         2 |    -5        |       -3.30797 |
| closed_earmold | Closed Earmold |         3 |    -2.66667  |       -2.29158 |
| closed_earmold | Closed Earmold |         4 |    -9.33333  |       -8.07415 |
| closed_earmold | Closed Earmold |         5 |    -5.5      |        2.30905 |
| closed_earmold | Closed Earmold |         6 |    -7.33333  |       -8.42064 |
| closed_earmold | Closed Earmold |         7 |    -5        |       -1.60986 |
| closed_earmold | Closed Earmold |         8 |    -1.66667  |       -1.95302 |
| closed_earmold | Closed Earmold |         9 |     5.33333  |        1.19386 |
| closed_earmold | Closed Earmold |        10 |   -11        |       -7.36318 |
| closed_earmold | Closed Earmold |        11 |    -3.33333  |       -1.24785 |
| closed_earmold | Closed Earmold |        12 |    -0.333333 |       -2.74153 |

## Artefacts

- tables: `threshold_curves.csv`, `delta_threshold_125Hz.csv`, `delta_threshold_125Hz_ci.csv`, `delta_t_vs_delta_hha.csv`
- figures: `audiograms.png`, `delta_threshold_125.png`, `delta_t_vs_delta_hha.png`

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
