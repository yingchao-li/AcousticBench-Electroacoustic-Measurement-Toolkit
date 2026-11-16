# E05 — Acoustic Feedback

**Status:** `completed`  
**Runtime:** 0.34 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `sign_convention` | ΔHfb > 0 = stronger feedback in the measurement condition |
| `open_minus_closed_feedback_1kHz_db` | 11.988793262070267 |

## Summary

The feedback path is weakest (most negative) for the tightly sealed earmolds and strongest for the open dome, consistent with the amount of sound leaking back to the hearing-aid microphone. Inserting the measurement probe slightly increases the feedback path for loosely sealed couplings, because the additional slit forms a leak. This is the physical mechanism behind reduced usable gain in real-ear measurements, and it is reported here rather than hidden.

## Tables

### `feedback_median_curves` (14308 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | coupling   | condition   |   median_db |   mean_db |   sd_db |   n_valid |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:-----------|:------------|------------:|----------:|--------:|----------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     28.5828 |   27.2633 | 4.21902 |        40 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     22.0994 |   21.6521 | 6.48242 |        40 |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     17.6791 |   19.04   | 7.40915 |        40 |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     16.1302 |   16.8495 | 7.82221 |        40 |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     13.8455 |   14.1923 | 8.93244 |        40 |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     14.6282 |   15.4073 | 7.90926 |        40 |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     16.4296 |   15.4125 | 7.21608 |        40 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     13.3995 |   13.1069 | 9.0007  |        40 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     12.5807 |   12.0919 | 9.49191 |        40 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     11.2242 |   12.0674 | 7.3214  |        40 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     11.4698 |   12.1513 | 6.93963 |        40 |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     11.0658 |   10.6356 | 8.24931 |        40 |

### `feedback_percentile_curves` (12971 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | condition   |   n_valid |      q10 |      q25 |   median_db |     q75 |     q90 |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:------------|----------:|---------:|---------:|------------:|--------:|--------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 22.3799  | 24.158   |     28.5828 | 29.7455 | 31.7133 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 13.0692  | 17.1504  |     22.0994 | 24.7149 | 29.1687 |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 11.1008  | 14.7487  |     17.6791 | 22.5207 | 25.1716 |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  9.12044 | 13.6316  |     16.1302 | 19.7193 | 22.5666 |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  8.38585 | 11.4903  |     13.8455 | 18.2345 | 20.9011 |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  8.49345 | 12.1771  |     14.6282 | 18.8557 | 21.8282 |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  7.0091  | 11.0323  |     16.4296 | 18.3944 | 19.8123 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  4.48417 |  9.61746 |     13.3995 | 16.3733 | 18.5349 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  1.09371 |  7.93495 |     12.5807 | 14.9835 | 21.3077 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  3.3188  |  7.49253 |     11.2242 | 14.5729 | 17.7218 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  5.19579 |  8.04062 |     11.4698 | 13.7447 | 18.2257 |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 |  1.66424 |  5.71233 |     11.0658 | 13.8    | 17.3158 |

### `feedback_band_levels` (63 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |   mean_db |    sd_db |   n |   index_x |   q25_db |   index_y |   q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|----------:|---------:|----:|----------:|---------:|----------:|---------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |    11.4345  |  12.6674  |  8.64575 |  40 |         0 |  7.25904 |         0 | 17.7645  |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |    13.5806  |  15.4017  |  6.27861 |  40 |         1 | 12.0744  |         1 | 16.0789  |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |    23.8098  |  24.282   |  4.53457 |  40 |         2 | 21.5074  |         2 | 27.1622  |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |    23.9197  |  23.0271  |  8.16801 |  40 |         3 | 18.788   |         3 | 28.4265  |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |     7.39252 |   8.97962 |  7.72476 |  40 |         4 |  4.95508 |         4 |  9.35425 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |    28.7683  |  27.1619  |  7.69127 |  40 |         5 | 23.8228  |         5 | 32.2312  |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |     6.50879 |   8.41013 | 10.0504  |  40 |         6 |  3.44587 |         6 |  8.26537 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |    24.0976  |  24.2966  |  4.59399 |  40 |         7 | 20.6537  |         7 | 25.9823  |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |    24.7833  |  25.1229  |  8.78572 |  40 |         8 | 20.091   |         8 | 33.1559  |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |    17.2128  |  16.4607  |  6.75816 |  37 |         9 | 13.0945  |         9 | 22.4925  |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |    12.816   |  12.7893  |  3.07316 |  37 |        10 | 10.6188  |        10 | 15.2621  |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |    27.3353  |  26.8087  |  4.07828 |  37 |        11 | 24.8897  |        11 | 29.3079  |

