"""Unit tests for :mod:`acousticbench.synthetic.generator`.

These tests close the loop: they render cases, apply the *measurement*
estimators from :mod:`acousticbench.dsp.metrics`, and compare the estimated
values against the analytic ground truth.  The strict targets of
``config/default.yaml`` are asserted for reference-condition cases.
"""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.metrics import (
    estimate_filter_response,
    estimate_gain_db,
    estimate_snr_db,
    estimate_thd,
)
from acousticbench.exceptions import SyntheticCaseError
from acousticbench.synthetic.cases import CATEGORIES, TARGETS, build_cases
from acousticbench.synthetic.generator import SyntheticCaseData, render_case

FS = 48000
N_CASES = 16


@pytest.fixture(scope="module")
def cases() -> tuple:
    """Small deterministic case set used by several tests."""
    return build_cases(N_CASES, seed=20260422, fs_hz=FS)


def _reference(cases: tuple, category: str) -> list:
    return [
        case
        for case in cases
        if case.category == category and case.is_reference_condition
    ]


def test_render_is_reproducible(cases: tuple) -> None:
    for case in cases:
        first = render_case(case)
        second = render_case(case)
        np.testing.assert_array_equal(first.input, second.input)
        np.testing.assert_array_equal(first.output, second.output)
        np.testing.assert_array_equal(first.clean_reference, second.clean_reference)
        if first.noise is not None:
            np.testing.assert_array_equal(first.noise, second.noise)


def test_rendered_arrays_have_expected_shape_and_dtype(cases: tuple) -> None:
    for case in cases:
        data = render_case(case)
        assert data.fs_hz == case.fs_hz
        assert data.n_samples == case.n_samples
        for array in (data.input, data.output, data.clean_reference):
            assert array.shape == (case.n_samples,)
            assert array.dtype == np.float64
        if data.noise is not None:
            assert data.noise.shape == (case.n_samples,)
            assert data.noise.dtype == np.float64


def test_all_signals_stay_below_full_scale(cases: tuple) -> None:
    for case in cases:
        data = render_case(case)
        arrays = [data.input, data.output, data.clean_reference]
        if data.noise is not None:
            arrays.append(data.noise)
        for array in arrays:
            assert float(np.max(np.abs(array))) <= 0.99 + 1e-12


def test_gain_case_ground_truth_is_consistent_with_waveforms(cases: tuple) -> None:
    for case in _reference(cases, "gain"):
        data = render_case(case)
        measured_gain = 20.0 * np.log10(
            np.sqrt(np.mean(data.output**2)) / np.sqrt(np.mean(data.input**2))
        )
        assert data.ground_truth["gain_db"] == pytest.approx(measured_gain, abs=1e-9)
        # The noiseless gain case has an exactly proportional output.
        np.testing.assert_allclose(
            data.output,
            data.input * 10.0 ** (data.ground_truth["gain_db"] / 20.0),
            atol=1e-12,
        )
        assert data.noise is None
        np.testing.assert_array_equal(data.clean_reference, data.output)


def test_snr_case_output_equals_clean_plus_noise(cases: tuple) -> None:
    for case in _reference(cases, "snr"):
        data = render_case(case)
        assert data.noise is not None
        np.testing.assert_allclose(data.output, data.clean_reference + data.noise, atol=1e-15)
        realised = 10.0 * np.log10(
            np.mean(data.clean_reference**2) / np.mean(data.noise**2)
        )
        assert data.ground_truth["snr_db"] == pytest.approx(realised, abs=1e-9)


def test_thd_case_ground_truth_matches_known_harmonics(cases: tuple) -> None:
    for case in _reference(cases, "thd"):
        data = render_case(case)
        amplitudes = data.ground_truth["harmonic_amplitudes"]
        fundamental = data.ground_truth["fundamental_amplitude"]
        expected = 100.0 * np.sqrt(np.sum(np.square(amplitudes))) / fundamental
        assert data.ground_truth["thd_percent"] == pytest.approx(expected, abs=1e-9)
        assert data.ground_truth["thd_percent"] == pytest.approx(
            case.parameters["thd_percent"], abs=1e-9
        )
        assert data.noise is None


