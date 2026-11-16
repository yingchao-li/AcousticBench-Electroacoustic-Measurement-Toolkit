# E01 — Frequency Response

**Status:** `completed`  
**Runtime:** 0.44 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `n_families` | 7 |
| `note` | Levels are dB SPL at the 11.2 mV receiver drive. The clinical configuration (measurement probe, measurement condition) is used so that all seven families are comparable; dome conditions have no reference-probe data. |

## Summary

Hha is highest at mid frequencies (≈2 kHz) and rolls off both below 500 Hz and above 8 kHz. Closed and nugget earmolds show the highest low-frequency output, while open domes show the lowest, reflecting the acoustic leakage of the coupling. The across-subject fan chart demonstrates substantial inter-individual variability that must be respected by any statistical comparison (subject is the independent unit).

## Tables

### `hha_median_curves` (14308 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | coupling   | condition   |   median_db |   mean_db |   sd_db |   n_valid |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:-----------|:------------|------------:|----------:|--------:|----------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     43.8057 |   46.3879 | 6.92516 |        40 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     45.5426 |   47.5518 | 6.78311 |        40 |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     47.1407 |   49.5083 | 6.42927 |        40 |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     50.1948 |   52.2546 | 6.3131  |        40 |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     50.9636 |   53.1813 | 6.16745 |        40 |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     53.5846 |   55.6    | 6.02723 |        40 |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     54.4708 |   56.4361 | 5.87409 |        40 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     55.8743 |   57.6748 | 5.72037 |        40 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     57.4037 |   59.1311 | 5.61808 |        40 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     57.8144 |   59.4864 | 5.43845 |        40 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     59.2965 |   60.7964 | 5.33811 |        40 |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |     60.3042 |   61.6668 | 5.20675 |        40 |

### `hha_percentile_curves` (12971 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | condition   |   n_valid |     q10 |     q25 |   median_db |     q75 |     q90 |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:------------|----------:|--------:|--------:|------------:|--------:|--------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 38.3528 | 41.5382 |     43.8057 | 52.2584 | 55.7034 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 39.4243 | 42.8081 |     45.5426 | 53.3548 | 56.8805 |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 42.4086 | 44.7032 |     47.1407 | 55.2504 | 58.0647 |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 44.9351 | 47.4219 |     50.1948 | 57.9997 | 60.78   |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 45.8058 | 48.4025 |     50.9636 | 58.9402 | 61.3283 |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 48.2297 | 51.003  |     53.5846 | 61.3205 | 63.4323 |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 49.6817 | 51.9066 |     54.4708 | 62.074  | 63.9421 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 50.5915 | 53.344  |     55.8743 | 63.259  | 64.7517 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 51.9676 | 54.7983 |     57.4037 | 64.7329 | 66.0144 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 52.5879 | 55.2448 |     57.8144 | 64.9748 | 66.0832 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 53.9558 | 56.6941 |     59.2965 | 66.2523 | 67.36   |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | 55.0015 | 57.6828 |     60.3042 | 67.0578 | 68.2561 |

### `hha_band_levels_summary` (63 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |   mean_db |   sd_db |   n |   index_x |   q25_db |   index_y |   q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|----------:|--------:|----:|----------:|---------:|----------:|---------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |     77.4875 |   77.3332 | 1.64275 |  40 |         0 |  76.337  |         0 |  78.4218 |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |     57.0945 |   58.7458 | 5.58549 |  40 |         1 |  54.4959 |         1 |  64.2517 |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |     54.5312 |   54.3726 | 4.18892 |  40 |         2 |  51.3633 |         2 |  56.9533 |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |     85.7973 |   85.6572 | 2.24967 |  40 |         3 |  84.1856 |         3 |  87.0682 |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |     67.2322 |   67.7465 | 4.22432 |  40 |         4 |  64.4533 |         4 |  71.5092 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |     81.3995 |   80.8982 | 2.96535 |  40 |         5 |  78.9753 |         5 |  82.7152 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |     73.1074 |   72.9068 | 3.56217 |  40 |         6 |  71.8948 |         6 |  75.0184 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |     47.2763 |   49.527  | 6.57378 |  40 |         7 |  44.6158 |         7 |  55.285  |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |     70.2254 |   70.9764 | 4.44245 |  40 |         8 |  67.6113 |         8 |  74.8755 |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |     78.2359 |   77.6198 | 1.82275 |  37 |         9 |  76.7091 |         9 |  78.8419 |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |     50.0807 |   51.7176 | 8.4901  |  37 |        10 |  44.5299 |        10 |  57.1187 |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |     52.5514 |   53.7231 | 4.55979 |  37 |        11 |  50.2592 |        11 |  56.0814 |

### `hha_band_levels_raw` (2646 rows)

| band   |   band_center_hz |   band_low_hz |   band_high_hz |   device_code | device                       | family         | family_label   | coupling   | condition   |   subject |   reinsertion |   level_db | valid   | quantity   | unit             |
|:-------|-----------------:|--------------:|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:-----------|:------------|----------:|--------------:|-----------:|:--------|:-----------|:-----------------|
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             1 |    44.9323 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             2 |    49.1788 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         1 |             3 |    46.9873 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             1 |    56.9336 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             2 |    55.5533 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         2 |             3 |    56.5592 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             1 |    44.5795 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             2 |    44.0814 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         3 |             3 |    46.3397 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             1 |    55.261  | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             2 |    55.9348 | True    | Hha        | dB SPL @ 11.2 mV |
| 63 Hz  |               63 |            50 |        89.0955 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | earmold    | measurement |         4 |             3 |    55.1988 | True    | Hha        | dB SPL @ 11.2 mV |

## Artefacts

- tables: `hha_median_curves.csv.gz`, `hha_percentile_curves.csv.gz`, `hha_band_levels_summary.csv`, `hha_band_levels_raw.csv.gz`
- figures: `hha_median_curves.png`, `hha_subject_distribution.png`, `hha_band_heatmap.png`

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
