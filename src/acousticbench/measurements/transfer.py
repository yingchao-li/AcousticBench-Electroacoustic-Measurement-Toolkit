"""Physical measurement quantities derived from the raw data containers.

All functions return either a :class:`~acousticbench.data.dataset.TransferCube`
(complex pressure or level) or a tidy :class:`pandas.DataFrame` with the
labels needed for plotting and statistics.

Validity policy
---------------
Every eardrum-pressure function restricts the device axis to *structurally
valid* combinations (see :mod:`acousticbench.types`).  For example,
``eardrum_pressure(..., probe=MEASUREMENT, condition=REFERENCE)`` raises
:class:`MeasurementError` instead of returning the loosely hanging probe
signal.  Measured NaNs are propagated through the cube's ``valid`` mask.

Units
-----
``Hha`` is reported in **dB SPL at the 11.2 mV receiver drive** (the unit used
in Figure 4 of the source publication) and, optionally, in **dB re 1 Pa/V**.
The loudspeaker-driven responses only carry a physically calibrated *ratio*:
``REOIG`` is scale-invariant, while absolute ``REOG``/``REUG`` levels use the
in-situ free-field reference estimated from the loosely hanging measurement
probe (documented in :mod:`acousticbench.data.audit`).
"""

from __future__ import annotations

import warnings
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from acousticbench.data.dataset import AcousticDataset, TransferCube
from acousticbench.exceptions import MeasurementError
from acousticbench.stats.bands import Band, octave_bands
from acousticbench.types import (
    DEVICES,
    P_REF_PA,
    U_HA_DRIVE_V,
    Condition,
    Coupling,
    Probe,
    Source,
)

__all__ = [
    "eardrum_pressure",
    "feedback_path_db_pa_per_v",
    "feedback_path_db_spl",
    "hha_band_levels",
    "hha_db_pa_per_v",
    "hha_db_spl",
    "hha_frequency_response",
    "loudspeaker_response",
    "reog_band_levels",
    "reog_db",
    "reoig_band_levels",
    "reoig_db",
    "reug_band_levels",
    "reug_db",
    "structurally_valid_codes",
    "threshold_dbv",
]

_SOURCE_CONTAINER: dict[tuple[Source, Probe], str] = {
    (Source.HEARING_AID_DRIVER, Probe.MEASUREMENT): "M_ha2edM",
    (Source.HEARING_AID_DRIVER, Probe.REFERENCE): "M_ha2edR",
    (Source.LOUDSPEAKER, Probe.MEASUREMENT): "M_ls2edM",
    (Source.LOUDSPEAKER, Probe.REFERENCE): "M_ls2edR",
}