def test_frequency_response_ground_truth_is_complete(cases: tuple) -> None:
    for case in _reference(cases, "frequency_response"):
        data = render_case(case)
        truth = data.ground_truth
        assert len(truth["frequencies_hz"]) == len(truth["magnitude_db"])
        assert len(truth["frequencies_hz"]) == len(truth["phase_deg"])
        assert len(truth["evaluation_mask"]) == len(truth["frequencies_hz"])
        assert any(truth["evaluation_mask"])
        assert truth["evaluation_magnitude_db"] == pytest.approx(
            tuple(
                value
                for value, keep in zip(truth["magnitude_db"], truth["evaluation_mask"])
                if keep
            )
        )
        assert truth["frequency_response_mae_tolerance_db"] == pytest.approx(
            TARGETS["frequency_response_mae_db"]
        )
        assert data.noise is None
        np.testing.assert_array_equal(data.clean_reference, data.output)


def test_frequency_response_with_noise_adds_noise(cases: tuple) -> None:
    noisy = [
        case
        for case in cases
        if case.category == "frequency_response" and case.parameters["noise_snr_db"] is not None
    ]
    for case in noisy:
        data = render_case(case)
        assert data.noise is not None
        np.testing.assert_allclose(data.output, data.clean_reference + data.noise, atol=1e-15)
        assert data.ground_truth["noise_snr_db"] == pytest.approx(
            case.parameters["noise_snr_db"], abs=0.5
        )


def test_reference_gain_estimator_meets_target(cases: tuple) -> None:
    reference = _reference(cases, "gain")
    assert reference
    for case in reference:
        data = render_case(case)
        result = estimate_gain_db(
            data.input, data.output, data.fs_hz, tone_hz=data.ground_truth["tone_hz"]
        )
        error = abs(result.gain_db - data.ground_truth["gain_db"])
        assert error <= TARGETS["gain_error_db"]


def test_reference_snr_estimator_meets_target(cases: tuple) -> None:
    reference = _reference(cases, "snr")
    assert reference
    for case in reference:
        data = render_case(case)
        result = estimate_snr_db(data.output, data.fs_hz, data.ground_truth["tone_hz"])
        error = abs(result.snr_db - data.ground_truth["snr_db"])
        assert error <= TARGETS["snr_error_db"]


def test_reference_thd_estimator_meets_target(cases: tuple) -> None:
    reference = _reference(cases, "thd")
    assert reference
    for case in reference:
        data = render_case(case)
        result = estimate_thd(
            data.output,
            data.fs_hz,
            data.ground_truth["tone_hz"],
            n_harmonics=data.ground_truth["n_harmonics"],
        )
        error = abs(result.thd_percent - data.ground_truth["thd_percent"])
        assert error <= TARGETS["thd_error_percentage_points"]


def test_reference_frequency_response_estimator_meets_target(cases: tuple) -> None:
    reference = _reference(cases, "frequency_response")
    assert reference
    for case in reference:
        data = render_case(case)
        result = estimate_filter_response(data.input, data.output, data.fs_hz)
        truth = data.ground_truth
        evaluation_frequencies = np.asarray(truth["evaluation_frequencies_hz"])
        truth_magnitude = np.asarray(truth["evaluation_magnitude_db"])
        estimated = np.interp(
            evaluation_frequencies, result.frequencies_hz, result.magnitude_db
        )
        mae = float(np.mean(np.abs(estimated - truth_magnitude)))
        assert mae <= TARGETS["frequency_response_mae_db"]


def test_non_reference_gain_and_thd_are_still_accurate(cases: tuple) -> None:
    non_reference_gain = [
        case for case in cases if case.category == "gain" and not case.is_reference_condition
    ]
    for case in non_reference_gain:
        data = render_case(case)
        result = estimate_gain_db(
            data.input, data.output, data.fs_hz, tone_hz=data.ground_truth["tone_hz"]
        )
        assert abs(result.gain_db - data.ground_truth["gain_db"]) <= TARGETS["gain_error_db"]
    non_reference_thd = [
        case for case in cases if case.category == "thd" and not case.is_reference_condition
    ]
    for case in non_reference_thd:
        data = render_case(case)
        result = estimate_thd(
            data.output,
            data.fs_hz,
            data.ground_truth["tone_hz"],
            n_harmonics=data.ground_truth["n_harmonics"],
        )
        assert abs(result.thd_percent - data.ground_truth["thd_percent"]) <= 0.05


def test_render_rejects_invalid_case() -> None:
    with pytest.raises(SyntheticCaseError):
        render_case("not a case")  # type: ignore[arg-type]


def test_all_categories_are_rendered(cases: tuple) -> None:
    rendered_categories = {render_case(case).case.category for case in cases}
    assert rendered_categories == set(CATEGORIES)
