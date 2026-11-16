"""Validity rules for the AcousticBench dataset.

Two independent validity dimensions are combined:

``measured``
    ``False`` where the data provider stored NaN (erroneous measurement).
``structural``
    ``False`` where the stored value is documented to be physically
    meaningless for the quantity (e.g. measurement-probe eardrum pressure in
    the reference condition, reference-probe pressure for domes).

The combined mask is used everywhere; AcousticBench never imputes values.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from acousticbench.types import (
    CONTAINERS,
    CONTAINER_ORDER,
    DEVICES,
    DeviceSpec,
    ContainerSpec,
)

__all__ = [
    "build_valid_mask",
    "combined_valid_mask",
    "finite_mask",
    "invalid_reasons_table",
    "invalid_sessions",
    "structural_validity",
    "structural_validity_table",
]


def finite_mask(values: np.ndarray) -> np.ndarray:
    """Element-wise finiteness mask that also works for complex arrays."""
    return np.isfinite(np.asarray(values))


def structural_validity(
    spec: ContainerSpec, devices: Sequence[DeviceSpec] = DEVICES
) -> np.ndarray:
    """Return a boolean array of structural validity for ``devices``."""
    return np.asarray([spec.structural_valid(device) for device in devices], dtype=bool)


def build_valid_mask(
    values: np.ndarray,
    spec: ContainerSpec,
    devices: Sequence[DeviceSpec] = DEVICES,
) -> np.ndarray:
    """Combine finiteness and structural validity for a 4-D container.

    Parameters
    ----------
    values:
        Array of shape ``(n_freq, n_devices, n_subjects, n_reinsertions)``.
    spec:
        Container metadata carrying the structural validity rules.
    devices:
        Device definitions matching axis 1 of ``values``.

    Returns
    -------
    numpy.ndarray
        Boolean array of the same shape as ``values``.
    """
    values = np.asarray(values)
    if values.ndim != 4:
        raise ValueError(f"expected a 4-D container, got shape {values.shape}")
    if values.shape[1] != len(devices):
        raise ValueError(
            f"device axis has length {values.shape[1]} but {len(devices)} devices were supplied"
        )
    measured = finite_mask(values)
    structural = structural_validity(spec, devices)[None, :, None, None]
    return measured & structural


def combined_valid_mask(
    values: np.ndarray,
    spec: ContainerSpec,
    devices: Sequence[DeviceSpec] = DEVICES,
) -> np.ndarray:
    """Alias of :func:`build_valid_mask` kept for API clarity."""
    return build_valid_mask(values, spec, devices)


def invalid_sessions(
    values: np.ndarray,
    *,
    freq_axis: int = 0,
    threshold: int | None = None,
) -> np.ndarray:
    """Return a boolean mask of sessions with too few finite frequency bins.

    For a 4-D transfer-function container the result has shape
    ``(n_devices, n_subjects, n_reinsertions)``; for the 2-D ``M_REUR``
    container it has shape ``(n_subjects,)``.

    Parameters
    ----------
    values:
        Data container (complex or real).
    freq_axis:
        Axis that enumerates frequency bins.
    threshold:
        Number of non-finite bins at which a session is declared invalid.
        Defaults to the full frequency axis (a completely NaN column).
    """
    values = np.asarray(values)
    non_finite = ~np.isfinite(values)
    required = values.shape[freq_axis] if threshold is None else int(threshold)
    counts = non_finite.sum(axis=freq_axis)
    return counts >= required


def structural_validity_table() -> pd.DataFrame:
    """Tabulate structural validity of every container × device combination.

    Useful for the data-audit page and the report appendix.
    """
    rows: list[dict[str, object]] = []
    for key in CONTAINER_ORDER:
        spec = CONTAINERS[key]
        for device in DEVICES:
            rows.append(
                {
                    "container": key,
                    "device_code": device.code,
                    "device": device.label,
                    "family": device.family,
                    "coupling": device.coupling.value,
                    "condition": device.condition.value if device.condition else None,
                    "structurally_valid": spec.structural_valid(device),
                }
            )
    return pd.DataFrame(rows)


def invalid_reasons_table() -> pd.DataFrame:
    """Return the human-readable structural validity rules of all containers."""
    rows = []
    for key in CONTAINER_ORDER:
        spec = CONTAINERS[key]
        valid_devices = [d for d in DEVICES if spec.structural_valid(d)]
        rows.append(
            {
                "container": key,
                "description": spec.description,
                "valid_conditions": (
                    ", ".join(sorted(c.value for c in spec.valid_conditions))
                    if spec.valid_conditions is not None
                    else "all"
                ),
                "valid_couplings": (
                    ", ".join(sorted(c.value for c in spec.valid_couplings))
                    if spec.valid_couplings is not None
                    else "all"
                ),
                "n_structurally_valid_devices": len(valid_devices),
                "valid_device_codes": ", ".join(str(d.code) for d in valid_devices),
                "rationale": spec.rationale,
            }
        )
    return pd.DataFrame(rows)
