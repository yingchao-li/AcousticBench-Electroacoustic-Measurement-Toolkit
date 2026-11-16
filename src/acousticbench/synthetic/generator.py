"""Rendering of synthetic cases into measured signals.

:func:`render_case` turns a :class:`~acousticbench.synthetic.cases.SyntheticCase`
into a :class:`SyntheticCaseData` bundle:

``input``
    The excitation (source) signal.
``output``
    The measured / processed signal (what an estimator sees).
``clean_reference``
    The same as ``output`` but without noise or distortion — the ideal signal.
``noise``
    The exact noise waveform added to the measured signal (``None`` if the
    case is noiseless).
``ground_truth``
    Authoritative analytic ground truth **computed from the actual generated
    waveforms** where appropriate (e.g. ``snr_db`` from ``mean(clean**2) /
    mean(noise**2)``), never simply echoed from the requested parameters.

All randomness derives from ``case.seed`` alone, so re-rendering a case is
bit-reproducible.  A common peak guard (default ``0.99`` full scale) rescales
input, output and reference together, which preserves every ratio-based ground
truth (gain, SNR, THD, transfer function) while guaranteeing that the generated
waveforms stay below clipping.

Case categories
---------------
``gain``
    1 kHz (reference) tone, no compression, no noise, known gain.
``snr``
    Tone + additive noise (white in the reference condition) with a known
    noise waveform; the SNR ground truth is computed from the waveforms.
``thd``
    Fundamental plus 2nd…5th harmonics with known amplitudes; no noise.
``frequency_response``
    Logarithmic sweep through a known FIR/high-Q biquad filter; the ground
    truth is the exact DTFT of the filter at a log-spaced evaluation grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp.filters import apply_filter
from acousticbench.dsp.signals import log_sweep, pink_noise, sine, white_noise
from acousticbench.exceptions import SyntheticCaseError
from acousticbench.logging_utils import get_logger
from acousticbench.synthetic.cases import (
    CATEGORIES,
    TARGETS,
    THD_MULTIPLIERS,
    SyntheticCase,
)
from acousticbench.synthetic.ground_truth import (
    analytic_filter_response,
    build_synthetic_filter,
    dbfs_from_rms,
    evaluation_mask,
    gain_db_from_rms,
    harmonic_percent_from_amplitudes,
    sine_amplitude_from_dbfs,
    snr_db_from_waveforms,
    thd_percent_from_amplitudes,
)

__all__ = [
    "FR_EVALUATION_POINTS",
    "SyntheticCaseData",
    "render_case",
]

logger = get_logger(__name__)

#: Peak amplitude allowed after the clipping guard.
PEAK_GUARD: float = 0.99
#: Number of log-spaced evaluation frequencies of a frequency-response case.
FR_EVALUATION_POINTS: int = 200
#: Lowest frequency of the pink-noise band limit (audio-band sensor noise).
PINK_NOISE_LOW_HZ: float = 20.0
#: Number of harmonics (2nd … 5th) of the THD cases.
THD_HARMONIC_COUNT: int = len(THD_MULTIPLIERS)


@dataclass(frozen=True, slots=True)
class SyntheticCaseData:
    """Rendered signals and ground truth of one synthetic case.

    Attributes
    ----------
    case:
        The originating :class:`SyntheticCase`.
    input:
        Excitation signal (``float64``).
    output:
        Measured / processed signal (``float64``).
    clean_reference:
        The ideal measured signal without noise or distortion (``float64``).
    noise:
        The exact additive noise waveform, or ``None``.
    ground_truth:
        Authoritative ground truth for this case.
    """

    case: SyntheticCase
    input: np.ndarray
    output: np.ndarray
    clean_reference: np.ndarray
    noise: np.ndarray | None
    ground_truth: Mapping[str, Any] = field(default_factory=dict)

    @property
    def fs_hz(self) -> int:
        """Sampling rate in Hz."""
        return int(self.case.fs_hz)

    @property
    def n_samples(self) -> int:
        """Number of samples of every waveform."""
        return int(self.case.n_samples)


def _rng(case: SyntheticCase, stream: int = 0) -> np.random.Generator:
    """Per-case random generator (all case randomness derives from the seed)."""
    return np.random.default_rng(np.random.SeedSequence([int(case.seed), int(stream)]))


def _tone_phase(rng: np.random.Generator) -> float:
    """Draw a tone phase in ``[0, 2 pi)``."""
    return float(rng.uniform(0.0, 2.0 * np.pi))


def _peak_guard(*arrays: np.ndarray) -> tuple[tuple[np.ndarray, ...], float]:
    """Rescale all arrays together so the largest peak is below full scale.

    Returns
    -------
    tuple
        ``(rescaled_arrays, scale)`` where ``scale`` is the applied factor
        (``1.0`` when no rescaling was required).
    """
    peak = max(float(np.max(np.abs(array))) for array in arrays)
    if peak <= PEAK_GUARD:
        scale = 1.0
    else:
        scale = PEAK_GUARD / peak
    return tuple(np.asarray(array * scale, dtype=np.float64) for array in arrays), float(scale)


def _band_limited_pink_noise(
    n_samples: int,
    fs_hz: int,
    seed: int,
    rms_level: float,
) -> np.ndarray:
    """Pink noise high-passed at :data:`PINK_NOISE_LOW_HZ` with exact RMS."""
    core = pink_noise(n_samples, seed=seed)
    if fs_hz > 2.0 * PINK_NOISE_LOW_HZ:
        sos = _signal.butter(4, PINK_NOISE_LOW_HZ, btype="highpass", output="sos", fs=fs_hz)
        core = _signal.sosfiltfilt(sos, core)
    current_rms = float(np.sqrt(np.mean(np.square(core))))
    if current_rms <= 0.0:  # pragma: no cover - noise is never silent
        raise SyntheticCaseError("generated pink noise is silent")
    return np.asarray(core * (rms_level / current_rms), dtype=np.float64)


def _common_ground_truth(case: SyntheticCase) -> dict[str, Any]:
    """Metadata present in every case's ground truth."""
    return {
        "case_id": case.case_id,
        "category": case.category,
        "fs_hz": int(case.fs_hz),
        "duration_s": float(case.duration_s),
        "is_reference_condition": bool(case.is_reference_condition),
    }


