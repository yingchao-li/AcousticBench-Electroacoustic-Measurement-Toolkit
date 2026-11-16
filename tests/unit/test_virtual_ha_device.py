"""Unit tests for :mod:`acousticbench.virtual_ha.device`."""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.signals import rms, sine, white_noise
from acousticbench.virtual_ha.compressor import CompressorConfig
from acousticbench.virtual_ha.device import (
    FaultInjectionConfig,
    NoiseInjectionConfig,
    VirtualHearingAid,
    VirtualHearingAidConfig,
)

FS = 8000


def _tone(amplitude: float = 0.2) -> np.ndarray:
    return sine(1000.0, FS, 0.5, amplitude=amplitude)


def test_identity_device_passes_signal_through() -> None:
    device = VirtualHearingAid(VirtualHearingAidConfig())
    signal = _tone()
    np.testing.assert_array_equal(device.process(signal, FS), signal)


def test_input_gain_is_applied_exactly() -> None:
    device = VirtualHearingAid(VirtualHearingAidConfig(input_gain_db=6.0))
    signal = _tone()
    output = device.process(signal, FS)
    np.testing.assert_allclose(
        output, signal * 10.0 ** (6.0 / 20.0), atol=1e-15
    )


def test_output_limiter_clips_peak() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(input_gain_db=20.0, output_limit_dbfs=-6.0)
    )
    output = device.process(_tone(), FS)
    assert np.max(np.abs(output)) == pytest.approx(10.0 ** (-6.0 / 20.0), rel=1e-12)


def test_noise_is_additive_and_deterministic() -> None:
    noise_config = NoiseInjectionConfig(level_dbfs=-50.0, color="white")
    device = VirtualHearingAid(VirtualHearingAidConfig(noise=noise_config))
    signal = _tone()
    first = device.process(signal, FS, seed=7)
    second = device.process(signal, FS, seed=7)
    other = device.process(signal, FS, seed=8)
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, other)
    noise = first - signal
    assert rms(noise) == pytest.approx(10.0 ** (-50.0 / 20.0), rel=1e-10)


def test_noise_default_seed_is_deterministic() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(noise=NoiseInjectionConfig(level_dbfs=-50.0))
    )
    signal = _tone()
    np.testing.assert_array_equal(device.process(signal, FS), device.process(signal, FS))


def test_pink_noise_injection_is_supported() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(noise=NoiseInjectionConfig(level_dbfs=-60.0, color="pink"))
    )
    output = device.process(_tone(), FS, seed=1)
    assert np.all(np.isfinite(output))
    assert output.shape == (FS // 2,)


def test_compressor_engages_and_reduces_gain() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, attack_s=0.002, release_s=0.02, knee_db=0.0
    )
    device = VirtualHearingAid(
        VirtualHearingAidConfig(compressor_configs=(config,), crossovers_hz=())
    )
    signal = sine(1000.0, FS, 1.0, amplitude=0.3)  # -13.4 dBFS RMS, above threshold
    output = device.process(signal, FS)
    settled = int(0.25 * signal.size)
    gain_db = 20.0 * np.log10(rms(output[settled:]) / rms(signal[settled:]))
    assert gain_db < -3.0
    assert np.all(np.isfinite(output))


def test_fault_chain_is_applied_in_order() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(
            faults=(
                FaultInjectionConfig("gain_error", {"gain_db": 2.0}),
                FaultInjectionConfig("dc_offset", {"offset": 0.01}),
            )
        )
    )
    signal = _tone()
    output = device.process(signal, FS)
    expected = signal * 10.0 ** (2.0 / 20.0) + 0.01
    np.testing.assert_allclose(output, expected, atol=1e-15)


def test_process_detailed_reports_intermediates() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(
            noise=NoiseInjectionConfig(level_dbfs=-50.0),
            faults=(FaultInjectionConfig("latency", {"delay_ms": 1.0}),),
        )
    )
    signal = _tone()
    result = device.process_detailed(signal, FS, seed=3)
    assert result.noise is not None
    assert result.noise.shape == signal.shape
    assert len(result.fault_results) == 1
    assert result.fault_results[0].fault_type == "latency"
    assert result.output.shape == signal.shape


def test_process_detailed_without_noise_or_faults() -> None:
    device = VirtualHearingAid(VirtualHearingAidConfig())
    result = device.process_detailed(_tone(), FS)
    assert result.noise is None
    assert result.fault_results == ()
    np.testing.assert_array_equal(result.noisy_input, _tone())


def test_config_validation_errors() -> None:
    with pytest.raises(ValueError):
        VirtualHearingAidConfig(compressor_configs=(CompressorConfig(), CompressorConfig()))
    with pytest.raises(ValueError):
        VirtualHearingAidConfig(crossovers_hz=(500.0, 200.0), compressor_configs=(CompressorConfig(),) * 3)
    with pytest.raises(ValueError):
        NoiseInjectionConfig(color="brown")
    with pytest.raises(ValueError):
        FaultInjectionConfig("unknown_fault")
    with pytest.raises(ValueError):
        VirtualHearingAidConfig(output_limit_dbfs=float("inf"))
    with pytest.raises(TypeError):
        VirtualHearingAid("not a config")  # type: ignore[arg-type]


def test_white_noise_input_is_processed_finitely() -> None:
    device = VirtualHearingAid(
        VirtualHearingAidConfig(
            input_gain_db=3.0,
            crossovers_hz=(500.0,),
            compressor_configs=(
                CompressorConfig(threshold_dbfs=-30.0, ratio=3.0),
                CompressorConfig(threshold_dbfs=-30.0, ratio=3.0),
            ),
            output_limit_dbfs=-3.0,
        )
    )
    output = device.process(white_noise(4096, seed=2, level_dbfs=-20.0), FS)
    assert np.all(np.isfinite(output))
    assert np.max(np.abs(output)) <= 10.0 ** (-3.0 / 20.0) + 1e-12
