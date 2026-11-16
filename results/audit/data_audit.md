# AcousticBench data audit

Generated: `2026-11-16T16:12:02+00:00`

**12 checks passed, 0 warnings, 0 errors.**

## Dataset provenance

- File: `Data.mat`
- Size: 86.1 MB
- MAT format: v5
- SHA-256: `45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48`
- Source: Denk, Hackenberg & Husstedt (2026), doi:10.5281/zenodo.20023285 (CC BY 4.0)

## Axes

- Frequency: 2049 bins, 0.0 … 22050.0 Hz, Δf = 10.7666015625 Hz (uniform grid: True)
- Audiometric frequencies: [125.0, 250.0, 500.0, 750.0, 1000.0, 2000.0] Hz
- Threshold quantisation: 1.0 dB (observed residual ≤ 0.0 dB)

## Checks

| Status | Code | Finding |
| --- | --- | --- |
| PASS | `nan_session_consistency` | All five transfer-function containers share the identical NaN session mask (18 invalid sessions); measurement sessions were invalidated as a whole. |
| PASS | `threshold_invalid_sessions` | The threshold container has 19 invalid sessions (transfer functions: 18); 1 extremely invalid threshold session(s) exist beyond the transfer-function mask and are excluded independently. |
| INFO | `partial_nan_sessions` | No partial NaN sessions: invalid data are whole search-block columns. |
| PASS | `frequency_axis` | Frequency axis is a uniform DFT grid: 2049 bins from 0 to 22050 Hz, Δf = 10.766602 Hz (4096-point DFT at 44.1 kHz). The DC bin and the < 50 Hz bins (outside the sweep range) are excluded from level statistics. |
| PASS | `threshold_axis` | Audiometric thresholds are given in dBV at 125, 250, 500, 750, 1000 and 2000 Hz; values are quantised to 1 dB (max residual 0.00e+00 dB). |
| PASS | `structural_mpt_loose_in_reference` | The measurement probe microphone in the REFERENCE condition is 45–65 dB below its in-ear level, confirming that it hung loosely around the ear. M_*edM reference-condition values are therefore structurally invalid for eardrum-pressure analysis and are masked, not imputed. |
| PASS | `structural_rpt_missing_for_domes` | For dome conditions the reference probe tube was not used (documented); its hearing-aid-driver level is 59.2 dB below the earmold level. M_*edR dome values are structurally invalid for eardrum pressure. |
| PASS | `structural_free_field_signature` | Loudspeaker-driven signals of loosely hanging probes are device-independent (across-device SD 0.52 dB at 1 kHz, 0.34 dB for dome RPT), confirming the free-field interpretation and enabling an in-situ free-field reference. |
| PASS | `units_hha_db_spl` | Hearing-aid driver pressures interpreted as Pa at 11.2 mV yield 82.8 dB SPL (median, 0.5–4 kHz), consistent with the documentation and Figure 4 of the preprint. |
| PASS | `units_cross_probe_agreement` | When both probe tubes are in the ear (measurement condition) the two probe microphones agree to a median |bias| of 1.69 dB; the reference probe reads systematically ~1.5 dB higher, which is reported as a probe-placement bias rather than hidden. |
| PASS | `units_reoig_sign` | Ratio-based REOIG at 1 kHz is strongly negative for the closed earmold (-10.9 dB) and near zero for the open dome (0.5 dB), as expected from the coupling tightness. |
| PASS | `units_reug_shape` | The real-ear unaided gain obtained with the in-situ free-field reference is +0.6 dB at 1 kHz, +14.0 dB at 2 kHz and +15.7 dB at 4 kHz, i.e. the expected ear-canal resonance shape. This validates the free-field normalisation used for loudspeaker-driven levels. |
| PASS | `expected_ptpe_direction` | Probe insertion reduces low-frequency hearing-aid-driver output (ΔHha at 100 Hz = -4.4 dB), increases sound leakage into the ear (ΔREOIG at 2 kHz = +1.4 dB) and increases the driver voltage at threshold (ΔT at 125 Hz = -2.0 dB). These reproducible directions validate the reference/measurement semantics. |
| INFO | `reinsertion_repeatability` | Within-subject reinsertion SD of |Hha| (0.5–4 kHz, measurement condition) has a median of 0.38 dB and a 95th percentile of 1.47 dB. This is the noise floor against which probe-presence effects must be judged. |
| INFO | `absolute_free_field_scaling` | The stored loudspeaker-driven levels are not normalised to 1 Pa free field: the in-situ free-field reference is ≈ −27 dB at 1 kHz. Absolute REUG/REOG figures in this toolkit therefore use the in-situ reference; REOIG ratios are scale-invariant and unaffected. See docs/data.md. |
| INFO | `reference_condition_not_available_for_domes` | For dome conditions no reference probe tube exists, so reference-condition Hha/REOIG are not available; the probe-tube presence effect for domes is evaluated via the threshold differences only. |
| INFO | `invalid_values_never_imputed` | NaN sessions and structurally invalid entries are excluded, never imputed. All analyses report the number of contributing subjects. |

## Variables