def _render_gain(case: SyntheticCase) -> SyntheticCaseData:
    """Render a ``gain`` case: one tone through a pure gain."""
    parameters = case.parameters
    tone_hz = float(parameters["tone_hz"])
    level_dbfs = float(parameters["input_level_dbfs"])
    gain_db = float(parameters["gain_db"])
    rng = _rng(case)
    phase = _tone_phase(rng)
    amplitude = sine_amplitude_from_dbfs(level_dbfs)
    input_signal = sine(tone_hz, case.fs_hz, case.duration_s, amplitude=amplitude, phase_rad=phase)
    output_signal = input_signal * 10.0 ** (gain_db / 20.0)
    clean_reference = np.array(output_signal, dtype=np.float64, copy=True)
    (input_signal, output_signal, clean_reference), scale = _peak_guard(
        input_signal, output_signal, clean_reference
    )
    ground_truth = _common_ground_truth(case)
    ground_truth.update(
        {
            "gain_db": gain_db_from_rms(
                float(np.sqrt(np.mean(np.square(input_signal)))),
                float(np.sqrt(np.mean(np.square(output_signal)))),
            ),
            "requested_gain_db": gain_db,
            "tone_hz": tone_hz,
            "input_level_dbfs": dbfs_from_rms(float(np.sqrt(np.mean(np.square(input_signal))))),
            "output_level_dbfs": dbfs_from_rms(float(np.sqrt(np.mean(np.square(output_signal))))),
            "amplitude_scale": scale,
        }
    )
    return SyntheticCaseData(
        case=case,
        input=input_signal,
        output=output_signal,
        clean_reference=clean_reference,
        noise=None,
        ground_truth=ground_truth,
    )


def _render_snr(case: SyntheticCase) -> SyntheticCaseData:
    """Render an ``snr`` case: one tone plus a known noise waveform."""
    parameters = case.parameters
    tone_hz = float(parameters["tone_hz"])
    level_dbfs = float(parameters["input_level_dbfs"])
    requested_snr_db = float(parameters["snr_db"])
    noise_color = str(parameters["noise_color"])
    rng = _rng(case)
    phase = _tone_phase(rng)
    amplitude = sine_amplitude_from_dbfs(level_dbfs)
    clean = sine(tone_hz, case.fs_hz, case.duration_s, amplitude=amplitude, phase_rad=phase)
    clean_rms = float(np.sqrt(np.mean(np.square(clean))))
    noise_rms = clean_rms / 10.0 ** (requested_snr_db / 20.0)
    if noise_color == "white":
        noise = white_noise(case.n_samples, seed=int(case.seed) + 1)
        noise = np.asarray(noise * noise_rms, dtype=np.float64)
    elif noise_color == "pink":
        noise = _band_limited_pink_noise(
            case.n_samples, int(case.fs_hz), int(case.seed) + 1, noise_rms
        )
    else:  # pragma: no cover - cases validate the colour
        raise SyntheticCaseError(f"unknown noise_color {noise_color!r}")
    output_signal = clean + noise
    (input_signal, clean_reference, noise, output_signal), scale = _peak_guard(
        clean, clean, noise, output_signal
    )
    realised_snr_db = snr_db_from_waveforms(clean_reference, noise)
    ground_truth = _common_ground_truth(case)
    ground_truth.update(
        {
            "snr_db": realised_snr_db,
            "requested_snr_db": requested_snr_db,
            "tone_hz": tone_hz,
            "noise_color": noise_color,
            "signal_power": float(np.mean(np.square(clean_reference))),
            "noise_power": float(np.mean(np.square(noise))),
            "input_level_dbfs": dbfs_from_rms(
                float(np.sqrt(np.mean(np.square(clean_reference))))
            ),
            "amplitude_scale": scale,
        }
    )
    return SyntheticCaseData(
        case=case,
        input=input_signal,
        output=output_signal,
        clean_reference=clean_reference,
        noise=noise,
        ground_truth=ground_truth,
    )


