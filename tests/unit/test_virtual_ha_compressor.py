"""Unit tests for :mod:`acousticbench.virtual_ha.compressor`.

The static compression curve is checked analytically (below-knee, above-knee
slope ``1 - 1/ratio``, soft-knee continuity) and the dynamic behaviour is
verified against that static curve at steady state.
"""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.metrics import estimate_gain_db
from acousticbench.dsp.signals import rms, sine, white_noise
from acousticbench.virtual_ha.compressor import CompressorConfig, MultibandCompressor

FS = 8000


def test_static_curve_below_and_above_threshold() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, attack_s=0.005, release_s=0.05, knee_db=0.0
    )
    assert config.static_gain_db(-40.0) == pytest.approx(0.0, abs=1e-12)
    assert config.static_gain_db(-30.0) == pytest.approx(0.0, abs=1e-12)
    # 10 dB above threshold with ratio 3: reduction = 10 * (1 - 1/3).
    assert config.static_gain_db(-20.0) == pytest.approx(-10.0 * (1.0 - 1.0 / 3.0), abs=1e-12)
    assert config.static_gain_db(-10.0) == pytest.approx(-20.0 * (1.0 - 1.0 / 3.0), abs=1e-12)


def test_static_curve_slope_equals_one_minus_inverse_ratio() -> None:
    config = CompressorConfig(threshold_dbfs=-35.0, ratio=4.0, knee_db=0.0)
    gain_high = float(config.static_gain_db(-10.0))
    gain_higher = float(config.static_gain_db(0.0))
    assert gain_higher - gain_high == pytest.approx(-10.0 * (1.0 - 1.0 / 4.0), abs=1e-12)


def test_makeup_gain_offsets_curve() -> None:
    base = CompressorConfig(threshold_dbfs=-30.0, ratio=3.0, knee_db=0.0)
    with_makeup = CompressorConfig(threshold_dbfs=-30.0, ratio=3.0, knee_db=0.0, makeup_db=6.0)
    for level in (-40.0, -20.0, -5.0):
        assert with_makeup.static_gain_db(level) == pytest.approx(
            float(base.static_gain_db(level)) + 6.0, abs=1e-12
        )


def test_soft_knee_is_continuous() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, knee_db=8.0, attack_s=0.01, release_s=0.1
    )
    half_knee = 4.0
    below = float(config.static_gain_db(-30.0 - half_knee))
    at_edge = float(config.static_gain_db(-30.0 - half_knee + 1e-9))
    assert below == pytest.approx(0.0, abs=1e-12)
    assert at_edge == pytest.approx(below, abs=1e-6)
    upper_edge = float(config.static_gain_db(-30.0 + half_knee))
    upper_linear = float(config.static_gain_db(-30.0 + half_knee + 1e-9))
    assert upper_edge == pytest.approx(upper_linear, abs=1e-6)


def test_compressor_config_validation() -> None:
    with pytest.raises(ValueError):
        CompressorConfig(ratio=0.5)
    with pytest.raises(ValueError):
        CompressorConfig(attack_s=0.0)
    with pytest.raises(ValueError):
        CompressorConfig(release_s=-0.1)
    with pytest.raises(ValueError):
        CompressorConfig(knee_db=-1.0)
    with pytest.raises(ValueError):
        CompressorConfig(detector="envelope")
    with pytest.raises(ValueError):
        CompressorConfig(threshold_dbfs=float("nan"))


def test_transparent_multiband_compressor_reconstructs_input() -> None:
    config = CompressorConfig(threshold_dbfs=-30.0, ratio=1.0, attack_s=0.005, release_s=0.05)
    compressor = MultibandCompressor((500.0, 2000.0), (config, config, config), FS)
    signal = white_noise(4096, seed=3, level_dbfs=-20.0)
    output = compressor.process(signal)
    np.testing.assert_allclose(output, signal, atol=1e-10)


def test_transparent_single_band_compressor_reconstructs_input() -> None:
    config = CompressorConfig(threshold_dbfs=-30.0, ratio=1.0, makeup_db=0.0)
    compressor = MultibandCompressor((), (config,), FS)
    signal = sine(1000.0, FS, 0.5, amplitude=0.3)
    np.testing.assert_allclose(compressor.process(signal), signal, atol=1e-12)


