"""Electroacoustic measurement metrics: gain, SNR, THD and frequency response.

The estimators in this module are *measurement* algorithms applied to signals;
they never receive ground-truth values.  Threshold-based actions raise
:class:`~acousticbench.exceptions.MeasurementError` rather than silently
returning a default when a quantity is undefined (silence, invalid band,
non-finite data, ...).

Tone analysis
-------------
All tone-based metrics use a coherent single-bin projection onto a Hann
window, i.e. the complex correlation

.. math::

    c = \\sum_{n=0}^{N-1} x[n] w[n] e^{-j 2 \\pi f n / f_s}, \\qquad
    \\hat A = \\frac{2 |c|}{\\sum_n w[n]}, \\qquad
    \\hat\\phi = \\arg(c) + \\pi / 2

which recovers the peak amplitude ``A`` and phase ``phi`` of
``x[n] = A sin(2 pi f n / fs + phi)``.  The Hann window suppresses spectral
leakage from other tones and noise; for coherently sampled tones the estimate
is numerically exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp._validation import (
    ArrayLike,
    as_float64_signal,
    validate_frequency,
    validate_fs,
)
from acousticbench.dsp.filters import FrequencyResponseResult
from acousticbench.dsp.spectra import welch_psd
from acousticbench.exceptions import MeasurementError
from acousticbench.logging_utils import get_logger
from acousticbench.stats.bands import Band

__all__ = [
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

logger = get_logger(__name__)

#: Analytical floor below which a tone is considered absent (linear amplitude).
_AMPLITUDE_FLOOR: float = 1e-12
#: Number of Welch bins masked around a tone when integrating the noise PSD.
_TONE_EXCLUSION_BINS: int = 8
#: Lowest frequency included in broadband noise integration.
_MIN_NOISE_FREQUENCY_HZ: float = 20.0


@dataclass(frozen=True, slots=True)
class ToneComponent:
    """Amplitude and phase of one tone extracted from a signal.

    Attributes
    ----------
    frequency_hz:
        Tone frequency in Hz.
    amplitude:
        Peak amplitude (linear).
    phase_rad:
        Phase in radians at ``t = 0`` (sine convention).
    rms:
        ``amplitude / sqrt(2)``.
    power:
        ``amplitude ** 2 / 2`` (mean square of the tone).
    """

    frequency_hz: float
    amplitude: float
    phase_rad: float

    @property
    def rms(self) -> float:
        """RMS value of the tone."""
        return self.amplitude / np.sqrt(2.0)

    @property
    def power(self) -> float:
        """Mean-square power of the tone (``amplitude**2 / 2``)."""
        return self.amplitude**2 / 2.0


@dataclass(frozen=True, slots=True)
class GainResult:
    """Result of a gain measurement.

    Attributes
    ----------
    gain_db:
        Estimated gain in dB.
    method:
        ``"tone"`` (single-bin projection), ``"band"`` (Welch band power) or
        ``"rms"`` (broadband RMS ratio).
    tone_hz:
        Tone frequency used, or ``None``.
    band_hz:
        Analysis band used, or ``None``.
    input_rms:
        RMS of the input signal.
    output_rms:
        RMS of the output signal.
    """

    gain_db: float
    method: Literal["tone", "band", "rms"]
    tone_hz: float | None
    band_hz: tuple[float, float] | None
    input_rms: float
    output_rms: float


@dataclass(frozen=True, slots=True)
class SnrResult:
    """Result of a signal-to-noise-ratio measurement.

    Attributes
    ----------
    snr_db:
        Estimated SNR in dB.
    method:
        ``"psd"`` (Welch PSD for the noise power) or ``"residual"``
        (time-domain residual after removing the fundamental).
    tone_hz:
        Tone frequency in Hz.
    signal_power:
        Estimated mean-square power of the tone.
    noise_power:
        Estimated mean-square noise power.
    noise_band_hz:
        Band used for the noise integration (``None``: full band).
    """

    snr_db: float
    method: Literal["psd", "residual"]
    tone_hz: float
    signal_power: float
    noise_power: float
    noise_band_hz: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class ThdResult:
    """Result of a total-harmonic-distortion analysis.

    Attributes
    ----------
    thd_percent:
        ``100 * sqrt(sum(harmonic_amplitudes**2)) / fundamental_amplitude``.
    thd_plus_n_percent:
        ``100 * rms(residual) / rms(fundamental)`` where the residual is the
        signal with the fundamental removed (harmonics + noise).
    harmonic_percent:
        Per-harmonic amplitude in percent of the fundamental, ordered
        ``h2, h3, …``.
    fundamental_dbfs:
        RMS level of the fundamental in dBFS.
    tone_hz:
        Fundamental frequency in Hz.
    n_harmonics:
        Number of harmonics analysed.
    fundamental_amplitude:
        Peak amplitude of the fundamental (linear).
    """

    thd_percent: float
    thd_plus_n_percent: float
    harmonic_percent: tuple[float, ...]
    fundamental_dbfs: float
    tone_hz: float
    n_harmonics: int
    fundamental_amplitude: float


def _complex_projection(x: np.ndarray, fs: float, freq_hz: float) -> complex:
    """Hann-windowed complex projection of ``x`` onto ``freq_hz``."""
    n = x.size
    window = _signal.get_window("hann", n, fftbins=True)
    time = np.arange(n, dtype=np.float64) / fs
    return complex(np.sum(x * window * np.exp(-2j * np.pi * freq_hz * time)))


def tone_component(
    signal: ArrayLike,
    fs: float,
    freq_hz: float,
) -> ToneComponent:
    """Extract amplitude and phase of a tone at a known frequency.

    Parameters
    ----------
    signal:
        Real one-dimensional signal.
    fs:
        Sampling rate in Hz.
    freq_hz:
        Tone frequency in Hz (must be inside ``(0, fs / 2)``).

    Returns
    -------
    ToneComponent
        Estimated amplitude, phase and power.

    Raises
    ------
    ValueError
        If the signal or frequency is invalid.

    Notes
    -----
    The estimator is the Hann-windowed coherent projection described in the
    module docstring.  It is unbiased for a coherent tone and changes by less
    than 0.01 dB in the presence of white noise at 0 dB SNR for a 1 s record.
    """
    data = as_float64_signal(signal)
    rate = validate_fs(fs)
    frequency = validate_frequency(freq_hz, rate)
    window = _signal.get_window("hann", data.size, fftbins=True)
    coherent_gain = float(np.sum(window))
    projection = _complex_projection(data, rate, frequency)
    amplitude = 2.0 * abs(projection) / coherent_gain
    phase = float(np.angle(projection) + np.pi / 2.0)
    return ToneComponent(frequency_hz=frequency, amplitude=amplitude, phase_rad=phase)


def _band_edges(
    band_hz: tuple[float, float] | Band | None,
    fs: float,
    name: str = "band_hz",
) -> tuple[float, float] | None:
    """Convert a band specification (pair or :class:`Band`) to a pair in Hz."""
    if band_hz is None:
        return None
    if isinstance(band_hz, Band):
        low, high = band_hz.low_hz, band_hz.high_hz
    else:
        try:
            low, high = float(band_hz[0]), float(band_hz[1])
        except (TypeError, IndexError) as exc:
            raise ValueError(f"{name} must be a (low_hz, high_hz) pair or a Band") from exc
    if not (np.isfinite(low) and np.isfinite(high)) or low < 0.0 or low >= high:
        raise ValueError(f"{name} must satisfy 0 <= low < high, got {band_hz!r}")
    if high > fs / 2.0:
        raise ValueError(f"{name} upper edge {high:g} Hz exceeds Nyquist {fs / 2.0:g} Hz")
    return (low, high)


def _psd_band_power(
    psd: np.ndarray,
    freqs: np.ndarray,
    df: float,
    low: float,
    high: float,
    name: str,
) -> float:
    """Integrate a one-sided PSD between ``low`` and ``high`` Hz."""
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        raise MeasurementError(f"band {name} ({(low, high)!r} Hz) contains no PSD bins")
    return float(np.sum(psd[mask]) * df)


def estimate_gain_db(
    x_in: ArrayLike,
    x_out: ArrayLike,
    fs: float,
    tone_hz: float | None = None,
    band_hz: tuple[float, float] | Band | None = None,
) -> GainResult:
    """Estimate the gain (transfer magnitude) of a system from input/output.

    Parameters
    ----------
    x_in:
        Input (reference) signal.
    x_out:
        Output (measured) signal, same length as ``x_in``.
    fs:
        Sampling rate in Hz.
    tone_hz:
        If given, the gain is measured from the coherent single-bin tone
        projection, which is robust against broadband noise and other tones.
        Exactly one of ``tone_hz`` / ``band_hz`` may be given.
    band_hz:
        If given, the gain is measured from the Welch band power ratio.  May be
        a ``(low_hz, high_hz)`` pair or a :class:`~acousticbench.stats.bands.Band`.

    Returns
    -------
    GainResult
        The gain in dB together with the method actually used.

    Raises
    ------
    ValueError
        If signals are invalid, of different lengths, or both ``tone_hz`` and
        ``band_hz`` are given.
    MeasurementError
        If the measured input power is zero (gain undefined).

    Notes
    -----
    Without ``tone_hz`` / ``band_hz`` the estimate is the robust broadband RMS
    ratio ``20 log10(rms(x_out) / rms(x_in))``.
    """
    input_data = as_float64_signal(x_in, "x_in")
    output_data = as_float64_signal(x_out, "x_out")
    rate = validate_fs(fs)
    if input_data.size != output_data.size:
        raise ValueError(
            f"x_in and x_out must have equal length, got {input_data.size} and {output_data.size}"
        )
    if tone_hz is not None and band_hz is not None:
        raise ValueError("specify either tone_hz or band_hz, not both")
    input_rms = float(np.sqrt(np.mean(np.square(input_data))))
    output_rms = float(np.sqrt(np.mean(np.square(output_data))))
    if tone_hz is not None:
        tone = tone_component(input_data, rate, tone_hz)
        tone_out = tone_component(output_data, rate, tone_hz)
        if tone.amplitude <= _AMPLITUDE_FLOOR:
            raise MeasurementError(
                f"input signal contains no measurable tone at {float(tone_hz):g} Hz"
            )
        gain = 20.0 * np.log10(tone_out.amplitude / tone.amplitude)
        method: Literal["tone", "band", "rms"] = "tone"
        band: tuple[float, float] | None = None
    elif band_hz is not None:
        edges = _band_edges(band_hz, rate)
        assert edges is not None  # for type checkers
        psd_in = welch_psd(input_data, rate)
        psd_out = welch_psd(output_data, rate)
        power_in = _psd_band_power(
            psd_in.psd, psd_in.frequencies_hz, psd_in.df, edges[0], edges[1], "band_hz"
        )
        power_out = _psd_band_power(
            psd_out.psd, psd_out.frequencies_hz, psd_out.df, edges[0], edges[1], "band_hz"
        )
        if power_in <= 0.0:
            raise MeasurementError(f"input signal has no power in band {edges!r} Hz")
        gain = 10.0 * np.log10(power_out / power_in)
        method = "band"
        band = edges
    else:
        if input_rms <= 0.0:
            raise MeasurementError("input signal is silent; gain is undefined")
        gain = 20.0 * np.log10(output_rms / input_rms)
        method = "rms"
        band = None
    logger.debug("estimate_gain_db: method=%s gain_db=%.4f", method, gain)
    return GainResult(
        gain_db=float(gain),
        method=method,
        tone_hz=None if tone_hz is None else float(tone_hz),
        band_hz=band,
        input_rms=input_rms,
        output_rms=output_rms,
    )


def _residual_after_tone(
    data: np.ndarray,
    fs: float,
    tone: ToneComponent,
) -> np.ndarray:
    """Remove the fitted tone waveform from ``data``."""
    time = np.arange(data.size, dtype=np.float64) / fs
    return data - tone.amplitude * np.sin(2.0 * np.pi * tone.frequency_hz * time + tone.phase_rad)


def estimate_snr_db(
    x: ArrayLike,
    fs: float,
    tone_hz: float,
    *,
    noise_band_hz: tuple[float, float] | Band | None = None,
    method: Literal["psd", "residual"] = "psd",
) -> SnrResult:
    """Estimate the signal-to-noise ratio of a tone in broadband noise.

    Parameters
    ----------
    x:
        Real one-dimensional measured signal.
    fs:
        Sampling rate in Hz.
    tone_hz:
        Frequency of the tone carrying the signal.
    noise_band_hz:
        Optional band in which the noise power is integrated (pair or
        :class:`~acousticbench.stats.bands.Band`).  ``None`` means the full
        one-sided band, using the Welch noise density outside a narrow
        exclusion band around the tone and scaling it to the full bandwidth
        (valid for locally flat, e.g. white, noise).
    method:
        ``"psd"`` uses the Welch PSD for the noise power (recommended for
        white noise); ``"residual"`` removes the fitted tone in the time
        domain and uses the residual power (exact for any noise colour, but
        sensitive to other tonal components).

    Returns
    -------
    SnrResult
        SNR in dB with the estimated signal and noise powers.

    Raises
    ------
    ValueError
        If the signal, tone frequency, band or method is invalid.
    MeasurementError
        If the tone is absent or the noise power is not positive.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    tone = tone_component(data, rate, tone_hz)
    if tone.amplitude <= _AMPLITUDE_FLOOR:
        raise MeasurementError(f"signal contains no measurable tone at {float(tone_hz):g} Hz")
    signal_power = tone.power
    if method == "residual":
        residual = _residual_after_tone(data, rate, tone)
        noise_power = float(np.mean(np.square(residual)))
        edges = _band_edges(noise_band_hz, rate, "noise_band_hz")
        if edges is not None:
            psd = welch_psd(residual, rate)
            noise_power = _psd_band_power(
                psd.psd, psd.frequencies_hz, psd.df, edges[0], edges[1], "noise_band_hz"
            )
        method_used: Literal["psd", "residual"] = "residual"
    elif method == "psd":
        edges = _band_edges(noise_band_hz, rate, "noise_band_hz")
        psd = welch_psd(data, rate)
        freqs = psd.frequencies_hz
        df = psd.df
        tone_mask = np.abs(freqs - float(tone_hz)) <= _TONE_EXCLUSION_BINS * df
        if edges is not None:
            low, high = edges
        else:
            low, high = max(_MIN_NOISE_FREQUENCY_HZ, df), float(freqs[-1])
        analysis_mask = (freqs >= low) & (freqs <= high)
        if not np.any(analysis_mask & ~tone_mask):
            raise MeasurementError(
                f"noise band {(low, high)!r} Hz is fully covered by the tone exclusion band"
            )
        kept_power = float(np.sum(psd.psd[analysis_mask & ~tone_mask]) * df)
        kept_freqs = freqs[analysis_mask & ~tone_mask]
        kept_bandwidth = float(kept_freqs[-1] - kept_freqs[0] + df)
        noise_density = kept_power / kept_bandwidth
        total_bandwidth = float(high - low + df)
        noise_power = noise_density * total_bandwidth
        method_used = "psd"
    else:
        raise ValueError(f"method must be 'psd' or 'residual', got {method!r}")
    if not np.isfinite(noise_power) or noise_power <= 0.0:
        raise MeasurementError("estimated noise power is not positive; SNR is undefined")
    snr_db = float(10.0 * np.log10(signal_power / noise_power))
    logger.debug("estimate_snr_db: method=%s tone=%g snr_db=%.3f", method_used, tone_hz, snr_db)
    return SnrResult(
        snr_db=snr_db,
        method=method_used,
        tone_hz=float(tone_hz),
        signal_power=float(signal_power),
        noise_power=float(noise_power),
        noise_band_hz=_band_edges(noise_band_hz, rate, "noise_band_hz"),
    )


