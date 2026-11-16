"""Unit tests for :mod:`acousticbench.virtual_ha.faults`."""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.metrics import estimate_thd
from acousticbench.dsp.signals import sine
from acousticbench.virtual_ha.faults import FAULT_TYPES, FaultResult, inject_fault

FS = 8000
DURATION = 0.5
TONE = 500.0


@pytest.fixture()
def tone() -> np.ndarray:
    """A 1 kHz, 0.3-peak-amplitude test tone."""
    return sine(TONE, FS, DURATION, amplitude=0.3)


def test_supported_fault_types() -> None:
    assert set(FAULT_TYPES) == {
        "clipping",
        "dropout",
        "dc_offset",
        "gain_error",
        "harmonic_distortion",
        "latency",
    }


def test_clipping_limits_peak_and_reports_true_params(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "clipping", clip_level_dbfs=-12.0)
    assert isinstance(result, FaultResult)
    assert result.fault_type == "clipping"
    expected_level = 10.0 ** (-12.0 / 20.0)
    assert np.max(np.abs(result.output)) == pytest.approx(expected_level, rel=1e-12)
    assert result.true_params["clip_level_dbfs"] == pytest.approx(-12.0)
    assert result.true_params["clip_level"] == pytest.approx(expected_level)
    assert result.fs == pytest.approx(FS)


def test_clipping_with_linear_level(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "clipping", clip_level=0.1)
    assert np.max(np.abs(result.output)) == pytest.approx(0.1, rel=1e-12)
    assert result.true_params["clip_level_dbfs"] == pytest.approx(20.0 * np.log10(0.1))


def test_dropout_silences_exact_interval(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "dropout", start_s=0.1, stop_s=0.2)
    start_sample = int(round(0.1 * FS))
    stop_sample = int(round(0.2 * FS))
    assert np.all(result.output[start_sample:stop_sample] == 0.0)
    np.testing.assert_array_equal(result.output[:start_sample], tone[:start_sample])
    np.testing.assert_array_equal(result.output[stop_sample:], tone[stop_sample:])
    assert result.true_params["start_sample"] == start_sample
    assert result.true_params["stop_sample"] == stop_sample


def test_dc_offset_adds_constant(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "dc_offset", offset=0.05)
    np.testing.assert_allclose(result.output, tone + 0.05, atol=1e-15)
    assert result.true_params["offset"] == pytest.approx(0.05)


def test_gain_error_scales_signal(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "gain_error", gain_db=3.0)
    np.testing.assert_allclose(result.output, tone * 10.0 ** (3.0 / 20.0), atol=1e-15)
    assert result.true_params["gain_linear"] == pytest.approx(10.0 ** (3.0 / 20.0))


def test_harmonic_distortion_has_requested_thd(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "harmonic_distortion", percentage=5.0, tone_hz=TONE)
    thd = estimate_thd(result.output, FS, TONE, n_harmonics=4)
    assert thd.thd_percent == pytest.approx(5.0, abs=0.02)
    assert result.true_params["percentage"] == pytest.approx(5.0)
    assert result.true_params["tone_hz"] == pytest.approx(TONE)
    assert len(result.true_params["harmonic_frequencies_hz"]) == 4
    assert result.true_params["harmonic_frequencies_hz"][0] == pytest.approx(2.0 * TONE)


def test_harmonic_distortion_detects_dominant_tone(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "harmonic_distortion", percentage=2.0)
    assert result.true_params["tone_hz"] == pytest.approx(TONE, rel=0.01)
    thd = estimate_thd(result.output, FS, TONE, n_harmonics=4)
    assert thd.thd_percent == pytest.approx(2.0, abs=0.02)


def test_latency_delays_signal(tone: np.ndarray) -> None:
    delay_ms = 1.0
    result = inject_fault(tone, FS, "latency", delay_ms=delay_ms)
    delay_samples = int(round(delay_ms * FS / 1000.0))
    assert delay_samples == 8
    np.testing.assert_array_equal(result.output[:delay_samples], np.zeros(delay_samples))
    np.testing.assert_array_equal(result.output[delay_samples:], tone[:-delay_samples])
    assert result.true_params["delay_samples"] == delay_samples
    assert result.true_params["latency_ms_actual"] == pytest.approx(delay_ms)


def test_zero_latency_is_identity(tone: np.ndarray) -> None:
    result = inject_fault(tone, FS, "latency", delay_ms=0.0)
    np.testing.assert_array_equal(result.output, tone)


def test_fault_injection_is_deterministic(tone: np.ndarray) -> None:
    first = inject_fault(tone, FS, "dropout", start_s=0.1, stop_s=0.2)
    second = inject_fault(tone, FS, "dropout", start_s=0.1, stop_s=0.2)
    np.testing.assert_array_equal(first.output, second.output)


def test_fault_validation_errors(tone: np.ndarray) -> None:
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "unknown_fault")
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "dropout", start_s=0.1)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "dropout", start_s=0.2, stop_s=0.1)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "dropout", start_s=0.1, stop_s=10.0)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "gain_error", gain_db=3.0, unexpected=1.0)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "clipping", clip_level_dbfs=-6.0, clip_level=0.1)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "harmonic_distortion", percentage=0.0)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "latency", delay_ms=-1.0)
    with pytest.raises(ValueError):
        inject_fault(tone, FS, "latency", delay_ms=10000.0)
    with pytest.raises(ValueError):
        inject_fault(np.zeros(16), FS, "harmonic_distortion", percentage=5.0)