def _render_thd(case: SyntheticCase) -> SyntheticCaseData:
    """Render a ``thd`` case: fundamental plus known harmonics."""
    parameters = case.parameters
    tone_hz = float(parameters["tone_hz"])
    level_dbfs = float(parameters["input_level_dbfs"])
    thd_percent = float(parameters["thd_percent"])
    multipliers = np.asarray(parameters.get("harmonic_multipliers", THD_MULTIPLIERS), dtype=int)
    rng = _rng(case)
    fundamental_phase = _tone_phase(rng)
    harmonic_phases = rng.uniform(0.0, 2.0 * np.pi, multipliers.size)
    fundamental_amplitude = sine_amplitude_from_dbfs(level_dbfs)
    input_signal = sine(
        tone_hz,
        case.fs_hz,
        case.duration_s,
        amplitude=fundamental_amplitude,
        phase_rad=fundamental_phase,
    )
    time = np.arange(case.n_samples, dtype=np.float64) / case.fs_hz
    # Distribute the total harmonic power with 1/k amplitude weights.
    weights = 1.0 / multipliers
    weights = weights / float(np.sqrt(np.sum(np.square(weights))))
    harmonic_amplitudes = fundamental_amplitude * (thd_percent / 100.0) * weights
    distortion = np.zeros_like(input_signal)
    for multiplier, harmonic_amplitude, harmonic_phase in zip(
        multipliers, harmonic_amplitudes, harmonic_phases
    ):
        distortion += harmonic_amplitude * np.sin(
            2.0 * np.pi * float(multiplier) * tone_hz * time + float(harmonic_phase)
        )
    clean_reference = np.array(input_signal, dtype=np.float64, copy=True)
    output_signal = input_signal + distortion
    (input_signal, output_signal, clean_reference), scale = _peak_guard(
        input_signal, output_signal, clean_reference
    )
    scaled_amplitudes = np.asarray(harmonic_amplitudes * scale, dtype=np.float64)
    scaled_fundamental = float(fundamental_amplitude * scale)
    ground_truth = _common_ground_truth(case)
    ground_truth.update(
        {
            "thd_percent": thd_percent_from_amplitudes(scaled_amplitudes, scaled_fundamental),
            "requested_thd_percent": thd_percent,
            "thd_plus_n_percent": thd_percent_from_amplitudes(
                scaled_amplitudes, scaled_fundamental
            ),
            "harmonic_percent": tuple(
                float(value)
                for value in harmonic_percent_from_amplitudes(
                    scaled_amplitudes, scaled_fundamental
                )
            ),
            "harmonic_frequencies_hz": tuple(
                float(multiplier) * tone_hz for multiplier in multipliers
            ),
            "harmonic_amplitudes": tuple(float(value) for value in scaled_amplitudes),
            "fundamental_amplitude": scaled_fundamental,
            "fundamental_dbfs": dbfs_from_rms(float(scaled_fundamental / np.sqrt(2.0))),
            "tone_hz": tone_hz,
            "n_harmonics": int(multipliers.size),
            "input_level_dbfs": dbfs_from_rms(
                float(np.sqrt(np.mean(np.square(clean_reference))))
            ),
            "amplitude_scale": scale,
        }
    )
    return SyntheticCaseData(
        case=case,
        input=input_signal,
        output=output_signal,
        clean_reference=clean_reference,
        noise=None,
        ground_truth=ground_truth,
    )


