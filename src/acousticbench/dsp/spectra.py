"""Spectral analysis: FFT, STFT and Welch power spectral density.

All functions return frozen dataclasses carrying the frequency axis together
with the analysed values, so that the sampling rate and window can never be
detached from the result.  Frequency axes are one-sided (``0 … fs / 2``).

Amplitude convention
--------------------
:func:`fft_spectrum` returns an **amplitude-corrected single-sided complex
spectrum**: the window is normalised by its coherent gain (``sum(window)``) and
all non-DC, non-Nyquist bins are doubled.  A coherent sine of peak amplitude
``A`` therefore appears with ``magnitude ≈ A`` in the bin of its frequency.
The complex value keeps the phase information (``phase_deg`` is the angle in
degrees); the spectrum is *not* power-normalised.

:func:`welch_psd` returns a one-sided **power spectral density** (``V**2 / Hz``
for a signal in volts), such that ``sum(psd) * df ≈ mean(x ** 2)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp._validation import ArrayLike, as_float64_signal, validate_fs
from acousticbench.logging_utils import get_logger

__all__ = ["PsdResult", "Spectrum", "StftResult", "fft_spectrum", "stft", "welch_psd"]

logger = get_logger(__name__)

#: Magnitude floor used when converting to dB (≈ -240 dB re 1.0).
_MAGNITUDE_FLOOR: float = 1e-12


def _window_array(window: str | None, n: int) -> np.ndarray:
    """Return a window array of length ``n`` (boxcar for ``None``)."""
    if window is None:
        return np.ones(n, dtype=np.float64)
    if not isinstance(window, str):
        raise ValueError(f"window must be a string or None, got {type(window).__name__}")
    try:
        return np.asarray(_signal.get_window(window, n, fftbins=True), dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"unknown window {window!r}") from exc


def _to_db(values: np.ndarray) -> np.ndarray:
    """``20 log10(|values|)`` with a numerical floor (never -inf)."""
    return 20.0 * np.log10(np.maximum(np.abs(values), _MAGNITUDE_FLOOR))


@dataclass(frozen=True, slots=True)
class Spectrum:
    """One-sided complex spectrum of a real signal.

    Attributes
    ----------
    frequencies_hz:
        Bin centre frequencies in Hz, shape ``(n_bins,)``.
    spectrum:
        Complex one-sided amplitude spectrum (window- and single-sided
        corrected), shape ``(n_bins,)``.
    magnitude:
        ``abs(spectrum)``.
    phase_deg:
        Phase of the spectrum in degrees.
    window:
        Window name used for the analysis (``"boxcar"`` for no window).
    fs:
        Sampling rate in Hz.
    """

    frequencies_hz: np.ndarray
    spectrum: np.ndarray
    magnitude: np.ndarray
    phase_deg: np.ndarray
    window: str
    fs: float

    @property
    def magnitude_db(self) -> np.ndarray:
        """Magnitude in dB re 1.0 (``20 log10``)."""
        return _to_db(self.spectrum)

    @property
    def power(self) -> np.ndarray:
        """Power ``|spectrum| ** 2`` (single-sided amplitude convention)."""
        return np.asarray(np.square(self.magnitude), dtype=np.float64)


@dataclass(frozen=True, slots=True)
class StftResult:
    """Short-time Fourier transform result.

    Attributes
    ----------
    frequencies_hz:
        Frequency axis in Hz, shape ``(n_freqs,)``.
    times_s:
        Segment centre times in seconds, shape ``(n_frames,)``.
    spectrum:
        Complex STFT matrix of shape ``(n_freqs, n_frames)`` (as returned by
        :func:`scipy.signal.stft`, ``scaling="spectrum"``).
    window:
        Window name used for the analysis.
    fs:
        Sampling rate in Hz.
    nperseg:
        Segment length in samples.
    noverlap:
        Overlap in samples.
    """

    frequencies_hz: np.ndarray
    times_s: np.ndarray
    spectrum: np.ndarray
    window: str
    fs: float
    nperseg: int
    noverlap: int

    @property
    def magnitude(self) -> np.ndarray:
        """Magnitude of the complex STFT."""
        return np.abs(self.spectrum)

    @property
    def magnitude_db(self) -> np.ndarray:
        """Magnitude of the complex STFT in dB re 1.0."""
        return _to_db(self.spectrum)


@dataclass(frozen=True, slots=True)
class PsdResult:
    """One-sided Welch power spectral density.

    Attributes
    ----------
    frequencies_hz:
        Frequency axis in Hz, shape ``(n_bins,)``.
    psd:
        One-sided power spectral density in ``V**2 / Hz`` for a signal in
        volts, shape ``(n_bins,)``.
    window:
        Window name used for the analysis.
    fs:
        Sampling rate in Hz.
    nperseg:
        Effective segment length used (clamped to the signal length).
    """

    frequencies_hz: np.ndarray
    psd: np.ndarray
    window: str
    fs: float
    nperseg: int

    @property
    def df(self) -> float:
        """Frequency resolution in Hz (bin spacing)."""
        return float(self.frequencies_hz[1] - self.frequencies_hz[0])

    def band_power(self, band_hz: tuple[float, float] | None = None) -> float:
        """Integrated power inside ``band_hz`` (``sum(psd) * df``).

        Parameters
        ----------
        band_hz:
            ``(low_hz, high_hz)`` limits (inclusive on both ends); ``None``
            integrates the full one-sided band.

        Returns
        -------
        float
            Power in the band.  With :func:`welch_psd` this approximates
            ``mean(x ** 2)`` of the signal inside the band.

        Raises
        ------
        ValueError
            If the band is empty or does not overlap the frequency axis.
        """
        freqs = self.frequencies_hz
        if band_hz is None:
            mask = np.ones_like(freqs, dtype=bool)
        else:
            low, high = (float(band_hz[0]), float(band_hz[1]))
            if not np.isfinite(low) or not np.isfinite(high) or high <= low:
                raise ValueError(f"band_hz must be an ascending finite pair, got {band_hz!r}")
            mask = (freqs >= low) & (freqs <= high)
        if not np.any(mask):
            raise ValueError(f"band {band_hz!r} does not overlap the frequency axis")
        return float(np.sum(self.psd[mask]) * self.df)


def fft_spectrum(
    x: ArrayLike,
    fs: float,
    window: str | None = "hann",
    detrend: bool = True,
    n_fft: int | None = None,
) -> Spectrum:
    """Compute an amplitude-corrected one-sided FFT spectrum.

    Parameters
    ----------
    x:
        Real one-dimensional signal.
    fs:
        Sampling rate in Hz.
    window:
        Window name accepted by :func:`scipy.signal.get_window`; ``None`` uses
        a rectangular window.
    detrend:
        If ``True``, remove a linear trend before windowing.
    n_fft:
        FFT length.  ``None`` uses the signal length; a larger value
        zero-pads and a smaller value is rejected (it would silently discard
        samples).

    Returns
    -------
    Spectrum
        Frequencies, complex spectrum, magnitude and phase.

    Notes
    -----
    A coherent sine of peak amplitude ``A`` produces ``magnitude ≈ A`` in its
    bin.  For non-coherent signals the estimated amplitude is attenuated by
    the window's scalloping loss, as in any single-window FFT analysis.

    Raises
    ------
    ValueError
        If the signal is invalid or ``n_fft < len(x)``.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    n = data.size
    if n_fft is None:
        n_fft_eff = n
    else:
        if isinstance(n_fft, bool) or not isinstance(n_fft, (int, np.integer)):
            raise ValueError(f"n_fft must be an integer or None, got {n_fft!r}")
        n_fft_eff = int(n_fft)
        if n_fft_eff < n:
            raise ValueError(
                f"n_fft ({n_fft_eff}) must be >= the signal length ({n}); "
                "use a longer FFT or truncate the signal explicitly"
            )
    window_name = "boxcar" if window is None else str(window)
    window_values = _window_array(window, n)

    analysed = _signal.detrend(data, type="linear") if detrend else data
    spectrum = np.fft.rfft(analysed * window_values, n=n_fft_eff)
    coherent_gain = float(np.sum(window_values))
    if coherent_gain <= 0.0:  # pragma: no cover - defensive, windows are positive
        raise ValueError("window has non-positive coherent gain")
    spectrum = spectrum / coherent_gain
    if n_fft_eff % 2 == 0:
        spectrum[1:-1] *= 2.0
    else:
        spectrum[1:] *= 2.0
    frequencies = np.fft.rfftfreq(n_fft_eff, d=1.0 / rate)
    magnitude = np.abs(spectrum)
    phase_deg = np.degrees(np.angle(spectrum))
    logger.debug(
        "fft_spectrum: n=%d n_fft=%d fs=%g window=%s", n, n_fft_eff, rate, window_name
    )
    return Spectrum(
        frequencies_hz=np.asarray(frequencies, dtype=np.float64),
        spectrum=np.asarray(spectrum, dtype=np.complex128),
        magnitude=np.asarray(magnitude, dtype=np.float64),
        phase_deg=np.asarray(phase_deg, dtype=np.float64),
        window=window_name,
        fs=rate,
    )


