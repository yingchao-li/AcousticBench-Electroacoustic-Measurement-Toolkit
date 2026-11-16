# E02 — Probe Tube Measurement Bias

**Status:** `completed`  
**Runtime:** 0.44 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `probe_bias_median_abs_500_4000Hz_db` | 1.7433473594504676 |
| `n_subjects` | 14 |
| `sign_convention` | ΔHha<0 and ΔT<0 = reduced driver output; ΔREOIG>0 = more leakage |

## Summary

The two probe tubes agree within ≈1.5 dB when both are in the ear, with the measurement probe reading slightly lower; the bias grows towards 8 kHz. Inserting the measurement probe reduces the low-frequency driver output (ΔHha < 0), most strongly for the nugget earmold, and increases the leakage of external sound (ΔREOIG > 0), most strongly for the nugget and closed earmolds. Threshold differences at 125 Hz confirm the effect for all families and extend it to domes, where no reference probe exists. These directions reproduce the source study and validate the validity model implemented in AcousticBench.

## Tables

### `probe_bias_curves_percentiles` (7412 rows)

|   frequency_hz |   device_code | device                | family         | family_label   | condition   |   n_valid |       q10 |       q25 |   median_db |       q75 |       q90 |
|---------------:|--------------:|:----------------------|:---------------|:---------------|:------------|----------:|----------:|----------:|------------:|----------:|----------:|
|        53.833  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 |  3.31703  |  4.08603  |    4.32993  |  4.94663  |  6.59664  |
|        64.5996 |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -0.041156 |  0.126189 |    0.378971 |  0.83097  |  1.15664  |
|        75.3662 |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.12431  | -0.945171 |   -0.710464 | -0.337132 |  0.55697  |
|        86.1328 |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -0.943054 | -0.677658 |   -0.497256 | -0.419924 |  0.312975 |
|        96.8994 |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -2.06109  | -1.82446  |   -1.64608  | -1.5471   | -1.16874  |
|       107.666  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.14096  | -0.935492 |   -0.80974  | -0.692087 | -0.33339  |
|       118.433  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.80349  | -1.58985  |   -1.49194  | -1.3521   | -0.830795 |
|       129.199  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.86549  | -1.58707  |   -1.50738  | -1.3922   | -0.811766 |
|       139.966  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.40834  | -1.18563  |   -1.0836   | -0.959961 | -0.687033 |
|       150.732  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -2.08236  | -1.7983   |   -1.69654  | -1.61016  | -1.03954  |
|       161.499  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.75475  | -1.51928  |   -1.41173  | -1.29779  | -1.04725  |
|       172.266  |             2 | Closed Earmold · bias | closed_earmold | Closed Earmold | measurement |        40 | -1.79694  | -1.58587  |   -1.41804  | -1.31382  | -1.05236  |

### `probe_bias_bands_summary` (36 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |    mean_db |    sd_db |   n |   index_x |    q25_db |   index_y |    q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|-----------:|---------:|----:|----------:|----------:|----------:|----------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |  -1.56982   | -1.39064   | 1.02566  |  40 |         0 | -1.72311  |         0 | -1.40932  |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |  -1.40584   | -1.31184   | 0.696846 |  40 |         1 | -1.48182  |         1 | -1.29834  |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |   1.56065   |  0.833477  | 5.3601   |  40 |         2 | -1.73792  |         2 |  4.35509  |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |  -1.94889   | -1.76221   | 1.27012  |  40 |         3 | -2.32209  |         3 | -1.61253  |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |  -1.82952   | -1.69814   | 0.766739 |  40 |         4 | -1.92664  |         4 | -1.69369  |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |  -2.22788   | -1.72347   | 2.25467  |  40 |         5 | -3.02632  |         5 | -0.787101 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |  -1.74899   | -1.56988   | 0.904262 |  40 |         6 | -1.81538  |         6 | -1.55293  |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |  -0.0152888 |  0.0457891 | 0.817737 |  40 |         7 | -0.231209 |         7 |  0.196459 |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  -1.38554   | -1.45118   | 4.13201  |  40 |         8 | -4.04386  |         8 |  0.646785 |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |  -1.56725   | -0.180942  | 4.67178  |  37 |         9 | -1.76791  |         9 | -1.3363   |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |  -1.51489   |  0.226262  | 5.51615  |  37 |        10 | -1.61017  |        10 | -1.20863  |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  -0.0787892 |  1.21336   | 5.46181  |  37 |        11 | -3.03158  |        11 |  4.97233  |