def _render_frequency_response(case: SyntheticCase) -> SyntheticCaseData:
    """Render a ``frequency_response`` case: sweep through a known filter."""
    parameters = case.parameters
    f_start_hz = float(parameters["f_start_hz"])
    f_end_hz = float(parameters["f_end_hz"])
    level_dbfs = float(parameters["input_level_dbfs"])
    noise_snr_db = parameters.get("noise_snr_db")
    rng = _rng(case)
    filt = build_synthetic_filter(parameters, case.fs_hz)
    amplitude = sine_amplitude_from_dbfs(level_dbfs)
    # log_sweep has a flat per-octave amplitude; a sinusoidal segment has RMS
    # amplitude / sqrt(2), so the sweep RMS level equals level_dbfs.
    input_signal = log_sweep(f_start_hz, f_end_hz, case.duration_s, case.fs_hz, amplitude=amplitude)
    filtered = apply_filter(input_signal, filt)
    noise: np.ndarray | None = None
    if noise_snr_db is not None:
        noise_rms = float(np.sqrt(np.mean(np.square(filtered)))) / 10.0 ** (
            float(noise_snr_db) / 20.0
        )
        noise = np.asarray(
            white_noise(case.n_samples, seed=int(case.seed) + 1) * noise_rms,
            dtype=np.float64,
        )
        output_signal = filtered + noise
    else:
        output_signal = np.array(filtered, dtype=np.float64, copy=True)
    clean_reference = np.array(filtered, dtype=np.float64, copy=True)
    (input_signal, clean_reference, output_signal), scale = _peak_guard(
        input_signal, clean_reference, output_signal
    )
    if noise is not None:
        noise = np.asarray(noise * scale, dtype=np.float64)
    evaluation_frequencies = np.geomspace(
        f_start_hz, f_end_hz, FR_EVALUATION_POINTS, dtype=np.float64
    )
    magnitude_db, phase_deg = analytic_filter_response(filt, case.fs_hz, evaluation_frequencies)
    mask = evaluation_mask(magnitude_db)
    ground_truth = _common_ground_truth(case)
    realised_noise_snr_db: float | None = None
    if noise is not None:
        realised_noise_snr_db = snr_db_from_waveforms(clean_reference, noise)
    ground_truth.update(
        {
            "filter_type": parameters["filter_type"],
            "cutoff_hz": parameters["cutoff_hz"],
            "f_start_hz": f_start_hz,
            "f_end_hz": f_end_hz,
            "frequencies_hz": tuple(float(value) for value in evaluation_frequencies),
            "magnitude_db": tuple(float(value) for value in magnitude_db),
            "phase_deg": tuple(float(value) for value in phase_deg),
            "evaluation_mask": tuple(bool(value) for value in mask),
            "evaluation_frequencies_hz": tuple(
                float(value) for value in evaluation_frequencies[mask]
            ),
            "evaluation_magnitude_db": tuple(float(value) for value in magnitude_db[mask]),
            "frequency_response_mae_tolerance_db": float(TARGETS["frequency_response_mae_db"]),
            "noise_snr_db": realised_noise_snr_db,
            "input_level_dbfs": dbfs_from_rms(
                float(np.sqrt(np.mean(np.square(input_signal))))
            ),
            "amplitude_scale": scale,
        }
    )
    if "peaking_gain_db" in parameters:
        ground_truth["peaking_gain_db"] = parameters["peaking_gain_db"]
        ground_truth["q"] = parameters["q"]
    return SyntheticCaseData(
        case=case,
        input=input_signal,
        output=output_signal,
        clean_reference=clean_reference,
        noise=noise,
        ground_truth=ground_truth,
    )


_RENDERERS = {
    "gain": _render_gain,
    "snr": _render_snr,
    "thd": _render_thd,
    "frequency_response": _render_frequency_response,
}


def render_case(case: SyntheticCase) -> SyntheticCaseData:
    """Render one synthetic case into measured signals and ground truth.

    Parameters
    ----------
    case:
        Case produced by :func:`acousticbench.synthetic.cases.build_cases`.

    Returns
    -------
    SyntheticCaseData
        Input, output, clean reference, noise and authoritative ground truth.

    Raises
    ------
    SyntheticCaseError
        If ``case`` is not a :class:`SyntheticCase` or its category is unknown.
    """
    if not isinstance(case, SyntheticCase):
        raise SyntheticCaseError(
            f"case must be a SyntheticCase, got {type(case).__name__}"
        )
    if case.category not in CATEGORIES:  # pragma: no cover - validated by the case
        raise SyntheticCaseError(f"unsupported category {case.category!r}")
    data = _RENDERERS[case.category](case)
    expected = case.n_samples
    for name in ("input", "output", "clean_reference"):
        array = getattr(data, name)
        if array.size != expected:
            raise SyntheticCaseError(
                f"rendered {name} has {array.size} samples, expected {expected}"
            )
        if array.dtype != np.float64:  # pragma: no cover - always float64
            raise SyntheticCaseError(f"rendered {name} is not float64")
    logger.debug("render_case: %s (%s)", case.case_id, case.category)
    return data
