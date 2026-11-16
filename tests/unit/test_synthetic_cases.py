"""Unit tests for :mod:`acousticbench.synthetic.cases`."""

from __future__ import annotations

import json

import pytest

from acousticbench.exceptions import SyntheticCaseError
from acousticbench.synthetic.cases import (
    CATEGORIES,
    GAIN_DB_RANGE,
    INPUT_LEVEL_DBFS_RANGE,
    REFERENCE_CONDITIONS,
    SNR_DB_RANGE,
    TARGETS,
    THD_PERCENT_RANGE,
    SyntheticCase,
    build_cases,
    save_manifest,
)

FS = 48000


def test_build_cases_is_balanced_and_deterministic() -> None:
    cases = build_cases(20, seed=20260422, fs_hz=FS)
    assert len(cases) == 20
    counts = {category: sum(case.category == category for case in cases) for category in CATEGORIES}
    assert counts == {category: 5 for category in CATEGORIES}
    assert [case.case_id for case in cases] == [
        case.case_id for case in build_cases(20, seed=20260422, fs_hz=FS)
    ]
    assert [case.seed for case in cases] == [
        case.seed for case in build_cases(20, seed=20260422, fs_hz=FS)
    ]


def test_build_cases_1000_has_250_per_category() -> None:
    cases = build_cases(1000, seed=20260422, fs_hz=FS)
    assert len(cases) == 1000
    for category in CATEGORIES:
        assert sum(case.category == category for case in cases) == 250
    reference = [case for case in cases if case.is_reference_condition]
    assert len(reference) == 400
    for category in CATEGORIES:
        assert sum(case.category == category for case in reference) == 100


def test_different_master_seeds_give_different_cases() -> None:
    first = build_cases(8, seed=1, fs_hz=FS)
    second = build_cases(8, seed=2, fs_hz=FS)
    assert [case.seed for case in first] != [case.seed for case in second]


def test_reference_condition_gain_cases_match_documentation() -> None:
    cases = [c for c in build_cases(40, seed=7, fs_hz=FS) if c.category == "gain"]
    reference = [c for c in cases if c.is_reference_condition]
    assert reference
    for case in reference:
        assert case.parameters["tone_hz"] == pytest.approx(1000.0)
        assert case.parameters["input_level_dbfs"] == pytest.approx(-20.0)
        assert GAIN_DB_RANGE[0] <= case.parameters["gain_db"] <= 15.0
    non_reference = [c for c in cases if not c.is_reference_condition]
    assert non_reference


def test_reference_condition_snr_cases_match_documentation() -> None:
    cases = [c for c in build_cases(40, seed=8, fs_hz=FS) if c.category == "snr"]
    for case in cases:
        if not case.is_reference_condition:
            continue
        assert case.parameters["tone_hz"] == pytest.approx(1000.0)
        assert case.parameters["noise_color"] == "white"
        assert 10.0 <= case.parameters["snr_db"] <= 40.0


def test_reference_condition_thd_cases_match_documentation() -> None:
    cases = [c for c in build_cases(40, seed=9, fs_hz=FS) if c.category == "thd"]
    for case in cases:
        if not case.is_reference_condition:
            continue
        assert case.parameters["tone_hz"] == pytest.approx(1000.0)
        assert 0.5 <= case.parameters["thd_percent"] <= 5.0


def test_reference_condition_frequency_response_cases_match_documentation() -> None:
    cases = [
        c for c in build_cases(40, seed=10, fs_hz=FS) if c.category == "frequency_response"
    ]
    reference = [c for c in cases if c.is_reference_condition]
    assert reference
    for case in reference:
        assert case.parameters["f_start_hz"] == pytest.approx(100.0)
        assert case.parameters["f_end_hz"] == pytest.approx(10000.0)
        assert case.parameters["noise_snr_db"] is None
        assert case.parameters["input_level_dbfs"] == pytest.approx(-20.0)


