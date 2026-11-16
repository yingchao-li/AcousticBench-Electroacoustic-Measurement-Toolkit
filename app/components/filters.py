"""Sidebar filter widgets shared by the dashboard pages.

Every widget uses an explicit ``key`` prefix so that pages keep independent
filter state, and returns plain Python values (family strings, ``Condition``
enums, subject integers, device codes) ready to pass to the measurement API.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import streamlit as st

from acousticbench.data.dataset import AcousticDataset
from acousticbench.stats.bands import Band, octave_bands, third_octave_bands
from acousticbench.types import DEVICES, FAMILIES, Condition, DeviceSpec, Probe

__all__ = [
    "band_set_widget",
    "condition_widget",
    "device_widget",
    "families_widget",
    "probe_widget",
    "reinsertion_widget",
    "subjects_widget",
]


def _sidebar():
    return st.sidebar


def families_widget(
    key: str,
    *,
    default_all: bool = True,
    options: Sequence[tuple[str, str]] | None = None,
) -> list[str]:
    """Multi-select of earpiece families (family labels shown to the user)."""
    choices = list(options or [(family, label) for family, label, _ in FAMILIES])
    lookup = dict(choices)
    selected = _sidebar().multiselect(
        "Earpiece family",
        options=[family for family, _ in choices],
        default=[family for family, _ in choices] if default_all else [],
        format_func=lambda family: lookup.get(family, family),
        key=f"{key}_families",
        help="All seven earpiece families are available; dome families have no reference-probe data.",
    )
    return selected


def condition_widget(
    key: str,
    *,
    default: Iterable[Condition | str] = (Condition.MEASUREMENT,),
    options: Iterable[Condition | str] = (Condition.MEASUREMENT, Condition.REFERENCE),
) -> list[Condition]:
    """Multi-select of probe conditions."""
    normalised = [Condition(value) for value in options]
    default_values = {Condition(value) for value in default}
    selected = _sidebar().multiselect(
        "Probe condition",
        options=normalised,
        default=[condition for condition in normalised if condition in default_values],
        format_func=lambda condition: condition.label,
        key=f"{key}_conditions",
        help=(
            "Reference: only the reference probe tube in place. "
            "Measurement: the measurement probe tube is additionally inserted."
        ),
    )
    return selected


def probe_widget(key: str, *, default: Probe | str | None = Probe.MEASUREMENT) -> Probe | None:
    """Radio button selecting one probe microphone (or none)."""
    options: list[str] = ["any", Probe.MEASUREMENT.value, Probe.REFERENCE.value]
    labels = {
        "any": "Any / not applicable",
        Probe.MEASUREMENT.value: "Measurement probe",
        Probe.REFERENCE.value: "Reference probe",
    }
    default_value = "any" if default is None else Probe(default).value
    selected = _sidebar().radio(
        "Probe microphone",
        options=options,
        index=options.index(default_value),
        format_func=lambda value: labels[value],
        key=f"{key}_probe",
    )
    return None if selected == "any" else Probe(selected)


def subjects_widget(key: str, dataset: AcousticDataset | None = None) -> list[int]:
    """Multi-select of subject indices (default: all available)."""
    subjects = (
        [int(value) for value in dataset.subjects]
        if dataset is not None
        else list(range(1, 15))
    )
    return _sidebar().multiselect(
        "Subjects",
        options=subjects,
        default=subjects,
        key=f"{key}_subjects",
        help="Subject is the independent statistical unit; reinsertions are technical repeats.",
    )


def reinsertion_widget(key: str, dataset: AcousticDataset | None = None) -> list[int]:
    """Multi-select of reinsertion indices."""
    reinsertions = (
        [int(value) for value in dataset.reinsertions]
        if dataset is not None
        else [1, 2, 3]
    )
    return _sidebar().multiselect(
        "Reinsertions",
        options=reinsertions,
        default=reinsertions,
        key=f"{key}_reinsertions",
    )


def device_widget(key: str, devices: Sequence[DeviceSpec]) -> list[int]:
    """Multi-select of device codes with human-readable labels."""
    options = list(devices)
    if not options:
        return []
    labels = {device.code: f"{device.code:>2d} \u00b7 {device.short_label}" for device in options}
    selected = _sidebar().multiselect(
        "Device codes",
        options=[device.code for device in options],
        default=[device.code for device in options],
        format_func=lambda code: labels.get(code, str(code)),
        key=f"{key}_devices",
    )
    return selected


def band_set_widget(key: str) -> tuple[Band, ...]:
    """Band-set selector (octave / third-octave)."""
    method = _sidebar().radio(
        "Frequency bands",
        options=["octave", "third_octave"],
        index=0,
        format_func=lambda value: "Octave bands" if value == "octave" else "One-third-octave bands",
        key=f"{key}_band_method",
    )
    return octave_bands() if method == "octave" else third_octave_bands()


def valid_devices(dataset: AcousticDataset, key: str) -> list[DeviceSpec]:
    """Devices that are structurally valid for a container (helper for pages)."""
    valid_codes = {
        device.code for device in DEVICES if dataset.spec(key).structural_valid(device)
    }
    return [device for device in DEVICES if device.code in valid_codes]
