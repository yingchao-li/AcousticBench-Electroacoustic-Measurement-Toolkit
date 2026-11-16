"""Dataset abstraction and labelled transfer-function cubes.

The :class:`AcousticDataset` is the single entry point for all analysis code::

    from acousticbench.data import load_dataset
    ds = load_dataset()
    cube = ds.get("M_ha2edR", conditions=["measurement"], couplings=["earmold"])
    level = cube.magnitude_db(reference=20e-6)   # dB SPL at 11.2 mV
    curve = level.median_level_curve()            # tidy DataFrame
    bands = level.band_levels(octave_bands())     # tidy DataFrame

Every cube carries:

* ``values`` – the raw complex/real array (as stored in the MAT-file),
* ``valid`` – a boolean mask combining measured NaNs and structural validity,
* labelled axes (frequency, devices, subjects, reinsertions) and units.

All aggregation helpers operate on the *masked* array and therefore can never
silently use a structurally invalid or NaN value.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from acousticbench.config import Config, load_config
from acousticbench.data.units import magnitude_db
from acousticbench.data.validity import build_valid_mask, invalid_sessions
from acousticbench.exceptions import DataSelectionError, DataValidationError
from acousticbench.io.mat_loader import RawMatData, load_mat
from acousticbench.stats.bands import Band
from acousticbench.types import (
    ALL_DEVICES,
    CONTAINERS,
    ContainerSpec,
    DEVICE_FREE_FIELD,
    DEVICE_OPEN_EAR,
    DEVICES,
    EARMOLD_DEVICE_CODES,
    N_REINSERTIONS,
    N_SUBJECTS,
    REFERENCE_DEVICE_CODES,
    REUR_CONTAINER_KEY,
    THRESHOLD_CONTAINER_KEY,
    TRANSFER_CONTAINER_KEYS,
    Condition,
    Coupling,
    DeviceSpec,
    Quantity,
    Source,
)

__all__ = ["AcousticDataset", "TransferCube", "load_dataset"]

_CUBE_KINDS = frozenset({"transfer", "level_db", "threshold_dbv", "phase_deg"})


# ---------------------------------------------------------------------------
# TransferCube
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TransferCube:
    """A labelled 4-D measurement cube.

    Axes are always ``(frequency, device, subject, reinsertion)``.  Derived
    cubes with a single device (open ear, in-situ free field) use a length-1
    device axis.  The data is stored as measured; consumers must respect
    :attr:`valid`.  ``masked`` returns the array with invalid entries set to
    NaN.
    """

    values: np.ndarray
    valid: np.ndarray
    freq_hz: np.ndarray
    devices: tuple[DeviceSpec, ...]
    subjects: np.ndarray
    reinsertions: np.ndarray
    unit: str
    unit_label: str
    name: str
    container: str | None = None
    kind: str = "transfer"
    axis_name: str = "frequency_hz"
    quantity: Quantity | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # -- validation ---------------------------------------------------------
    def __post_init__(self) -> None:
        values = np.asarray(self.values)
        valid = np.asarray(self.valid, dtype=bool)
        freq = np.asarray(self.freq_hz, dtype=float)
        subjects = np.asarray(self.subjects)
        reinsertions = np.asarray(self.reinsertions)
        devices = tuple(self.devices)

        if values.ndim != 4:
            raise ValueError(f"TransferCube values must be 4-D, got shape {values.shape}")
        if valid.shape != values.shape:
            raise ValueError(
                f"valid mask shape {valid.shape} does not match values shape {values.shape}"
            )
        if freq.ndim != 1 or freq.size != values.shape[0]:
            raise ValueError(
                f"frequency axis has length {freq.size}, expected {values.shape[0]}"
            )
        if len(devices) != values.shape[1]:
            raise ValueError(
                f"device axis has length {values.shape[1]} but {len(devices)} devices were supplied"
            )
        if subjects.size != values.shape[2]:
            raise ValueError(
                f"subject axis has length {values.shape[2]} but {subjects.size} subjects were supplied"
            )
        if reinsertions.size != values.shape[3]:
            raise ValueError(
                f"reinsertion axis has length {values.shape[3]} but "
                f"{reinsertions.size} reinsertions were supplied"
            )
        if self.kind not in _CUBE_KINDS:
            raise ValueError(f"unknown cube kind {self.kind!r}")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "freq_hz", freq)
        object.__setattr__(self, "devices", devices)
        object.__setattr__(self, "subjects", subjects)
        object.__setattr__(self, "reinsertions", reinsertions)

    # -- basic properties ---------------------------------------------------
    @property
    def shape(self) -> tuple[int, int, int, int]:
        return tuple(self.values.shape)  # type: ignore[return-value]

    @property
    def n_frequencies(self) -> int:
        return self.values.shape[0]

    @property
    def n_devices(self) -> int:
        return self.values.shape[1]

    @property
    def n_subjects(self) -> int:
        return self.values.shape[2]

    @property
    def n_reinsertions(self) -> int:
        return self.values.shape[3]

    @property
    def is_empty(self) -> bool:
        return self.values.size == 0

    @property
    def device_codes(self) -> tuple[int, ...]:
        return tuple(d.code for d in self.devices)

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(d.family for d in self.devices))

    @property
    def conditions(self) -> tuple[Condition, ...]:
        return tuple(dict.fromkeys(d.condition for d in self.devices if d.condition is not None))

    @property
    def masked(self) -> np.ndarray:
        """Values with invalid entries replaced by NaN."""
        if np.iscomplexobj(self.values):
            fill = np.complex128(complex(np.nan, np.nan))
            return np.where(self.valid, self.values, fill)
        return np.where(self.valid, self.values, np.nan)

    @property
    def n_valid(self) -> int:
        return int(self.valid.sum())

    @property
    def valid_fraction(self) -> float:
        return float(self.valid.mean()) if self.valid.size else float("nan")

    # -- selection ----------------------------------------------------------
    def select(
        self,
        *,
        device_codes: Iterable[int] | None = None,
        conditions: Iterable[Condition | str] | None = None,
        families: Iterable[str] | None = None,
        couplings: Iterable[Coupling | str] | None = None,
        subjects: Iterable[int] | None = None,
        reinsertions: Iterable[int] | None = None,
        freq_range: tuple[float, float] | None = None,
    ) -> "TransferCube":
        """Return a filtered cube.  Filters are combined with logical AND."""
        selected = list(self.devices)
        if device_codes is not None:
            wanted = {int(c) for c in device_codes}
            selected = [d for d in selected if d.code in wanted]
        if conditions is not None:
            wanted_cond = {Condition(c) for c in conditions}
            selected = [d for d in selected if d.condition in wanted_cond]
        if families is not None:
            wanted_fam = set(families)
            selected = [d for d in selected if d.family in wanted_fam]
        if couplings is not None:
            wanted_coup = {Coupling(c) for c in couplings}
            selected = [d for d in selected if d.coupling in wanted_coup]

        device_indices = [i for i, d in enumerate(self.devices) if d in selected]
        if not device_indices:
            raise DataSelectionError(
                f"Selection of {self.name!r} yields no devices "
                f"(codes={device_codes}, conditions={conditions}, families={families})"
            )

        subject_mask = np.ones(self.subjects.size, dtype=bool)
        if subjects is not None:
            wanted_subj = {int(s) for s in subjects}
            subject_mask = np.isin(self.subjects, list(wanted_subj))
            if not subject_mask.any():
                raise DataSelectionError(
                    f"Selection of {self.name!r} yields no subjects {sorted(wanted_subj)}"
                )
        reinsertion_mask = np.ones(self.reinsertions.size, dtype=bool)
        if reinsertions is not None:
            wanted_re = {int(r) for r in reinsertions}
            reinsertion_mask = np.isin(self.reinsertions, list(wanted_re))
            if not reinsertion_mask.any():
                raise DataSelectionError(
                    f"Selection of {self.name!r} yields no reinsertions {sorted(wanted_re)}"
                )

        freq_mask = np.ones(self.freq_hz.size, dtype=bool)
        if freq_range is not None:
            lo, hi = sorted(float(v) for v in freq_range)
            freq_mask = (self.freq_hz >= lo) & (self.freq_hz <= hi)
            if not freq_mask.any():
                raise DataSelectionError(
                    f"Selection of {self.name!r} yields no frequencies in {freq_range}"
                )

        values = self.values[np.ix_(freq_mask, device_indices, subject_mask, reinsertion_mask)]
        valid = self.valid[np.ix_(freq_mask, device_indices, subject_mask, reinsertion_mask)]
        return replace(
            self,
            values=values,
            valid=valid,
            freq_hz=self.freq_hz[freq_mask],
            devices=tuple(self.devices[i] for i in device_indices),
            subjects=self.subjects[subject_mask],
            reinsertions=self.reinsertions[reinsertion_mask],
        )

    # -- unit transforms ----------------------------------------------------
    def magnitude_db(
        self,
        reference: float = 1.0,
        floor_db: float = -200.0,
        *,
        unit_label: str | None = None,
        name: str | None = None,
    ) -> "TransferCube":
        """Return a real-valued level cube ``20 log10(|value| / reference)``."""
        if self.kind != "transfer":
            raise ValueError(f"magnitude_db() requires a transfer cube, got kind={self.kind!r}")
        levels = magnitude_db(self.masked, reference=reference, floor_db=floor_db)
        return replace(
            self,
            values=levels,
            valid=self.valid.copy(),
            unit="dB",
            unit_label=unit_label or self.unit_label + " [dB]",
            name=name or f"{self.name} [dB]",
            kind="level_db",
        )

    def phase_deg(self) -> "TransferCube":
        """Return a phase cube in degrees."""
        if self.kind != "transfer":
            raise ValueError(f"phase_deg() requires a transfer cube, got kind={self.kind!r}")
        values = np.degrees(np.angle(self.masked))
        return replace(
            self,
            values=values,
            valid=self.valid.copy(),
            unit="deg",
            unit_label="deg",
            name=f"{self.name} [phase]",
            kind="phase_deg",
        )

    def level_cube(self, reference: float = 1.0, floor_db: float = -200.0) -> "TransferCube":
        """Return a dB cube (no-op for cubes that are already levels)."""
        if self.kind == "transfer":
            return self.magnitude_db(reference=reference, floor_db=floor_db)
        if self.kind in {"level_db", "threshold_dbv"}:
            return self
        raise ValueError(f"Cannot convert kind={self.kind!r} to levels")

    def with_name(self, name: str) -> "TransferCube":
        return replace(self, name=name)

    # -- aggregation --------------------------------------------------------
    def mean_reinsertions(self) -> "TransferCube":
        """Average the three reinsertions (subject-level summary)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            with np.errstate(invalid="ignore"):
                values = np.nanmean(np.where(self.valid, self.values, np.nan), axis=3)
        if np.iscomplexobj(self.values):
            values = np.asarray(values, dtype=np.complex128)
        else:
            values = np.asarray(values, dtype=float)
        valid = self.valid.any(axis=3)
        return replace(
            self,
            values=values[:, :, :, None],
            valid=valid[:, :, :, None],
            reinsertions=np.array([-1], dtype=int),
            name=f"{self.name} (reinsertion mean)",
            metadata={**dict(self.metadata), "aggregation": "mean_reinsertions"},
        )

    def std_reinsertions(self, ddof: int = 1) -> "TransferCube":
        """Standard deviation across the three reinsertions."""
        masked = self.masked
        with np.errstate(invalid="ignore"):
            if np.iscomplexobj(self.values):
                values = np.nanstd(masked.real, axis=3, ddof=ddof) + 1j * np.nanstd(
                    masked.imag, axis=3, ddof=ddof
                )
            else:
                values = np.nanstd(masked, axis=3, ddof=ddof)
        valid = self.valid.sum(axis=3) > ddof
        return replace(
            self,
            values=np.asarray(values)[:, :, :, None],
            valid=valid[:, :, :, None],
            reinsertions=np.array([-1], dtype=int),
            name=f"{self.name} (reinsertion std)",
            unit=self.unit,
            unit_label=self.unit_label,
            kind=self.kind,
            metadata={**dict(self.metadata), "aggregation": "std_reinsertions", "ddof": ddof},
        )

    def level_cube_for(self, reference: float, floor_db: float = -200.0) -> "TransferCube":
        """Internal helper kept for readability in experiments."""
        return self.level_cube(reference=reference, floor_db=floor_db)

    def level_array(self, reference: float = 1.0, floor_db: float = -200.0) -> np.ndarray:
        """Return a float level array with NaN for invalid entries.

        Transfer cubes are converted to ``20 log10(|value| / reference)``;
        level/threshold cubes are returned unchanged.  This is the canonical
        way for statistics/measurement code to obtain analysis-ready arrays.
        """
        return np.asarray(self.level_cube(reference=reference, floor_db=floor_db).masked, dtype=float)

    def subject_level_means(self, reference: float = 1.0) -> np.ndarray:
        """Mean level per device/subject over valid reinsertions, shape (freq, device, subject)."""
        levels = self.level_array(reference=reference)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            return np.nanmean(levels, axis=3)

    def median_level_curve(self, reference: float = 1.0, floor_db: float = -200.0) -> pd.DataFrame:
        """Median level across subjects and reinsertions, per frequency/device.

        Returns a tidy DataFrame with columns
        ``frequency_hz, device_code, device, family, coupling, condition,
        median_db, mean_db, sd_db, n_valid``.
        """
        levels = self.level_cube(reference=reference, floor_db=floor_db)
        array = levels.masked  # NaN where invalid
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            median = np.nanmedian(array, axis=(2, 3))
            mean = np.nanmean(array, axis=(2, 3))
            sd = np.nanstd(array, axis=(2, 3))
        n_valid = levels.valid.sum(axis=(2, 3))
        frames = []
        for index, device in enumerate(levels.devices):
            frames.append(
                pd.DataFrame(
                    {
                        "frequency_hz": levels.freq_hz,
                        "device_code": device.code,
                        "device": device.label,
                        "family": device.family,
                        "family_label": device.family_label,
                        "coupling": device.coupling.value,
                        "condition": device.condition.value if device.condition else None,
                        "median_db": median[:, index],
                        "mean_db": mean[:, index],
                        "sd_db": sd[:, index],
                        "n_valid": n_valid[:, index].astype(int),
                    }
                )
            )
        return pd.concat(frames, ignore_index=True)

    def band_levels(
        self,
        bands: Sequence[Band],
        reference: float = 1.0,
        floor_db: float = -200.0,
    ) -> pd.DataFrame:
        """Power-averaged band levels as a tidy DataFrame.

        Requires a complex transfer cube.  The power average over DFT bins
        within a band is the correct operation for level comparisons; ratios
        of conditions are unaffected by the arbitrary free-field scaling.
        """
        if self.kind != "transfer":
            raise ValueError(f"band_levels() requires a transfer cube, got kind={self.kind!r}")
        power = np.abs(self.masked) ** 2
        rows: list[pd.DataFrame] = []
        floor_power = reference**2 * 10.0 ** (floor_db / 10.0)
        for band in bands:
            data_mask = band.contains(self.freq_hz)
            if not data_mask.any():
                continue
            with warnings.catch_warnings(), np.errstate(invalid="ignore"):
                warnings.simplefilter("ignore", category=RuntimeWarning)
                band_power = np.nanmean(power[data_mask], axis=0)
            valid = self.valid[data_mask].any(axis=0)
            level = 10.0 * np.log10(np.maximum(band_power / reference**2, floor_power / reference**2))
            level = np.where(valid, level, np.nan)
            frame = _cube_to_frame(self, level, valid)
            frame.insert(0, "band", band.label)
            frame.insert(1, "band_center_hz", band.center_hz)
            frame.insert(2, "band_low_hz", band.low_hz)
            frame.insert(3, "band_high_hz", band.high_hz)
            frame = frame.rename(columns={"value": "level_db"})
            rows.append(frame)
        if not rows:
            raise DataValidationError(
                "No configured frequency band overlaps the cube's frequency axis"
            )
        return pd.concat(rows, ignore_index=True)

    def to_dataframe(self, *, valid_only: bool = False) -> pd.DataFrame:
        """Tidy long-format DataFrame of the raw values."""
        n_freq, n_dev, n_subj, n_re = self.values.shape
        frame = pd.DataFrame(
            {
                self.axis_name: np.repeat(self.freq_hz, n_dev * n_subj * n_re),
                "device_code": np.tile(np.repeat([d.code for d in self.devices], n_subj * n_re), n_freq),
                "device": np.tile(
                    np.repeat([d.label for d in self.devices], n_subj * n_re), n_freq
                ),
                "family": np.tile(
                    np.repeat([d.family for d in self.devices], n_subj * n_re), n_freq
                ),
                "family_label": np.tile(
                    np.repeat([d.family_label for d in self.devices], n_subj * n_re), n_freq
                ),
                "coupling": np.tile(
                    np.repeat([d.coupling.value for d in self.devices], n_subj * n_re), n_freq
                ),
                "condition": np.tile(
                    np.repeat(
                        [d.condition.value if d.condition else None for d in self.devices],
                        n_subj * n_re,
                    ),
                    n_freq,
                ),
                "subject": np.tile(np.repeat(self.subjects, n_re), n_freq * n_dev),
                "reinsertion": np.tile(self.reinsertions, n_freq * n_dev * n_subj),
                "value": self.values.reshape(-1),
                "valid": self.valid.reshape(-1),
            }
        )
        if valid_only:
            frame = frame.loc[frame["valid"]].reset_index(drop=True)
        return frame

    def to_level_dataframe(
        self, reference: float = 1.0, *, valid_only: bool = False
    ) -> pd.DataFrame:
        """Tidy long-format DataFrame of levels in dB."""
        levels = self.level_cube(reference=reference)
        frame = levels.to_dataframe(valid_only=valid_only)
        frame["level_db"] = frame["value"].astype(float)
        return frame.drop(columns=["value"])

    def describe(self) -> str:
        parts = [
            f"{self.name}",
            f"  shape       : {self.shape} (freq × device × subject × reinsertion)",
            f"  unit        : {self.unit} ({self.unit_label})",
            f"  kind        : {self.kind}",
            f"  devices     : {', '.join(d.short_label for d in self.devices) or '—'}",
            f"  valid       : {self.n_valid}/{self.valid.size} ({self.valid_fraction * 100:.1f} %)",
        ]
        return "\n".join(parts)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"TransferCube(name={self.name!r}, shape={self.shape}, kind={self.kind!r}, "
            f"devices={len(self.devices)}, valid={self.valid_fraction:.1%})"
        )


