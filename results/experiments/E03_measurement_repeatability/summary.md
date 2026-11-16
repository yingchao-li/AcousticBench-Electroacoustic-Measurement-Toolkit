# E03 — Measurement Repeatability

**Status:** `completed`  
**Runtime:** 0.75 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `overall_median_sd_500_4000Hz_db` | 0.38379709903873427 |
| `note` | SD is taken across the three reinsertions of the same subject; the probe tubes stayed in place between reinsertions. |

## Summary

Reinsertion variability is a few dB in the mid frequencies and grows at the spectral extremes and for loosely coupled domes. The repeatability coefficient sets the smallest probe-tube presence effect that can be resolved for a single ear; the ICC indicates how much of the between-measurement variance is explained by the subject (high ICC = the ear dominates, low ICC = reinsertion noise dominates).

## Tables

### `repeatability_summary` (63 rows)

| band   |   band_center_hz |   device_code | device                         | family           | coupling   | condition   |   n_subjects |   median_level_db |   sd_reinsertion_db_median |   sd_reinsertion_db_p95 |   repeatability_coefficient_db |   icc_2_1 |
|:-------|-----------------:|--------------:|:-------------------------------|:-----------------|:-----------|:------------|-------------:|------------------:|---------------------------:|------------------------:|-------------------------------:|----------:|
| 63 Hz  |               63 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |           47.345  |                   2.02062  |                 4.60906 |                       5.60087  |  0.831046 |
| 63 Hz  |               63 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |           29.7027 |                   1.33267  |                 2.95022 |                       3.69398  |  0.578132 |
| 63 Hz  |               63 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |           42.7535 |                   1.97783  |                 7.8034  |                       5.48225  |  0.882456 |
| 63 Hz  |               63 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |           41.1268 |                   2.23834  |                 3.98252 |                       6.20435  |  0.907351 |
| 63 Hz  |               63 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |           16.5774 |                   2.84812  |                 4.10046 |                       7.89458  |  0.10112  |
| 63 Hz  |               63 |            12 | Tulip Dome · Measurement       | tulip_dome       | dome       | measurement |           14 |           25.1736 |                   1.85011  |                 4.69761 |                       5.12823  |  0.894985 |
| 63 Hz  |               63 |            14 | Power Dome · Measurement       | power_dome       | dome       | measurement |           14 |           33.2556 |                   3.50111  |                 7.80969 |                       9.70457  |  0.816045 |
| 125 Hz |              125 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |           56.5114 |                   1.57311  |                 4.12576 |                       4.36043  |  0.835954 |
| 125 Hz |              125 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |           44.6848 |                   0.327873 |                 2.58394 |                       0.908817 |  0.919755 |
| 125 Hz |              125 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |           52.653  |                   1.67854  |                 5.08212 |                       4.65269  |  0.871685 |
| 125 Hz |              125 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |           51.3745 |                   1.53098  |                 3.41848 |                       4.24366  |  0.910027 |
| 125 Hz |              125 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |           24.6258 |                   0.551795 |                 1.82765 |                       1.5295   |  0.906905 |

### `repeatability_wide_band` (7 rows)

