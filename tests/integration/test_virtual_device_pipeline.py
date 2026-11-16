"""Integration test of the virtual hearing-aid signal chain.

Data-free: builds deterministic synthetic signals, runs them through the
virtual device (gain → sensor noise → multiband compression → fault chain →
output limiter) and verifies that the known ground truth of the chain is
recovered by the DSP estimators.
"""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.metrics import estimate_gain_db, estimate_thd
from acousticbench.dsp.signals import pink_noise, rms, sine, white_noise
from acousticbench.virtual_ha import (
    FAULT_TYPES,
    CompressorConfig,
    FaultInjectionConfig,
    NoiseInjectionConfig,
    VirtualHearingAid,
    VirtualHearingAidConfig,
    add_sensor_noise,
    inject_fault,
    sensor_noise,
)

pytestmark = pytest.mark.integration

FS = 48000.0


def test_sensor_noise_levels_and_validation():
    for color in ("white", "pink"):
        noise = sensor_noise(48000, -40.0, seed=3, color=color)
        assert noise.size == 48000
        assert np.all(np.isfinite(noise))
        assert 20 * np.log10(rms(noise)) == pytest.approx(-40.0, abs=0.5)
    with pytest.raises(ValueError, match="color must be one of"):
        sensor_noise(48000, -40.0, color="brown")

    # Noise added by SNR recovers the requested SNR.
    signal = sine(1000.0, fs=FS, duration_s=1.0, amplitude=0.1)
    noisy = add_sensor_noise(signal, snr_db=20.0, seed=11)
    measured_snr = 20 * np.log10(rms(signal) / rms(noisy - signal))
    assert measured_snr == pytest.approx(20.0, abs=1.0)
    # Absolute level variant.
    noisy_level = add_sensor_noise(signal, level_dbfs=-50.0, seed=11)
    assert 20 * np.log10(rms(noisy_level - signal)) == pytest.approx(-50.0, abs=0.5)
    # Exactly one of the two arguments is required.
    with pytest.raises(ValueError, match="exactly one"):
        add_sensor_noise(signal)
    with pytest.raises(ValueError, match="exactly one"):
        add_sensor_noise(signal, snr_db=10.0, level_dbfs=-40.0)
    with pytest.raises(ValueError, match="silent"):
        add_sensor_noise(np.zeros(1000), snr_db=10.0)
    with pytest.raises(ValueError, match="color must be one of"):
        add_sensor_noise(signal, level_dbfs=-40.0, color="brown")
    assert np.isfinite(pink_noise(1000, seed=0)).all()
    assert np.isfinite(white_noise(1000, seed=0)).all()


def test_virtual_device_gain_noise_and_compression():
    signal = sine(1000.0, fs=FS, duration_s=0.5, amplitude=0.05)
    device = VirtualHearingAid(VirtualHearingAidConfig(input_gain_db=6.0))
    output = device.process(signal, FS)
    assert output.shape == signal.shape
    assert np.all(np.isfinite(output))
    estimate = estimate_gain_db(signal, output, FS, tone_hz=1000.0)
    assert estimate.gain_db == pytest.approx(6.0, abs=0.1)

    # Noise injection is reported in the detailed result.
    noisy_config = VirtualHearingAidConfig(
        input_gain_db=0.0,
        noise=NoiseInjectionConfig(level_dbfs=-60.0, color="white"),
    )
    detailed = VirtualHearingAid(noisy_config).process_detailed(signal, FS, seed=5)
    assert detailed.noise is not None
    assert np.allclose(detailed.noisy_input, signal + detailed.noise)
    assert detailed.fault_results == ()
    assert detailed.output.shape == signal.shape

    # A multiband compressor changes the level of a loud tone.
    compression = CompressorConfig(
        threshold_dbfs=-40.0, ratio=4.0, attack_s=0.005, release_s=0.05,
        knee_db=3.0, makeup_db=0.0,
    )
    compressed_config = VirtualHearingAidConfig(
        crossovers_hz=(1000.0,), compressor_configs=(compression, compression)
    )
    compressed = VirtualHearingAid(compressed_config).process(signal, FS)
    assert np.all(np.isfinite(compressed))
    assert rms(compressed) < rms(signal) * 10 ** (0.0 / 20.0)


def test_fault_chain_ground_truth():
    signal = sine(1000.0, fs=FS, duration_s=0.5, amplitude=0.2)
    for fault_type in FAULT_TYPES:
        parameters = {
            "clipping": {"clip_level": 0.1},
            "dropout": {"start_s": 0.1, "stop_s": 0.2},
            "dc_offset": {"offset": 0.05},
            "gain_error": {"gain_db": -6.0},
            "harmonic_distortion": {"percentage": 2.0, "tone_hz": 1000.0},
            "latency": {"delay_ms": 1.0},
        }[fault_type]
        result = inject_fault(signal, FS, fault_type, **parameters)
        assert result.fault_type == fault_type
        assert result.output.shape == signal.shape
        assert np.all(np.isfinite(result.output))
        assert result.true_params
        assert result.description
        assert result.fs == FS

    with pytest.raises(ValueError, match="unknown fault"):
        inject_fault(signal, FS, "banana")
    with pytest.raises(ValueError):
        inject_fault(signal, FS, "gain_error")  # required parameter missing

    # End-to-end: known THD fault is recovered by the estimator.
    distorted = inject_fault(
        signal, FS, "harmonic_distortion", percentage=3.0, tone_hz=1000.0
    )
    n_harmonics = len(distorted.true_params["harmonic_frequencies_hz"])
    estimate = estimate_thd(distorted.output, FS, 1000.0, n_harmonics=n_harmonics)
    assert estimate.thd_percent == pytest.approx(3.0, rel=0.05)

    # A full device fault chain preserves length and records every fault.
    config = VirtualHearingAidConfig(
        input_gain_db=3.0,
        output_limit_dbfs=-1.0,
        faults=(
            FaultInjectionConfig("gain_error", {"gain_db": -3.0}),
            FaultInjectionConfig("latency", {"delay_ms": 1.0}),
        ),
    )
    detailed = VirtualHearingAid(config).process_detailed(signal, FS)
    assert len(detailed.fault_results) == 2
    assert detailed.output.shape == signal.shape
    assert np.max(np.abs(detailed.output)) <= 10 ** (-1.0 / 20.0) + 1e-12
    assert np.all(np.isfinite(detailed.output))