### `probe_bias_bands_ci` (36 rows)

| family         | family_label   | band     |   band_center_hz |   n |     mean_db |    sd_db |     se_db |   ci_low_db |   ci_high_db |   abs_bias_db |
|:---------------|:---------------|:---------|-----------------:|----:|------------:|---------:|----------:|------------:|-------------:|--------------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |  14 | -1.40594    | 0.509697 | 0.136222  |   -1.70023  |    -1.11165  |    1.40594    |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |  14 | -1.31725    | 0.332543 | 0.0888758 |   -1.50926  |    -1.12525  |    1.31725    |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |  14 |  0.605475   | 4.44028  | 1.18671   |   -1.95826  |     3.16921  |    0.605475   |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |  14 | -1.79797    | 0.616503 | 0.164767  |   -2.15393  |    -1.44201  |    1.79797    |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |  14 | -1.70311    | 0.326427 | 0.0872414 |   -1.89158  |    -1.51464  |    1.70311    |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |  14 | -1.83102    | 1.40464  | 0.375406  |   -2.64204  |    -1.02001  |    1.83102    |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |  14 | -1.57694    | 0.411259 | 0.109914  |   -1.8144   |    -1.33949  |    1.57694    |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |  14 |  0.0498926  | 0.38045  | 0.10168   |   -0.169773 |     0.269558 |    0.0498926  |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  14 | -1.42106    | 3.58358  | 0.957752  |   -3.49015  |     0.648042 |    1.42106    |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |  14 | -0.387504   | 3.50256  | 0.936099  |   -2.40982  |     1.63481  |    0.387504   |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |  14 | -0.00216496 | 4.14005  | 1.10647   |   -2.39256  |     2.38823  |    0.00216496 |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  14 |  1.14989    | 4.09429  | 1.09425   |   -1.21409  |     3.51386  |    1.14989    |

### `ptpe_hha_curves_percentiles` (7412 rows)

|   frequency_hz |   device_code | device                | family         | family_label   | condition   |   n_valid |       q10 |       q25 |   median_db |       q75 |     q90 |
|---------------:|--------------:|:----------------------|:---------------|:---------------|:------------|----------:|----------:|----------:|------------:|----------:|--------:|
|        53.833  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 | -12.8101  | -10.1448  |    -5.02355 | -0.708715 | 3.23522 |
|        64.5996 |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 | -11.2125  |  -9.5068  |    -4.59376 | -1.11331  | 3.38397 |
|        75.3662 |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 | -10.4375  |  -9.16053 |    -4.62769 | -0.868105 | 2.96019 |
|        86.1328 |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 | -10.1649  |  -8.62399 |    -4.20377 | -0.384283 | 3.11062 |
|        96.8994 |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -9.81706 |  -8.06675 |    -4.05132 | -0.376902 | 2.88732 |
|       107.666  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -9.86099 |  -7.92385 |    -3.68648 | -0.72852  | 2.84835 |
|       118.433  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -9.22747 |  -7.51566 |    -3.39602 | -0.254294 | 2.95495 |
|       129.199  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -9.06076 |  -6.88171 |    -3.5469  | -0.381537 | 2.96484 |
|       139.966  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -8.74886 |  -6.5088  |    -2.98482 | -0.430452 | 2.87737 |
|       150.732  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -8.60712 |  -6.05997 |    -2.77705 | -0.550443 | 2.91315 |
|       161.499  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -8.50481 |  -5.67908 |    -2.4797  | -0.226752 | 2.83885 |
|       172.266  |           101 | Closed Earmold · ΔHha | closed_earmold | Closed Earmold |             |        40 |  -8.31814 |  -5.25448 |    -2.3683  | -0.430475 | 2.69767 |

