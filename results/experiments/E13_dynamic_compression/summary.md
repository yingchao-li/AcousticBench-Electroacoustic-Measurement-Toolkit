# E13 — Dynamic Compression

**Status:** `completed`  
**Runtime:** 0.12 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `configured_threshold_dbfs` | -35.0 |
| `configured_ratio` | 3.0 |
| `configured_attack_ms` | 5.0 |
| `configured_release_ms` | 50.0 |
| `measured_compression_ratio` | 3.0000000000000018 |
| `measured_static_slope` | 0.33333333333333315 |
| `max_static_curve_error_db` | 0.014968665483650057 |
| `measured_attack_settling_ms` | 2.9375000000000373 |
| `measured_release_settling_ms` | 237.2291666666667 |
| `settling_definition` | time to enter and remain within ±3 dB of the steady-state output level |
| `dynamic_note` | The configured attack/release values are one-pole detector time constants applied to signal power; the observed output-level settling time is not numerically identical to them, especially for release. |
| `multiband_low_band_gain_db` | -8.91172544206942 |
| `multiband_high_band_gain_db` | -3.3361834809762625 |
| `multiband_gain_difference_db` | 5.575541961093157 |
| `note` | All values are measured through the virtual device; configured ground truth is reported alongside the estimates. |

## Summary

The virtual compressor follows the configured static curve closely; the effective compression ratio recovered above the kneepoint is close to the configured ratio, and attack/release times are in the expected millisecond range. The multiband test shows that a loud high-frequency tone can be compressed independently of the low-frequency band, which is the behaviour needed for realistic hearing-aid fitting scenarios and for validating the gain-estimation experiments.

## Tables

### `static_compression_curve` (31 rows)

|   input_dbfs |   output_dbfs_measured |   output_dbfs_expected |   gain_db_measured |   gain_db_expected |     error_db |
|-------------:|-----------------------:|-----------------------:|-------------------:|-------------------:|-------------:|
|          -60 |               -60      |                    -60 |        0           |                  0 |  0           |
|          -58 |               -58      |                    -58 |        0           |                  0 |  0           |
|          -56 |               -56      |                    -56 |        0           |                  0 |  0           |
|          -54 |               -54      |                    -54 |        0           |                  0 |  0           |
|          -52 |               -52      |                    -52 |        0           |                  0 |  0           |
|          -50 |               -50      |                    -50 |        0           |                  0 |  0           |
|          -48 |               -48      |                    -48 |        0           |                  0 |  0           |
|          -46 |               -46      |                    -46 |        0           |                  0 |  0           |
|          -44 |               -44      |                    -44 |        0           |                  0 |  0           |
|          -42 |               -42      |                    -42 |        0           |                  0 |  0           |
|          -40 |               -40      |                    -40 |        0           |                  0 |  0           |
|          -38 |               -38.0001 |                    -38 |       -7.39971e-05 |                  0 | -7.39971e-05 |

### `multiband_gains` (2 rows)

| band         |   configured_ratio |   configured_kneepoint_dbfs |   measured_gain_db |   expected_static_gain_db |
|:-------------|-------------------:|----------------------------:|-------------------:|--------------------------:|
| low (300 Hz) |                8   |                         -40 |           -8.91173 |                  -8.75    |
| high (5 kHz) |                1.2 |                         -40 |           -3.33618 |                  -3.33333 |

## Artefacts

- tables: `static_compression_curve.csv`, `multiband_gains.csv`
- figures: `static_compression_curve.png`, `attack_release.png`, `multiband_gains.png`

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
