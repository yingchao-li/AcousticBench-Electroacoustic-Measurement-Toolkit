"""Digital signal processing layer of AcousticBench.

The package is intentionally split into four small modules:

``signals``
    Deterministic generators (tones, noise, sweeps) and level helpers.
``spectra``
    FFT, STFT and Welch PSD with labelled frequency axes.
``filters``
    FIR/IIR design, application and frequency-response evaluation.
``metrics``
    Measurement estimators (gain, SNR, THD, THD+N, H1 frequency response).

Everything operates on ``float64`` :class:`numpy.ndarray` signals and validates
its inputs eagerly.
"""

from __future__ import annotations

from acousticbench.dsp.filters import (
    FIR_KINDS,
    FirFilter,
    FrequencyResponseResult,
    IirFilter,
    apply_filter,
    design_fir,
    design_iir,
    frequency_response,
)
from acousticbench.dsp.metrics import (
    GainResult,
    SnrResult,
    ThdResult,
    ToneComponent,
    estimate_filter_response,
    estimate_gain_db,
    estimate_snr_db,
    estimate_thd,
    estimate_thd_plus_n,
    tone_component,
)
from acousticbench.dsp.signals import (
    add_awgn,
    apply_gain_db,
    dbfs,
    log_sweep,
    multi_tone,
    pink_noise,
    rms,
    sine,
    white_noise,
)
from acousticbench.dsp.spectra import (
    PsdResult,
    Spectrum,
    StftResult,
    fft_spectrum,
    stft,
    welch_psd,
)

__all__ = [
    # signals
    "add_awgn",
    "apply_gain_db",
    "dbfs",
    "log_sweep",
    "multi_tone",
    "pink_noise",
    "rms",
    "sine",
    "white_noise",
    # spectra
    "PsdResult",
    "Spectrum",
    "StftResult",
    "fft_spectrum",
    "stft",
    "welch_psd",
    # filters
    "FIR_KINDS",
    "FirFilter",
    "FrequencyResponseResult",
    "IirFilter",
    "apply_filter",
    "design_fir",
    "design_iir",
    "frequency_response",
    # metrics
    "GainResult",
    "SnrResult",
    "ThdResult",
    "ToneComponent",
    "estimate_filter_response",
    "estimate_gain_db",
    "estimate_snr_db",
    "estimate_thd",
    "estimate_thd_plus_n",
    "tone_component",
]
