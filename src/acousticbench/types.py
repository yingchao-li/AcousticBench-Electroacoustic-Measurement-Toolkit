"""Immutable domain metadata for the AcousticBench dataset.

The dataset published by Denk, Hackenberg & Husstedt (2026) contains
frequency-domain measurements on 14 ears, 7 earpiece designs, 2 probe
conditions and 3 reinsertions.  This module encodes the metadata once so that
every other module (data loading, measurement functions, statistics,
dashboard, reports) uses the *same* labels and the *same* validity rules.

Datasets and dimensions
-----------------------
Dim 1
    Frequency axis.  Transfer functions use ``v_frq`` (2049 DFT bins,
    0 … 22 050 Hz, Δf = 10.7666 Hz, i.e. the non-negative half of a
    4096-point DFT at 44.1 kHz).  Thresholds use ``v_fAud`` (125, 250, 500,
    750, 1000, 2000 Hz).
Dim 2
    Device code 1 … 14 = 7 earpiece families × {reference, measurement}
    probe condition (see :data:`DEVICES`).
Dim 3
    Subject index 1 … 14.
Dim 4
    Reinsertion index 1 … 3.

Validity semantics
------------------
Two distinct kinds of "no usable data" exist and must **never** be conflated:

1. **Measured NaN** – values flagged as erroneous by the data provider.
   Exactly 18 complete (device, subject, reinsertion) sessions are NaN in the
   five 4-D transfer-function containers, and 19 in ``M_thr_ha``.
2. **Structural invalid** – values that exist but are documented to be
   physically meaningless for the intended quantity.  Example: in the
   *reference* probe condition the measurement probe tube was hanging loosely
   around the ear, therefore ``M_ha2edM`` / ``M_ls2edM`` in the reference
   condition are free-field-ish signals, not eardrum pressures.  Likewise the
   reference probe tube was used only with earmolds, so ``M_ha2edR`` /
   ``M_ls2edR`` are meaningless for dome conditions.

AcousticBench encodes both in :class:`ContainerSpec` and in the validity masks
of :class:`acousticbench.data.dataset.TransferCube`; it never imputes values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final


class Condition(str, Enum):
    """Probe condition of a measurement.

    ``REFERENCE``
        Only the reference probe tube microphone in place (earmolds); no probe
        tube at all for domes.
    ``MEASUREMENT``
        The measurement probe tube microphone is additionally inserted between
        earpiece and ear canal wall (clinical placement).
    """

    REFERENCE = "reference"
    MEASUREMENT = "measurement"

    @property
    def label(self) -> str:
        return "Reference" if self is Condition.REFERENCE else "Measurement"

    @property
    def short(self) -> str:
        return "Ref" if self is Condition.REFERENCE else "Meas"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Coupling(str, Enum):
    """Coupling style of the earpiece."""

    EARMOLD = "earmold"
    DOME = "dome"
    OPEN = "open"

    @property
    def label(self) -> str:
        return {"earmold": "Earmold", "dome": "Dome", "open": "Open ear"}[self.value]


class Probe(str, Enum):
    """Probe tube microphone used to measure the eardrum pressure."""

    MEASUREMENT = "measurement"
    REFERENCE = "reference"

    @property
    def label(self) -> str:
        return "Measurement probe" if self is Probe.MEASUREMENT else "Reference probe"

    @property
    def short(self) -> str:
        return "MPT" if self is Probe.MEASUREMENT else "RPT"


class Source(str, Enum):
    """Acoustic source of a transfer function measurement."""

    HEARING_AID_DRIVER = "hearing_aid_driver"
    LOUDSPEAKER = "loudspeaker"

    @property
    def label(self) -> str:
        return "Hearing-aid driver" if self is Source.HEARING_AID_DRIVER else "Loudspeaker"


class Quantity(str, Enum):
    """Physical quantity represented by a data container."""

    EARDRUM_PRESSURE = "eardrum_pressure"
    HA_MICROPHONE_PRESSURE = "ha_microphone_pressure"
    THRESHOLD = "threshold"


@dataclass(frozen=True, slots=True)
class DeviceSpec:
    """Metadata for one of the 14 device/condition codes (or a derived axis).

    Parameters
    ----------
    code:
        Dataset device-code (1 … 14).  Synthetic axis entries use 0 or -1.
    family:
        Machine-readable earpiece family, e.g. ``"closed_earmold"``.
    family_label:
        Human-readable family, e.g. ``"Closed Earmold"``.
    coupling:
        Coupling style (:class:`Coupling`).
    condition:
        Probe condition, or ``None`` for derived/open-ear entries.
    label:
        Full label, e.g. ``"Closed Earmold · Measurement"``.
    short_label:
        Compact plot label, e.g. ``"Closed/Meas"``.
    """

    code: int
    family: str
    family_label: str
    coupling: Coupling
    condition: Condition | None
    label: str
    short_label: str

    @property
    def is_earmold(self) -> bool:
        return self.coupling is Coupling.EARMOLD

    @property
    def is_dome(self) -> bool:
        return self.coupling is Coupling.DOME

    @property
    def condition_label(self) -> str:
        return self.condition.label if self.condition is not None else "—"


def _make_device(code: int, family: str, family_label: str, coupling: Coupling) -> DeviceSpec:
    condition = Condition.REFERENCE if code % 2 == 1 else Condition.MEASUREMENT
    short_family = {
        "closed_earmold": "Closed",
        "vented_earmold": "Vented",
        "nugget_earmold": "Nugget",
        "silicone_earmold": "Silicone",
        "open_dome": "Open",
        "tulip_dome": "Tulip",
        "power_dome": "Power",
    }[family]
    return DeviceSpec(
        code=code,
        family=family,
        family_label=family_label,
        coupling=coupling,
        condition=condition,
        label=f"{family_label} · {condition.label}",
        short_label=f"{short_family}/{condition.short}",
    )


#: The 14 measurement device codes, in dataset order (Dim 2 = 1 … 14).
DEVICES: Final[tuple[DeviceSpec, ...]] = (
    _make_device(1, "closed_earmold", "Closed Earmold", Coupling.EARMOLD),
    _make_device(2, "closed_earmold", "Closed Earmold", Coupling.EARMOLD),
    _make_device(3, "vented_earmold", "Vented Earmold", Coupling.EARMOLD),
    _make_device(4, "vented_earmold", "Vented Earmold", Coupling.EARMOLD),
    _make_device(5, "nugget_earmold", "Nugget Earmold", Coupling.EARMOLD),
    _make_device(6, "nugget_earmold", "Nugget Earmold", Coupling.EARMOLD),
    _make_device(7, "silicone_earmold", "Silicone Earmold", Coupling.EARMOLD),
    _make_device(8, "silicone_earmold", "Silicone Earmold", Coupling.EARMOLD),
    _make_device(9, "open_dome", "Open Dome", Coupling.DOME),
    _make_device(10, "open_dome", "Open Dome", Coupling.DOME),
    _make_device(11, "tulip_dome", "Tulip Dome", Coupling.DOME),
    _make_device(12, "tulip_dome", "Tulip Dome", Coupling.DOME),
    _make_device(13, "power_dome", "Power Dome", Coupling.DOME),
    _make_device(14, "power_dome", "Power Dome", Coupling.DOME),
)

#: Device families in display order: (family, family_label, coupling).
FAMILIES: Final[tuple[tuple[str, str, Coupling], ...]] = (
    ("closed_earmold", "Closed Earmold", Coupling.EARMOLD),
    ("vented_earmold", "Vented Earmold", Coupling.EARMOLD),
    ("nugget_earmold", "Nugget Earmold", Coupling.EARMOLD),
    ("silicone_earmold", "Silicone Earmold", Coupling.EARMOLD),
    ("open_dome", "Open Dome", Coupling.DOME),
    ("tulip_dome", "Tulip Dome", Coupling.DOME),
    ("power_dome", "Power Dome", Coupling.DOME),
)

#: Derived device entry for the unaided (open-ear) real-ear response.
DEVICE_OPEN_EAR: Final[DeviceSpec] = DeviceSpec(
    code=0,
    family="open_ear",
    family_label="Open Ear",
    coupling=Coupling.OPEN,
    condition=None,
    label="Open Ear · Unaided",
    short_label="Open ear",
)

#: Derived device entry for the in-situ free-field estimate.
DEVICE_FREE_FIELD: Final[DeviceSpec] = DeviceSpec(
    code=-1,
    family="free_field",
    family_label="In-situ Free Field",
    coupling=Coupling.OPEN,
    condition=None,
    label="In-situ Free Field",
    short_label="Free field",
)

#: All device specs, including the two derived entries.
ALL_DEVICES: Final[tuple[DeviceSpec, ...]] = (DEVICE_FREE_FIELD, DEVICE_OPEN_EAR, *DEVICES)

DEVICE_BY_CODE: Final[dict[int, DeviceSpec]] = {d.code: d for d in ALL_DEVICES}

#: Earmold device codes (the only codes with reference-probe eardrum data).
EARMOLD_DEVICE_CODES: Final[tuple[int, ...]] = tuple(d.code for d in DEVICES if d.is_earmold)
#: Dome device codes.
DOME_DEVICE_CODES: Final[tuple[int, ...]] = tuple(d.code for d in DEVICES if d.is_dome)
#: Reference-condition device codes (MPT loose → free-field proxy).
REFERENCE_DEVICE_CODES: Final[tuple[int, ...]] = tuple(
    d.code for d in DEVICES if d.condition is Condition.REFERENCE
)
#: Measurement-condition device codes.
MEASUREMENT_DEVICE_CODES: Final[tuple[int, ...]] = tuple(
    d.code for d in DEVICES if d.condition is Condition.MEASUREMENT
)


@dataclass(frozen=True, slots=True)
class ContainerSpec:
    """Metadata and validity rules for one MAT-file container.

    Attributes
    ----------
    key:
        MAT variable name, e.g. ``"M_ha2edR"``.
    description:
        Human-readable description.
    source:
        Acoustic source used for the measurement.
    probe:
        Probe microphone used to measure eardrum pressure (``None`` for the
        hearing-aid microphone container).
    quantity:
        Physical quantity stored in the container.
    unit:
        Storage unit of the complex values.
    unit_label:
        Short unit label used in plots/tables.
    valid_conditions:
        Probe conditions in which the quantity is physically meaningful, or
        ``None`` for all conditions.
    valid_couplings:
        Coupling styles for which the quantity is meaningful, or ``None`` for
        all couplings.
    rationale:
        Why the structural validity rule exists (traceable to the
        documentation / preprint).
    axis:
        ``"frequency"`` for transfer functions, ``"threshold"`` for audiograms.
    """

    key: str
    description: str
    source: Source
    probe: Probe | None
    quantity: Quantity
    unit: str
    unit_label: str
    valid_conditions: frozenset[Condition] | None
    valid_couplings: frozenset[Coupling] | None
    rationale: str
    axis: str = "frequency"
    is_reur: bool = False

    def structural_valid(self, device: DeviceSpec) -> bool:
        """Return ``True`` if ``device`` can physically support this quantity."""
        if self.valid_conditions is not None and device.condition not in self.valid_conditions:
            return False
        return not (
            self.valid_couplings is not None and device.coupling not in self.valid_couplings
        )


#: Transfer-function containers available in the dataset.
CONTAINERS: Final[dict[str, ContainerSpec]] = {
    "M_ha2edM": ContainerSpec(
        key="M_ha2edM",
        description="Hearing-aid driver response at the eardrum, measurement probe tube",
        source=Source.HEARING_AID_DRIVER,
        probe=Probe.MEASUREMENT,
        quantity=Quantity.EARDRUM_PRESSURE,
        unit="Pa at 11.2 mV drive",
        unit_label="Pa @ 11.2 mV",
        valid_conditions=frozenset({Condition.MEASUREMENT}),
        valid_couplings=None,
        rationale=(
            "In the reference condition the measurement probe tube microphone "
            "was hanging loosely around the ear (Documentation.pdf); its signal "
            "is not an eardrum pressure, although it is stored as a number."
        ),
    ),
    "M_ha2edR": ContainerSpec(
        key="M_ha2edR",
        description="Hearing-aid driver response at the eardrum, reference probe tube",
        source=Source.HEARING_AID_DRIVER,
        probe=Probe.REFERENCE,
        quantity=Quantity.EARDRUM_PRESSURE,
        unit="Pa at 11.2 mV drive",
        unit_label="Pa @ 11.2 mV",
        valid_conditions=None,
        valid_couplings=frozenset({Coupling.EARMOLD}),
        rationale=(
            "The reference probe tube was inserted through a dedicated bore in "
            "the earmold and used only for earmold measurements; for domes no "
            "reference-probe eardrum pressure exists."
        ),
    ),
    "M_ha2haf": ContainerSpec(
        key="M_ha2haf",
        description="Hearing-aid driver response at the hearing-aid microphone (feedback path)",
        source=Source.HEARING_AID_DRIVER,
        probe=None,
        quantity=Quantity.HA_MICROPHONE_PRESSURE,
        unit="Pa at 11.2 mV drive",
        unit_label="Pa @ 11.2 mV",
        valid_conditions=None,
        valid_couplings=None,
        rationale="The hearing-aid microphone is part of the device and always present.",
    ),
    "M_ls2edM": ContainerSpec(
        key="M_ls2edM",
        description="Loudspeaker response at the eardrum, measurement probe tube",
        source=Source.LOUDSPEAKER,
        probe=Probe.MEASUREMENT,
        quantity=Quantity.EARDRUM_PRESSURE,
        unit="Pa at free-field reference",
        unit_label="Pa (free field)",
        valid_conditions=frozenset({Condition.MEASUREMENT}),
        valid_couplings=None,
        rationale=(
            "In the reference condition the measurement probe tube was hanging "
            "loosely around the ear; the stored loudspeaker response then "
            "measures the free field, not the eardrum."
        ),
    ),
    "M_ls2edR": ContainerSpec(
        key="M_ls2edR",
        description="Loudspeaker response at the eardrum, reference probe tube",
        source=Source.LOUDSPEAKER,
        probe=Probe.REFERENCE,
        quantity=Quantity.EARDRUM_PRESSURE,
        unit="Pa at free-field reference",
        unit_label="Pa (free field)",
        valid_conditions=None,
        valid_couplings=frozenset({Coupling.EARMOLD}),
        rationale=(
            "The reference probe tube was available for earmolds only; dome "
            "conditions store the loosely hanging reference microphone instead."
        ),
    ),
    "M_thr_ha": ContainerSpec(
        key="M_thr_ha",
        description="Hearing threshold measured with the hearing-aid driver",
        source=Source.HEARING_AID_DRIVER,
        probe=None,
        quantity=Quantity.THRESHOLD,
        unit="dBV",
        unit_label="dBV",
        valid_conditions=None,
        valid_couplings=None,
        rationale="Thresholds are behavioural and exist for all earpieces/conditions.",
    ),
    "M_REUR": ContainerSpec(
        key="M_REUR",
        description="Real-ear unaided response (open ear, one insertion per participant)",
        source=Source.LOUDSPEAKER,
        probe=Probe.MEASUREMENT,
        quantity=Quantity.EARDRUM_PRESSURE,
        unit="Pa at free-field reference",
        unit_label="Pa (free field)",
        valid_conditions=None,
        valid_couplings=None,
        rationale=(
            "Measured in the open ear with the measurement probe in place and "
            "one insertion per participant; used as the unaided (open-ear) "
            "reference of the real-ear occluded insertion gain."
        ),
        is_reur=True,
    ),
}

#: Containers with four dimensions (frequency × device × subject × reinsertion).
TRANSFER_CONTAINER_KEYS: Final[tuple[str, ...]] = (
    "M_ha2edM",
    "M_ha2edR",
    "M_ha2haf",
    "M_ls2edM",
    "M_ls2edR",
)

#: Threshold container key.
THRESHOLD_CONTAINER_KEY: Final[str] = "M_thr_ha"
#: Real-ear unaided response container key.
REUR_CONTAINER_KEY: Final[str] = "M_REUR"

#: Container keys in canonical presentation order.
CONTAINER_ORDER: Final[tuple[str, ...]] = (
    "M_ha2edM",
    "M_ha2edR",
    "M_ha2haf",
    "M_ls2edM",
    "M_ls2edR",
    "M_thr_ha",
    "M_REUR",
)

#: Physical constants used for unit conversions.
P_REF_PA: Final[float] = 20e-6  # 20 µPa (0 dB SPL)
U_HA_DRIVE_V: Final[float] = 11.2e-3  # 11.2 mV receiver drive voltage
DB_SPL_OFFSET_FROM_PA: Final[float] = 20.0 * math.log10(1.0 / P_REF_PA)  # 93.9794
#: Ideal frequency resolution of the transfer-function grid (44.1 kHz / 4096).
FREQUENCY_RESOLUTION_HZ: Final[float] = 22050.0 / 2048.0
#: Nyquist frequency of the DFT grid.
NYQUIST_HZ: Final[float] = 22050.0
#: Number of frequency bins in transfer-function containers (incl. DC).
N_FREQUENCIES: Final[int] = 2049
#: Number of audiometric frequencies in the threshold container.
N_THRESHOLD_FREQUENCIES: Final[int] = 6
#: Number of subjects.
N_SUBJECTS: Final[int] = 14
#: Number of reinsertions.
N_REINSERTIONS: Final[int] = 3


def device(code: int) -> DeviceSpec:
    """Return the :class:`DeviceSpec` for a device code (0 and -1 included)."""
    try:
        return DEVICE_BY_CODE[code]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown device code {code!r}; expected 0, -1 or 1…14") from exc


def devices_for(
    *,
    conditions: tuple[Condition, ...] | list[Condition] | None = None,
    families: tuple[str, ...] | list[str] | None = None,
    couplings: tuple[Coupling, ...] | list[Coupling] | None = None,
    codes: tuple[int, ...] | list[int] | None = None,
) -> tuple[DeviceSpec, ...]:
    """Filter the 14 device definitions.

    Parameters are combined with logical AND.  ``None`` means "no filter".
    """
    selected = list(DEVICES)
    if conditions is not None:
        wanted = {Condition(c) for c in conditions}
        selected = [d for d in selected if d.condition in wanted]
    if families is not None:
        wanted_f = set(families)
        selected = [d for d in selected if d.family in wanted_f]
    if couplings is not None:
        wanted_c = {Coupling(c) for c in couplings}
        selected = [d for d in selected if d.coupling in wanted_c]
    if codes is not None:
        wanted_codes = set(codes)
        selected = [d for d in selected if d.code in wanted_codes]
    return tuple(selected)


def family_devices(family: str, condition: Condition | None = None) -> tuple[DeviceSpec, ...]:
    """Return the device codes of one earpiece family (optionally one condition)."""
    items = [d for d in DEVICES if d.family == family]
    if condition is not None:
        items = [d for d in items if d.condition is condition]
    return tuple(items)
