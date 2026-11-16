# E09 — Gain Estimation

**Status:** `completed`  
**Runtime:** 2.35 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_cases` | 250 |
| `n_reference_cases` | 100 |
| `target_db` | 0.1 |
| `reference_condition` | 1 kHz tone, no compression, no noise, 4 s, -20 dBFS; estimate from the DFT bin of the tone |
| `target_met_in_reference_condition` | True |
| `note` | The estimator receives only input/output waveforms and the tone frequency. Errors are expressed in dB relative to the applying gain. |

## Summary

The coherent single-bin tone projection recovers the applied gain to within 5.33e-15 dB in the reference condition (target 0.1 dB) and remains accurate over the wider gain/level/frequency range. Because the estimate uses the input waveform as reference, it is insensitive to the absolute playback level and therefore directly transferable to a real measurement where the drive level is known.

## Tables

### `gain_case_results` (250 rows)

| case_id   |   tone_hz |   input_level_dbfs |   gain_db_true |   gain_db_estimated |     error_db | is_reference_condition   |
|:----------|----------:|-------------------:|---------------:|--------------------:|-------------:|:-------------------------|
| gain-0000 |      1000 |                -20 |       -4.11958 |            -4.11958 |  0           | True                     |
| gain-0001 |      1000 |                -20 |       -5.85193 |            -5.85193 |  0           | True                     |
| gain-0002 |      1000 |                -20 |       -2.06965 |            -2.06965 | -1.33227e-15 | True                     |
| gain-0003 |      1000 |                -20 |       -7.83297 |            -7.83297 | -1.77636e-15 | True                     |
| gain-0004 |      1000 |                -20 |        4.11669 |             4.11669 |  0           | True                     |
| gain-0005 |      1000 |                -20 |       -6.40333 |            -6.40333 |  0           | True                     |
| gain-0006 |      1000 |                -20 |       -8.84649 |            -8.84649 | -5.32907e-15 | True                     |
| gain-0007 |      1000 |                -20 |        6.28537 |             6.28537 | -8.88178e-16 | True                     |
| gain-0008 |      1000 |                -20 |      -10.395   |           -10.395   |  0           | True                     |
| gain-0009 |      1000 |                -20 |      -13.9559  |           -13.9559  |  0           | True                     |
| gain-0010 |      1000 |                -20 |      -11.6711  |           -11.6711  | -1.77636e-15 | True                     |
| gain-0011 |      1000 |                -20 |      -17.4805  |           -17.4805  | -3.55271e-15 | True                     |

## Artefacts

- tables: `gain_case_results.csv`
- figures: `gain_scatter.png`, `gain_error_histogram.png`, `gain_error_vs_tone.png`

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
