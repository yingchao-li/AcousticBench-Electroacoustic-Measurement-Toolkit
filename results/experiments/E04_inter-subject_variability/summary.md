# E04 — Inter-subject Variability

**Status:** `completed`  
**Runtime:** 0.76 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `note` | Between-subject SD uses subject-level means (reinsertions averaged); variance components are one-way random-effects estimates. |

## Summary

Between-ear differences dominate the reinsertion noise for occluding couplings, especially at low frequencies where ear-canal volume and earpiece fit vary strongly. For open domes the between-ear spread is smaller at low frequencies but still substantial. This justifies treating the subject as the independent statistical unit and using paired designs wherever possible.

## Tables

### `inter_subject_variability` (63 rows)

| band   |   band_center_hz |   device_code | device                         | family           | coupling   | condition   |   n_subjects |   n_subjects_complete |   mean_level_db |   sd_between_subject_db |   iqr_db |   range_db |    cv_db |   between_subject_variance_db2 |   within_subject_variance_db2 |   icc_1_1 |
|:-------|-----------------:|--------------:|:-------------------------------|:-----------------|:-----------|:------------|-------------:|----------------------:|----------------:|------------------------:|---------:|-----------:|---------:|-------------------------------:|------------------------------:|----------:|
| 63 Hz  |               63 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |                    12 |         48.959  |                 6.60059 | 10.5467  |   20.5754  | 13.4819  |                      36.3522   |                      7.36005  | 0.831625  |
| 63 Hz  |               63 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |                    13 |         28.9573 |                 2.00652 |  2.31516 |    5.95999 |  6.92923 |                       2.74578  |                      2.05832  | 0.57155   |
| 63 Hz  |               63 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |                     9 |         40.7795 |                10.7029  | 14.3117  |   39.1863  | 26.2458  |                     111.712    |                     14.8131   | 0.882923  |
| 63 Hz  |               63 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |                    13 |         40.4281 |                 7.67238 | 10.2843  |   24.8823  | 18.9778  |                      61.5401   |                      6.28099  | 0.907389  |
| 63 Hz  |               63 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |                    14 |         16.3826 |                 1.85963 |  1.61096 |    6.61011 | 11.3513  |                       0.788687 |                      8.00863  | 0.0896508 |
| 63 Hz  |               63 |            12 | Tulip Dome · Measurement       | tulip_dome       | dome       | measurement |           14 |                    14 |         26.6138 |                 7.5161  |  8.55957 |   29.1495  | 28.2414  |                      54.3654   |                      6.37919  | 0.894983  |
| 63 Hz  |               63 |            14 | Power Dome · Measurement       | power_dome       | dome       | measurement |           14 |                    14 |         33.1681 |                 9.95794 | 14.6477  |   32.1208  | 30.0226  |                      92.2063   |                     20.8628   | 0.815487  |
| 125 Hz |              125 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |                    12 |         58.0028 |                 5.64234 | 10.007   |   16.8854  |  9.72769 |                      27.3554   |                      5.34941  | 0.836433  |
| 125 Hz |              125 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |                    13 |         44.4843 |                 2.01303 |  2.76804 |    5.92497 |  4.52525 |                       3.37773  |                      0.295365 | 0.919587  |
| 125 Hz |              125 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |                     9 |         51.1517 |                 8.6502  | 11.8997  |   30.606   | 16.9109  |                      71.0929   |                     10.4031   | 0.872348  |
| 125 Hz |              125 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |                    13 |         51.2675 |                 6.59019 |  8.82716 |   20.3591  | 12.8545  |                      45.4081   |                      4.48716  | 0.910068  |
| 125 Hz |              125 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |                    14 |         24.994  |                 3.19584 |  4.77873 |    9.74625 | 12.7865  |                       9.87595  |                      1.01234  | 0.907025  |

### `inter_subject_variability_wide_band` (7 rows)