def _cube_to_frame(cube: TransferCube, values: np.ndarray, valid: np.ndarray) -> pd.DataFrame:
    """Convert a ``(device, subject, reinsertion)`` array to a tidy frame."""
    n_dev, n_subj, n_re = values.shape
    return pd.DataFrame(
        {
            "device_code": np.repeat([d.code for d in cube.devices], n_subj * n_re),
            "device": np.repeat([d.label for d in cube.devices], n_subj * n_re),
            "family": np.repeat([d.family for d in cube.devices], n_subj * n_re),
            "family_label": np.repeat([d.family_label for d in cube.devices], n_subj * n_re),
            "coupling": np.repeat([d.coupling.value for d in cube.devices], n_subj * n_re),
            "condition": np.repeat(
                [d.condition.value if d.condition else None for d in cube.devices], n_subj * n_re
            ),
            "subject": np.tile(np.repeat(cube.subjects, n_re), n_dev),
            "reinsertion": np.tile(cube.reinsertions, n_dev * n_subj),
            "value": values.reshape(-1),
            "valid": valid.reshape(-1),
        }
    )


# ---------------------------------------------------------------------------
# AcousticDataset
# ---------------------------------------------------------------------------
class AcousticDataset:
    """Validated, labelled view of the Denk et al. (2026) measurement dataset."""

    def __init__(self, raw: RawMatData, config: Config | None = None) -> None:
        self.raw = raw
        self.config = config or load_config()
        self.info = raw.info
        variables = raw.variables
        self.frequency_hz = np.asarray(variables["v_frq"], dtype=float).ravel()
        self.threshold_frequency_hz = np.asarray(variables["v_fAud"], dtype=float).ravel()
        self.subjects = np.arange(1, N_SUBJECTS + 1, dtype=int)
        self.reinsertions = np.arange(1, N_REINSERTIONS + 1, dtype=int)
        self.devices = DEVICES
        self._validate()

    # -- construction -------------------------------------------------------
    @classmethod
    def from_file(
        cls,
        path: str | Path | None = None,
        *,
        config: Config | None = None,
        compute_hash: bool = True,
    ) -> "AcousticDataset":
        cfg = config or load_config()
        data_path = Path(path) if path is not None else cfg.data_path
        raw = load_mat(data_path, compute_hash=compute_hash)
        return cls(raw, config=cfg)

    def _validate(self) -> None:
        expected = {
            "M_ha2edM": (2049, 14, 14, 3),
            "M_ha2edR": (2049, 14, 14, 3),
            "M_ha2haf": (2049, 14, 14, 3),
            "M_ls2edM": (2049, 14, 14, 3),
            "M_ls2edR": (2049, 14, 14, 3),
            "M_thr_ha": (6, 14, 14, 3),
            "M_REUR": (2049, 14),
        }
        problems = []
        for key, shape in expected.items():
            if key not in self.raw.variables:
                problems.append(f"missing {key}")
                continue
            observed = tuple(self.raw.variables[key].shape)
            if observed != shape:
                problems.append(f"{key}: shape {observed} != {shape}")
        if self.frequency_hz.size != 2049:
            problems.append(f"v_frq length {self.frequency_hz.size} != 2049")
        if self.threshold_frequency_hz.size != 6:
            problems.append(f"v_fAud length {self.threshold_frequency_hz.size} != 6")
        if problems:
            raise DataValidationError("; ".join(problems))

    # -- metadata -----------------------------------------------------------
    @property
    def path(self) -> Path:
        return self.info.path

    @property
    def containers(self) -> tuple[str, ...]:
        return tuple(CONTAINERS)

    def spec(self, key: str) -> ContainerSpec:
        try:
            return CONTAINERS[key]
        except KeyError as exc:
            raise KeyError(f"Unknown container {key!r}; available: {', '.join(CONTAINERS)}") from exc

    def values(self, key: str) -> np.ndarray:
        """Raw values of a container (never modified)."""
        if key not in self.raw.variables:
            raise KeyError(f"Unknown container {key!r}")
        return np.asarray(self.raw.variables[key])

    # -- validity -----------------------------------------------------------
    def structural_mask(self, key: str) -> np.ndarray:
        """Structural validity per device for ``key`` (shape ``(14,)``)."""
        spec = self.spec(key)
        return np.asarray([spec.structural_valid(d) for d in self.devices], dtype=bool)

    def valid_mask(self, key: str) -> np.ndarray:
        """Combined measured + structural validity mask for a 4-D container."""
        if key == REUR_CONTAINER_KEY:
            values = self.values(key)
            return np.isfinite(values)[:, None, :, None]
        spec = self.spec(key)
        return build_valid_mask(self.values(key), spec, self.devices)

    def invalid_sessions(self, key: str) -> pd.DataFrame:
        """Tidy table of sessions with a completely invalid frequency axis."""
        values = self.values(key)
        spec = self.spec(key)
        if key == REUR_CONTAINER_KEY:
            return pd.DataFrame(
                columns=["container", "device_code", "device", "subject", "reinsertion", "reason"]
            )
        session_invalid = invalid_sessions(values, freq_axis=0)
        rows = []
        for d_index, subject_index, reinsertion_index in np.argwhere(session_invalid):
            device = self.devices[int(d_index)]
            rows.append(
                {
                    "container": key,
                    "device_code": device.code,
                    "device": device.label,
                    "family": device.family,
                    "condition": device.condition.value if device.condition else None,
                    "subject": int(self.subjects[subject_index]),
                    "reinsertion": int(self.reinsertions[reinsertion_index]),
                    "measured_nan": True,
                    "structurally_valid": bool(spec.structural_valid(device)),
                }
            )
        return pd.DataFrame(rows)

    def session_validity_summary(self) -> pd.DataFrame:
        """Per-container count of invalid sessions (measured NaNs)."""
        rows = []
        for key in (*TRANSFER_CONTAINER_KEYS, THRESHOLD_CONTAINER_KEY, REUR_CONTAINER_KEY):
            values = self.values(key)
            if key == REUR_CONTAINER_KEY:
                invalid = int(np.isnan(values).all(axis=0).sum())
                total = int(values.shape[1])
            else:
                invalid = int(invalid_sessions(values, freq_axis=0).sum())
                total = int(np.prod(values.shape[1:]))
            rows.append(
                {
                    "container": key,
                    "n_invalid_sessions": invalid,
                    "n_sessions": total,
                    "invalid_fraction": invalid / total if total else float("nan"),
                }
            )
        return pd.DataFrame(rows)

    # -- cube access --------------------------------------------------------
    def get(
        self,
        key: str,
        *,
        conditions: Iterable[Condition | str] | None = None,
        couplings: Iterable[Coupling | str] | None = None,
        families: Iterable[str] | None = None,
        device_codes: Iterable[int] | None = None,
        subjects: Iterable[int] | None = None,
        reinsertions: Iterable[int] | None = None,
        freq_range: tuple[float, float] | None = None,
    ) -> TransferCube:
        """Return a labelled cube for a container, optionally filtered."""
        spec = self.spec(key)
        cube = self._build_cube(spec)
        return cube.select(
            conditions=conditions,
            couplings=couplings,
            families=families,
            device_codes=device_codes,
            subjects=subjects,
            reinsertions=reinsertions,
            freq_range=freq_range,
        )

    def threshold(self, **selection: Any) -> TransferCube:
        """Threshold cube (frequencies 125 … 2000 Hz, values in dBV)."""
        return self.get(THRESHOLD_CONTAINER_KEY, **selection)

    def reur(self, **selection: Any) -> TransferCube:
        """Real-ear unaided response cube (open ear, one device/insertion axis)."""
        selection.pop("device_codes", None)
        selection.pop("conditions", None)
        selection.pop("couplings", None)
        selection.pop("families", None)
        return self.get(REUR_CONTAINER_KEY, **selection)

    def _build_cube(self, spec: ContainerSpec) -> TransferCube:
        key = spec.key
        values = self.values(key)
        if key == REUR_CONTAINER_KEY:
            cube_values = values[:, None, :, None]
            valid = np.isfinite(cube_values)
            return TransferCube(
                values=cube_values,
                valid=valid,
                freq_hz=self.frequency_hz,
                devices=(DEVICE_OPEN_EAR,),
                subjects=self.subjects,
                reinsertions=np.array([1], dtype=int),
                unit=spec.unit,
                unit_label=spec.unit_label,
                name=key,
                container=key,
                kind="transfer",
                quantity=spec.quantity,
                metadata={"description": spec.description, "single_insertion": True},
            )
        if key == THRESHOLD_CONTAINER_KEY:
            return TransferCube(
                values=values,
                valid=np.isfinite(values),
                freq_hz=self.threshold_frequency_hz,
                devices=self.devices,
                subjects=self.subjects,
                reinsertions=self.reinsertions,
                unit=spec.unit,
                unit_label=spec.unit_label,
                name=key,
                container=key,
                kind="threshold_dbv",
                axis_name="threshold_frequency_hz",
                quantity=spec.quantity,
                metadata={"description": spec.description, "quantisation_db": 1.0},
            )
        return TransferCube(
            values=values,
            valid=build_valid_mask(values, spec, self.devices),
            freq_hz=self.frequency_hz,
            devices=self.devices,
            subjects=self.subjects,
            reinsertions=self.reinsertions,
            unit=spec.unit,
            unit_label=spec.unit_label,
            name=key,
            container=key,
            kind="transfer",
            quantity=spec.quantity,
            metadata={
                "description": spec.description,
                "source": spec.source.value,
                "probe": spec.probe.value if spec.probe else None,
                "valid_conditions": (
                    sorted(c.value for c in spec.valid_conditions)
                    if spec.valid_conditions
                    else None
                ),
                "valid_couplings": (
                    sorted(c.value for c in spec.valid_couplings)
                    if spec.valid_couplings
                    else None
                ),
                "rationale": spec.rationale,
            },
        )

    # -- derived reference --------------------------------------------------
    def free_field_reference(
        self,
        *,
        per_device: bool = False,
        subjects: Iterable[int] | None = None,
        reinsertions: Iterable[int] | None = None,
    ) -> TransferCube:
        """In-situ free-field estimate from the *loosely hanging* measurement probe.

        In the reference probe condition the measurement probe tube hangs
        loosely around the ear (documented).  The loudspeaker-driven signal it
        records therefore approximates the free-field pressure at the ear
        position per loudspeaker drive.  Using the median across the seven
        reference-condition earpieces removes the (small) residual
        device-dependent scattering and yields a per-subject free-field
        reference.

        With ``per_device=True`` the seven individual reference-condition
        curves are returned (useful for the data audit).  Otherwise a single
        ``DEVICE_FREE_FIELD`` axis entry is returned, shape
        ``(n_freq, 1, n_subj, n_reinsertions)``.

        .. note::
           These entries are *structurally invalid* for the stored eardrum
           quantity, so this function intentionally bypasses
           :meth:`structural_mask`; the finiteness mask is still honoured.
        """
        values = self.values("M_ls2edM")
        ref_indices = [code - 1 for code in REFERENCE_DEVICE_CODES]
        reference_devices = [self.devices[i] for i in ref_indices]
        subset = values[:, ref_indices, :, :]
        finite = np.isfinite(subset)
        counts = finite.sum(axis=1)
        if per_device:
            cube = TransferCube(
                values=subset,
                valid=finite,
                freq_hz=self.frequency_hz,
                devices=tuple(reference_devices),
                subjects=self.subjects,
                reinsertions=self.reinsertions,
                unit="Pa at free-field reference",
                unit_label="Pa (free field)",
                name="in_situ_free_field_per_device",
                kind="transfer",
                quantity=Quantity.EARDRUM_PRESSURE,
                metadata={
                    "method": "reference-condition measurement probe (loose)",
                    "note": "Loudspeaker-driven; approximates free-field pressure per drive.",
                },
            )
            return cube.select(subjects=subjects, reinsertions=reinsertions)

        median = _nanmedian_complex(subset, axis=1)
        min_devices = max(1, int(self.config.data.free_field_reference.min_devices))
        valid = counts >= min_devices
        cube = TransferCube(
            values=median[:, None, :, :],
            valid=valid[:, None, :, :],
            freq_hz=self.frequency_hz,
            devices=(DEVICE_FREE_FIELD,),
            subjects=self.subjects,
            reinsertions=self.reinsertions,
            unit="Pa at free-field reference",
            unit_label="Pa (free field)",
            name="in_situ_free_field",
            kind="transfer",
            quantity=Quantity.EARDRUM_PRESSURE,
            metadata={
                "method": "median of reference-condition loose measurement-probe response",
                "n_devices": len(ref_indices),
                "min_devices": min_devices,
            },
        )
        return cube.select(subjects=subjects, reinsertions=reinsertions)

    # -- reporting ----------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        """Machine-readable dataset summary for reports and audits."""
        validity = self.session_validity_summary()
        return {
            "file": self.info.to_dict(),
            "n_frequencies": int(self.frequency_hz.size),
            "frequency_range_hz": [float(self.frequency_hz.min()), float(self.frequency_hz.max())],
            "frequency_resolution_hz": float(np.median(np.diff(self.frequency_hz))),
            "threshold_frequencies_hz": self.threshold_frequency_hz.tolist(),
            "n_devices": len(self.devices),
            "n_subjects": int(self.subjects.size),
            "n_reinsertions": int(self.reinsertions.size),
            "containers": list(self.containers),
            "invalid_sessions": validity.to_dict(orient="records"),
            "configuration": {
                "invalid_policy": self.config.data.invalid_policy,
                "free_field_reference": self.config.data.free_field_reference.method,
            },
        }

    def describe(self) -> str:
        lines = [
            "AcousticBench dataset",
            f"  file        : {self.path.name} ({self.info.mat_format}, "
            f"{self.info.size_bytes / 1024**2:.1f} MB)",
            f"  sha256      : {self.info.sha256 or '—'}",
            f"  axes        : {self.frequency_hz.size} freqs × 14 devices × "
            f"{self.subjects.size} subjects × {self.reinsertions.size} reinsertions",
            f"  freq range  : {self.frequency_hz[0]:.1f} … {self.frequency_hz[-1]:.1f} Hz "
            f"(Δf = {np.median(np.diff(self.frequency_hz)):.4f} Hz)",
            f"  audiogram   : {', '.join(f'{f:g}' for f in self.threshold_frequency_hz)} Hz",
            "",
            "Containers and validity:",
        ]
        for key in (*TRANSFER_CONTAINER_KEYS, THRESHOLD_CONTAINER_KEY, REUR_CONTAINER_KEY):
            spec = CONTAINERS[key]
            n_valid_devices = int(self.structural_mask(key).sum()) if key != REUR_CONTAINER_KEY else 1
            values = self.values(key)
            n_nan = int(np.isnan(values).sum()) if np.iscomplexobj(values) else int(np.isnan(values).sum())
            lines.append(
                f"  {key:10s} {str(tuple(values.shape)):20s} "
                f"valid_devices={n_valid_devices:2d}  nan_values={n_nan:6d}  ({spec.description})"
            )
        return "\n".join(lines)

    def audit(self):  # noqa: ANN201 - avoid circular import at module load
        """Run the full data-quality audit (see :mod:`acousticbench.data.audit`)."""
        from acousticbench.data.audit import DataAuditor

        return DataAuditor(self, config=self.config).run()

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"AcousticDataset(path={self.path.name!r}, "
            f"shape={self.frequency_hz.size}×14×{self.subjects.size}×{self.reinsertions.size})"
        )


def _nanmedian_complex(values: np.ndarray, axis: int) -> np.ndarray:
    """NaN-aware median for complex arrays (component-wise fallback)."""
    values = np.asarray(values)
    if not np.iscomplexobj(values):
        return np.nanmedian(values, axis=axis)
    try:
        return np.nanmedian(values, axis=axis)
    except (TypeError, ValueError):  # pragma: no cover - older numpy fallback
        return np.nanmedian(values.real, axis=axis) + 1j * np.nanmedian(values.imag, axis=axis)


def load_dataset(
    path: str | Path | None = None,
    *,
    config: Config | None = None,
    compute_hash: bool = True,
) -> AcousticDataset:
    """Load the measurement dataset (``Data.mat`` by default).

    Parameters
    ----------
    path:
        Explicit path to the MAT-file.  Defaults to ``config.paths.data_mat``.
    config:
        Configuration override.  Defaults to ``load_config()``.
    compute_hash:
        Compute the SHA-256 fingerprint (needed for the provenance audit).
    """
    return AcousticDataset.from_file(path, config=config, compute_hash=compute_hash)
