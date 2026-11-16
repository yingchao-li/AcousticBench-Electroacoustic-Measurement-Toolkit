"""Digital filter design, application and frequency-response evaluation.

Two filter representations are supported:

``FirFilter``
    Linear-phase FIR taps designed with the window method
    (:func:`scipy.signal.firwin`).
``IirFilter``
    Second-order-sections (SOS) IIR filter designed as a Butterworth
    prototype (:func:`scipy.signal.butter`).

:func:`apply_filter` and :func:`frequency_response` accept either
representation, as well as a bare ``float64`` FIR tap array.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp._validation import ArrayLike, as_float64_signal, validate_fs
from acousticbench.logging_utils import get_logger

__all__ = [
    "FIR_KINDS",
    "FirFilter",
    "FilterSpec",
    "FrequencyResponseResult",
    "IirFilter",
    "apply_filter",
    "design_fir",
    "design_iir",
    "frequency_response",
]

logger = get_logger(__name__)

#: Filter kinds accepted by :func:`design_fir` and :func:`design_iir`.
FIR_KINDS: tuple[str, ...] = ("lowpass", "highpass", "bandpass", "bandstop")

#: Magnitude floor used for dB conversion (≈ -240 dB re 1.0).
_MAGNITUDE_FLOOR: float = 1e-12


def _normalise_cutoff(
    kind: str,
    cutoff_hz: float | tuple[float, float] | list[float],
    fs: float,
) -> float | tuple[float, float]:
    """Validate and normalise a filter cutoff specification.

    Returns a float for lowpass/highpass and an ascending pair for
    bandpass/bandstop.
    """
    if kind not in FIR_KINDS:
        raise ValueError(f"kind must be one of {FIR_KINDS}, got {kind!r}")
    nyquist = fs / 2.0
    if kind in ("lowpass", "highpass"):
        cutoff = float(cutoff_hz)  # type: ignore[arg-type]
        if not np.isfinite(cutoff) or cutoff <= 0.0 or cutoff >= nyquist:
            raise ValueError(
                f"{kind} cutoff must be in (0, {nyquist:g}) Hz, got {cutoff_hz!r}"
            )
        return cutoff
    try:
        low, high = (float(cutoff_hz[0]), float(cutoff_hz[1]))  # type: ignore[index]
    except (TypeError, IndexError) as exc:
        raise ValueError(
            f"{kind} cutoff must be a (low_hz, high_hz) pair, got {cutoff_hz!r}"
        ) from exc
    if not (np.isfinite(low) and np.isfinite(high)):
        raise ValueError(f"cutoff frequencies must be finite, got {cutoff_hz!r}")
    if low <= 0.0 or high >= nyquist or low >= high:
        raise ValueError(
            f"{kind} cutoff must satisfy 0 < low < high < {nyquist:g} Hz, got {cutoff_hz!r}"
        )
    return (low, high)


@dataclass(frozen=True, slots=True)
class FirFilter:
    """A linear-phase FIR filter designed with the window method.

    Attributes
    ----------
    kind:
        One of ``"lowpass"``, ``"highpass"``, ``"bandpass"``, ``"bandstop"``.
    fs:
        Sampling rate in Hz.
    cutoff_hz:
        Cutoff frequency in Hz (float for lowpass/highpass, pair otherwise).
    fir_taps:
        FIR impulse response, shape ``(numtaps,)``, ``float64``.
    numtaps:
        Number of taps.
    window:
        Window name used for the design.
    """

    kind: str
    fs: float
    cutoff_hz: float | tuple[float, float]
    fir_taps: np.ndarray
    numtaps: int
    window: str

    @property
    def taps(self) -> np.ndarray:
        """Alias of :attr:`fir_taps`."""
        return self.fir_taps


@dataclass(frozen=True, slots=True)
class IirFilter:
    """A Butterworth IIR filter in second-order-sections form.

    Attributes
    ----------
    kind:
        One of ``"lowpass"``, ``"highpass"``, ``"bandpass"``, ``"bandstop"``.
    fs:
        Sampling rate in Hz.
    cutoff_hz:
        Cutoff frequency in Hz (float for lowpass/highpass, pair otherwise).
    sos:
        Second-order sections of shape ``(n_sections, 6)``.
    order:
        Prototype order (number of poles of the low-pass prototype).
    """

    kind: str
    fs: float
    cutoff_hz: float | tuple[float, float]
    sos: np.ndarray
    order: int


#: Union type of the two filter representations plus a bare FIR tap array.
FilterSpec = FirFilter | IirFilter | np.ndarray


@dataclass(frozen=True, slots=True)
class FrequencyResponseResult:
    """Complex frequency response sampled on a linear frequency grid.

    Attributes
    ----------
    frequencies_hz:
        Evaluation frequencies in Hz (``0 … fs / 2`` inclusive).
    magnitude_db:
        Magnitude in dB re 1.0 (``20 log10 |H|``), floored at ≈ -240 dB.
    phase_deg:
        Unwrapped phase in degrees.
    """

    frequencies_hz: np.ndarray
    magnitude_db: np.ndarray
    phase_deg: np.ndarray


def design_fir(
    kind: str,
    fs: float,
    cutoff_hz: float | tuple[float, float] | list[float],
    numtaps: int = 101,
    window: str = "hamming",
) -> FirFilter:
    """Design a linear-phase FIR filter with the window method.

    Parameters
    ----------
    kind:
        ``"lowpass"``, ``"highpass"``, ``"bandpass"`` or ``"bandstop"``.
    fs:
        Sampling rate in Hz.
    cutoff_hz:
        Cutoff frequency in Hz for lowpass/highpass, or an ascending
        ``(low_hz, high_hz)`` pair for bandpass/bandstop.
    numtaps:
        Number of taps (>= 3).
    window:
        Window name accepted by :func:`scipy.signal.get_window`.

    Returns
    -------
    FirFilter
        The designed filter with ``fir_taps``.

    Raises
    ------
    ValueError
        If any design parameter is invalid.
    """
    rate = validate_fs(fs)
    if isinstance(numtaps, bool) or not isinstance(numtaps, (int, np.integer)):
        raise ValueError(f"numtaps must be an integer, got {numtaps!r}")
    taps_count = int(numtaps)
    if taps_count < 3:
        raise ValueError(f"numtaps must be >= 3, got {taps_count}")
    cutoff = _normalise_cutoff(kind, cutoff_hz, rate)
    pass_zero = kind in ("lowpass", "bandstop")
    try:
        taps = _signal.firwin(
            taps_count,
            cutoff,
            window=window,
            pass_zero=pass_zero,
            fs=rate,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"could not design FIR {kind} filter (numtaps={taps_count}, window={window!r}): {exc}"
        ) from exc
    logger.debug("design_fir: kind=%s fs=%g cutoff=%s numtaps=%d", kind, rate, cutoff, taps_count)
    return FirFilter(
        kind=kind,
        fs=rate,
        cutoff_hz=cutoff,
        fir_taps=np.asarray(taps, dtype=np.float64),
        numtaps=taps_count,
        window=str(window),
    )


def design_iir(
    kind: str,
    fs: float,
    cutoff_hz: float | tuple[float, float] | list[float],
    order: int = 4,
) -> IirFilter:
    """Design a Butterworth IIR filter in SOS form.

    Parameters
    ----------
    kind:
        ``"lowpass"``, ``"highpass"``, ``"bandpass"`` or ``"bandstop"``.
    fs:
        Sampling rate in Hz.
    cutoff_hz:
        Cutoff frequency in Hz for lowpass/highpass, or an ascending
        ``(low_hz, high_hz)`` pair for bandpass/bandstop.
    order:
        Prototype order (>= 1).

    Returns
    -------
    IirFilter
        The designed filter with ``sos``.

    Raises
    ------
    ValueError
        If any design parameter is invalid.
    """
    rate = validate_fs(fs)
    if isinstance(order, bool) or not isinstance(order, (int, np.integer)):
        raise ValueError(f"order must be an integer, got {order!r}")
    order_value = int(order)
    if order_value < 1:
        raise ValueError(f"order must be >= 1, got {order_value}")
    cutoff = _normalise_cutoff(kind, cutoff_hz, rate)
    try:
        sos = _signal.butter(order_value, cutoff, btype=kind, output="sos", fs=rate)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"could not design IIR {kind} filter (order={order_value}): {exc}"
        ) from exc
    logger.debug("design_iir: kind=%s fs=%g cutoff=%s order=%d", kind, rate, cutoff, order_value)
    return IirFilter(
        kind=kind,
        fs=rate,
        cutoff_hz=cutoff,
        sos=np.asarray(sos, dtype=np.float64),
        order=order_value,
    )


def _filter_parts(filt: FilterSpec) -> tuple[str, np.ndarray, np.ndarray]:
    """Return ``(representation, fir_taps, sos)`` for a filter specification.

    Exactly one of ``fir_taps`` / ``sos`` is non-empty.
    """
    empty = np.empty(0, dtype=np.float64)
    if isinstance(filt, FirFilter):
        return ("fir", np.asarray(filt.fir_taps, dtype=np.float64), empty)
    if isinstance(filt, IirFilter):
        return ("sos", empty, np.asarray(filt.sos, dtype=np.float64))
    if isinstance(filt, np.ndarray) or isinstance(filt, (list, tuple)):
        taps = np.asarray(filt, dtype=np.float64)
        if taps.ndim != 1 or taps.size < 2:
            raise ValueError(f"FIR taps must be a one-dimensional array with >= 2 taps")
        if not np.all(np.isfinite(taps)):
            raise ValueError("FIR taps contain non-finite values")
        return ("fir", taps, empty)
    raise TypeError(
        "filt must be a FirFilter, an IirFilter or a one-dimensional FIR tap array, "
        f"got {type(filt).__name__}"
    )


def apply_filter(
    signal: ArrayLike,
    filt: FilterSpec,
    zero_phase: bool = False,
) -> np.ndarray:
    """Apply a digital filter to a signal.

    Parameters
    ----------
    signal:
        Real one-dimensional input signal.
    filt:
        A :class:`FirFilter`, an :class:`IirFilter`, or a one-dimensional FIR
        tap array.
    zero_phase:
        If ``True``, filter forward and backward (``filtfilt`` /
        ``sosfiltfilt``).  This makes the phase response zero but doubles the
        magnitude response in dB (standard ``filtfilt`` semantics) and
        requires the signal to be longer than the filter's padding.

    Returns
    -------
    numpy.ndarray
        Filtered ``float64`` signal of the same length as the input.

    Raises
    ------
    ValueError
        If the signal or filter specification is invalid, or the signal is
        too short for zero-phase filtering.
    """
    data = as_float64_signal(signal)
    representation, taps, sos = _filter_parts(filt)
    if representation == "fir":
        if np.all(taps == 0.0):
            raise ValueError("FIR taps must not be all zero")
        if zero_phase:
            try:
                return np.asarray(_signal.filtfilt(taps, [1.0], data), dtype=np.float64)
            except ValueError as exc:
                raise ValueError(
                    f"zero-phase FIR filtering failed (signal too short for the filter): {exc}"
                ) from exc
        return np.asarray(_signal.lfilter(taps, [1.0], data), dtype=np.float64)
    if zero_phase:
        try:
            return np.asarray(_signal.sosfiltfilt(sos, data), dtype=np.float64)
        except ValueError as exc:
            raise ValueError(
                f"zero-phase IIR filtering failed (signal too short for the filter): {exc}"
            ) from exc
    return np.asarray(_signal.sosfilt(sos, data), dtype=np.float64)


def frequency_response(
    filt: FilterSpec,
    fs: float,
    n_freqs: int = 2048,
) -> FrequencyResponseResult:
    """Evaluate the complex frequency response of a filter.

    Parameters
    ----------
    filt:
        A :class:`FirFilter`, an :class:`IirFilter`, or a one-dimensional FIR
        tap array.
    fs:
        Sampling rate in Hz.
    n_freqs:
        Number of equally spaced frequencies on ``[0, fs / 2]`` (>= 2).

    Returns
    -------
    FrequencyResponseResult
        Magnitude in dB and unwrapped phase in degrees.

    Raises
    ------
    ValueError
        If the filter specification or ``n_freqs`` is invalid.
    """
    rate = validate_fs(fs)
    if isinstance(n_freqs, bool) or not isinstance(n_freqs, (int, np.integer)):
        raise ValueError(f"n_freqs must be an integer, got {n_freqs!r}")
    count = int(n_freqs)
    if count < 2:
        raise ValueError(f"n_freqs must be >= 2, got {count}")
    representation, taps, sos = _filter_parts(filt)
    freqs = np.linspace(0.0, rate / 2.0, count)
    if representation == "fir":
        _, response = _signal.freqz(taps, worN=freqs, fs=rate)
    else:
        _, response = _signal.sosfreqz(sos, worN=freqs, fs=rate)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), _MAGNITUDE_FLOOR))
    phase_deg = np.degrees(np.unwrap(np.angle(response)))
    return FrequencyResponseResult(
        frequencies_hz=np.asarray(freqs, dtype=np.float64),
        magnitude_db=np.asarray(magnitude_db, dtype=np.float64),
        phase_deg=np.asarray(phase_deg, dtype=np.float64),
    )