def _as_enum(value, enum_type, name: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        raise MeasurementError(
            f"Invalid {name} {value!r}; expected one of {[e.value for e in enum_type]}"
        ) from exc


def structurally_valid_codes(dataset: AcousticDataset, key: str) -> tuple[int, ...]:
    """Device codes that are physically meaningful for a container."""
    spec = dataset.spec(key)
    return tuple(device.code for device in DEVICES if spec.structural_valid(device))


def eardrum_pressure(
    dataset: AcousticDataset,
    *,
    source: Source | str,
    probe: Probe | str,
    condition: Condition | str,
    families: Iterable[str] | None = None,
    couplings: Iterable[Coupling | str] | None = None,
    device_codes: Iterable[int] | None = None,
    subjects: Iterable[int] | None = None,
    reinsertions: Iterable[int] | None = None,
) -> TransferCube:
    """Complex eardrum pressure for a documented source/probe/condition.

    Parameters
    ----------
    dataset:
        Loaded dataset.
    source:
        ``"hearing_aid_driver"`` or ``"loudspeaker"``.
    probe:
        ``"measurement"`` or ``"reference"``.
    condition:
        ``"reference"`` or ``"measurement"`` probe condition.
    families, device_codes, subjects, reinsertions:
        Optional filters.  Filters that would remove every structurally valid
        device raise :class:`MeasurementError`.

    Raises
    ------
    MeasurementError
        If the requested combination is not physically measurable (e.g. the
        measurement probe in the reference condition, or the reference probe
        for domes).
    """
    source_enum = _as_enum(source, Source, "source")
    probe_enum = _as_enum(probe, Probe, "probe")
    condition_enum = _as_enum(condition, Condition, "condition")
    key = _SOURCE_CONTAINER[(source_enum, probe_enum)]
    spec = dataset.spec(key)
    if spec.valid_conditions is not None and condition_enum not in spec.valid_conditions:
        raise MeasurementError(
            f"{key} is not a physically meaningful eardrum pressure in the "
            f"{condition_enum.value} condition. Reason: {spec.rationale}"
        )
    valid_codes = list(structurally_valid_codes(dataset, key))
    if device_codes is not None:
        wanted = {int(c) for c in device_codes}
        valid_codes = [code for code in valid_codes if code in wanted]
        if not valid_codes:
            raise MeasurementError(
                f"Requested device codes {sorted(wanted)} are all structurally invalid for {key}"
            )
    if families is not None:
        wanted_families = set(families)
        valid_codes = [code for code in valid_codes if DEVICES[code - 1].family in wanted_families]
        if not valid_codes:
            raise MeasurementError(
                f"Requested families {sorted(wanted_families)} are all structurally invalid "
                f"for {key} in the {condition_enum.value} condition. Reason: {spec.rationale}"
            )
    if couplings is not None:
        try:
            wanted_couplings = {Coupling(c) for c in couplings}
        except ValueError as exc:
            raise MeasurementError(f"Invalid coupling filter {couplings!r}") from exc
        valid_codes = [
            code for code in valid_codes if DEVICES[code - 1].coupling in wanted_couplings
        ]
        if not valid_codes:
            raise MeasurementError(
                f"Requested couplings {sorted(c.value for c in wanted_couplings)} are all "
                f"structurally invalid for {key} in the {condition_enum.value} condition. "
                f"Reason: {spec.rationale}"
            )
    cube = dataset.get(
        key,
        conditions=[condition_enum],
        device_codes=valid_codes,
        families=families,
        couplings=couplings,
        subjects=subjects,
        reinsertions=reinsertions,
    )
    cube = cube.with_name(f"{key} [{condition_enum.value}, {probe_enum.value} probe]")
    return cube


def loudspeaker_response(
    dataset: AcousticDataset,
    *,
    probe: Probe | str,
    condition: Condition | str,
    families: Iterable[str] | None = None,
    couplings: Iterable[Coupling | str] | None = None,
    device_codes: Iterable[int] | None = None,
    subjects: Iterable[int] | None = None,
    reinsertions: Iterable[int] | None = None,
) -> TransferCube:
    """Complex loudspeaker-driven eardrum pressure (free-field referenced)."""
    return eardrum_pressure(
        dataset,
        source=Source.LOUDSPEAKER,
        probe=probe,
        condition=condition,
        families=families,
        couplings=couplings,
        device_codes=device_codes,
        subjects=subjects,
        reinsertions=reinsertions,
    )


# ---------------------------------------------------------------------------
# Hha – hearing-aid driver response
# ---------------------------------------------------------------------------
def hha_db_spl(
    dataset: AcousticDataset,
    *,
    probe: Probe | str = Probe.MEASUREMENT,
    condition: Condition | str = Condition.MEASUREMENT,
    **selection,
) -> TransferCube:
    """``Hha`` in dB SPL at 11.2 mV receiver drive."""
    pressure = eardrum_pressure(
        dataset,
        source=Source.HEARING_AID_DRIVER,
        probe=probe,
        condition=condition,
        **selection,
    )
    level = pressure.magnitude_db(
        reference=P_REF_PA,
        unit_label="dB SPL @ 11.2 mV",
        name=f"Hha [dB SPL @ 11.2 mV, {Probe(probe).value} probe, {Condition(condition).value}]",
    )
    return level


def hha_db_pa_per_v(
    dataset: AcousticDataset,
    *,
    probe: Probe | str = Probe.MEASUREMENT,
    condition: Condition | str = Condition.MEASUREMENT,
    **selection,
) -> TransferCube:
    """``Hha`` in dB re 1 Pa/V (= stored Pa / 0.0112 V)."""
    pressure = eardrum_pressure(
        dataset,
        source=Source.HEARING_AID_DRIVER,
        probe=probe,
        condition=condition,
        **selection,
    )
    level = pressure.magnitude_db(
        reference=U_HA_DRIVE_V,
        unit_label="dB re 1 Pa/V",
        name=f"Hha [dB re Pa/V, {Probe(probe).value} probe, {Condition(condition).value}]",
    )
    return level


def hha_frequency_response(
    dataset: AcousticDataset,
    *,
    probe: Probe | str = Probe.MEASUREMENT,
    condition: Condition | str = Condition.MEASUREMENT,
    **selection,
) -> pd.DataFrame:
    """Median Hha curve (dB SPL) per device across subjects/reinsertions."""
    return hha_db_spl(dataset, probe=probe, condition=condition, **selection).median_level_curve()


def hha_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
    *,
    probe: Probe | str = Probe.MEASUREMENT,
    condition: Condition | str = Condition.MEASUREMENT,
    reference: float = P_REF_PA,
    **selection,
) -> pd.DataFrame:
    """Power-averaged Hha per frequency band (dB SPL by default)."""
    bands = tuple(bands) if bands is not None else octave_bands()
    pressure = eardrum_pressure(
        dataset,
        source=Source.HEARING_AID_DRIVER,
        probe=probe,
        condition=condition,
        **selection,
    )
    frame = pressure.band_levels(bands, reference=reference)
    frame["quantity"] = "Hha"
    frame["unit"] = "dB SPL @ 11.2 mV" if np.isclose(reference, P_REF_PA) else "dB"
    return frame