def test_multiband_properties() -> None:
    config = CompressorConfig(threshold_dbfs=-35.0, ratio=3.0)
    compressor = MultibandCompressor((1000.0, 3000.0), (config, config, config), FS)
    assert compressor.n_bands == 3
    assert compressor.crossovers_hz == (1000.0, 3000.0)
    assert compressor.band_edges_hz == ((0.0, 1000.0), (1000.0, 3000.0), (3000.0, FS / 2.0))
    static_gains = compressor.static_gain_db(-10.0)
    assert len(static_gains) == 3
    assert static_gains[0] == pytest.approx(float(config.static_gain_db(-10.0)))


def test_multiband_validation() -> None:
    config = CompressorConfig()
    with pytest.raises(ValueError):
        MultibandCompressor((1000.0, 500.0), (config, config, config), FS)
    with pytest.raises(ValueError):
        MultibandCompressor((500.0,), (config,), FS)
    with pytest.raises(ValueError):
        MultibandCompressor((4000.0,), (config, config), FS)  # above Nyquist
    with pytest.raises(ValueError):
        MultibandCompressor((0.0,), (config, config), FS)
    with pytest.raises(TypeError):
        MultibandCompressor((), ("not a config",), FS)  # type: ignore[arg-type]


def _steady_state_gain_db(
    compressor: MultibandCompressor,
    amplitude: float,
    tone_hz: float = 1000.0,
) -> float:
    """Measure the compressor gain on the settled part of a tone."""
    signal = sine(tone_hz, FS, 1.0, amplitude=amplitude)
    output = compressor.process(signal)
    settled = int(0.25 * signal.size)
    return estimate_gain_db(signal[settled:], output[settled:], FS, tone_hz=tone_hz).gain_db


def test_single_band_process_matches_static_curve() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, attack_s=0.002, release_s=0.02, knee_db=0.0
    )
    compressor = MultibandCompressor((), (config,), FS)
    amplitude = 0.1  # RMS level = 20 log10(0.1/sqrt2) = -23.01 dBFS
    input_level_dbfs = 20.0 * np.log10(amplitude / np.sqrt(2.0))
    expected = float(config.static_gain_db(input_level_dbfs))
    measured = _steady_state_gain_db(compressor, amplitude)
    assert measured == pytest.approx(expected, abs=0.2)


def test_compression_reduces_dynamic_range() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, attack_s=0.002, release_s=0.02, knee_db=0.0
    )
    compressor = MultibandCompressor((), (config,), FS)
    low_gain = _steady_state_gain_db(compressor, 0.1)
    high_gain = _steady_state_gain_db(compressor, 0.3)  # 10 dB louder
    # Above threshold, a 9.54 dB input increase produces a 9.54/ratio increase.
    input_step_db = 20.0 * np.log10(0.3 / 0.1)
    output_step_db = input_step_db + (high_gain - low_gain)
    assert output_step_db == pytest.approx(input_step_db / config.ratio, abs=0.3)


def test_makeup_gain_shifts_processed_gain() -> None:
    base = CompressorConfig(threshold_dbfs=-30.0, ratio=3.0, attack_s=0.002, release_s=0.02)
    makeup = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, attack_s=0.002, release_s=0.02, makeup_db=6.0
    )
    base_gain = _steady_state_gain_db(MultibandCompressor((), (base,), FS), 0.2)
    makeup_gain = _steady_state_gain_db(MultibandCompressor((), (makeup,), FS), 0.2)
    assert makeup_gain - base_gain == pytest.approx(6.0, abs=0.2)


def test_peak_detector_processes_without_error() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=3.0, detector="peak", attack_s=0.001, release_s=0.05
    )
    compressor = MultibandCompressor((), (config,), FS)
    output = compressor.process(sine(1000.0, FS, 0.5, amplitude=0.2))
    assert output.shape == (FS // 2,)
    assert np.all(np.isfinite(output))


def test_multiband_compression_is_finite_and_reduces_level() -> None:
    config = CompressorConfig(
        threshold_dbfs=-30.0, ratio=4.0, attack_s=0.002, release_s=0.02, knee_db=6.0
    )
    compressor = MultibandCompressor((500.0, 2000.0), (config, config, config), FS)
    signal = sine(1000.0, FS, 1.0, amplitude=0.3)
    output = compressor.process(signal)
    settled = int(0.25 * signal.size)
    assert rms(output[settled:]) < rms(signal[settled:]) * 0.9
    assert np.all(np.isfinite(output))