### `feedback_delta_bands` (63 rows)

| family         | band     |   band_center_hz |   median_db |   mean_db |   sd_db |   n |   index_x |    q25_db |   index_y |   q75_db |
|:---------------|:---------|-----------------:|------------:|----------:|--------:|----:|----------:|----------:|----------:|---------:|
| closed_earmold | 1000 Hz  |             1000 |  2.21565    |  2.53138  | 4.98654 |  40 |         0 |  0.176992 |         0 |  5.35552 |
| closed_earmold | 125 Hz   |              125 |  0.575281   |  1.54336  | 5.71562 |  40 |         1 | -1.82773  |         1 |  3.25913 |
| closed_earmold | 16000 Hz |            16000 | -0.522537   | -0.897004 | 3.48109 |  40 |         2 | -2.39602  |         2 |  1.26014 |
| closed_earmold | 2000 Hz  |             2000 |  0.724935   |  1.19806  | 5.80281 |  40 |         3 | -1.64759  |         3 |  4.48628 |
| closed_earmold | 250 Hz   |              250 | -0.136593   |  0.44028  | 6.69311 |  40 |         4 | -2.49864  |         4 |  3.01876 |
| closed_earmold | 4000 Hz  |             4000 | -0.220192   |  1.23489  | 6.88704 |  40 |         5 | -2.76946  |         5 |  5.75051 |
| closed_earmold | 500 Hz   |              500 |  0.868734   |  1.64884  | 5.66709 |  40 |         6 | -0.817562 |         6 |  2.60746 |
| closed_earmold | 63 Hz    |               63 |  0.00137587 |  0.25488  | 5.05797 |  40 |         7 | -2.83844  |         7 |  2.57185 |
| closed_earmold | 8000 Hz  |             8000 |  0.445723   |  0.648208 | 4.62889 |  40 |         8 | -1.46636  |         8 |  2.93978 |
| nugget_earmold | 1000 Hz  |             1000 |  5.83845    |  4.95818  | 5.98604 |  35 |         9 |  1.75776  |         9 |  8.84215 |
| nugget_earmold | 125 Hz   |              125 |  0.105207   |  0.297068 | 4.22281 |  35 |        10 | -2.23338  |        10 |  4.12784 |
| nugget_earmold | 16000 Hz |            16000 |  0.77312    |  1.06343  | 3.2039  |  35 |        11 | -0.98963  |        11 |  2.55539 |

### `feedback_delta_raw` (2646 rows)

| band   |   band_center_hz |   band_low_hz |   band_high_hz |   device_code | device                       | family         | family_label   | coupling   | condition   |   subject |   reinsertion | valid   |   delta_hfb_db |
|:-------|-----------------:|--------------:|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:-----------|:------------|----------:|--------------:|:--------|---------------:|
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             1 | True    |       -2.70055 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             2 | True    |        1.98209 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             3 | True    |       -2.83483 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             1 | True    |       -4.13125 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             2 | True    |        4.23295 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             3 | True    |       -5.25659 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             1 | True    |        4.03169 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             2 | True    |        1.97536 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             3 | True    |       -1.80531 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             1 | True    |       11.4868  |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             2 | True    |       -2.66434 |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             3 | True    |       -4.14339 |

## Artefacts

- tables: `feedback_median_curves.csv.gz`, `feedback_percentile_curves.csv.gz`, `feedback_band_levels.csv`, `feedback_delta_bands.csv`, `feedback_delta_raw.csv.gz`
- figures: `feedback_curves.png`, `feedback_percentiles.png`, `feedback_band_levels.png`, `feedback_ptpe_bands.png`, `feedback_ptpe_heatmap.png`

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
