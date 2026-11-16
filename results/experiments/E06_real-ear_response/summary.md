# E06 — Real-Ear Response

**Status:** `completed`  
**Runtime:** 0.60 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_subjects` | 14 |
| `reug_median_db_at_1kHz` | 0.6427422613706462 |
| `reug_median_db_at_2kHz` | 13.967958079602573 |
| `reug_median_db_at_4kHz` | 15.738972032823444 |
| `note` | REOIG is a pressure ratio and scale-invariant. REUG/REOG use the in-situ free-field reference; see docs/data.md for the documented scaling caveat. |

## Summary

The open ear shows the characteristic ear-canal resonance of roughly +14 dB near 2 kHz relative to 1 kHz. Occluding the ear with a tightly sealed earmold strongly attenuates external sound below 2 kHz (negative REOIG), whereas open and tulip domes provide almost no attenuation. REOIG therefore quantifies coupling tightness and is the acoustic quantity most directly related to the probe-tube presence effect.

## Tables

### `reug_percentiles` (1853 rows)

|   frequency_hz |   device_code | device             | family   | family_label   | condition   |   n_valid |        q10 |        q25 |   median_db |      q75 |      q90 |
|---------------:|--------------:|:-------------------|:---------|:---------------|:------------|----------:|-----------:|-----------:|------------:|---------:|---------:|
|        53.833  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.905134  | -0.321328  |    0.479402 | 1.25857  | 1.62154  |
|        64.5996 |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -1.0205    | -0.626321  |    1.00687  | 2.07263  | 2.77893  |
|        75.3662 |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.739502  |  0.769661  |    1.13955  | 2.79146  | 3.49114  |
|        86.1328 |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.283318  |  0.165045  |    0.930826 | 1.43245  | 2.856    |
|        96.8994 |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.340129  | -0.0462197 |    0.395561 | 1.42315  | 2.21741  |
|       107.666  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.131785  |  0.213022  |    0.452181 | 0.786083 | 1.54998  |
|       118.433  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.043361  |  0.164574  |    0.603087 | 0.63601  | 0.846436 |
|       129.199  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.0104912 |  0.167636  |    0.513484 | 0.674603 | 0.825238 |
|       139.966  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 |  0.0553872 |  0.279996  |    0.367546 | 0.618595 | 0.908673 |
|       150.732  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 | -0.286973  |  0.05016   |    0.329898 | 0.647374 | 0.822723 |
|       161.499  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 |  0.0853288 |  0.223952  |    0.379878 | 0.713176 | 1.18983  |
|       172.266  |             0 | Open Ear · Unaided | open_ear | Open Ear       |             |        14 |  0.0782621 |  0.176214  |    0.30511  | 0.47794  | 0.805402 |

### `reoig_percentiles` (12971 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | condition   |   n_valid |      q10 |      q25 |   median_db |       q75 |        q90 |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:------------|----------:|---------:|---------:|------------:|----------:|-----------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.90182 | -1.88094 |   -0.814388 | -0.429013 |  0.856566  |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.54879 | -2.92636 |   -1.30527  | -0.700585 | -0.31505   |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.82329 | -2.55135 |   -1.64833  | -1.09195  |  0.165141  |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.43053 | -2.31171 |   -1.46347  | -0.965823 |  0.317224  |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.82347 | -1.78057 |   -1.13563  | -0.794936 |  0.268557  |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.81742 | -1.47675 |   -0.877627 | -0.648195 |  0.150016  |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.91772 | -1.22451 |   -0.682667 | -0.536105 |  0.146437  |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.11015 | -1.22219 |   -0.672019 | -0.479025 |  0.0985208 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.37518 | -1.35038 |   -0.704765 | -0.509374 |  0.0803824 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.71169 | -1.51182 |   -0.775726 | -0.580379 |  0.166798  |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -4.082   | -1.65924 |   -0.83116  | -0.563605 |  0.215764  |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -4.43638 | -1.81355 |   -0.819629 | -0.495136 |  0.271631  |

### `reog_percentiles` (12971 rows)

|   frequency_hz |   device_code | device                       | family         | family_label   | condition   |   n_valid |      q10 |       q25 |   median_db |       q75 |      q90 |
|---------------:|--------------:|:-----------------------------|:---------------|:---------------|:------------|----------:|---------:|----------:|------------:|----------:|---------:|
|        53.833  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.9456  | -1.44742  |   -0.307258 | 0.176437  | 0.730841 |
|        64.5996 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.37537 | -2.10208  |   -0.987351 | 0.57586   | 1.22351  |
|        75.3662 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.89353 | -2.35739  |   -0.156297 | 1.51219   | 2.65914  |
|        86.1328 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.63258 | -1.94767  |   -0.468993 | 0.691599  | 1.61324  |
|        96.8994 |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.98293 | -1.73166  |   -0.692839 | 0.549098  | 1.93836  |
|       107.666  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.31448 | -1.25927  |   -0.549771 | 0.529618  | 1.07725  |
|       118.433  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.43655 | -0.813536 |   -0.260452 | 0.103249  | 0.729158 |
|       129.199  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -2.34414 | -0.891559 |   -0.154465 | 0.221413  | 0.672725 |
|       139.966  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -3.22202 | -1.04113  |   -0.396052 | 0.0563335 | 0.793417 |
|       150.732  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -4.22316 | -1.11106  |   -0.706903 | 0.128903  | 0.525683 |
|       161.499  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -4.01724 | -1.33168  |   -0.46587  | 0.0895681 | 0.812286 |
|       172.266  |             2 | Closed Earmold · Measurement | closed_earmold | Closed Earmold | measurement |        40 | -4.30517 | -1.58608  |   -0.440906 | 0.113742  | 0.56835  |

### `reug_band_levels` (9 rows)

| family   | family_label   | band     |   band_center_hz |   median_db |     mean_db |    sd_db |   n |   index_x |     q25_db |   index_y |    q75_db |
|:---------|:---------------|:---------|-----------------:|------------:|------------:|---------:|----:|----------:|-----------:|----------:|----------:|
| open_ear | Open Ear       | 1000 Hz  |             1000 |   2.94221   |  2.44012    | 1.33329  |  14 |         0 |  1.89289   |         0 |  3.17613  |
| open_ear | Open Ear       | 125 Hz   |              125 |   0.397596  |  0.4308     | 0.440156 |  14 |         1 |  0.145447  |         1 |  0.660447 |
| open_ear | Open Ear       | 16000 Hz |            16000 |   5.41506   |  4.96739    | 3.00934  |  14 |         2 |  2.64128   |         2 |  7.33432  |
| open_ear | Open Ear       | 2000 Hz  |             2000 |  13.7396    | 14.1198     | 2.67379  |  14 |         3 | 12.3827    |         3 | 15.0949   |
| open_ear | Open Ear       | 250 Hz   |              250 |   0.0479268 |  0.00957268 | 0.515954 |  14 |         4 | -0.225657  |         4 |  0.371062 |
| open_ear | Open Ear       | 4000 Hz  |             4000 |  14.8692    | 14.4119     | 2.53906  |  14 |         5 | 12.6252    |         5 | 15.8156   |
| open_ear | Open Ear       | 500 Hz   |              500 |   0.307786  |  0.402165   | 0.735298 |  14 |         6 |  0.128317  |         6 |  0.940641 |
| open_ear | Open Ear       | 63 Hz    |               63 |   0.723504  |  0.959994   | 1.23655  |  14 |         7 | -0.0573771 |         7 |  1.85287  |
| open_ear | Open Ear       | 8000 Hz  |             8000 |   1.65951   |  2.21515    | 3.97877  |  14 |         8 |  0.281981  |         8 |  4.02122  |

### `reoig_band_levels` (63 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |   mean_db |   sd_db |   n |   index_x |     q25_db |   index_y |        q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|----------:|--------:|----:|----------:|-----------:|----------:|--------------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |  -10.6951   | -11.6168  | 6.81233 |  40 |         0 | -14.2119   |         0 |  -5.67768     |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |   -0.752072 |  -1.51084 | 2.22958 |  40 |         1 |  -1.42537  |         1 |  -0.578146    |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |  -11.5657   | -12.931   | 4.48498 |  40 |         2 | -17.0696   |         2 |  -9.39207     |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |  -22.079    | -22.8798  | 5.75234 |  40 |         3 | -26.5128   |         3 | -18.9551      |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |   -1.22736  |  -2.42118 | 3.69147 |  40 |         4 |  -3.054    |         4 |  -0.295608    |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |  -22.8897   | -23.8272  | 3.21742 |  40 |         5 | -26.0316   |         5 | -21.8527      |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |   -4.35768  |  -5.46693 | 5.58371 |  40 |         6 |  -7.42593  |         6 |  -1.00911     |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |   -1.43292  |  -1.65999 | 1.71782 |  40 |         7 |  -2.39559  |         7 |  -0.892685    |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  -12.726    | -12.9422  | 2.96862 |  40 |         8 | -15.3018   |         8 | -10.7497      |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |   -5.02712  |  -7.07542 | 8.46558 |  37 |         9 |  -9.96234  |         9 |  -1.13263     |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |   -0.466228 |  -1.1694  | 3.27247 |  37 |        10 |  -0.712814 |        10 |   0.000270463 |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  -11.708    | -11.6592  | 3.09421 |  37 |        11 | -13.2903   |        11 | -10.1101      |

## Artefacts

- tables: `reug_percentiles.csv`, `reoig_percentiles.csv.gz`, `reog_percentiles.csv.gz`, `reug_band_levels.csv`, `reoig_band_levels.csv`
- figures: `reug_curves.png`, `reoig_curves.png`, `reoig_band_levels.png`, `reog_curves.png`, `reoig_heatmap.png`

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