def test_parameter_ranges_match_configuration() -> None:
    cases = build_cases(40, seed=11, fs_hz=FS)
    for case in cases:
        if case.category == "gain":
            assert GAIN_DB_RANGE[0] <= case.parameters["gain_db"] <= 40.0
        if case.category == "snr":
            assert SNR_DB_RANGE[0] <= case.parameters["snr_db"] <= SNR_DB_RANGE[1]
            assert case.parameters["noise_color"] in {"white", "pink"}
        if case.category == "thd":
            assert THD_PERCENT_RANGE[0] <= case.parameters["thd_percent"] <= THD_PERCENT_RANGE[1]
        assert INPUT_LEVEL_DBFS_RANGE[0] <= case.parameters["input_level_dbfs"] <= INPUT_LEVEL_DBFS_RANGE[1]
        assert case.fs_hz == FS
        assert case.duration_s == pytest.approx(4.0)
        assert case.n_samples == 4 * FS


def test_ground_truth_matches_parameters_for_reference_cases() -> None:
    cases = build_cases(16, seed=12, fs_hz=FS)
    for case in cases:
        if case.category == "gain":
            assert case.ground_truth["gain_db"] == pytest.approx(case.parameters["gain_db"])
        if case.category == "snr":
            assert case.ground_truth["snr_db"] == pytest.approx(case.parameters["snr_db"])
        if case.category == "thd":
            assert case.ground_truth["thd_percent"] == pytest.approx(
                case.parameters["thd_percent"]
            )


def test_targets_and_reference_conditions_are_documented() -> None:
    assert set(TARGETS) == {
        "gain_error_db",
        "snr_error_db",
        "thd_error_percentage_points",
        "frequency_response_mae_db",
    }
    assert set(REFERENCE_CONDITIONS) == set(CATEGORIES)
    assert all(isinstance(value, str) and value for value in REFERENCE_CONDITIONS.values())


def test_save_manifest_writes_csv_and_json(tmp_path) -> None:
    cases = build_cases(8, seed=13, fs_hz=FS)
    csv_path, json_path = save_manifest(cases, tmp_path / "manifest")
    assert csv_path.exists()
    assert json_path.exists()
    records = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(records) == 8
    assert records[0]["case_id"] == cases[0].case_id
    assert set(records[0]) == {
        "case_id",
        "seed",
        "category",
        "fs_hz",
        "duration_s",
        "is_reference_condition",
        "parameters",
        "ground_truth",
    }
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "case_id" in header and "is_reference_condition" in header


def test_save_manifest_accepts_explicit_extension(tmp_path) -> None:
    cases = build_cases(4, seed=14, fs_hz=FS)
    csv_path, json_path = save_manifest(cases, tmp_path / "cases.csv")
    assert csv_path.name == "cases.csv"
    assert json_path.name == "cases.json"


def test_save_manifest_rejects_empty_manifest(tmp_path) -> None:
    with pytest.raises(ValueError):
        save_manifest((), tmp_path / "manifest")


def test_invalid_build_arguments_raise() -> None:
    with pytest.raises(SyntheticCaseError):
        build_cases(0)
    with pytest.raises(SyntheticCaseError):
        build_cases(-3)
    with pytest.raises(SyntheticCaseError):
        build_cases(4, seed=-1)
    with pytest.raises(SyntheticCaseError):
        build_cases(4, seed=1, fs_hz=0)


def test_case_dataclass_validation() -> None:
    with pytest.raises(SyntheticCaseError):
        SyntheticCase(
            case_id="bad-1",
            seed=1,
            category="unknown",
            fs_hz=FS,
            duration_s=1.0,
            parameters={},
            ground_truth={},
            is_reference_condition=False,
        )
    with pytest.raises(SyntheticCaseError):
        SyntheticCase(
            case_id="",
            seed=1,
            category="gain",
            fs_hz=FS,
            duration_s=1.0,
            parameters={},
            ground_truth={},
            is_reference_condition=False,
        )