def stft(
    x: ArrayLike,
    fs: float,
    nperseg: int = 1024,
    noverlap: int = 512,
    window: str = "hann",
) -> StftResult:
    """Compute the short-time Fourier transform.

    Parameters
    ----------
    x:
        Real one-dimensional signal.
    fs:
        Sampling rate in Hz.
    nperseg:
        Segment length in samples (must not exceed the signal length).
    noverlap:
        Number of overlapping samples (``0 <= noverlap < nperseg``).
    window:
        Window name accepted by :func:`scipy.signal.get_window`.

    Returns
    -------
    StftResult
        Frequencies, segment times and the complex STFT matrix.

    Raises
    ------
    ValueError
        If the signal is invalid or the segment parameters are inconsistent.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    n = data.size
    if isinstance(nperseg, bool) or not isinstance(nperseg, (int, np.integer)):
        raise ValueError(f"nperseg must be an integer, got {nperseg!r}")
    if isinstance(noverlap, bool) or not isinstance(noverlap, (int, np.integer)):
        raise ValueError(f"noverlap must be an integer, got {noverlap!r}")
    segment = int(nperseg)
    overlap = int(noverlap)
    if segment < 2 or segment > n:
        raise ValueError(f"nperseg must be in [2, {n}], got {segment}")
    if overlap < 0 or overlap >= segment:
        raise ValueError(f"noverlap must be in [0, nperseg), got {overlap}")
    frequencies, times, spectrum = _signal.stft(
        data,
        fs=rate,
        window=window,
        nperseg=segment,
        noverlap=overlap,
        boundary=None,
        padded=False,
    )
    logger.debug(
        "stft: n=%d nperseg=%d noverlap=%d frames=%d", n, segment, overlap, spectrum.shape[1]
    )
    return StftResult(
        frequencies_hz=np.asarray(frequencies, dtype=np.float64),
        times_s=np.asarray(times, dtype=np.float64),
        spectrum=np.asarray(spectrum, dtype=np.complex128),
        window=str(window),
        fs=rate,
        nperseg=segment,
        noverlap=overlap,
    )


def welch_psd(
    x: ArrayLike,
    fs: float,
    nperseg: int = 4096,
    noverlap: int | None = None,
    window: str = "hann",
) -> PsdResult:
    """Estimate the one-sided power spectral density with Welch averaging.

    Parameters
    ----------
    x:
        Real one-dimensional signal.
    fs:
        Sampling rate in Hz.
    nperseg:
        Segment length in samples.  Clamped to the signal length (a debug
        message is logged) because a segment longer than the signal is
        meaningless.
    noverlap:
        Overlap in samples.  Defaults to ``nperseg // 2``.
    window:
        Window name accepted by :func:`scipy.signal.get_window`.

    Returns
    -------
    PsdResult
        One-sided PSD in ``V**2 / Hz``; ``sum(psd) * df ≈ mean(x ** 2)``.

    Raises
    ------
    ValueError
        If the signal is invalid or the segment parameters are inconsistent.
    """
    data = as_float64_signal(x)
    rate = validate_fs(fs)
    n = data.size
    if isinstance(nperseg, bool) or not isinstance(nperseg, (int, np.integer)):
        raise ValueError(f"nperseg must be an integer, got {nperseg!r}")
    segment = int(nperseg)
    if segment > n:
        logger.debug("welch_psd: nperseg=%d clamped to signal length %d", segment, n)
        segment = n
    if segment < 4:
        raise ValueError(f"nperseg must be >= 4, got {segment}")
    if noverlap is None:
        overlap = segment // 2
    else:
        if isinstance(noverlap, bool) or not isinstance(noverlap, (int, np.integer)):
            raise ValueError(f"noverlap must be an integer or None, got {noverlap!r}")
        overlap = int(noverlap)
    if overlap < 0 or overlap >= segment:
        raise ValueError(f"noverlap must be in [0, nperseg), got {overlap}")
    frequencies, psd = _signal.welch(
        data,
        fs=rate,
        window=window,
        nperseg=segment,
        noverlap=overlap,
        detrend=False,
        scaling="density",
        return_onesided=True,
    )
    logger.debug("welch_psd: n=%d nperseg=%d noverlap=%d", n, segment, overlap)
    return PsdResult(
        frequencies_hz=np.asarray(frequencies, dtype=np.float64),
        psd=np.asarray(psd, dtype=np.float64),
        window=str(window),
        fs=rate,
        nperseg=segment,
    )