def _harmonic_analysis(
    data: np.ndarray,
    fs: float,
    tone_hz: float,
    n_harmonics: int,
) -> tuple[ToneComponent, tuple[ToneComponent, ...], ThdResult]:
    """Analyse fundamental and harmonics and return the intermediate objects."""
    if isinstance(n_harmonics, bool) or not isinstance(n_harmonics, (int, np.integer)):
        raise ValueError(f"n_harmonics must be an integer, got {n_harmonics!r}")
    count = int(n_harmonics)
    if count < 1:
        raise ValueError(f"n_harmonics must be >= 1, got {count}")
    fundamental = tone_component(data, fs, tone_hz)
    if fundamental.amplitude <= _AMPLITUDE_FLOOR:
        raise MeasurementError(f"signal contains no measurable fundamental at {float(tone_hz):g} Hz")
    highest = (count + 1) * float(tone_hz)
    if highest >= fs / 2.0:
        raise ValueError(
            f"harmonic {count + 1} ({highest:g} Hz) is at or above Nyquist; "
            "reduce n_harmonics or the tone frequency"
        )
    harmonics = tuple(
        tone_component(data, fs, multiplier * float(tone_hz))
        for multiplier in range(2, count + 2)
    )
    harmonic_amplitudes = np.asarray([component.amplitude for component in harmonics])
    harmonic_percent = tuple(
        float(100.0 * amplitude / fundamental.amplitude) for amplitude in harmonic_amplitudes
    )
    thd_percent = float(
        100.0
        * np.sqrt(np.sum(np.square(harmonic_amplitudes)))
        / fundamental.amplitude
    )
    residual = _residual_after_tone(data, fs, fundamental)
    residual_rms = float(np.sqrt(np.mean(np.square(residual))))
    fundamental_rms = fundamental.rms
    thd_plus_n_percent = (
        float(100.0 * residual_rms / fundamental_rms) if fundamental_rms > 0.0 else float("inf")
    )
    result = ThdResult(
        thd_percent=thd_percent,
        thd_plus_n_percent=thd_plus_n_percent,
        harmonic_percent=harmonic_percent,
        fundamental_dbfs=float(20.0 * np.log10(max(fundamental_rms, _AMPLITUDE_FLOOR))),
        tone_hz=float(tone_hz),
        n_harmonics=count,
        fundamental_amplitude=float(fundamental.amplitude),
    )
    return fundamental, harmonics, result


