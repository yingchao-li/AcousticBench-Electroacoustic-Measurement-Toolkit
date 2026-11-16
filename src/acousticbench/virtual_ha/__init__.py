"""A virtual hearing aid: multiband compression, noise and fault injection.

The package provides a deterministic signal-processing surrogate for a
hearing-aid fitting, so that measurement and validation algorithms can be
tested against known ground truth:

``compressor``
    Feed-forward multiband compressor with Linkwitz-Riley crossovers.
``noise``
    White/pink sensor-noise helpers.
``faults``
    Six deterministic fault types with reported true parameters.
``device``
    The complete virtual device (gain → noise → compression → faults →
    output limiter).
"""

from __future__ import annotations

from acousticbench.virtual_ha.compressor import CompressorConfig, MultibandCompressor
from acousticbench.virtual_ha.device import (
    FaultInjectionConfig,
    NoiseInjectionConfig,
    VirtualHearingAid,
    VirtualHearingAidConfig,
    VirtualHearingAidResult,
)
from acousticbench.virtual_ha.faults import FAULT_TYPES, FaultResult, inject_fault
from acousticbench.virtual_ha.noise import NOISE_COLORS, add_sensor_noise, sensor_noise

__all__ = [
    # compressor
    "CompressorConfig",
    "MultibandCompressor",
    # noise
    "NOISE_COLORS",
    "add_sensor_noise",
    "sensor_noise",
    # faults
    "FAULT_TYPES",
    "FaultResult",
    "inject_fault",
    # device
    "FaultInjectionConfig",
    "NoiseInjectionConfig",
    "VirtualHearingAid",
    "VirtualHearingAidConfig",
    "VirtualHearingAidResult",
]
