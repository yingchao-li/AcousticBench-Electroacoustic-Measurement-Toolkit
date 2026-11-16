"""Unit conversions and level arithmetic.

The dataset mixes three physical scales that must never be confused:

``Pa at 11.2 mV``
    Complex pressure at the eardrum (or hearing-aid microphone) for a
    hearing-aid receiver drive voltage of 11.2 mV.  ``Hha`` in dB SPL at that
    drive is ``20 log10(|p| / 20 µPa)``; the transfer function in dB re Pa/V is
    ``20 log10(|p| / 0.0112 V)``.
``Pa at free-field reference``
    Loudspeaker-driven pressure.  Only *ratios* of these values are physically
    calibrated (the free-field reference cancels in REOIG); see
    :mod:`acousticbench.data.audit`.
``dBV``
    Hearing threshold as the receiver voltage at threshold.
"""

from __future__ import annotations

import numpy as np

from acousticbench.exceptions import UnitError
from acousticbench.types import P_REF_PA, U_HA_DRIVE_V

__all__ = [
    "dB_SPL_OFFSET",
    "db_to_amplitude",
    "db_to_pa",
    "magnitude",
    "magnitude_db",
    "pa_to_db_pa_per_v",
    "pa_to_db_spl",
    "phase_deg",
    "phase_rad",
    "threshold_dbv_to_voltage",
]

#: Offset to convert dB re 1 Pa into dB SPL: 20 log10(1 / 20e-6) ≈ 93.9794 dB.
dB_SPL_OFFSET: float = 20.0 * np.log10(1.0 / P_REF_PA)


def magnitude(values: np.ndarray) -> np.ndarray:
    """Absolute value of real or complex values (NaNs are preserved)."""
    return np.abs(np.asarray(values))


def magnitude_db(
    values: np.ndarray,
    reference: float = 1.0,
    floor_db: float = -200.0,
) -> np.ndarray:
    """Convert values to ``20 log10(|value| / reference)``.

    Zero magnitudes are clamped to ``floor_db``; non-finite inputs yield NaN.
    """
    if reference <= 0:
        raise UnitError(f"reference must be positive, got {reference!r}")
    array = np.asarray(values)
    mag = np.abs(array)
    floor_linear = reference * 10.0 ** (floor_db / 20.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 20.0 * np.log10(np.maximum(mag, floor_linear) / reference)
    db = np.where(np.isfinite(mag), db, np.nan)
    return np.asarray(db, dtype=float)


def phase_rad(values: np.ndarray) -> np.ndarray:
    """Phase in radians (NaN for non-finite magnitudes)."""
    array = np.asarray(values)
    return np.asarray(np.angle(array), dtype=float)


def phase_deg(values: np.ndarray) -> np.ndarray:
    """Phase in degrees, NaN where the value is non-finite."""
    array = np.asarray(values)
    deg = np.degrees(np.angle(array))
    return np.where(np.isfinite(array), deg, np.nan)


def pa_to_db_spl(values: np.ndarray, floor_db: float = -200.0) -> np.ndarray:
    """Pressure in Pa → dB SPL (re 20 µPa)."""
    return magnitude_db(values, reference=P_REF_PA, floor_db=floor_db)


def pa_to_db_pa_per_v(
    values: np.ndarray,
    drive_voltage_v: float = U_HA_DRIVE_V,
    floor_db: float = -200.0,
) -> np.ndarray:
    """Pressure in Pa at a drive voltage → dB re 1 Pa/V."""
    if drive_voltage_v <= 0:
        raise UnitError(f"drive voltage must be positive, got {drive_voltage_v!r}")
    return magnitude_db(values, reference=drive_voltage_v, floor_db=floor_db)


def db_to_amplitude(db: np.ndarray | float) -> np.ndarray:
    """Amplitude ratio from dB: ``10 ** (db / 20)``."""
    return np.asarray(10.0 ** (np.asarray(db, dtype=float) / 20.0))


def db_to_pa(db_spl: np.ndarray | float) -> np.ndarray:
    """dB SPL → pressure in Pa."""
    return P_REF_PA * db_to_amplitude(db_spl)


def threshold_dbv_to_voltage(dbv: np.ndarray | float) -> np.ndarray:
    """Receiver voltage at threshold (dBV) → volts RMS."""
    return np.asarray(10.0 ** (np.asarray(dbv, dtype=float) / 20.0))
