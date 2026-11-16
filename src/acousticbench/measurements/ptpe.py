"""Probe-tube presence effect (PTPE) and probe-to-probe bias.

The experimental design (Denk, Hackenberg & Husstedt, 2026) compares two probe
conditions:

``reference``
    Only the reference probe tube is in the ear (earmolds; it is routed through
    a dedicated bore in the earmold).  For domes no reference probe exists.
``measurement``
    The measurement probe tube is additionally inserted between the earpiece
    and the ear canal wall.

The probe-tube presence effect is defined as the change caused by inserting
the measurement probe.  Because the reference probe stays in place for
earmolds, the cleanest estimator uses the reference probe in *both*
conditions:

``ΔHha = Hha(RPT, measurement) − Hha(RPT, reference)``
``ΔREOIG = REOIG(measurement) − REOIG(reference)``
``ΔT = T(reference) − T(measurement)``

``ΔT`` is equivalent to a change of ``Hha`` at the eardrum, because the
threshold voltage is inversely related to the transfer function:
``Hha_meas − Hha_ref = T_ref − T_meas``.  This makes the probe-tube presence
effect measurable for domes, where no reference probe exists.

Sign conventions (as in the source publication)
-----------------------------------------------
* ``ΔHha < 0``: the probe tube reduces the driver level at low frequencies.
* ``ΔREOIG > 0``: more external sound leaks into the ear.
* ``ΔT < 0``: a higher receiver voltage is needed at threshold.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from acousticbench.data.dataset import AcousticDataset, TransferCube
from acousticbench.exceptions import MeasurementError
from acousticbench.measurements.transfer import (
    hha_band_levels,
    hha_db_spl,
    reoig_band_levels,
    reoig_db,
    threshold_dbv,
)
from acousticbench.stats.bands import Band, octave_bands
from acousticbench.types import (
    DEVICES,
    Condition,
    Coupling,
    DeviceSpec,
    Probe,
)

__all__ = [
    "family_axis",
    "probe_bias_band_levels",
    "probe_bias_db",
    "ptpe_band_levels",
    "ptpe_hha_db",
    "ptpe_reoig_db",
    "ptpe_summary",
    "ptpe_threshold_db",
    "threshold_ptpe",
]

_EARMOLD_FAMILIES = (
    ("closed_earmold", "Closed Earmold"),
    ("vented_earmold", "Vented Earmold"),
    ("nugget_earmold", "Nugget Earmold"),
    ("silicone_earmold", "Silicone Earmold"),
)
_ALL_FAMILIES = (
    ("closed_earmold", "Closed Earmold", Coupling.EARMOLD),
    ("vented_earmold", "Vented Earmold", Coupling.EARMOLD),
    ("nugget_earmold", "Nugget Earmold", Coupling.EARMOLD),
    ("silicone_earmold", "Silicone Earmold", Coupling.EARMOLD),
    ("open_dome", "Open Dome", Coupling.DOME),
    ("tulip_dome", "Tulip Dome", Coupling.DOME),
    ("power_dome", "Power Dome", Coupling.DOME),
)


def family_axis(
    families: Iterable[str] | None = None,
    *,
    suffix: str = "",
) -> tuple[DeviceSpec, ...]:
    """Synthetic device axis for family-level derived metrics.

    Codes 101… are used so they never collide with the dataset's device codes.
    """
    wanted = set(families) if families is not None else None
    axis: list[DeviceSpec] = []
    for index, (family, label, coupling) in enumerate(_ALL_FAMILIES):
        if wanted is not None and family not in wanted:
            continue
        short = {
            "closed_earmold": "Closed",
            "vented_earmold": "Vented",
            "nugget_earmold": "Nugget",
            "silicone_earmold": "Silicone",
            "open_dome": "Open",
            "tulip_dome": "Tulip",
            "power_dome": "Power",
        }[family]
        axis.append(
            DeviceSpec(
                code=101 + index,
                family=family,
                family_label=label,
                coupling=coupling,
                condition=None,
                label=f"{label}{suffix}",
                short_label=f"{short}{suffix}",
            )
        )
    return tuple(axis)


def _family_of(code: int) -> str:
    return DEVICES[code - 1].family


def probe_bias_db(
    dataset: AcousticDataset,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
) -> TransferCube:
    """Level difference measurement probe − reference probe (dB, earmolds).

    Both probes are in the ear in the measurement condition, so this is a pure
    probe-placement bias.  Positive values mean the measurement probe reads
    higher than the reference probe.
    """
    condition_enum = Condition(condition)
    mpt = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=condition_enum)
    rpt = hha_db_spl(dataset, probe=Probe.REFERENCE, condition=condition_enum)
    shared = [code for code in mpt.device_codes if code in set(rpt.device_codes)]
    if not shared:
        raise MeasurementError("No shared earmold devices for probe-to-probe bias")
    mpt = mpt.select(device_codes=shared)
    rpt = rpt.select(device_codes=shared)
    values = mpt.values - rpt.values
    valid = mpt.valid & rpt.valid
    devices = tuple(
        replace(device, label=f"{device.family_label} · bias", short_label=f"{device.short_label} bias")
        for device in rpt.devices
    )
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=rpt.freq_hz,
        devices=devices,
        subjects=rpt.subjects,
        reinsertions=rpt.reinsertions,
        unit="dB",
        unit_label="dB (MPT − RPT)",
        name="Probe-to-probe bias [dB, MPT − RPT]",
        kind="level_db",
        metadata={"condition": condition_enum.value, "probe_pair": "measurement - reference"},
    )


def probe_bias_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
) -> pd.DataFrame:
    """Power-averaged probe bias per band (dB)."""
    bands = tuple(bands) if bands is not None else octave_bands()
    condition_enum = Condition(condition)
    mpt = hha_band_levels(
        dataset, bands, probe=Probe.MEASUREMENT, condition=condition_enum
    )
    rpt = hha_band_levels(dataset, bands, probe=Probe.REFERENCE, condition=condition_enum)
    merged = mpt.merge(
        rpt[["band", "family", "subject", "reinsertion", "level_db", "valid"]],
        on=["band", "family", "subject", "reinsertion"],
        how="inner",
        suffixes=("", "_rpt"),
    )
    merged["bias_db"] = merged["level_db"] - merged["level_db_rpt"]
    merged["valid"] = merged["valid"] & merged["valid_rpt"]
    return merged.drop(columns=["level_db", "level_db_rpt", "valid_rpt"])


# ---------------------------------------------------------------------------
# PTPE on Hha and REOIG (earmolds only)
# ---------------------------------------------------------------------------
def ptpe_hha_db(dataset: AcousticDataset) -> TransferCube:
    """ΔHha = Hha(RPT, measurement) − Hha(RPT, reference), earmolds only."""
    measurement = hha_db_spl(dataset, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT)
    reference = hha_db_spl(dataset, probe=Probe.REFERENCE, condition=Condition.REFERENCE)
    # Both cubes are in family order (closed, vented, nugget, silicone).
    if [d.family for d in measurement.devices] != [d.family for d in reference.devices]:
        raise MeasurementError("Earmold family order differs between probe conditions")
    values = measurement.values - reference.values
    valid = measurement.valid & reference.valid
    devices = family_axis([d.family for d in measurement.devices], suffix=" · ΔHha")
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=measurement.freq_hz,
        devices=devices,
        subjects=measurement.subjects,
        reinsertions=measurement.reinsertions,
        unit="dB",
        unit_label="dB ΔHha",
        name="Probe-tube presence effect on Hha [dB]",
        kind="level_db",
        metadata={
            "formula": "Hha(measurement, RPT) - Hha(reference, RPT)",
            "applicable_couplings": "earmold",
            "note": "Reference probe available for earmolds only.",
        },
    )


def ptpe_hha_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
) -> pd.DataFrame:
    """Band-level ΔHha (dB) for earmolds, using power-averaged band levels."""
    bands = tuple(bands) if bands is not None else octave_bands()
    measurement = hha_band_levels(
        dataset, bands, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT
    )
    reference = hha_band_levels(
        dataset, bands, probe=Probe.REFERENCE, condition=Condition.REFERENCE
    )
    merged = measurement.merge(
        reference[["band", "family", "subject", "reinsertion", "level_db", "valid"]],
        on=["band", "family", "subject", "reinsertion"],
        how="inner",
        suffixes=("", "_ref"),
    )
    merged["ptpe_db"] = merged["level_db"] - merged["level_db_ref"]
    merged["valid"] = merged["valid"] & merged["valid_ref"]
    return merged.drop(columns=["level_db", "level_db_ref", "valid_ref"])


def ptpe_reoig_db(dataset: AcousticDataset) -> TransferCube:
    """ΔREOIG = REOIG(measurement) − REOIG(reference) for earmolds."""
    # Use the reference probe in BOTH conditions so that the difference isolates
    # the acoustic probe-tube presence effect without probe-to-probe bias.
    measurement = reoig_db(dataset, condition=Condition.MEASUREMENT, probe=Probe.REFERENCE)
    reference = reoig_db(dataset, condition=Condition.REFERENCE, probe=Probe.REFERENCE)
    if [d.family for d in measurement.devices] != [d.family for d in reference.devices]:
        raise MeasurementError("Earmold family order differs between probe conditions")
    values = measurement.values - reference.values
    valid = measurement.valid & reference.valid
    devices = family_axis([d.family for d in measurement.devices], suffix=" · ΔREOIG")
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=measurement.freq_hz,
        devices=devices,
        subjects=measurement.subjects,
        reinsertions=measurement.reinsertions,
        unit="dB",
        unit_label="dB ΔREOIG",
        name="Probe-tube presence effect on REOIG [dB]",
        kind="level_db",
        metadata={
            "formula": "REOIG(measurement) - REOIG(reference)",
            "applicable_couplings": "earmold",
        },
    )


def ptpe_reoig_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
) -> pd.DataFrame:
    """Band-level ΔREOIG (dB) for earmolds."""
    bands = tuple(bands) if bands is not None else octave_bands()
    measurement = reoig_band_levels(
        dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.REFERENCE
    )
    reference = reoig_band_levels(
        dataset, bands, condition=Condition.REFERENCE, probe=Probe.REFERENCE
    )
    merged = measurement.merge(
        reference[["band", "family", "subject", "reinsertion", "reoig_db", "valid"]],
        on=["band", "family", "subject", "reinsertion"],
        how="inner",
        suffixes=("", "_ref"),
    )
    merged["ptpe_db"] = merged["reoig_db"] - merged["reoig_db_ref"]
    merged["valid"] = merged["valid"] & merged["valid_ref"]
    return merged.drop(columns=["reoig_db", "reoig_db_ref", "valid_ref"])


# ---------------------------------------------------------------------------
# PTPE on thresholds (all couplings)
# ---------------------------------------------------------------------------
def ptpe_threshold_db(dataset: AcousticDataset) -> TransferCube:
    """ΔT = T(reference) − T(measurement) in dB, all seven earpiece families.

    Thresholds are measured at 125, 250, 500, 750, 1000 and 2000 Hz.  ``ΔT``
    equals the equivalent change of ``Hha`` at the eardrum, which is how the
    probe-tube presence effect is assessed for domes.
    """
    reference_codes = [d.code for d in DEVICES if d.condition is Condition.REFERENCE]
    measurement_codes = [d.code for d in DEVICES if d.condition is Condition.MEASUREMENT]
    reference = dataset.threshold(device_codes=reference_codes).values
    measurement = dataset.threshold(device_codes=measurement_codes).values
    reference_valid = np.isfinite(reference)
    measurement_valid = np.isfinite(measurement)
    values = reference - measurement
    valid = reference_valid & measurement_valid
    devices = family_axis(suffix=" · ΔT")
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=dataset.threshold_frequency_hz,
        devices=devices,
        subjects=dataset.subjects,
        reinsertions=dataset.reinsertions,
        unit="dB",
        unit_label="dB ΔT",
        name="Probe-tube presence effect on threshold [dB]",
        kind="level_db",
        axis_name="threshold_frequency_hz",
        metadata={
            "formula": "T(reference) - T(measurement)",
            "equivalence": "ΔT equals the change of Hha at the eardrum at fixed drive voltage",
            "note": "Available for domes, where no reference probe exists.",
        },
    )


def threshold_ptpe(dataset: AcousticDataset) -> pd.DataFrame:
    """Tidy table of threshold-level PTPE (family, subject, reinsertion, frequency)."""
    cube = ptpe_threshold_db(dataset)
    frame = cube.to_dataframe()
    frame["delta_t_db"] = frame["value"].astype(float)
    return frame.drop(columns=["value"])


# ---------------------------------------------------------------------------
# Summary for reports
# ---------------------------------------------------------------------------
def ptpe_summary(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
) -> pd.DataFrame:
    """Compact per-family summary of the probe-tube presence effect.

    Returns a tidy frame with columns ``metric, family, band, value_db,
    n_subjects`` where the metric is one of ``delta_hha`` (earmolds),
    ``delta_reoig`` (earmolds) or ``delta_threshold`` (all families).  Values
    are medians across subjects of the subject-level reinsertion means.
    """
    bands = tuple(bands) if bands is not None else octave_bands()
    rows: list[pd.DataFrame] = []

    # ΔHha at low-frequency bands.
    hha_bands = ptpe_hha_band_levels(dataset, bands)
    hha_bands = hha_bands.loc[hha_bands["valid"]]
    hha_subject = (
        hha_bands.groupby(["family", "band", "band_center_hz", "subject"], as_index=False)[
            "ptpe_db"
        ]
        .mean()
    )
    summary = hha_subject.groupby(
        ["family", "band", "band_center_hz"], as_index=False
    ).agg(value_db=("ptpe_db", "median"), n_subjects=("ptpe_db", "count"))
    summary["metric"] = "delta_hha"
    rows.append(summary[["metric", "family", "band", "band_center_hz", "value_db", "n_subjects"]])

    reoig_bands = ptpe_reoig_band_levels(dataset, bands)
    reoig_bands = reoig_bands.loc[reoig_bands["valid"]]
    reoig_subject = (
        reoig_bands.groupby(["family", "band", "band_center_hz", "subject"], as_index=False)[
            "ptpe_db"
        ]
        .mean()
    )
    summary_r = reoig_subject.groupby(
        ["family", "band", "band_center_hz"], as_index=False
    ).agg(value_db=("ptpe_db", "median"), n_subjects=("ptpe_db", "count"))
    summary_r["metric"] = "delta_reoig"
    rows.append(
        summary_r[["metric", "family", "band", "band_center_hz", "value_db", "n_subjects"]]
    )

    threshold = ptpe_threshold_db(dataset)
    freq = threshold.freq_hz
    idx_125 = int(np.argmin(np.abs(freq - 125.0)))
    values = threshold.masked[idx_125]  # (n_families, n_subjects, n_reinsertions)
    with np.errstate(invalid="ignore"):
        subject_values = np.nanmean(values, axis=2)
    frame_rows = []
    for index, device in enumerate(threshold.devices):
        data = subject_values[index]
        frame_rows.append(
            {
                "metric": "delta_threshold",
                "family": device.family,
                "band": "125 Hz",
                "band_center_hz": 125.0,
                "value_db": float(np.nanmedian(data)),
                "n_subjects": int(np.sum(np.isfinite(data))),
            }
        )
    rows.append(pd.DataFrame(frame_rows))
    return pd.concat(rows, ignore_index=True)