# ---------------------------------------------------------------------------
# Feedback path
# ---------------------------------------------------------------------------
def feedback_path_db_spl(
    dataset: AcousticDataset,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    subjects: Iterable[int] | None = None,
    reinsertions: Iterable[int] | None = None,
) -> TransferCube:
    """Feedback path ``Hfb = |p_ha / u_ha|`` in dB SPL at 11.2 mV."""
    cube = dataset.get(
        "M_ha2haf",
        conditions=[_as_enum(condition, Condition, "condition")],
        subjects=subjects,
        reinsertions=reinsertions,
    )
    return cube.magnitude_db(
        reference=P_REF_PA,
        unit_label="dB SPL @ 11.2 mV",
        name="Feedback path [dB SPL @ 11.2 mV]",
    )


def feedback_path_db_pa_per_v(
    dataset: AcousticDataset,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    **selection,
) -> TransferCube:
    """Feedback path in dB re 1 Pa/V."""
    cube = dataset.get(
        "M_ha2haf",
        conditions=[_as_enum(condition, Condition, "condition")],
        **selection,
    )
    return cube.magnitude_db(
        reference=U_HA_DRIVE_V,
        unit_label="dB re 1 Pa/V",
        name="Feedback path [dB re Pa/V]",
    )


# ---------------------------------------------------------------------------
# Real-ear gains
# ---------------------------------------------------------------------------
def reoig_db(
    dataset: AcousticDataset,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    probe: Probe | str = Probe.MEASUREMENT,
    **selection,
) -> TransferCube:
    """Real-ear occluded insertion gain (REOIG) in dB.

    ``REOIG = 20 log10|p_occluded / p_open|``.  Both pressures are loudspeaker
    driven, so the (arbitrary) free-field scaling cancels exactly.

    The clinically relevant variant is the default: the measurement-probe
    occluded pressure in the measurement condition divided by the open-ear
    real-ear unaided response (also measured with the measurement probe).
    Using ``probe="reference", condition="reference"`` yields the
    reference-condition REOIG of the earmolds (reference probe occluded vs.
    measurement-probe open ear; see docs/data.md for the documented caveat).
    """
    condition_enum = _as_enum(condition, Condition, "condition")
    probe_enum = _as_enum(probe, Probe, "probe")
    occluded = loudspeaker_response(
        dataset,
        probe=probe_enum,
        condition=condition_enum,
        **selection,
    )
    open_ear = dataset.reur()
    occluded_level = occluded.magnitude_db(reference=1.0)
    open_level = open_ear.magnitude_db(reference=1.0)
    # M_REUR has one insertion per subject; broadcast across devices/reinsertions.
    open_values = np.broadcast_to(open_level.values[:, :1, :, :], occluded_level.values.shape)
    open_valid = np.broadcast_to(open_level.valid[:, :1, :, :], occluded_level.valid.shape)
    values = occluded_level.values - open_values
    valid = occluded_level.valid & open_valid
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=occluded_level.freq_hz,
        devices=occluded_level.devices,
        subjects=occluded_level.subjects,
        reinsertions=occluded_level.reinsertions,
        unit="dB",
        unit_label="dB REOIG",
        name=f"REOIG [dB, {probe_enum.value} probe, {condition_enum.value}]",
        container=None,
        kind="level_db",
        quantity=occluded.quantity,
        metadata={
            "formula": "20log10|p_occluded| - 20log10|p_open|",
            "open_ear": "M_REUR (measurement probe)",
            "condition": condition_enum.value,
            "probe": probe_enum.value,
        },
    )