| key      | shape             | dtype      |   n_nan |   nan_fraction |   median_level_db | unit                       |
|:---------|:------------------|:-----------|--------:|---------------:|------------------:|:---------------------------|
| M_ha2edM | (2049, 14, 14, 3) | complex128 |   36882 |      0.0306122 |          -53.9383 | Pa at 11.2 mV drive        |
| M_ha2edR | (2049, 14, 14, 3) | complex128 |   36882 |      0.0306122 |          -53.3007 | Pa at 11.2 mV drive        |
| M_ha2haf | (2049, 14, 14, 3) | complex128 |   36882 |      0.0306122 |          -71.5515 | Pa at 11.2 mV drive        |
| M_ls2edM | (2049, 14, 14, 3) | complex128 |   36882 |      0.0306122 |          -30.0022 | Pa at free-field reference |
| M_ls2edR | (2049, 14, 14, 3) | complex128 |   36882 |      0.0306122 |          -32.5957 | Pa at free-field reference |
| M_thr_ha | (6, 14, 14, 3)    | float64    |     114 |      0.0323129 |          -91      | dBV                        |
| M_REUR   | (2049, 14)        | complex128 |       0 |      0         |          -25.5397 | Pa at free-field reference |

## Invalid (NaN) sessions

109 (container, device, subject, reinsertion) sessions are completely NaN and are excluded from every analysis.

| container   |   n_invalid_sessions |
|:------------|---------------------:|
| M_ha2edM    |                   18 |
| M_ha2edR    |                   18 |
| M_ha2haf    |                   18 |
| M_ls2edM    |                   18 |
| M_ls2edR    |                   18 |
| M_thr_ha    |                   19 |

## Derived interpretation

### structural_signatures

- **measurement_probe_reference_condition_level_gap_db**: {'closed_earmold': 62.37, 'vented_earmold': 62.43, 'nugget_earmold': 60.86, 'silicone_earmold': 60.92, 'open_dome': 44.92, 'tulip_dome': 57.1, 'power_dome': 60.25}
- **reference_probe_dome_level_gap_db**: 59.21
- **free_field_across_device_sd_db**: {'M_ls2edM_reference_at_1kHz': 0.522, 'M_ls2edM_reference_at_4kHz': 0.537, 'M_ls2edR_domes_at_1kHz': 0.344}

### unit_interpretation

- **hha_median_db_spl_500_4000Hz**: 82.84
- **threshold_range_dbv**: [-125.0, -23.0]
- **cross_probe_bias_db**: {'100': -1.6879677059620022, '250': -1.6868304169398058, '500': -1.713144660512981, '1000': -1.3698198229699763, '2000': -1.571666798496679, '4000': -1.4568284545989023, '8000': -3.1386494411363373}
- **reoig_1kHz_db**: {'closed_earmold': -10.92, 'vented_earmold': -0.74, 'nugget_earmold': -5.14, 'silicone_earmold': -6.52, 'open_dome': 0.47, 'tulip_dome': 1.02, 'power_dome': -0.43}
- **reug_db**: {'1000': 0.64, '2000': 13.97, '4000': 15.74}

### probe_tube_presence_effect

- **delta_hha_100Hz_db_by_family**: {'closed_earmold': -4.05, 'vented_earmold': -0.22, 'nugget_earmold': -9.27, 'silicone_earmold': -4.67}
- **delta_hha_100Hz_median_db**: -4.36
- **delta_hha_1kHz_median_db**: -0.19690184092678997
- **delta_reoig_2kHz_median_db**: 1.45
- **delta_threshold_125Hz_median_db**: -2.0
- **note**: ΔT = T_ref − T_meas equals the equivalent change of Hha at the eardrum, so threshold data extend the PTPE to domes where no reference probe exists.

### repeatability

- **within_subject_reinsertion_sd_db_median_500_4000**: 0.38
- **p95_db**: 1.47
- **note**: SD across the three reinsertions with probe tubes left in place.


## Structural validity rules

| container   | valid_conditions   | valid_couplings   |   n_structurally_valid_devices | rationale                                                                                                                                                                                          |
|:------------|:-------------------|:------------------|-------------------------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| M_ha2edM    | measurement        | all               |                              7 | In the reference condition the measurement probe tube microphone was hanging loosely around the ear (Documentation.pdf); its signal is not an eardrum pressure, although it is stored as a number. |
| M_ha2edR    | all                | earmold           |                              8 | The reference probe tube was inserted through a dedicated bore in the earmold and used only for earmold measurements; for domes no reference-probe eardrum pressure exists.                        |
| M_ha2haf    | all                | all               |                             14 | The hearing-aid microphone is part of the device and always present.                                                                                                                               |
| M_ls2edM    | measurement        | all               |                              7 | In the reference condition the measurement probe tube was hanging loosely around the ear; the stored loudspeaker response then measures the free field, not the eardrum.                           |
| M_ls2edR    | all                | earmold           |                              8 | The reference probe tube was available for earmolds only; dome conditions store the loosely hanging reference microphone instead.                                                                  |
| M_thr_ha    | all                | all               |                             14 | Thresholds are behavioural and exist for all earpieces/conditions.                                                                                                                                 |
| M_REUR      | all                | all               |                              1 | Measured in the open ear with the measurement probe in place and one insertion per participant; used as the unaided (open-ear) reference of the real-ear occluded insertion gain.                  |