def estimate_thd(
    x: ArrayLike,
    fs: float,
    tone_hz: float,
    *,
    n_harmonics: int = 5,
) -> ThdResult:
    """Estimate total harmonic distortion (harmonic amplitudes only).

    Parameters
    ----------
    x:
        Real one-dimensional measured signal.
    fs:
        Sampling rate in Hz.
    tone_hz:
        Fundamental frequency in Hz.
    n_harmonics:
        Number of harmonics (2nd … ``(n_harmonics + 1)``-th) to analyse.

    Returns
    -------
    ThdResult
        THD in percent, per-harmonic amplitudes and fundamental level.

    Raises
    ------
    ValueError
        If the signal, frequency or harmonic count is invalid, or a harmonic
        would be at/above Nyquist.
    MeasurementError
        If the fundamental is absent.

    Notes
    -----
    Harmonics are measured with the same coherent Hann-windowed projection as
    the fundamental, so the result is insensitive to the coherence of the
    fundamental with respect to the record length (integer periods are *not*
    required), while remaining exactly correct when they are coherent.
    ``thd_plus_n_percent`` is also filled in from the residual signal, i.e. it
    equals the THD for a noiseless signal.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    frequency = validate_frequency(tone_hz, rate, "tone_hz")
    _, _, result = _harmonic_analysis(data, rate, frequency, n_harmonics)
    logger.debug("estimate_thd: tone=%g thd=%.4f%%", frequency, result.thd_percent)
    return result


def estimate_thd_plus_n(
    x: ArrayLike,
    fs: float,
    tone_hz: float,
    *,
    n_harmonics: int = 5,
    noise_band_hz: tuple[float, float] | Band | None = None,
) -> ThdResult:
    """Estimate THD+N = harmonics + noise relative to the fundamental.

    Parameters
    ----------
    x:
        Real one-dimensional measured signal.
    fs:
        Sampling rate in Hz.
    tone_hz:
        Fundamental frequency in Hz.
    n_harmonics:
        Number of harmonics reported in :attr:`ThdResult.harmonic_percent`.
    noise_band_hz:
        Optional band in which the residual (harmonic + noise) power is
        integrated.  ``None`` uses the full-band time-domain residual.

    Returns
    -------
    ThdResult
        ``thd_plus_n_percent`` is derived from the residual signal with the
        fundamental removed; ``thd_percent`` still reports the harmonic-only
        THD.

    Raises
    ------
    ValueError
        If the signal, frequency or band is invalid.
    MeasurementError
        If the fundamental is absent.

    Notes
    -----
    The residual is formed in the time domain by subtracting the fitted
    fundamental waveform, so it contains harmonics *and* broadband noise.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    frequency = validate_frequency(tone_hz, rate, "tone_hz")
    fundamental, _, result = _harmonic_analysis(data, rate, frequency, n_harmonics)
    edges = _band_edges(noise_band_hz, rate, "noise_band_hz")
    if edges is None:
        residual = _residual_after_tone(data, rate, fundamental)
        residual_rms = float(np.sqrt(np.mean(np.square(residual))))
    else:
        residual = _residual_after_tone(data, rate, fundamental)
        psd = welch_psd(residual, rate)
        power = _psd_band_power(
            psd.psd, psd.frequencies_hz, psd.df, edges[0], edges[1], "noise_band_hz"
        )
        residual_rms = float(np.sqrt(power))
    fundamental_rms = fundamental.rms
    thd_plus_n = (
        float(100.0 * residual_rms / fundamental_rms) if fundamental_rms > 0.0 else float("inf")
    )
    result = ThdResult(
        thd_percent=result.thd_percent,
        thd_plus_n_percent=thd_plus_n,
        harmonic_percent=result.harmonic_percent,
        fundamental_dbfs=result.fundamental_dbfs,
        tone_hz=result.tone_hz,
        n_harmonics=result.n_harmonics,
        fundamental_amplitude=result.fundamental_amplitude,
    )
    logger.debug("estimate_thd_plus_n: tone=%g thd+n=%.4f%%", frequency, thd_plus_n)
    return result