def reog_db(
    dataset: AcousticDataset,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    probe: Probe | str = Probe.MEASUREMENT,
    **selection,
) -> TransferCube:
    """Real-ear occluded gain (REOG) in dB re the in-situ free field.

    The stored loudspeaker-driven levels lack an absolute free-field
    normalisation (see the data audit); this function normalises by the
    in-situ free-field estimate obtained from the loosely hanging measurement
    probe in the reference condition.  Consequently REOG values are physically
    interpretable *relative to the free field at the ear position*.
    """
    condition_enum = _as_enum(condition, Condition, "condition")
    probe_enum = _as_enum(probe, Probe, "probe")
    occluded = loudspeaker_response(
        dataset,
        probe=probe_enum,
        condition=condition_enum,
        **selection,
    )
    free_field = dataset.free_field_reference()
    occluded_level = occluded.magnitude_db(reference=1.0)
    free_level = free_field.magnitude_db(reference=1.0)
    values = occluded_level.values - free_level.values
    valid = occluded_level.valid & free_level.valid
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=occluded_level.freq_hz,
        devices=occluded_level.devices,
        subjects=occluded_level.subjects,
        reinsertions=occluded_level.reinsertions,
        unit="dB",
        unit_label="dB REOG (re in-situ free field)",
        name=f"REOG [dB re free field, {probe_enum.value} probe, {condition_enum.value}]",
        kind="level_db",
        quantity=occluded.quantity,
        metadata={
            "formula": "20log10|p_occluded| - 20log10|p_free_field|",
            "free_field_reference": "M_ls2edM reference condition (loose measurement probe)",
        },
    )


def reug_db(
    dataset: AcousticDataset,
    *,
    free_field_aggregation: str = "median",
) -> TransferCube:
    """Real-ear unaided gain (REUG) in dB re the in-situ free field.

    ``M_REUR`` contains one insertion per subject, while the free-field
    reference has three reinsertions; the free-field values are aggregated
    over reinsertions (median by default) before the difference.
    """
    if free_field_aggregation not in {"median", "mean"}:
        raise MeasurementError(
            f"free_field_aggregation must be 'median' or 'mean', got {free_field_aggregation!r}"
        )
    reur = dataset.reur()
    reur_level = reur.magnitude_db(reference=1.0)
    free = dataset.free_field_reference().magnitude_db(reference=1.0)
    aggregation = np.nanmedian if free_field_aggregation == "median" else np.nanmean
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        free_values = aggregation(free.values, axis=3, keepdims=True)
        free_valid = free.valid.any(axis=3, keepdims=True)
    values = reur_level.values - free_values
    valid = reur_level.valid & free_valid
    return TransferCube(
        values=values,
        valid=valid,
        freq_hz=reur_level.freq_hz,
        devices=reur_level.devices,
        subjects=reur_level.subjects,
        reinsertions=np.array([-1], dtype=int),
        unit="dB",
        unit_label="dB REUG (re in-situ free field)",
        name="Real-ear unaided gain [dB re in-situ free field]",
        kind="level_db",
        quantity=reur.quantity,
        metadata={
            "formula": "20log10|p_open| - 20log10|p_free_field|",
            "free_field_aggregation": free_field_aggregation,
        },
    )


