# E12 — Filter Response Estimation

**Status:** `completed`  
**Runtime:** 3.49 s  
**Seed:** 20260422

## Metrics

| metric | value |
| --- | --- |
| `n_cases` | 250 |
| `n_reference_cases` | 100 |
| `target_mae_db` | 0.5 |
| `reference_condition` | logarithmic sweep 100 Hz…10 kHz, 4 s, no noise, no compression; deconvolution vs. known filter response |
| `target_met_in_reference_condition` | True |
| `note` | The magnitude error is evaluated on the documented logarithmic evaluation grid within a 20 dB dynamic range of the pass-band; the phase is estimated but not scored because absolute delay is not part of the ground truth. |

## Summary

The H1 estimator recovers the magnitude response with a median MAE of 0.0161 dB in the reference condition (target 0.5 dB). The wider range adds sweep bands and noise; those cases are reported separately. Deep stop bands are excluded by the documented dynamic-range mask, since a finite-dynamic-range measurement cannot resolve them.

## Tables

### `frequency_response_case_results` (250 rows)

| case_id                 | filter_type   | cutoff_hz                               |   noise_snr_db |      mae_db |   max_abs_error_db |   n_evaluation_points | is_reference_condition   |
|:------------------------|:--------------|:----------------------------------------|---------------:|------------:|-------------------:|----------------------:|:-------------------------|
| frequency_response-0000 | bandpass      | (609.4530024265094, 2437.8120097060378) |            nan | 0.016093    |          0.0321655 |                   100 | True                     |
| frequency_response-0001 | highpass      | 100.65901354875122                      |            nan | 0.0439105   |          2.51824   |                   200 | True                     |
| frequency_response-0002 | lowpass       | 587.5865799367933                       |            nan | 0.01537     |          0.105871  |                    97 | True                     |
| frequency_response-0003 | lowpass       | 1107.2410760837236                      |            nan | 0.0167987   |          0.126124  |                   116 | True                     |
| frequency_response-0004 | highpass      | 988.8888922947884                       |            nan | 0.060872    |          2.51851   |                   119 | True                     |
| frequency_response-0005 | peaking       | 2190.039190589654                       |            nan | 0.000169715 |          0.0119948 |                   200 | True                     |
| frequency_response-0006 | lowpass       | 396.90920776151137                      |            nan | 0.0134863   |          0.0781856 |                    88 | True                     |
| frequency_response-0007 | peaking       | 2290.210235031638                       |            nan | 0.000174684 |          0.0105227 |                   200 | True                     |
| frequency_response-0008 | peaking       | 2674.8118650270885                      |            nan | 0.000269812 |          0.0202695 |                   200 | True                     |
| frequency_response-0009 | lowpass       | 1034.9554210125784                      |            nan | 0.0169179   |          0.126658  |                   114 | True                     |
| frequency_response-0010 | bandpass      | (898.8600917027555, 3595.440366811022)  |            nan | 0.0150159   |          0.0340052 |                    84 | True                     |
| frequency_response-0011 | bandpass      | (594.8364729366972, 2379.3458917467888) |            nan | 0.0161801   |          0.0320052 |                   102 | True                     |

## Artefacts

- tables: `frequency_response_case_results.csv`
- figures: `fr_example.png`, `fr_mae_histogram.png`, `fr_mae_by_filter.png`

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