| band        |   band_center_hz |   device_code | device                         | family           | coupling   | condition   |   n_subjects |   median_level_db |   sd_reinsertion_db_median |   sd_reinsertion_db_p95 |   repeatability_coefficient_db |   icc_2_1 |
|:------------|-----------------:|--------------:|:-------------------------------|:-----------------|:-----------|:------------|-------------:|------------------:|---------------------------:|------------------------:|-------------------------------:|----------:|
| 500–4000 Hz |          1414.21 |             2 | Closed Earmold · Measurement   | closed_earmold   | earmold    | measurement |           14 |           81.3389 |                   0.422147 |                1.55959  |                       1.17013  |  0.765149 |
| 500–4000 Hz |          1414.21 |             4 | Vented Earmold · Measurement   | vented_earmold   | earmold    | measurement |           14 |           82.4526 |                   0.254391 |                2.3028   |                       0.705135 |  0.982943 |
| 500–4000 Hz |          1414.21 |             6 | Nugget Earmold · Measurement   | nugget_earmold   | earmold    | measurement |           14 |           81.8299 |                   0.461489 |                1.03944  |                       1.27918  |  0.870409 |
| 500–4000 Hz |          1414.21 |             8 | Silicone Earmold · Measurement | silicone_earmold | earmold    | measurement |           14 |           80.8559 |                   0.279295 |                0.560225 |                       0.774167 |  0.959853 |
| 500–4000 Hz |          1414.21 |            10 | Open Dome · Measurement        | open_dome        | dome       | measurement |           14 |           77.232  |                   0.369724 |                0.954718 |                       1.02482  |  0.948469 |
| 500–4000 Hz |          1414.21 |            12 | Tulip Dome · Measurement       | tulip_dome       | dome       | measurement |           14 |           79.0854 |                   0.383797 |                0.913224 |                       1.06383  |  0.938046 |
| 500–4000 Hz |          1414.21 |            14 | Power Dome · Measurement       | power_dome       | dome       | measurement |           14 |           79.172  |                   0.424852 |                0.903079 |                       1.17763  |  0.905454 |

### `reinsertion_sd_by_frequency` (200312 rows)

|   frequency_hz |   device_code | device                       | family         | coupling   | condition   |   subject |   n_reinsertions |   sd_db |   range_db |
|---------------:|--------------:|:-----------------------------|:---------------|:-----------|:------------|----------:|-----------------:|--------:|-----------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 2.97269 |    5.94348 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 2.12798 |    4.2503  |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 2.16058 |    4.31361 |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.90384 |    3.80635 |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.98288 |    3.96314 |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.82418 |    3.64631 |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.83225 |    3.66373 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.74886 |    3.49257 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.80922 |    3.61771 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.65466 |    3.30878 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.69108 |    3.38155 |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | earmold    | measurement |         1 |                3 | 1.66887 |    3.33617 |

### `reinsertion_sd_frequency_summary` (14308 rows)

| family         |   frequency_hz |   median_sd_db |   q25_sd_db |   q75_sd_db |   n |
|:---------------|---------------:|---------------:|------------:|------------:|----:|
| closed_earmold |        53.833  |        2.16058 |    0.884414 |     3.28182 |  14 |
| closed_earmold |        64.5996 |        2.06907 |    1.30841  |     3.54911 |  14 |
| closed_earmold |        75.3662 |        2.00371 |    1.43643  |     2.837   |  14 |
| closed_earmold |        86.1328 |        1.8868  |    1.23881  |     2.85715 |  14 |
| closed_earmold |        96.8994 |        1.77823 |    1.23834  |     2.71879 |  14 |
| closed_earmold |       107.666  |        1.74491 |    1.23579  |     2.7503  |  14 |
| closed_earmold |       118.433  |        1.63686 |    1.17631  |     2.64626 |  14 |
| closed_earmold |       129.199  |        1.59513 |    1.17849  |     2.60846 |  14 |
| closed_earmold |       139.966  |        1.54832 |    1.17237  |     2.67009 |  14 |
| closed_earmold |       150.732  |        1.47177 |    1.0679   |     2.63849 |  14 |
| closed_earmold |       161.499  |        1.43768 |    0.962869 |     2.53167 |  14 |
| closed_earmold |       172.266  |        1.3741  |    0.867366 |     2.57655 |  14 |

## Artefacts

- tables: `repeatability_summary.csv`, `repeatability_wide_band.csv`, `reinsertion_sd_by_frequency.csv.gz`, `reinsertion_sd_frequency_summary.csv.gz`
- figures: `reinsertion_sd_spectrum.png`, `reinsertion_sd_bands.png`, `icc_bands.png`, `reinsertion_example.png`

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