def _smooth_fractional_octave(
    frequencies_hz: np.ndarray,
    magnitude_db: np.ndarray,
    fraction: float,
) -> np.ndarray:
    """Fractional-octave smoothing of a magnitude spectrum in dB.

    Parameters
    ----------
    frequencies_hz:
        Strictly increasing frequency axis in Hz.
    magnitude_db:
        Magnitude values in dB to smooth.
    fraction:
        Fraction of an octave, e.g. ``3.0`` for one-third-octave smoothing.

    Returns
    -------
    numpy.ndarray
        Smoothed magnitude in dB.
    """
    if not np.isfinite(fraction) or fraction <= 0.0:
        raise ValueError(f"smoothing_fraction must be finite and > 0, got {fraction!r}")
    half_band = 2.0 ** (0.5 / float(fraction))
    smoothed = np.empty_like(magnitude_db)
    for index, center in enumerate(frequencies_hz):
        if center <= 0.0:
            smoothed[index] = magnitude_db[index]
            continue
        low = center / half_band
        high = center * half_band
        mask = (frequencies_hz >= low) & (frequencies_hz <= high)
        smoothed[index] = float(np.mean(magnitude_db[mask]))
    return np.asarray(smoothed, dtype=np.float64)


def estimate_filter_response(
    x_in: ArrayLike,
    x_out: ArrayLike,
    fs: float,
    *,
    n_fft: int | None = None,
    smoothing_fraction: float | None = None,
) -> FrequencyResponseResult:
    """Estimate a system frequency response with the H1 cross-spectrum estimator.

    The H1 estimator averages Welch auto/cross spectra over segments:

    .. math::

        H_1(f) = \\frac{P_{xy}(f)}{P_{xx}(f)}

    where ``x`` is the input and ``y`` the output signal.  Averaging suppresses
    uncorrelated output noise (the estimate is then the minimum-variance
    unbiased estimator for a noise-free input), which is essential for the
    synthetic frequency-response cases.

    Parameters
    ----------
    x_in:
        Input (excitation) signal.
    x_out:
        Output (measured) signal, same length as ``x_in``.
    fs:
        Sampling rate in Hz.
    n_fft:
        Welch segment length.  ``None`` uses ``min(4096, len(x_in))``.  A
        longer segment improves frequency resolution but smears
        time-varying excitation (e.g. sweeps) more.
    smoothing_fraction:
        Optional fractional-octave smoothing of the magnitude in dB (e.g.
        ``3`` for one-third-octave).

    Returns
    -------
    FrequencyResponseResult
        Frequencies (Welch grid), magnitude in dB and unwrapped phase.

    Raises
    ------
    ValueError
        If the signals are invalid or of different lengths.

    Notes
    -----
    The phase convention is ``angle(Y / X)`` with a positive delay producing
    negative phase; it is unwrapped along frequency.
    """
    input_data = as_float64_signal(x_in, "x_in")
    output_data = as_float64_signal(x_out, "x_out")
    rate = validate_fs(fs)
    if input_data.size != output_data.size:
        raise ValueError(
            f"x_in and x_out must have equal length, got {input_data.size} and {output_data.size}"
        )
    n = input_data.size
    if n_fft is None:
        segment = min(4096, n)
    else:
        if isinstance(n_fft, bool) or not isinstance(n_fft, (int, np.integer)):
            raise ValueError(f"n_fft must be an integer or None, got {n_fft!r}")
        segment = int(n_fft)
    if segment < 8:
        raise ValueError(f"n_fft must be >= 8, got {segment}")
    if segment > n:
        logger.debug("estimate_filter_response: n_fft=%d clamped to %d", segment, n)
        segment = n
    overlap = segment * 3 // 4
    frequencies, pxx = _signal.welch(
        input_data,
        fs=rate,
        window="hann",
        nperseg=segment,
        noverlap=overlap,
        detrend=False,
        scaling="density",
        return_onesided=True,
    )
    _, pxy = _signal.csd(
        input_data,
        output_data,
        fs=rate,
        window="hann",
        nperseg=segment,
        noverlap=overlap,
        detrend=False,
        scaling="density",
        return_onesided=True,
    )
    denominator = np.maximum(pxx, np.finfo(np.float64).tiny)
    response = pxy / denominator
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), _AMPLITUDE_FLOOR))
    phase_deg = np.degrees(np.unwrap(np.angle(response)))
    if smoothing_fraction is not None:
        magnitude_db = _smooth_fractional_octave(
            np.asarray(frequencies, dtype=np.float64),
            np.asarray(magnitude_db, dtype=np.float64),
            smoothing_fraction,
        )
    logger.debug(
        "estimate_filter_response: n=%d nperseg=%d bins=%d", n, segment, frequencies.size
    )
    return FrequencyResponseResult(
        frequencies_hz=np.asarray(frequencies, dtype=np.float64),
        magnitude_db=np.asarray(magnitude_db, dtype=np.float64),
        phase_deg=np.asarray(phase_deg, dtype=np.float64),
    )