| band        |   band_center_hz |   device_code | device                         | family           | coupling   | condition   |   n_subjects |   n_subjects_complete |   mean_level_db |   sd_between_subject_db |   iqr_db |   range_db |   cv_db |   between_subject_variance_db2 |   within_subject_variance_db2 |   icc_1_1 |
|:------------|-----------------:|--------------:|:-------------------------------|:-----------------|:-----------|:------------|-------------:|----------------------:|----------------:|------------------------:|---------:|-----------:|--------:|-------------------------------:|------------------------------:|----------:|
| 500–4000 Hz |          1414.21 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |                    12 |         81.2709 |                 1.95667 |  2.51784 |    7.24113 | 2.40759 |                        2.40683 |                     0.737081  |  0.765553 |
| 500–4000 Hz |          1414.21 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |                    13 |         81.835  |                 2.08884 |  2.87493 |    7.15188 | 2.5525  |                        4.28882 |                     0.0743914 |  0.98295  |
| 500–4000 Hz |          1414.21 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |                     9 |         81.9111 |                 1.36731 |  1.73582 |    5.14519 | 1.66926 |                        1.72123 |                     0.256693  |  0.87022  |
| 500–4000 Hz |          1414.21 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |                    13 |         81.1094 |                 1.72836 |  2.35391 |    6.26083 | 2.1309  |                        2.86121 |                     0.119585  |  0.959882 |
| 500–4000 Hz |          1414.21 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |                    14 |         77.1695 |                 2.20473 |  3.00755 |    6.97976 | 2.85699 |                        4.77446 |                     0.259105  |  0.948525 |
| 500–4000 Hz |          1414.21 |            12 | Tulip Dome · Measurement       | tulip_dome       | dome       | measurement |           14 |                    14 |         79.4113 |                 2.19394 |  3.13153 |    7.13927 | 2.76276 |                        4.70963 |                     0.311257  |  0.938008 |
| 500–4000 Hz |          1414.21 |            14 | Power Dome · Measurement       | power_dome       | dome       | measurement |           14 |                    14 |         79.1467 |                 1.62321 |  2.15027 |    5.84837 | 2.05089 |                        2.5464  |                     0.265253  |  0.90566  |

### `between_subject_sd_by_frequency` (14308 rows)

|   frequency_hz |   device_code | family         | family_label   |   sd_between_subject_db |   n_subjects |
|---------------:|--------------:|:---------------|:---------------|------------------------:|-------------:|
|        53.833  |             2 | closed_earmold | Closed Earmold |                 6.89245 |           14 |
|        64.5996 |             2 | closed_earmold | Closed Earmold |                 6.79571 |           14 |
|        75.3662 |             2 | closed_earmold | Closed Earmold |                 6.41331 |           14 |
|        86.1328 |             2 | closed_earmold | Closed Earmold |                 6.30824 |           14 |
|        96.8994 |             2 | closed_earmold | Closed Earmold |                 6.16432 |           14 |
|       107.666  |             2 | closed_earmold | Closed Earmold |                 6.01724 |           14 |
|       118.433  |             2 | closed_earmold | Closed Earmold |                 5.85935 |           14 |
|       129.199  |             2 | closed_earmold | Closed Earmold |                 5.69016 |           14 |
|       139.966  |             2 | closed_earmold | Closed Earmold |                 5.58296 |           14 |
|       150.732  |             2 | closed_earmold | Closed Earmold |                 5.40808 |           14 |
|       161.499  |             2 | closed_earmold | Closed Earmold |                 5.29755 |           14 |
|       172.266  |             2 | closed_earmold | Closed Earmold |                 5.15887 |           14 |

### `between_subject_sd_frequency_summary` (14308 rows)

| family         |   frequency_hz |   median_sd_db |   q25_sd_db |   q75_sd_db |
|:---------------|---------------:|---------------:|------------:|------------:|
| closed_earmold |        53.833  |        6.89245 |     6.89245 |     6.89245 |
| closed_earmold |        64.5996 |        6.79571 |     6.79571 |     6.79571 |
| closed_earmold |        75.3662 |        6.41331 |     6.41331 |     6.41331 |
| closed_earmold |        86.1328 |        6.30824 |     6.30824 |     6.30824 |
| closed_earmold |        96.8994 |        6.16432 |     6.16432 |     6.16432 |
| closed_earmold |       107.666  |        6.01724 |     6.01724 |     6.01724 |
| closed_earmold |       118.433  |        5.85935 |     5.85935 |     5.85935 |
| closed_earmold |       129.199  |        5.69016 |     5.69016 |     5.69016 |
| closed_earmold |       139.966  |        5.58296 |     5.58296 |     5.58296 |
| closed_earmold |       150.732  |        5.40808 |     5.40808 |     5.40808 |
| closed_earmold |       161.499  |        5.29755 |     5.29755 |     5.29755 |
| closed_earmold |       172.266  |        5.15887 |     5.15887 |     5.15887 |

## Artefacts

- tables: `inter_subject_variability.csv`, `inter_subject_variability_wide_band.csv`, `between_subject_sd_by_frequency.csv.gz`, `between_subject_sd_frequency_summary.csv.gz`
- figures: `between_subject_sd_spectrum.png`, `between_subject_sd_bands.png`, `variance_decomposition.png`, `between_subject_heatmap.png`

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