# ---------------------------------------------------------------------------
# Band-level conveniences
# ---------------------------------------------------------------------------
def _difference_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_column: str,
    right_column: str,
    merge_on: Sequence[str],
    name: str,
) -> pd.DataFrame:
    """Subtract two tidy level frames on shared labels."""
    right_values = right_column + "_right"
    right_subset = right[list(merge_on) + [right_column, "valid"]].rename(
        columns={right_column: right_values, "valid": "valid_right"}
    )
    merged = left.merge(right_subset, on=list(merge_on), how="inner")
    if merged.empty:
        raise MeasurementError(f"No overlapping rows to compute {name}")
    merged[name] = merged[left_column] - merged[right_values]
    merged["valid"] = merged["valid"] & merged["valid_right"]
    return merged.drop(columns=[right_values, "valid_right"])


def reoig_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    probe: Probe | str = Probe.MEASUREMENT,
    **selection,
) -> pd.DataFrame:
    """Power-averaged REOIG per band (dB)."""
    bands = tuple(bands) if bands is not None else octave_bands()
    condition_enum = _as_enum(condition, Condition, "condition")
    probe_enum = _as_enum(probe, Probe, "probe")
    occluded = loudspeaker_response(dataset, probe=probe_enum, condition=condition_enum, **selection)
    occluded_bands = occluded.band_levels(bands, reference=1.0)
    open_bands = dataset.reur().band_levels(bands, reference=1.0)
    result = _difference_frames(
        occluded_bands,
        open_bands,
        left_column="level_db",
        right_column="level_db",
        merge_on=("band", "subject"),
        name="reoig_db",
    )
    # keep the occluded reinsertions (open ear is a single insertion)
    return result


def reog_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
    *,
    condition: Condition | str = Condition.MEASUREMENT,
    probe: Probe | str = Probe.MEASUREMENT,
    **selection,
) -> pd.DataFrame:
    """Power-averaged REOG per band re the in-situ free field (dB)."""
    bands = tuple(bands) if bands is not None else octave_bands()
    condition_enum = _as_enum(condition, Condition, "condition")
    probe_enum = _as_enum(probe, Probe, "probe")
    occluded = loudspeaker_response(dataset, probe=probe_enum, condition=condition_enum, **selection)
    occluded_bands = occluded.band_levels(bands, reference=1.0)
    free_bands = dataset.free_field_reference().band_levels(bands, reference=1.0)
    return _difference_frames(
        occluded_bands,
        free_bands,
        left_column="level_db",
        right_column="level_db",
        merge_on=("band", "subject", "reinsertion"),
        name="reog_db",
    )


def reug_band_levels(
    dataset: AcousticDataset,
    bands: Sequence[Band] | None = None,
) -> pd.DataFrame:
    """Power-averaged REUG per band (dB re in-situ free field)."""
    bands = tuple(bands) if bands is not None else octave_bands()
    reur_bands = dataset.reur().band_levels(bands, reference=1.0)
    free_bands = dataset.free_field_reference().band_levels(bands, reference=1.0)
    free_subject = free_bands.groupby(
        ["band", "band_center_hz", "band_low_hz", "band_high_hz", "subject"], as_index=False
    ).agg(level_db=("level_db", "mean"), valid=("valid", "any"))
    result = _difference_frames(
        reur_bands,
        free_subject,
        left_column="level_db",
        right_column="level_db",
        merge_on=("band", "band_center_hz", "band_low_hz", "band_high_hz", "subject"),
        name="reug_db",
    )
    result["reinsertion"] = -1
    return result


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
def threshold_dbv(dataset: AcousticDataset, **selection) -> TransferCube:
    """Hearing threshold in dBV at the hearing-aid receiver."""
    return dataset.threshold(**selection)
