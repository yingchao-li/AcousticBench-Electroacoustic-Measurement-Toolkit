"""Deterministic synthetic validation cases with known ground truth.

The case design is a **randomised factorial** over four measurement categories,
each holding out a documented *reference condition* for which the acceptance
targets of ``config/default.yaml`` apply:

============  =============================================================
category      documented reference condition
============  =============================================================
``gain``      1 kHz tone, no compression, no noise, 4 s, -20 dBFS.
``snr``       1 kHz tone + white Gaussian noise, SNR 10…40 dB, 4 s, -20 dBFS.
``thd``       1 kHz tone, THD 0.5…5 %, no noise, integer number of periods.
``frequency_response``
              logarithmic sweep 100 Hz…10 kHz, 4 s, no noise, no
              compression, known FIR/IIR filter.
============  =============================================================

``is_reference_condition`` is ``True`` exactly for cases generated inside the
documented condition, so experiments can select the subset for the strict
accuracy targets while still exercising wider parameter ranges elsewhere.

Reproducibility
---------------
``build_cases`` is a pure function of ``(n_cases, seed, fs_hz)``: the master
seed is split into one stream per category, and every case stores its own
``seed`` from which :func:`acousticbench.synthetic.generator.render_case`
derives all waveforms.  Rebuilding the cases and re-rendering a case therefore
always yields bit-identical signals.

Case-level ``ground_truth`` holds the *requested* (nominal) values; the
generator returns the *authoritative* ground truth recomputed from the actual
generated waveforms (e.g. the SNR from the realised noise waveform).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from acousticbench.exceptions import SyntheticCaseError
from acousticbench.logging_utils import get_logger
from acousticbench.synthetic.ground_truth import FILTER_TYPES

__all__ = [
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
]

logger = get_logger(__name__)

#: Measurement categories of the synthetic validation suite.
CATEGORIES: tuple[str, ...] = ("gain", "snr", "thd", "frequency_response")

#: Defaults mirroring ``config/default.yaml`` → ``synthetic``.
DEFAULT_N_CASES: int = 1000
DEFAULT_SEED: int = 20260422
DEFAULT_FS_HZ: int = 48000
DEFAULT_DURATION_S: float = 4.0
SNR_DB_RANGE: tuple[float, float] = (0.0, 40.0)
THD_PERCENT_RANGE: tuple[float, float] = (0.1, 10.0)
GAIN_DB_RANGE: tuple[float, float] = (-20.0, 40.0)
INPUT_LEVEL_DBFS_RANGE: tuple[float, float] = (-30.0, -10.0)
#: Supported noise colours (``config/default.yaml``: ``noise_colors``).
NOISE_COLORS: tuple[str, ...] = ("white", "pink")

#: Acceptance targets (``synthetic.targets`` in ``config/default.yaml``).
TARGETS: Mapping[str, float] = {
    "gain_error_db": 0.1,
    "snr_error_db": 0.5,
    "thd_error_percentage_points": 0.1,
    "frequency_response_mae_db": 0.5,
}

#: Documented reference conditions (``synthetic.reference_conditions``).
REFERENCE_CONDITIONS: Mapping[str, str] = {
    "gain": (
        "1 kHz tone, no compression, no noise, 4 s, -20 dBFS; estimate from the "
        "DFT bin of the tone"
    ),
    "snr": (
        "1 kHz tone in additive white Gaussian noise, SNR 10…40 dB, 4 s "
        "Hann-windowed PSD estimate"
    ),
    "thd": (
        "1 kHz tone, THD 0.5…5 %, no noise, integer number of periods, "
        "Hann-windowed harmonic analysis"
    ),
    "frequency_response": (
        "logarithmic sweep 100 Hz…10 kHz, 4 s, no noise, no compression; "
        "deconvolution vs. known filter response"
    ),
}

#: Fraction of cases per category generated inside the reference condition.
REFERENCE_FRACTION: float = 0.4
#: Reference condition constants.
REFERENCE_TONE_HZ: float = 1000.0
REFERENCE_LEVEL_DBFS: float = -20.0
REFERENCE_SNR_DB_RANGE: tuple[float, float] = (10.0, 40.0)
REFERENCE_THD_PERCENT_RANGE: tuple[float, float] = (0.5, 5.0)
REFERENCE_SWEEP_HZ: tuple[float, float] = (100.0, 10000.0)
#: At -20 dBFS a sine peaks at ≈ -17 dBFS, so +15 dB keeps the output below
#: full scale without post-hoc scaling (see the generator's peak guard).
REFERENCE_MAX_GAIN_DB: float = 15.0
#: Number of FIR taps of the known frequency-response filters.
FR_NUMTAPS: int = 129

#: Tone choices for non-reference cases (all integer Hz → integer periods in
#: the 4 s record).
_TONE_CHOICES_HZ: tuple[float, ...] = (500.0, 1000.0, 2000.0, 4000.0)
_THD_TONE_CHOICES_HZ: tuple[float, ...] = (500.0, 1000.0, 1500.0, 2000.0, 4000.0)
_SWEEP_CHOICES_HZ: tuple[tuple[float, float], ...] = (
    (100.0, 8000.0),
    (200.0, 10000.0),
    (150.0, 6000.0),
    (120.0, 9000.0),
)
#: Harmonic multipliers used by the THD cases (2nd … 5th harmonic).
THD_MULTIPLIERS: tuple[int, ...] = (2, 3, 4, 5)


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    """One synthetic validation case.

    Attributes
    ----------
    case_id:
        Human-readable identifier, e.g. ``"snr-0042"``.
    seed:
        Seed sufficient to reproduce every waveform of the case.
    category:
        One of :data:`CATEGORIES`.
    fs_hz:
        Sampling rate in Hz.
    duration_s:
        Signal duration in seconds.
    parameters:
        All varied parameters of the case (tone frequencies, levels, gains,
        filter design, sweep range, ...).
    ground_truth:
        Nominal analytic ground truth derived from ``parameters``.
    is_reference_condition:
        Whether the case belongs to the documented reference condition of its
        category.
    """

    case_id: str
    seed: int
    category: str
    fs_hz: int
    duration_s: float
    parameters: Mapping[str, Any]
    ground_truth: Mapping[str, Any]
    is_reference_condition: bool

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise SyntheticCaseError(
                f"category must be one of {CATEGORIES}, got {self.category!r}"
            )
        if not self.case_id:
            raise SyntheticCaseError("case_id must not be empty")
        if isinstance(self.seed, bool) or not isinstance(self.seed, (int, np.integer)):
            raise SyntheticCaseError(f"seed must be an integer, got {self.seed!r}")
        if int(self.seed) < 0:
            raise SyntheticCaseError(f"seed must be >= 0, got {self.seed!r}")
        if not isinstance(self.fs_hz, (int, np.integer)) or int(self.fs_hz) <= 0:
            raise SyntheticCaseError(f"fs_hz must be a positive integer, got {self.fs_hz!r}")
        duration = float(self.duration_s)
        if not np.isfinite(duration) or duration <= 0.0:
            raise SyntheticCaseError(f"duration_s must be finite and > 0, got {self.duration_s!r}")
        if not isinstance(self.parameters, Mapping):
            raise SyntheticCaseError("parameters must be a mapping")
        if not isinstance(self.ground_truth, Mapping):
            raise SyntheticCaseError("ground_truth must be a mapping")

    @property
    def n_samples(self) -> int:
        """Number of samples of every waveform of the case."""
        return int(round(int(self.fs_hz) * float(self.duration_s)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation with nested values."""
        return {
            "case_id": self.case_id,
            "seed": int(self.seed),
            "category": self.category,
            "fs_hz": int(self.fs_hz),
            "duration_s": float(self.duration_s),
            "is_reference_condition": bool(self.is_reference_condition),
            "parameters": _jsonable(dict(self.parameters)),
            "ground_truth": _jsonable(dict(self.ground_truth)),
        }