### `ptpe_hha_bands_summary` (36 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |    mean_db |    sd_db |   n |   index_x |     q25_db |   index_y |    q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|-----------:|---------:|----:|----------:|-----------:|----------:|----------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 | -0.0865165  |  0.0346752 |  1.85248 |  40 |         0 |  -0.464358 |         0 |  0.461333 |
| closed_earmold | Closed Earmold | 125 Hz   |              125 | -2.90393    | -2.9184    |  4.50583 |  40 |         1 |  -6.30803  |         1 | -0.405184 |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 | -0.162827   |  0.868355  |  4.04431 |  40 |         2 |  -1.30213  |         2 |  2.3881   |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 | -0.156431   | -0.197048  |  2.20715 |  40 |         3 |  -0.768103 |         3 |  0.247528 |
| closed_earmold | Closed Earmold | 250 Hz   |              250 | -1.31141    | -1.43334   |  3.21569 |  40 |         4 |  -2.66326  |         4 | -0.126947 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 | -0.439118   | -0.742999  |  3.28021 |  40 |         5 |  -1.63611  |         5 |  0.359621 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 | -0.280188   | -0.483936  |  2.10772 |  40 |         6 |  -1.4203   |         6 |  0.294739 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 | -4.45936    | -4.15858   |  5.64897 |  40 |         7 |  -8.91285  |         7 | -0.490525 |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  0.00330652 | -0.0240183 |  3.44341 |  40 |         8 |  -1.68832  |         8 |  2.58961  |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 | -0.209203   | -0.804038  |  3.90252 |  35 |         9 |  -0.826719 |         9 |  0.452175 |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 | -6.70178    | -8.3518    | 10.1075  |  35 |        10 | -12.5216   |        10 | -2.97774  |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  0.727241   |  0.78467   |  5.69509 |  35 |        11 |  -1.68885  |        11 |  2.73394  |

### `ptpe_hha_bands_ci` (36 rows)

| family         | family_label   | band     |   band_center_hz |   n |    mean_db |   sd_db |    se_db |   ci_low_db |   ci_high_db |
|:---------------|:---------------|:---------|-----------------:|----:|-----------:|--------:|---------:|------------:|-------------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |  14 |  0.104905  | 1.29251 | 0.345438 |   -0.641369 |     0.851178 |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |  14 | -2.76278   | 3.21198 | 0.858437 |   -4.61732  |    -0.908245 |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |  14 |  0.997532  | 2.41298 | 0.644896 |   -0.395681 |     2.39075  |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |  14 | -0.107782  | 1.59796 | 0.427072 |   -1.03042  |     0.814851 |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |  14 | -1.33521   | 2.28123 | 0.609685 |   -2.65235  |    -0.018064 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |  14 | -0.653831  | 2.30635 | 0.616399 |   -1.98548  |     0.677818 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |  14 | -0.430356  | 1.47057 | 0.393026 |   -1.27944  |     0.418726 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |  14 | -3.997     | 4.08553 | 1.09191  |   -6.35592  |    -1.63808  |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  14 |  0.0343251 | 2.67382 | 0.714608 |   -1.50949  |     1.57814  |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |  14 | -0.747742  | 2.6433  | 0.706453 |   -2.27394  |     0.778456 |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |  14 | -9.01127   | 9.33255 | 2.49423  |  -14.3997   |    -3.62281  |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  14 |  1.05625   | 4.46068 | 1.19217  |   -1.51927  |     3.63177  |

### `ptpe_reoig_bands_summary` (36 rows)

| family         | family_label   | band     |   band_center_hz |   median_db |   mean_db |   sd_db |   n |   index_x |      q25_db |   index_y |   q75_db |
|:---------------|:---------------|:---------|-----------------:|------------:|----------:|--------:|----:|----------:|------------:|----------:|---------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |    3.24366  |  4.18043  | 5.10246 |  40 |         0 |  1.13607    |         0 |  7.34788 |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |    0.704981 |  2.97816  | 4.06962 |  40 |         1 |  0.0201044  |         1 |  5.27846 |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |    0.302673 |  0.124641 | 4.39603 |  40 |         2 | -1.0776     |         2 |  1.74256 |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |    2.38962  |  2.60748  | 3.91451 |  40 |         3 | -0.0200429  |         3 |  5.42791 |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |    1.60156  |  3.83952  | 4.61157 |  40 |         4 |  0.00925682 |         4 |  7.49145 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |    2.08305  |  2.02105  | 5.51377 |  40 |         5 | -0.594788   |         5 |  3.97277 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |    3.87718  |  4.45289  | 5.07547 |  40 |         6 | -0.142801   |         6 |  8.85243 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |    0.678549 |  2.23329  | 3.52546 |  40 |         7 |  0.177165   |         7 |  3.9063  |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |    2.02332  |  1.74735  | 6.82855 |  40 |         8 | -0.390836   |         8 |  3.44383 |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |    6.06355  |  6.50859  | 5.787   |  35 |         9 |  2.27821    |         9 | 11.1272  |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |    0.973035 |  3.67597  | 5.58517 |  35 |        10 |  0.0422569  |        10 |  4.81145 |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |    0.622489 |  3.01251  | 5.18369 |  35 |        11 |  0.0168875  |        11 |  3.50415 |

### `ptpe_reoig_bands_ci` (36 rows)

