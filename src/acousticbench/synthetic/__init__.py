"""Reproducible synthetic validation cases with known ground truth.

The synthetic layer is the reference source of truth for the signal-processing
validation experiments (E09–E12, E14): it builds a deterministic randomised
factorial of gain, SNR, THD and frequency-response cases, renders them into
"measured" signals, and provides analytic ground truth derived from the actual
generated waveforms.

Typical usage::

    from acousticbench.synthetic import build_cases, render_case
    from acousticbench.dsp import estimate_gain_db

    cases = build_cases(n_cases=1000, seed=20260422, fs_hz=48000)
    reference_gain = [c for c in cases if c.category == "gain" and c.is_reference_condition]
    data = render_case(reference_gain[0])
    result = estimate_gain_db(data.input, data.output, data.fs_hz, tone_hz=1000.0)
    error_db = result.gain_db - data.ground_truth["gain_db"]
"""

from __future__ import annotations

from acousticbench.synthetic.cases import (
    CATEGORIES,
    DEFAULT_DURATION_S,
    DEFAULT_FS_HZ,
    DEFAULT_N_CASES,
    DEFAULT_SEED,
    GAIN_DB_RANGE,
    INPUT_LEVEL_DBFS_RANGE,
    NOISE_COLORS,
    REFERENCE_CONDITIONS,
    SNR_DB_RANGE,
    TARGETS,
    THD_PERCENT_RANGE,
    SyntheticCase,
    build_cases,
    save_manifest,
)
from acousticbench.synthetic.generator import SyntheticCaseData, render_case
from acousticbench.synthetic.ground_truth import (
    FILTER_TYPES,
    analytic_filter_response,
    build_synthetic_filter,
    evaluation_mask,
    gain_db_from_rms,
    harmonic_percent_from_amplitudes,
    sine_amplitude_from_dbfs,
    snr_db_from_powers,
    snr_db_from_waveforms,
    thd_percent_from_amplitudes,
    thd_plus_n_percent_from_rms,
)

__all__ = [
    # cases
    "CATEGORIES",
    "DEFAULT_DURATION_S",
    "DEFAULT_FS_HZ",
    "DEFAULT_N_CASES",
    "DEFAULT_SEED",
    "GAIN_DB_RANGE",
    "INPUT_LEVEL_DBFS_RANGE",
    "NOISE_COLORS",
    "REFERENCE_CONDITIONS",
    "SNR_DB_RANGE",
    "TARGETS",
    "THD_PERCENT_RANGE",
    "SyntheticCase",
    "build_cases",
    "save_manifest",
    # generator
    "SyntheticCaseData",
    "render_case",
    # ground truth
    "FILTER_TYPES",
    "analytic_filter_response",
    "build_synthetic_filter",
    "evaluation_mask",
    "gain_db_from_rms",
    "harmonic_percent_from_amplitudes",
    "sine_amplitude_from_dbfs",
    "snr_db_from_powers",
    "snr_db_from_waveforms",
    "thd_percent_from_amplitudes",
    "thd_plus_n_percent_from_rms",
]
