"""Loading and schema validation of the MATLAB ``Data.mat`` file.

The published file is a MATLAB v5 MAT-file (platform PCWIN64) containing:

===============  =========================  ==============  ==========================
Variable         Shape                      Type            Meaning
===============  =========================  ==============  ==========================
``v_frq``        (1, 2049)                  float64         frequency axis [Hz]
``v_fAud``       (1, 6)                     uint16          audiometric frequencies [Hz]
``M_ha2edM``     (2049, 14, 14, 3)          complex128      HA driver → eardrum (MPT)
``M_ha2edR``     (2049, 14, 14, 3)          complex128      HA driver → eardrum (RPT)
``M_ha2haf``     (2049, 14, 14, 3)          complex128      HA driver → HA microphone
``M_ls2edM``     (2049, 14, 14, 3)          complex128      loudspeaker → eardrum (MPT)
``M_ls2edR``     (2049, 14, 14, 3)          complex128      loudspeaker → eardrum (RPT)
``M_thr_ha``     (6, 14, 14, 3)             float64         hearing threshold [dBV]
``M_REUR``       (2049, 14)                 complex128      real-ear unaided response
===============  =========================  ==============  ==========================

A MATLAB v7.3 (HDF5) file is also accepted through the optional ``h5py``
fallback, which makes the loader robust to re-saves of the dataset.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import scipy.io

from acousticbench.exceptions import DataValidationError
from acousticbench.types import (
    N_FREQUENCIES,
    N_REINSERTIONS,
    N_SUBJECTS,
    N_THRESHOLD_FREQUENCIES,
    NYQUIST_HZ,
    FREQUENCY_RESOLUTION_HZ,
)

__all__ = [
    "EXPECTED_SHAPES",
    "MatFileInfo",
    "RawMatData",
    "inspect_mat",
    "load_mat",
    "validate_variables",
]

#: Expected shape of every dataset variable (C-order after squeezing the row/column vectors).
EXPECTED_SHAPES: dict[str, tuple[int, ...]] = {
    "v_frq": (N_FREQUENCIES,),
    "v_fAud": (N_THRESHOLD_FREQUENCIES,),
    "M_ha2edM": (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_ha2edR": (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_ha2haf": (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_ls2edM": (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_ls2edR": (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_thr_ha": (N_THRESHOLD_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS),
    "M_REUR": (N_FREQUENCIES, N_SUBJECTS),
}

#: Variables that must be complex-valued.
COMPLEX_VARIABLES = frozenset({"M_ha2edM", "M_ha2edR", "M_ha2haf", "M_ls2edM", "M_ls2edR", "M_REUR"})

#: Variables that must be real-valued.
REAL_VARIABLES = frozenset({"v_frq", "v_fAud", "M_thr_ha"})


@dataclass(frozen=True)
class MatFileInfo:
    """Provenance and fingerprint of a MAT-file."""

    path: Path
    size_bytes: int
    sha256: str
    header: str
    mat_format: str
    load_seconds: float
    md5: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
            "sha256": self.sha256,
            "md5": self.md5,
            "header": self.header,
            "mat_format": self.mat_format,
            "load_seconds": round(self.load_seconds, 4),
        }


@dataclass(frozen=True)
class RawMatData:
    """Raw variables of a MAT-file plus provenance information."""

    info: MatFileInfo
    variables: Mapping[str, np.ndarray]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __getitem__(self, key: str) -> np.ndarray:
        return self.variables[key]

    def __contains__(self, key: object) -> bool:
        return key in self.variables

    def keys(self) -> tuple[str, ...]:
        return tuple(self.variables)

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def shape_table(self) -> dict[str, tuple[int, ...]]:
        return {k: tuple(v.shape) for k, v in self.variables.items()}


def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _read_header(path: Path) -> str:
    with path.open("rb") as handle:
        raw = handle.read(128)
    text = raw.decode("latin-1", errors="replace")
    # The 128-byte MAT header is padded with spaces and NUL bytes; keep only
    # the printable description up to the first NUL.
    return text.split("\x00", 1)[0].strip()


def _convert_compound(values: np.ndarray) -> np.ndarray:
    """Convert MATLAB v7.3 HDF5 complex compound types to complex128."""
    if values.dtype.fields is not None:
        fields = values.dtype.fields
        if {"real", "imag"}.issubset(fields):
            return values["real"] + 1j * values["imag"]
        # Some writers use ("r", "i") instead.
        if {"r", "i"}.issubset(fields):
            return values["r"] + 1j * values["i"]
    return values


def _load_hdf5(path: Path) -> dict[str, np.ndarray]:
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - h5py is a hard dependency
        raise DataValidationError(
            "Data.mat is a MATLAB v7.3 (HDF5) file but h5py is not installed."
        ) from exc
    variables: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as handle:
        for name in handle.keys():
            if name.startswith("#"):
                continue
            dataset = handle[name]
            values = _convert_compound(np.asarray(dataset[()]))
            # MATLAB stores column-major arrays; h5py exposes reversed dimensions.
            if values.ndim > 1:
                values = values.T
            variables[name] = np.asarray(values)
    return variables


def validate_variables(
    variables: Mapping[str, np.ndarray],
    *,
    strict_axes: bool = True,
) -> tuple[dict[str, np.ndarray], list[str]]:
    """Validate the dataset schema and return normalised arrays.

    The frequency axes are normalised to 1-D arrays; all other variables keep
    their documented dimensions.  A list of non-fatal warnings is returned.

    Raises
    ------
    DataValidationError
        If a variable is missing, has the wrong shape/dtype or the frequency
        axis is not a physical DFT grid.
    """
    issues: list[str] = []
    warnings: list[str] = []

    for name, expected_shape in EXPECTED_SHAPES.items():
        if name not in variables:
            issues.append(f"missing variable {name!r}")
            continue
        values = np.asarray(variables[name])
        if name == "v_fAud" and values.dtype.kind in "iu":
            # integer frequency list is expected; cast later
            pass
        if tuple(values.shape) != expected_shape:
            # row/column vectors for the two axes are documented as (1, N)
            if name in {"v_frq", "v_fAud"} and values.size == int(np.prod(expected_shape)):
                values = values.reshape(expected_shape)
            else:
                issues.append(
                    f"{name!r} has shape {tuple(values.shape)}, expected {expected_shape}"
                )
                continue
        if name in COMPLEX_VARIABLES and not np.iscomplexobj(values):
            issues.append(f"{name!r} must be complex-valued (got dtype {values.dtype})")
        if name in REAL_VARIABLES and np.iscomplexobj(values):
            issues.append(f"{name!r} must be real-valued (got dtype {values.dtype})")
        if name in {"v_frq", "v_fAud"}:
            if not np.all(np.isfinite(values)):
                issues.append(f"{name!r} contains non-finite values")
        else:
            finite = np.isfinite(values)
            if not np.any(finite):
                issues.append(f"{name!r} contains no finite values")
            if np.any(np.isinf(values)):
                issues.append(f"{name!r} contains infinite values")
        variables = dict(variables)
        variables[name] = values

    if issues:
        raise DataValidationError(
            "Data.mat does not match the documented schema:\n  - " + "\n  - ".join(issues)
        )

    frq = np.asarray(variables["v_frq"], dtype=float).ravel()
    f_aud = np.asarray(variables["v_fAud"]).ravel().astype(float)

    if frq.size != N_FREQUENCIES:
        raise DataValidationError(f"v_frq must have {N_FREQUENCIES} entries, got {frq.size}")
    if frq[0] != 0.0:
        warnings.append(f"v_frq does not start at 0 Hz (starts at {frq[0]:g} Hz)")
    if not np.all(np.diff(frq) > 0):
        raise DataValidationError("v_frq must be strictly increasing")
    diffs = np.diff(frq)
    if strict_axes:
        if not np.allclose(diffs, FREQUENCY_RESOLUTION_HZ, rtol=1e-6, atol=1e-9):
            raise DataValidationError(
                "v_frq is not a uniform DFT grid with "
                f"Δf={FREQUENCY_RESOLUTION_HZ:.6f} Hz (observed median Δf={np.median(diffs):.6f} Hz)"
            )
        if not np.isclose(frq[-1], NYQUIST_HZ, rtol=1e-9):
            raise DataValidationError(
                f"v_frq must end at {NYQUIST_HZ} Hz, got {frq[-1]} Hz"
            )
    if f_aud.size != N_THRESHOLD_FREQUENCIES:
        raise DataValidationError(
            f"v_fAud must have {N_THRESHOLD_FREQUENCIES} entries, got {f_aud.size}"
        )
    if not np.all(np.diff(f_aud) > 0):
        raise DataValidationError("v_fAud must be strictly increasing")
    if not np.allclose(f_aud, [125, 250, 500, 750, 1000, 2000]):
        warnings.append(
            "v_fAud differs from the documented [125, 250, 500, 750, 1000, 2000] Hz"
        )

    variables["v_frq"] = frq
    variables["v_fAud"] = f_aud
    return dict(variables), warnings


def load_mat(path: str | Path, *, compute_hash: bool = True, strict_axes: bool = True) -> RawMatData:
    """Load and validate a MAT-file.

    Parameters
    ----------
    path:
        Path to ``Data.mat`` (MATLAB v5 or v7.3).
    compute_hash:
        Compute the SHA-256 fingerprint (needed for the audit; ~0.2 s for 90 MB).
    strict_axes:
        Enforce the documented uniform DFT frequency grid.

    Returns
    -------
    RawMatData
        Validated variables with provenance metadata.
    """
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise DataValidationError(
            f"Data file not found: {file_path}. Run scripts/fetch_data.py or place "
            "Data.mat at the repository root (see DATA_LICENSE.md)."
        )

    header = _read_header(file_path)
    started = time.perf_counter()
    format_name = "v7.3 (HDF5)" if header.startswith("MATLAB 7.3") else "v5"
    try:
        contents = scipy.io.loadmat(file_path, squeeze_me=False, struct_as_record=False)
        variables = {
            key: value
            for key, value in contents.items()
            if not key.startswith("__")
        }
    except NotImplementedError:
        variables = _load_hdf5(file_path)
        format_name = "v7.3 (HDF5)"
    load_seconds = time.perf_counter() - started

    validated, warnings = validate_variables(variables, strict_axes=strict_axes)
    digest = _sha256(file_path) if compute_hash else ""
    info = MatFileInfo(
        path=file_path,
        size_bytes=file_path.stat().st_size,
        sha256=digest,
        header=header,
        mat_format=format_name,
        load_seconds=load_seconds,
    )
    return RawMatData(info=info, variables=validated, warnings=tuple(warnings))


def inspect_mat(path: str | Path) -> dict[str, Any]:
    """Return a human-readable inspection summary of a MAT-file."""
    data = load_mat(path)
    summary: dict[str, Any] = {
        "file": data.info.to_dict(),
        "variables": {},
        "warnings": list(data.warnings),
    }
    for name, values in data.variables.items():
        entry: dict[str, Any] = {
            "shape": tuple(int(v) for v in values.shape),
            "dtype": str(values.dtype),
            "complex": bool(np.iscomplexobj(values)),
        }
        if name.startswith("M_") and name != "M_thr_ha":
            finite = np.isfinite(values)
            entry["finite_fraction"] = float(finite.mean())
            if np.iscomplexobj(values):
                mag = np.abs(values[finite])
                if mag.size:
                    entry["magnitude_median"] = float(np.median(mag))
        if name == "M_thr_ha":
            entry["nan_count"] = int(np.isnan(values).sum())
            entry["min_dbv"] = float(np.nanmin(values))
            entry["max_dbv"] = float(np.nanmax(values))
        if name in {"v_frq", "v_fAud"}:
            entry["values"] = values.tolist()
        summary["variables"][name] = entry
    return summary