| family         | family_label   | band     |   band_center_hz |   n |   mean_db |   sd_db |    se_db |   ci_low_db |   ci_high_db |
|:---------------|:---------------|:---------|-----------------:|----:|----------:|--------:|---------:|------------:|-------------:|
| closed_earmold | Closed Earmold | 1000 Hz  |             1000 |  14 | 4.18519   | 4.12616 | 1.10276  |    1.80282  |      6.56757 |
| closed_earmold | Closed Earmold | 125 Hz   |              125 |  14 | 3.15197   | 4.13332 | 1.10468  |    0.765464 |      5.53848 |
| closed_earmold | Closed Earmold | 16000 Hz |            16000 |  14 | 0.0318538 | 2.98306 | 0.797255 |   -1.69051  |      1.75422 |
| closed_earmold | Closed Earmold | 2000 Hz  |             2000 |  14 | 2.52145   | 3.05961 | 0.817715 |    0.754888 |      4.28802 |
| closed_earmold | Closed Earmold | 250 Hz   |              250 |  14 | 3.93629   | 4.30755 | 1.15124  |    1.44918  |      6.42339 |
| closed_earmold | Closed Earmold | 4000 Hz  |             4000 |  14 | 1.87256   | 3.67607 | 0.982471 |   -0.249935 |      3.99506 |
| closed_earmold | Closed Earmold | 500 Hz   |              500 |  14 | 4.50877   | 4.39455 | 1.17449  |    1.97143  |      7.04611 |
| closed_earmold | Closed Earmold | 63 Hz    |               63 |  14 | 2.41338   | 3.61978 | 0.967427 |    0.323381 |      4.50338 |
| closed_earmold | Closed Earmold | 8000 Hz  |             8000 |  14 | 1.56522   | 3.94821 | 1.0552   |   -0.714403 |      3.84485 |
| nugget_earmold | Nugget Earmold | 1000 Hz  |             1000 |  14 | 6.74506   | 4.85666 | 1.298    |    3.94091  |      9.54921 |
| nugget_earmold | Nugget Earmold | 125 Hz   |              125 |  14 | 3.41167   | 4.55977 | 1.21865  |    0.778938 |      6.0444  |
| nugget_earmold | Nugget Earmold | 16000 Hz |            16000 |  14 | 3.20372   | 4.48232 | 1.19795  |    0.615708 |      5.79174 |

### `ptpe_threshold_125Hz` (98 rows)

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

### `ptpe_threshold_125Hz_ci` (7 rows)

| family           | family_label     |   n |      mean_db |    sd_db |    se_db |   ci_low_db |   ci_high_db |
|:-----------------|:-----------------|----:|-------------:|---------:|---------:|------------:|-------------:|
| closed_earmold   | Closed Earmold   |  14 | -3.89286     |  3.98909 | 1.06613  |    -6.19609 |    -1.58962  |
| nugget_earmold   | Nugget Earmold   |  14 | -5.95238     | 11.6019  | 3.10074  |   -12.6511  |     0.746364 |
| open_dome        | Open Dome        |  14 | -6.34413e-17 |  3.53735 | 0.945396 |    -2.0424  |     2.0424   |
| power_dome       | Power Dome       |  14 | -5.27381     |  5.7778  | 1.54418  |    -8.60981 |    -1.93781  |
| silicone_earmold | Silicone Earmold |  14 | -1.15476     |  4.93222 | 1.31819  |    -4.00254 |     1.69302  |
| tulip_dome       | Tulip Dome       |  14 | -1.28571     |  2.96664 | 0.792869 |    -2.9986  |     0.427175 |
| vented_earmold   | Vented Earmold   |  14 | -3.17207e-17 |  4.22902 | 1.13025  |    -2.44176 |     2.44176  |

## Artefacts

- tables: `probe_bias_curves_percentiles.csv.gz`, `probe_bias_bands_summary.csv`, `probe_bias_bands_ci.csv`, `ptpe_hha_curves_percentiles.csv.gz`, `ptpe_hha_bands_summary.csv`, `ptpe_hha_bands_ci.csv`, `ptpe_reoig_bands_summary.csv`, `ptpe_reoig_bands_ci.csv`, `ptpe_threshold_125Hz.csv`, `ptpe_threshold_125Hz_ci.csv`
- figures: `probe_bias_curves.png`, `ptpe_hha_curves.png`, `ptpe_reoig_bands.png`, `ptpe_hha_bands.png`, `ptpe_threshold_125.png`

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