def _jsonable(value: Any) -> Any:
    """Recursively convert tuples/NumPy scalars to JSON-serialisable values."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _log_uniform(rng: np.random.Generator, low: float, high: float) -> float:
    """Draw a value log-uniformly between ``low`` and ``high``."""
    return float(np.exp(rng.uniform(np.log(low), np.log(high))))


def _draw_tone(rng: np.random.Generator, choices: tuple[float, ...]) -> float:
    """Draw one of the integer-Hz tone frequencies."""
    return float(choices[int(rng.integers(0, len(choices)))])


def _reference_count(count: int) -> int:
    """Number of reference-condition cases for a category of ``count`` cases."""
    return min(count, max(1, int(round(count * REFERENCE_FRACTION))))


def _gain_case(
    index: int,
    seed: int,
    fs_hz: int,
    duration_s: float,
    *,
    reference: bool,
    rng: np.random.Generator,
) -> SyntheticCase:
    """Build one ``gain`` case."""
    if reference:
        tone_hz = REFERENCE_TONE_HZ
        level_dbfs = REFERENCE_LEVEL_DBFS
        gain_db = float(rng.uniform(GAIN_DB_RANGE[0], REFERENCE_MAX_GAIN_DB))
    else:
        tone_hz = _draw_tone(rng, _TONE_CHOICES_HZ)
        level_dbfs = float(rng.uniform(*INPUT_LEVEL_DBFS_RANGE))
        gain_db = float(rng.uniform(*GAIN_DB_RANGE))
    parameters: dict[str, Any] = {
        "tone_hz": tone_hz,
        "input_level_dbfs": level_dbfs,
        "gain_db": gain_db,
        "duration_s": duration_s,
    }
    ground_truth: dict[str, Any] = {
        "category": "gain",
        "gain_db": gain_db,
        "tone_hz": tone_hz,
        "input_level_dbfs": level_dbfs,
    }
    return SyntheticCase(
        case_id=f"gain-{index:04d}",
        seed=seed,
        category="gain",
        fs_hz=fs_hz,
        duration_s=duration_s,
        parameters=parameters,
        ground_truth=ground_truth,
        is_reference_condition=reference,
    )


def _snr_case(
    index: int,
    seed: int,
    fs_hz: int,
    duration_s: float,
    *,
    reference: bool,
    rng: np.random.Generator,
) -> SyntheticCase:
    """Build one ``snr`` case."""
    if reference:
        tone_hz = REFERENCE_TONE_HZ
        level_dbfs = REFERENCE_LEVEL_DBFS
        noise_color = "white"
        snr_db = float(rng.uniform(*REFERENCE_SNR_DB_RANGE))
    else:
        tone_hz = _draw_tone(rng, _TONE_CHOICES_HZ)
        level_dbfs = float(rng.uniform(*INPUT_LEVEL_DBFS_RANGE))
        noise_color = NOISE_COLORS[int(rng.integers(0, len(NOISE_COLORS)))]
        snr_db = float(rng.uniform(*SNR_DB_RANGE))
    parameters: dict[str, Any] = {
        "tone_hz": tone_hz,
        "input_level_dbfs": level_dbfs,
        "snr_db": snr_db,
        "noise_color": noise_color,
        "duration_s": duration_s,
    }
    ground_truth: dict[str, Any] = {
        "category": "snr",
        "snr_db": snr_db,
        "tone_hz": tone_hz,
        "noise_color": noise_color,
        "input_level_dbfs": level_dbfs,
    }
    return SyntheticCase(
        case_id=f"snr-{index:04d}",
        seed=seed,
        category="snr",
        fs_hz=fs_hz,
        duration_s=duration_s,
        parameters=parameters,
        ground_truth=ground_truth,
        is_reference_condition=reference,
    )


def _thd_case(
    index: int,
    seed: int,
    fs_hz: int,
    duration_s: float,
    *,
    reference: bool,
    rng: np.random.Generator,
) -> SyntheticCase:
    """Build one ``thd`` case."""
    if reference:
        tone_hz = REFERENCE_TONE_HZ
        level_dbfs = REFERENCE_LEVEL_DBFS
        thd_percent = float(rng.uniform(*REFERENCE_THD_PERCENT_RANGE))
    else:
        tone_hz = _draw_tone(rng, _THD_TONE_CHOICES_HZ)
        level_dbfs = float(rng.uniform(*INPUT_LEVEL_DBFS_RANGE))
        thd_percent = float(rng.uniform(*THD_PERCENT_RANGE))
    highest_harmonic = THD_MULTIPLIERS[-1] * tone_hz
    if highest_harmonic >= fs_hz / 2.0:  # pragma: no cover - choices are safe
        raise SyntheticCaseError(
            f"tone {tone_hz:g} Hz would place harmonic {THD_MULTIPLIERS[-1]} above Nyquist"
        )
    parameters: dict[str, Any] = {
        "tone_hz": tone_hz,
        "input_level_dbfs": level_dbfs,
        "thd_percent": thd_percent,
        "harmonic_multipliers": THD_MULTIPLIERS,
        "duration_s": duration_s,
    }
    ground_truth: dict[str, Any] = {
        "category": "thd",
        "thd_percent": thd_percent,
        "tone_hz": tone_hz,
        "input_level_dbfs": level_dbfs,
        "n_harmonics": len(THD_MULTIPLIERS),
    }
    return SyntheticCase(
        case_id=f"thd-{index:04d}",
        seed=seed,
        category="thd",
        fs_hz=fs_hz,
        duration_s=duration_s,
        parameters=parameters,
        ground_truth=ground_truth,
        is_reference_condition=reference,
    )


def _fr_filter_parameters(rng: np.random.Generator) -> dict[str, Any]:
    """Draw the known filter design of a frequency-response case."""
    filter_type = FILTER_TYPES[int(rng.integers(0, len(FILTER_TYPES)))]
    if filter_type == "lowpass":
        return {
            "filter_type": filter_type,
            "cutoff_hz": _log_uniform(rng, 300.0, 3000.0),
            "numtaps": FR_NUMTAPS,
        }
    if filter_type == "highpass":
        return {
            "filter_type": filter_type,
            "cutoff_hz": _log_uniform(rng, 100.0, 1500.0),
            "numtaps": FR_NUMTAPS,
        }
    if filter_type == "bandpass":
        center = _log_uniform(rng, 400.0, 3000.0)
        return {
            "filter_type": filter_type,
            "cutoff_hz": (max(100.0, center / 2.0), min(12000.0, center * 2.0)),
            "numtaps": FR_NUMTAPS,
        }
    sign = -1.0 if rng.random() < 0.5 else 1.0
    return {
        "filter_type": "peaking",
        "cutoff_hz": _log_uniform(rng, 500.0, 4000.0),
        "peaking_gain_db": sign * float(rng.uniform(3.0, 9.0)),
        "q": float(rng.uniform(0.7, 2.0)),
        "numtaps": FR_NUMTAPS,
    }


def _fr_case(
    index: int,
    seed: int,
    fs_hz: int,
    duration_s: float,
    *,
    reference: bool,
    rng: np.random.Generator,
) -> SyntheticCase:
    """Build one ``frequency_response`` case."""
    if reference:
        f_start_hz, f_end_hz = REFERENCE_SWEEP_HZ
        level_dbfs = REFERENCE_LEVEL_DBFS
        noise_snr_db: float | None = None
    else:
        sweep = _SWEEP_CHOICES_HZ[int(rng.integers(0, len(_SWEEP_CHOICES_HZ)))]
        f_start_hz, f_end_hz = sweep
        level_dbfs = float(rng.uniform(*INPUT_LEVEL_DBFS_RANGE))
        noise_snr_db = float(rng.uniform(30.0, 50.0)) if rng.random() < 0.5 else None
    filter_parameters = _fr_filter_parameters(rng)
    parameters: dict[str, Any] = {
        **filter_parameters,
        "f_start_hz": f_start_hz,
        "f_end_hz": f_end_hz,
        "input_level_dbfs": level_dbfs,
        "noise_snr_db": noise_snr_db,
        "duration_s": duration_s,
    }
    ground_truth: dict[str, Any] = {
        "category": "frequency_response",
        "filter_type": filter_parameters["filter_type"],
        "cutoff_hz": filter_parameters["cutoff_hz"],
        "f_start_hz": f_start_hz,
        "f_end_hz": f_end_hz,
        "input_level_dbfs": level_dbfs,
        "noise_snr_db": noise_snr_db,
    }
    if "peaking_gain_db" in filter_parameters:
        ground_truth["peaking_gain_db"] = filter_parameters["peaking_gain_db"]
        ground_truth["q"] = filter_parameters["q"]
    return SyntheticCase(
        case_id=f"frequency_response-{index:04d}",
        seed=seed,
        category="frequency_response",
        fs_hz=fs_hz,
        duration_s=duration_s,
        parameters=parameters,
        ground_truth=ground_truth,
        is_reference_condition=reference,
    )


_CASE_BUILDERS = {
    "gain": _gain_case,
    "snr": _snr_case,
    "thd": _thd_case,
    "frequency_response": _fr_case,
}


def build_cases(
    n_cases: int = DEFAULT_N_CASES,
    seed: int = DEFAULT_SEED,
    fs_hz: int = DEFAULT_FS_HZ,
) -> tuple[SyntheticCase, ...]:
    """Build the deterministic synthetic validation suite.

    The cases are split evenly over the four categories (``n_cases // 4`` each,
    any remainder assigned to the first categories in :data:`CATEGORIES`
    order).  Within each category, the first
    ``max(1, round(0.4 * count))`` cases belong to the documented reference
    condition.

    Parameters
    ----------
    n_cases:
        Total number of cases (>= 1).
    seed:
        Master seed.
    fs_hz:
        Sampling rate in Hz for every case.

    Returns
    -------
    tuple of SyntheticCase
        The cases, in category order.

    Raises
    ------
    SyntheticCaseError
        If an argument is out of range.
    """
    if isinstance(n_cases, bool) or not isinstance(n_cases, (int, np.integer)):
        raise SyntheticCaseError(f"n_cases must be an integer, got {n_cases!r}")
    total = int(n_cases)
    if total < 1:
        raise SyntheticCaseError(f"n_cases must be >= 1, got {total}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise SyntheticCaseError(f"seed must be an integer, got {seed!r}")
    if int(seed) < 0:
        raise SyntheticCaseError(f"seed must be >= 0, got {seed!r}")
    if isinstance(fs_hz, bool) or not isinstance(fs_hz, (int, np.integer)) or int(fs_hz) <= 0:
        raise SyntheticCaseError(f"fs_hz must be a positive integer, got {fs_hz!r}")
    rate = int(fs_hz)
    duration_s = DEFAULT_DURATION_S
    base = total // len(CATEGORIES)
    remainder = total % len(CATEGORIES)
    counts = [base + (1 if position < remainder else 0) for position in range(len(CATEGORIES))]
    cases: list[SyntheticCase] = []
    for category_index, (category, count) in enumerate(zip(CATEGORIES, counts)):
        if count == 0:
            continue
        rng = np.random.default_rng(np.random.SeedSequence([int(seed), category_index]))
        n_reference = _reference_count(count)
        builder = _CASE_BUILDERS[category]
        for index in range(count):
            case_seed = int(rng.integers(0, 2**31 - 1))
            cases.append(
                builder(
                    index,
                    case_seed,
                    rate,
                    duration_s,
                    reference=index < n_reference,
                    rng=rng,
                )
            )
    logger.debug(
        "build_cases: n_cases=%d seed=%d fs=%d counts=%s", total, seed, rate, counts
    )
    return tuple(cases)


def save_manifest(cases: tuple[SyntheticCase, ...], path: str | Path) -> tuple[Path, Path]:
    """Write the case manifest as CSV and JSON.

    Parameters
    ----------
    cases:
        Cases to describe.
    path:
        Either a directory (existing, or a path without suffix — the files are
        then ``manifest.csv`` / ``manifest.json`` inside it), or a base file
        name whose ``.csv`` / ``.json`` variants are written.

    Returns
    -------
    tuple of pathlib.Path
        The written ``(csv_path, json_path)``.

    Raises
    ------
    ValueError
        If ``cases`` is empty.
    """
    case_tuple = tuple(cases)
    if not case_tuple:
        raise ValueError("cannot save a manifest of zero cases")
    base = Path(path)
    if base.is_dir() or base.suffix == "":
        directory = base
        stem = directory / "manifest"
    elif base.suffix.lower() in {".csv", ".json"}:
        stem = base.with_suffix("")
    else:
        stem = base
    csv_path = stem.with_suffix(".csv")
    json_path = stem.with_suffix(".json")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    records = [case.to_dict() for case in case_tuple]
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "case_id": record["case_id"],
                "category": record["category"],
                "seed": record["seed"],
                "fs_hz": record["fs_hz"],
                "duration_s": record["duration_s"],
                "is_reference_condition": record["is_reference_condition"],
                "parameters": json.dumps(record["parameters"], sort_keys=True),
                "ground_truth": json.dumps(record["ground_truth"], sort_keys=True),
            }
            for record in records
        ]
    )
    frame.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    logger.info("save_manifest: wrote %d cases to %s and %s", len(records), csv_path, json_path)
    return csv_path, json_path
