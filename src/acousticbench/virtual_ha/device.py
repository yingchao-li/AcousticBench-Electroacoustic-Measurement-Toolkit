"""Deterministic virtual hearing aid built from the DSP building blocks.

Signal chain (in order)::

    input gain  →  additive input noise  →  multiband compression
                →  fault chain  →  output limiter

The device is deterministic: for a fixed configuration and ``seed`` the output
is bit-for-bit reproducible.  ``seed=None`` uses a fixed internal seed (``0``),
so even noise injection is deterministic by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from acousticbench.dsp._validation import ArrayLike, as_float64_signal, validate_fs
from acousticbench.logging_utils import get_logger
from acousticbench.virtual_ha.compressor import CompressorConfig, MultibandCompressor
from acousticbench.virtual_ha.faults import FaultResult, inject_fault
from acousticbench.virtual_ha.noise import NOISE_COLORS, sensor_noise

__all__ = [
    "FaultInjectionConfig",
    "NoiseInjectionConfig",
    "VirtualHearingAid",
    "VirtualHearingAidConfig",
    "VirtualHearingAidResult",
]

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NoiseInjectionConfig:
    """Additive sensor noise at the device input.

    Attributes
    ----------
    level_dbfs:
        RMS level of the injected noise in dBFS.
    color:
        ``"white"`` or ``"pink"``.
    """

    level_dbfs: float = -80.0
    color: str = "white"

    def __post_init__(self) -> None:
        if not np.isfinite(float(self.level_dbfs)):
            raise ValueError(f"noise level_dbfs must be finite, got {self.level_dbfs!r}")
        if self.color not in NOISE_COLORS:
            raise ValueError(f"noise color must be one of {NOISE_COLORS}, got {self.color!r}")


@dataclass(frozen=True, slots=True)
class FaultInjectionConfig:
    """One entry of the fault chain.

    Attributes
    ----------
    fault_type:
        Fault name accepted by :func:`~acousticbench.virtual_ha.faults.inject_fault`.
    parameters:
        Fault-specific parameters.
    """

    fault_type: str
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from acousticbench.virtual_ha.faults import FAULT_TYPES

        if self.fault_type not in FAULT_TYPES:
            raise ValueError(
                f"unknown fault_type {self.fault_type!r}; expected one of {FAULT_TYPES}"
            )
        if not isinstance(self.parameters, Mapping):
            raise TypeError("parameters must be a mapping")


@dataclass(frozen=True, slots=True)
class VirtualHearingAidConfig:
    """Configuration of the virtual hearing aid.

    Attributes
    ----------
    input_gain_db:
        Linear input gain in dB applied before the compressor.
    crossovers_hz:
        Crossover frequencies of the multiband compressor (ascending).  Empty
        for a single full-band compressor (when ``compressor_configs`` is set)
        or for a compressor bypass (when it is empty).
    compressor_configs:
        One :class:`CompressorConfig` per band (``len(crossovers_hz) + 1``).
        Empty disables compression entirely.
    output_limit_dbfs:
        Hard output limiter level in dBFS (``None`` disables the limiter).
    noise:
        Optional additive input noise.
    faults:
        Fault chain applied after compression (in order).
    """

    input_gain_db: float = 0.0
    crossovers_hz: tuple[float, ...] = ()
    compressor_configs: tuple[CompressorConfig, ...] = ()
    output_limit_dbfs: float | None = None
    noise: NoiseInjectionConfig | None = None
    faults: tuple[FaultInjectionConfig, ...] = ()

    def __post_init__(self) -> None:
        if not np.isfinite(float(self.input_gain_db)):
            raise ValueError(f"input_gain_db must be finite, got {self.input_gain_db!r}")
        crossovers = tuple(float(value) for value in self.crossovers_hz)
        if any(not np.isfinite(value) or value <= 0.0 for value in crossovers):
            raise ValueError("crossovers_hz must be finite and > 0")
        if any(later <= earlier for earlier, later in zip(crossovers, crossovers[1:])):
            raise ValueError("crossovers_hz must be strictly increasing")
        configs = tuple(self.compressor_configs)
        for config in configs:
            if not isinstance(config, CompressorConfig):
                raise TypeError(
                    "compressor_configs must contain CompressorConfig instances, "
                    f"got {type(config).__name__}"
                )
        if configs and len(configs) != len(crossovers) + 1:
            raise ValueError(
                f"expected {len(crossovers) + 1} compressor configs for "
                f"{len(crossovers)} crossovers, got {len(configs)}"
            )
        if self.output_limit_dbfs is not None and not np.isfinite(float(self.output_limit_dbfs)):
            raise ValueError(f"output_limit_dbfs must be finite or None, got {self.output_limit_dbfs!r}")
        if self.noise is not None and not isinstance(self.noise, NoiseInjectionConfig):
            raise TypeError("noise must be a NoiseInjectionConfig or None")
        faults = tuple(self.faults)
        for fault in faults:
            if not isinstance(fault, FaultInjectionConfig):
                raise TypeError(
                    "faults must contain FaultInjectionConfig instances, "
                    f"got {type(fault).__name__}"
                )

    @property
    def compressors(self) -> tuple[CompressorConfig, ...]:
        """Alias of :attr:`compressor_configs`."""
        return self.compressor_configs

    @property
    def compression_enabled(self) -> bool:
        """Whether the multiband compressor is active."""
        return len(self.compressor_configs) > 0


@dataclass(frozen=True, slots=True)
class VirtualHearingAidResult:
    """Detailed result of :meth:`VirtualHearingAid.process_detailed`.

    Attributes
    ----------
    output:
        Final processed signal.
    noisy_input:
        Signal after input gain and optional additive noise (before
        compression).
    noise:
        The injected noise waveform, or ``None``.
    fault_results:
        One :class:`FaultResult` per injected fault, in chain order.
    """

    output: np.ndarray
    noisy_input: np.ndarray
    noise: np.ndarray | None
    fault_results: tuple[FaultResult, ...]


class VirtualHearingAid:
    """A deterministic virtual hearing aid.

    Parameters
    ----------
    config:
        Device configuration.

    Examples
    --------
    >>> from acousticbench.dsp.signals import sine
    >>> device = VirtualHearingAid(VirtualHearingAidConfig(input_gain_db=6.0))
    >>> y = device.process(sine(1000.0, 48000.0, 0.1), 48000.0)
    >>> y.shape
    (4800,)
    """

    def __init__(self, config: VirtualHearingAidConfig) -> None:
        if not isinstance(config, VirtualHearingAidConfig):
            raise TypeError(
                f"config must be a VirtualHearingAidConfig, got {type(config).__name__}"
            )
        self._config = config
        self._compressors: dict[float, MultibandCompressor] = {}

    @property
    def config(self) -> VirtualHearingAidConfig:
        """The device configuration."""
        return self._config

    def _compressor_for(self, fs: float) -> MultibandCompressor:
        """Return (and cache) the multiband compressor for a sampling rate."""
        if fs not in self._compressors:
            self._compressors[fs] = MultibandCompressor(
                self._config.crossovers_hz, self._config.compressor_configs, fs
            )
        return self._compressors[fs]

    def _run(self, signal: ArrayLike, fs: float, seed: int | None) -> VirtualHearingAidResult:
        """Execute the full signal chain and return all intermediate results."""
        data = as_float64_signal(signal)
        rate = validate_fs(fs)
        config = self._config
        deterministic_seed = 0 if seed is None else int(seed)

        stage = data * 10.0 ** (float(config.input_gain_db) / 20.0)
        noise: np.ndarray | None = None
        if config.noise is not None:
            noise = sensor_noise(
                data.size,
                level_dbfs=config.noise.level_dbfs,
                seed=deterministic_seed,
                color=config.noise.color,
            )
            stage = stage + noise
        noisy_input = np.asarray(stage, dtype=np.float64)

        if config.compression_enabled:
            stage = self._compressor_for(rate).process(stage)

        fault_results: list[FaultResult] = []
        for fault in config.faults:
            result = inject_fault(stage, rate, fault.fault_type, **dict(fault.parameters))
            stage = result.output
            fault_results.append(result)

        if config.output_limit_dbfs is not None:
            limit = 10.0 ** (float(config.output_limit_dbfs) / 20.0)
            stage = np.clip(stage, -limit, limit)

        logger.debug(
            "VirtualHearingAid: n=%d fs=%g compression=%s faults=%d",
            data.size,
            rate,
            config.compression_enabled,
            len(fault_results),
        )
        return VirtualHearingAidResult(
            output=np.asarray(stage, dtype=np.float64),
            noisy_input=noisy_input,
            noise=noise,
            fault_results=tuple(fault_results),
        )

    def process(self, signal: ArrayLike, fs: float, seed: int | None = None) -> np.ndarray:
        """Process a mono signal through the virtual device.

        Parameters
        ----------
        signal:
            Real one-dimensional input signal.
        fs:
            Sampling rate in Hz.
        seed:
            Seed for the deterministic noise generator (``None`` uses the
            fixed default seed ``0``).

        Returns
        -------
        numpy.ndarray
            Processed ``float64`` signal of the same length.

        Raises
        ------
        ValueError
            If the signal or sampling rate is invalid.
        """
        return self._run(signal, fs, seed).output

    def process_detailed(
        self,
        signal: ArrayLike,
        fs: float,
        seed: int | None = None,
    ) -> VirtualHearingAidResult:
        """Like :meth:`process` but also return injected noise and faults."""
        return self._run(signal, fs, seed)
