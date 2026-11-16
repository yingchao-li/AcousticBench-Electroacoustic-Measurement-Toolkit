"""Unit tests for :mod:`acousticbench.io.mat_loader`.

The synthetic MAT-file fixture (see ``tests/conftest.py``) carries the exact
documented schema, so it validates the loader without the real 90 MB dataset.
The MATLAB v7.3 / HDF5 fallback is exercised with a separately written
HDF5 fixture.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from acousticbench.exceptions import DataValidationError
from acousticbench.io.mat_loader import (
    COMPLEX_VARIABLES,
    EXPECTED_SHAPES,
    REAL_VARIABLES,
    RawMatData,
    inspect_mat,
    load_mat,
    validate_variables,
)
from acousticbench.types import (
    FREQUENCY_RESOLUTION_HZ,
    N_FREQUENCIES,
    N_REINSERTIONS,
    N_SUBJECTS,
    N_THRESHOLD_FREQUENCIES,
    NYQUIST_HZ,
)


@pytest.fixture(scope="module")
def raw_variables(_small_mat_template) -> dict[str, np.ndarray]:
    """Raw variables of the synthetic MAT-file (loaded once per module)."""
    import scipy.io

    contents = scipy.io.loadmat(_small_mat_template, squeeze_me=False, struct_as_record=False)
    return {key: value for key, value in contents.items() if not key.startswith("__")}


def _copy(variables: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: np.array(value, copy=True) for key, value in variables.items()}


# ---------------------------------------------------------------------------
# documented schema
# ---------------------------------------------------------------------------
def test_expected_shapes_documented():
    assert EXPECTED_SHAPES["v_frq"] == (N_FREQUENCIES,)
    assert EXPECTED_SHAPES["v_fAud"] == (N_THRESHOLD_FREQUENCIES,)
    assert EXPECTED_SHAPES["M_ha2edM"] == (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS)
    assert EXPECTED_SHAPES["M_REUR"] == (N_FREQUENCIES, N_SUBJECTS)
    assert set(EXPECTED_SHAPES) == {
        "v_frq",
        "v_fAud",
        "M_ha2edM",
        "M_ha2edR",
        "M_ha2haf",
        "M_ls2edM",
        "M_ls2edR",
        "M_thr_ha",
        "M_REUR",
    }
    assert set(COMPLEX_VARIABLES) == {
        "M_ha2edM",
        "M_ha2edR",
        "M_ha2haf",
        "M_ls2edM",
        "M_ls2edR",
        "M_REUR",
    }
    assert set(REAL_VARIABLES) == {"v_frq", "v_fAud", "M_thr_ha"}


def test_load_valid_fixture(small_mat_file):
    data = load_mat(small_mat_file, compute_hash=False)
    assert isinstance(data, RawMatData)
    assert data.info.path == small_mat_file.resolve()
    assert data.info.size_bytes == small_mat_file.stat().st_size
    assert data.info.mat_format == "v5"
    assert data.info.header  # platform / creation string
    assert set(data.keys()) == set(EXPECTED_SHAPES)
    table = data.shape_table()
    for key, shape in EXPECTED_SHAPES.items():
        assert table[key] == shape
    assert data.variables["v_frq"][0] == 0.0
    assert data.variables["v_frq"][-1] == pytest.approx(NYQUIST_HZ)
    np.testing.assert_allclose(np.diff(data.variables["v_frq"]), FREQUENCY_RESOLUTION_HZ)
    assert data.variables["v_fAud"].dtype.kind == "f"
    np.testing.assert_allclose(data.variables["v_fAud"], [125, 250, 500, 750, 1000, 2000])
    for key in COMPLEX_VARIABLES:
        assert np.iscomplexobj(data.variables[key])
    assert np.issubdtype(data.variables["M_thr_ha"].dtype, np.floating)


def test_compute_hash_matches_hashlib(small_mat_file, small_fixture_sha256):
    data = load_mat(small_mat_file, compute_hash=True)
    assert data.info.sha256 == small_fixture_sha256
    assert len(data.info.sha256) == 64
    assert data.info.md5 is None
    entry = data.info.to_dict()
    assert entry["sha256"] == small_fixture_sha256
    assert entry["size_bytes"] == small_mat_file.stat().st_size
    assert entry["size_mb"] == pytest.approx(small_mat_file.stat().st_size / 1024**2, rel=0.01)
    assert entry["mat_format"] == "v5"


def test_compute_hash_false_leaves_digest_empty(small_mat_file):
    assert load_mat(small_mat_file, compute_hash=False).info.sha256 == ""


def test_load_accepts_path_object_and_string(small_mat_file):
    from_path = load_mat(small_mat_file, compute_hash=False)
    from_str = load_mat(str(small_mat_file), compute_hash=False)
    assert from_path.info.path == from_str.info.path


def test_raw_data_helpers(small_mat_file):
    data = load_mat(small_mat_file, compute_hash=False)
    values = data["M_REUR"]
    assert values.shape == (N_FREQUENCIES, N_SUBJECTS)
    assert "M_REUR" in data
    assert "nope" not in data
    assert data.get("nope", "fallback") == "fallback"
    assert data.get("M_REUR") is values
    assert set(data.keys()) == set(EXPECTED_SHAPES)


def test_missing_file_raises(tmp_path):
    with pytest.raises(DataValidationError, match="not found"):
        load_mat(tmp_path / "does_not_exist.mat")


# ---------------------------------------------------------------------------
# HDF5 / MATLAB v7.3 fallback
# ---------------------------------------------------------------------------
def test_hdf5_fallback_loads(h5_mat_file):
    data = load_mat(h5_mat_file, compute_hash=False)
    assert data.info.mat_format == "v7.3 (HDF5)"
    assert data.info.header.startswith("MATLAB 7.3")
    assert data.shape_table() == EXPECTED_SHAPES
    for key in COMPLEX_VARIABLES:
        assert np.iscomplexobj(data.variables[key])
    # The fixture stores a deterministic ramp in the real part of M_REUR.
    real = np.real(data.variables["M_REUR"])
    assert np.all(np.isfinite(real))
    np.testing.assert_allclose(np.diff(real, axis=0), 0.0)


# ---------------------------------------------------------------------------
# schema validation failures
# ---------------------------------------------------------------------------
def test_missing_variable_raises(raw_variables):
    variables = _copy(raw_variables)
    del variables["M_REUR"]
    with pytest.raises(DataValidationError, match="missing variable"):
        validate_variables(variables)


def test_wrong_shape_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["M_ha2edM"] = variables["M_ha2edM"][:100]
    with pytest.raises(DataValidationError, match="shape"):
        validate_variables(variables)


def test_real_container_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["M_ha2edM"] = np.real(variables["M_ha2edM"])
    with pytest.raises(DataValidationError, match="complex-valued"):
        validate_variables(variables)


def test_complex_real_variable_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["M_thr_ha"] = variables["M_thr_ha"].astype(np.complex128)
    with pytest.raises(DataValidationError, match="real-valued"):
        validate_variables(variables)


def test_non_uniform_frequency_axis_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["v_frq"] = variables["v_frq"].copy()
    variables["v_frq"][0, 100] += 1.0
    with pytest.raises(DataValidationError, match="uniform DFT grid"):
        validate_variables(variables)


def test_wrong_nyquist_raises(raw_variables):
    variables = _copy(raw_variables)
    # Uniform grid (constant Δf) that nevertheless does not end at Nyquist.
    variables["v_frq"] = raw_variables["v_frq"] + 100.0
    with pytest.raises(DataValidationError, match="end at"):
        validate_variables(variables)


def test_non_increasing_frequency_axis_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["v_frq"] = variables["v_frq"].copy()
    variables["v_frq"][0, 10], variables["v_frq"][0, 11] = (
        variables["v_frq"][0, 11],
        variables["v_frq"][0, 10],
    )
    with pytest.raises(DataValidationError, match="strictly increasing"):
        validate_variables(variables)


def test_non_increasing_threshold_axis_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["v_fAud"] = np.array([[2000, 250, 500, 750, 1000, 125]], dtype=np.uint16)
    with pytest.raises(DataValidationError, match="strictly increasing"):
        validate_variables(variables)


def test_non_finite_axis_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["v_frq"] = variables["v_frq"].copy()
    variables["v_frq"][0, 5] = np.nan
    with pytest.raises(DataValidationError, match="non-finite"):
        validate_variables(variables)


def test_infinite_container_values_raise(raw_variables):
    variables = _copy(raw_variables)
    variables["M_ls2edM"] = variables["M_ls2edM"].copy()
    variables["M_ls2edM"][0, 0, 0, 0] = np.inf
    with pytest.raises(DataValidationError, match="infinite"):
        validate_variables(variables)


def test_all_nan_container_raises(raw_variables):
    variables = _copy(raw_variables)
    variables["M_ha2haf"] = np.full_like(variables["M_ha2haf"], np.nan)
    with pytest.raises(DataValidationError, match="no finite values"):
        validate_variables(variables)


def test_non_strict_axes_reports_warning(raw_variables):
    variables = _copy(raw_variables)
    variables["v_frq"] = (np.arange(N_FREQUENCIES) + 1.0).reshape(1, -1) * FREQUENCY_RESOLUTION_HZ
    validated, warnings = validate_variables(variables, strict_axes=False)
    assert any("does not start at 0 Hz" in warning for warning in warnings)
    assert validated["v_frq"].shape == (N_FREQUENCIES,)


def test_unexpected_threshold_axis_warns(raw_variables):
    variables = _copy(raw_variables)
    variables["v_fAud"] = np.array([[125, 250, 500, 750, 1000, 1500]], dtype=np.uint16)
    _, warnings = validate_variables(variables, strict_axes=False)
    assert any("v_fAud differs" in warning for warning in warnings)


def test_row_vector_axes_are_normalised(raw_variables):
    validated, _ = validate_variables(_copy(raw_variables))
    assert validated["v_frq"].ndim == 1
    assert validated["v_fAud"].ndim == 1
    assert validated["M_ha2edM"].ndim == 4


def test_validate_does_not_modify_inputs(raw_variables):
    variables = _copy(raw_variables)
    original = variables["v_frq"].copy()
    validate_variables(variables)
    np.testing.assert_array_equal(variables["v_frq"], original)


# ---------------------------------------------------------------------------
# inspect_mat
# ---------------------------------------------------------------------------
def test_inspect_mat_summary(small_mat_file):
    summary = inspect_mat(small_mat_file)
    assert set(summary) == {"file", "variables", "warnings"}
    assert summary["file"]["mat_format"] == "v5"
    entries = summary["variables"]
    assert set(entries) == set(EXPECTED_SHAPES)
    entry = entries["M_ha2edM"]
    assert entry["shape"] == (N_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS)
    assert entry["complex"] is True
    assert 0.0 < entry["finite_fraction"] < 1.0  # planted NaN sessions
    assert entry["magnitude_median"] > 0.0
    threshold = entries["M_thr_ha"]
    assert threshold["nan_count"] == 0
    assert threshold["min_dbv"] <= threshold["max_dbv"]
    assert entries["v_frq"]["values"][0] == 0.0
    assert len(entries["v_fAud"]["values"]) == N_THRESHOLD_FREQUENCIES
