"""Unit tests for the MATLAB-transcribed reference port and the cross-language
validation workflow (:mod:`acousticbench.validation`).

The numerical port is compared with the production DSP/measurement
implementations on small deterministic signals and on the synthetic dataset.
The E15 workflow is exercised end-to-end on the real dataset (marked
``requires_data`` / ``slow``); MATLAB itself is not available in this
environment, so the report must honestly record ``matlab_status="not_run"``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from acousticbench.config import load_config
from acousticbench.dsp.metrics import estimate_gain_db, estimate_snr_db, estimate_thd
from acousticbench.dsp.signals import sine, white_noise
from acousticbench.stats.bands import custom_bands, octave_bands
from acousticbench.validation import cross_language
from acousticbench.validation import matlab_port as port
from acousticbench.validation.cross_language import (
    AgreementComparison,
    CrossLanguageReport,
    export_matlab_inputs,
    matlab_executable,
    run_cross_language_validation,
    run_matlab_export,
)


# ---------------------------------------------------------------------------
# small deterministic signals
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tone_signal():
    fs = 48000
    n = fs  # exactly 1000 periods of a 1 kHz tone
    return sine(1000.0, fs=fs, duration_s=1.0), fs, n


def test_tone_amplitude_port(tone_signal):
    signal, fs, n = tone_signal
    amplitude = port.tone_amplitude_port(signal, fs, 1000.0)
    assert amplitude == pytest.approx(1.0, rel=1e-6)
    # A coherent frequency that does not correspond to a DFT bin leaks
    # (Dirichlet-kernel leakage is small but non-zero).
    leakage = port.tone_amplitude_port(signal, fs, 1234.5)
    assert leakage < 0.01


def test_gain_db_port_matches_production(tone_signal):
    signal, fs, _ = tone_signal
    output = 2.0 * signal  # +6.0206 dB
    reference = port.gain_db_port(signal, output, fs, 1000.0)
    production = estimate_gain_db(signal, output, fs, tone_hz=1000.0).gain_db
    assert reference == pytest.approx(20 * np.log10(2.0), abs=1e-9)
    assert production == pytest.approx(reference, abs=1e-9)


@pytest.mark.parametrize("sigma", [0.007, 0.02])
def test_snr_db_port_matches_production(sigma):
    fs = 48000
    signal = sine(1000.0, fs=fs, duration_s=1.0, amplitude=0.1) + sigma * white_noise(
        fs, seed=7
    )
    reference = port.snr_db_port(signal, fs, 1000.0)
    production = estimate_snr_db(
        signal, fs, 1000.0, method="residual"
    ).snr_db
    assert np.isfinite(reference)
    assert reference == pytest.approx(production, abs=1.0)


def test_thd_percent_port_matches_production():
    fs = 48000
    duration = 1.0
    n = int(fs * duration)
    time = np.arange(n) / fs
    amplitude = 0.2
    second = 0.02
    third = 0.01
    signal = (
        amplitude * np.sin(2 * np.pi * 1000.0 * time)
        + second * np.sin(2 * np.pi * 2000.0 * time)
        + third * np.sin(2 * np.pi * 3000.0 * time)
    )
    reference = port.thd_percent_port(signal, fs, 1000.0, n_harmonics=2)
    expected = 100.0 * np.sqrt(second**2 + third**2) / amplitude
    production = estimate_thd(signal, fs, 1000.0, n_harmonics=2).thd_percent
    assert reference == pytest.approx(expected, rel=1e-6)
    assert reference == pytest.approx(production, rel=1e-6)


def test_band_levels_port_formula():
    fs = 48000
    signal = sine(1000.0, fs=fs, duration_s=1.0, amplitude=0.5)
    bands = custom_bands([500.0, 2000.0])
    frame = port.band_levels_port(signal, fs, bands)
    assert list(frame["band"]) == ["500–2000 Hz"]
    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2 / signal.size**2
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / fs)
    mask = (frequencies >= 500.0) & (frequencies < 2000.0)
    expected = 10 * np.log10(np.mean(power[mask]))
    assert frame.loc[0, "level_db"] == pytest.approx(expected, abs=1e-9)


def test_fir_dtft_port():
    taps = np.array([0.5, 0.5])
    fs = 1000.0
    frequencies = np.array([0.0, 250.0])
    response = port.fir_dtft_port(taps, fs, frequencies)
    expected = 20 * np.log10(
        np.abs(0.5 + 0.5 * np.exp(-2j * np.pi * frequencies / fs))
    )
    np.testing.assert_allclose(response, expected, atol=1e-12)
    # A half-band (fs/4) two-tap averager attenuates by 3 dB.
    assert response[1] == pytest.approx(-3.0103, abs=1e-3)
    # The Nyquist null is clamped to the numerical floor of the port.
    nyquist = port.fir_dtft_port(taps, fs, np.array([500.0]))
    assert nyquist[0] == pytest.approx(-240.0, abs=1e-6)


# ---------------------------------------------------------------------------
# dataset-level port vs production implementations (synthetic dataset)
# ---------------------------------------------------------------------------
def test_band_levels_from_transfer_port(small_dataset):
    cube = small_dataset.reur().select(freq_range=(50.0, 4000.0))
    bands = octave_bands()
    production = cube.band_levels(bands, reference=1.0)
    values = port.band_levels_from_transfer_port(cube.values, cube.freq_hz, bands, 1.0)
    for band_label, level in values.items():
        expected = production.loc[production["band"] == band_label, "level_db"].to_numpy()
        np.testing.assert_allclose(level.reshape(-1), expected, atol=1e-9)


def test_hha_band_levels_port(small_dataset, bands):
    from acousticbench.measurements.transfer import hha_band_levels
    from acousticbench.types import Condition, Probe

    production = hha_band_levels(
        small_dataset, bands, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT
    )
    production = production.loc[production["valid"]]
    expected = (
        production.groupby(["device_code", "band_center_hz"], as_index=False)["level_db"].median()
    )
    reference = port.hha_band_levels_port(small_dataset, bands)
    merged = expected.merge(
        reference, on=["device_code", "band_center_hz"], how="inner", suffixes=("_prod", "_port")
    )
    assert len(merged) == len(expected) == len(reference)
    np.testing.assert_allclose(merged["level_db"], merged["median_db"], atol=1e-9)


def test_reoig_band_levels_port(small_dataset, bands):
    from acousticbench.measurements.transfer import reoig_band_levels
    from acousticbench.types import Condition, Probe

    production = reoig_band_levels(
        small_dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    production = production.loc[production["valid"]]
    expected = (
        production.groupby(["family", "band_center_hz"], as_index=False)["reoig_db"].median()
    )
    reference = port.reoig_band_levels_port(small_dataset, bands)
    merged = expected.merge(
        reference[["family", "band_center_hz", "median_db"]],
        on=["family", "band_center_hz"],
        how="inner",
    )
    assert len(merged) == len(expected)
    np.testing.assert_allclose(merged["reoig_db"], merged["median_db"], atol=1e-9)


def test_ptpe_hha_band_levels_port(small_dataset, bands):
    from acousticbench.measurements.ptpe import ptpe_hha_band_levels

    production = ptpe_hha_band_levels(small_dataset, bands)
    production = production.loc[production["valid"]]
    expected = (
        production.groupby(["family", "band_center_hz"], as_index=False)["ptpe_db"].median()
    )
    reference = port.ptpe_hha_band_levels_port(small_dataset, bands)
    merged = expected.merge(
        reference[["family", "band_center_hz", "median_db"]],
        on=["family", "band_center_hz"],
        how="inner",
    )
    assert len(merged) == len(expected)
    np.testing.assert_allclose(merged["ptpe_db"], merged["median_db"], atol=1e-9)


# ---------------------------------------------------------------------------
# MATLAB availability / export contract
# ---------------------------------------------------------------------------
def test_matlab_executable_absent_in_this_environment():
    if shutil.which("matlab") or shutil.which("MATLAB"):
        pytest.skip("MATLAB is installed in this environment")
    assert matlab_executable() is None
    csv_path, error = run_matlab_export(Path(__file__).resolve().parents[2])
    assert csv_path is None
    assert error is not None and "MATLAB executable not found" in error


def test_export_matlab_inputs(config, small_dataset, tmp_path):
    small_config = config.with_overrides({"synthetic": {"n_cases": 40}})
    mat_path, expected = export_matlab_inputs(small_dataset, small_config, tmp_path)
    assert mat_path.is_file()
    assert mat_path.name == "matlab_inputs.mat"
    import scipy.io

    contents = scipy.io.loadmat(mat_path, squeeze_me=True)
    documented = {
        "ids",
        "category",
        "fs",
        "input",
        "output",
        "clean_reference",
        "tone_hz",
        "gain_db",
        "snr_db",
        "thd_percent",
        "freq_start_hz",
        "freq_end_hz",
        "contract",
    }
    assert documented.issubset(contents)
    n_cases = len(expected)
    assert 20 <= n_cases <= 30
    # Synthetic reference cases are 4 s long at 48 kHz.
    assert np.asarray(contents["input"]).shape == (192000, n_cases)
    assert np.asarray(contents["output"]).shape == (192000, n_cases)
    assert np.asarray(contents["clean_reference"]).shape == (192000, n_cases)
    assert np.asarray(contents["fs"]).shape == (n_cases,)
    np.testing.assert_allclose(np.asarray(contents["fs"]), 48000.0)
    assert "AcousticBench E15" in str(contents["contract"])
    ids = np.asarray(contents["ids"]).reshape(-1)
    assert len(ids) == n_cases
    categories = np.asarray(contents["category"]).reshape(-1)
    assert set(map(str, categories)) <= {"gain", "snr", "thd", "frequency_response"}
    # The expected-value CSV follows the documented MATLAB contract.
    csv_path = tmp_path / "expected_synthetic_values.csv"
    assert csv_path.is_file()
    table = pd.read_csv(csv_path)
    assert {"test_id", "quantity", "unit", "expected_python", "ground_truth"}.issubset(
        table.columns
    )
    assert len(table) == n_cases
    assert set(table["quantity"]) == {"gain_db", "snr_db", "thd_percent", "fr_mae_db"}
    # Finite expected values for the estimator categories, NaN for frequency response.
    finite = table.loc[table["quantity"] != "fr_mae_db", "expected_python"]
    assert finite.notna().all()
    assert table.loc[table["quantity"] == "fr_mae_db", "expected_python"].isna().all()


# ---------------------------------------------------------------------------
# production filter response vs the independent DTFT port
# ---------------------------------------------------------------------------
def test_frequency_response_production_vs_port():
    from acousticbench.dsp.filters import (
        design_fir,
        design_iir,
        frequency_response,
    )

    fs = 48000.0
    fir = design_fir("lowpass", fs, 2000.0, numtaps=51)
    response = frequency_response(fir, fs, n_freqs=512)
    assert response.frequencies_hz[0] == 0.0
    assert response.frequencies_hz[-1] == pytest.approx(fs / 2.0)
    assert response.magnitude_db.shape == response.phase_deg.shape == (512,)
    # At the low-frequency evaluation points the independent DTFT must agree
    # with the production freqz evaluation.
    for frequency in (100.0, 500.0, 1000.0, 2000.0):
        index = int(np.argmin(np.abs(response.frequencies_hz - frequency)))
        expected = port.fir_dtft_port(fir.fir_taps, fs, response.frequencies_hz[index:index + 1])
        assert response.magnitude_db[index] == pytest.approx(float(expected[0]), abs=1e-9)
    # IIR filters are evaluated too; response must be finite and lowpass-shaped.
    iir = design_iir("lowpass", fs, 1000.0, order=4)
    iir_response = frequency_response(iir, fs, n_freqs=256)
    assert np.all(np.isfinite(iir_response.magnitude_db))
    assert iir_response.magnitude_db[0] == pytest.approx(0.0, abs=0.5)
    assert iir_response.magnitude_db[-1] < -40.0
    with pytest.raises(ValueError, match="n_freqs"):
        frequency_response(fir, fs, n_freqs=1)


# ---------------------------------------------------------------------------
# cross-language comparison plumbing (no MATLAB required)
# ---------------------------------------------------------------------------
def test_expected_dataset_values_public(small_dataset, config):
    frame = cross_language.expected_dataset_values(small_dataset, config)
    assert isinstance(frame, pd.DataFrame)
    assert {"test_id", "quantity", "unit", "expected_python"}.issubset(frame.columns)
    assert len(frame) > 0
    assert set(frame["quantity"]) <= {
        "hha_band_db",
        "reoig_db",
        "ptpe_hha_db",
        "delta_t_db",
    }


def test_compare_series_empty_overlap(monkeypatch):
    expected = pd.Series([1.0, 2.0], index=["a", "b"])
    actual = pd.Series([1.0], index=["c"])
    comparison = cross_language._compare_series(
        "empty", expected, actual, tolerance=0.1, unit="dB"
    )
    assert comparison.n == 0
    assert comparison.passed is False
    assert np.isnan(comparison.max_abs_diff)


def test_answer_agreement_property_with_matlab_comparisons():
    comparison = AgreementComparison(
        name="gain", unit="dB", n=2, max_abs_diff=0.1,
        median_abs_diff=0.05, tolerance=0.01, passed=False,
    )
    report = CrossLanguageReport(
        matlab_available=True,
        matlab_executable="/usr/bin/matlab",
        matlab_status="executed",
        matlab_reference_csv="reference.csv",
        matlab_error=None,
        matlab_comparisons=[comparison],
    )
    assert report.matlab_agreement_passed is False
    assert report.port_agreement_passed is True  # empty -> all() is True


def test_run_matlab_export_missing_script(monkeypatch, tmp_path):
    monkeypatch.setattr(cross_language, "matlab_executable", lambda: "/bin/true")
    csv_path, error = run_matlab_export(tmp_path)
    assert csv_path is None
    assert error is not None and "export script not found" in error


def test_run_matlab_export_nonzero_exit(monkeypatch, repo_root):
    failing = shutil.which("false")
    if failing is None:
        pytest.skip("no `false` executable available")
    monkeypatch.setattr(cross_language, "matlab_executable", lambda: failing)
    csv_path, error = run_matlab_export(repo_root)
    assert csv_path is None
    assert error is not None and "exited with code" in error


# ---------------------------------------------------------------------------
# report dataclasses
# ---------------------------------------------------------------------------
def test_agreement_comparison_and_report_dict():
    comparison = AgreementComparison(
        name="gain", unit="dB", n=3, max_abs_diff=0.001,
        median_abs_diff=0.0005, tolerance=0.01, passed=True,
    )
    payload = comparison.to_dict()
    assert payload["name"] == "gain" and payload["passed"] is True
    assert payload["n"] == 3

    report = CrossLanguageReport(
        matlab_available=False,
        matlab_executable=None,
        matlab_status="not_run",
        matlab_reference_csv=None,
        matlab_error="not installed",
        port_comparisons=[comparison],
    )
    assert report.port_agreement_passed is True
    assert report.matlab_agreement_passed is None
    data = report.to_dict()
    assert data["matlab_status"] == "not_run"
    assert data["matlab_available"] is False
    assert data["port_agreement_passed"] is True
    assert data["matlab_agreement_passed"] is None
    assert data["port_comparisons"][0]["passed"] is True
    assert json.dumps(data)


# ---------------------------------------------------------------------------
# full E15 workflow on the real dataset
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.requires_data
def test_run_cross_language_validation_real_data(config, dataset, tmp_path):
    if shutil.which("matlab") or shutil.which("MATLAB"):
        pytest.skip("MATLAB is installed; the not-run assertion would not hold")
    report = run_cross_language_validation(dataset, config, tmp_path)
    assert report.matlab_available is False
    assert report.matlab_executable is None
    assert report.matlab_status == "not_run"
    assert report.matlab_error and "MATLAB is not installed" in report.matlab_error
    assert len(report.port_comparisons) >= 5
    assert all(comparison.passed for comparison in report.port_comparisons)
    assert report.port_agreement_passed is True
    assert report.matlab_agreement_passed is None
    assert report.expected_test_ids > 0
    assert report.matched_matlab_test_ids == 0
    assert report.inputs_mat and Path(report.inputs_mat).is_file()
    assert (tmp_path / "cross_language_report.json").is_file()
    payload = json.loads((tmp_path / "cross_language_report.json").read_text(encoding="utf-8"))
    assert payload["matlab_status"] == "not_run"
    assert len(payload["port_comparisons"]) == len(report.port_comparisons)
    names = {comparison.name for comparison in report.port_comparisons}
    assert "hha_band_db (port vs production)" in names
    assert "reoig_db (port vs production)" in names
    assert "ptpe_hha_db (port vs production)" in names
    assert any("gain_db" in name for name in names)



@pytest.mark.slow
@pytest.mark.requires_data
def test_run_cross_language_validation_with_simulated_matlab_csv(
    config, dataset, tmp_path, monkeypatch
):
    """Exercise the MATLAB-comparison branch with a *simulated* MATLAB CSV.

    MATLAB is not installed here.  This test feeds a synthetic reference CSV
    (constructed from the Python expected values) into the comparison plumbing
    to verify parsing, matching and tolerance handling.  It is a unit test of
    the branch only and does **not** claim that MATLAB was executed; the
    report's ``matlab_status`` simply records that a reference CSV was
    consumed.
    """
    expected = cross_language.expected_dataset_values(dataset, config)
    monkeypatch.setattr(
        cross_language, "matlab_executable", lambda: "/usr/bin/fake-matlab"
    )

    def fake_export(repo_root_arg, *, timeout_s=600.0):
        csv_path = tmp_path / "fake_matlab_reference.csv"
        frame = expected.copy()
        frame["value"] = frame["expected_python"]
        frame["unit"] = "dB"
        frame[["test_id", "quantity", "value", "unit"]].to_csv(csv_path, index=False)
        return csv_path, None

    monkeypatch.setattr(cross_language, "run_matlab_export", fake_export)
    report = run_cross_language_validation(dataset, config, tmp_path / "out")
    assert report.matlab_available is True
    assert report.matlab_status == "executed"
    assert report.matlab_comparisons
    assert all(comparison.passed for comparison in report.matlab_comparisons)
    assert report.matched_matlab_test_ids == len(expected)
    assert report.matlab_agreement_passed is True

    def fake_export_missing_columns(repo_root_arg, *, timeout_s=600.0):
        csv_path = tmp_path / "bad_matlab_reference.csv"
        pd.DataFrame({"test_id": ["x"], "quantity": ["gain_db"], "value": [1.0]}).to_csv(
            csv_path, index=False
        )
        return csv_path, None

    monkeypatch.setattr(
        cross_language, "run_matlab_export", fake_export_missing_columns
    )
    bad_report = run_cross_language_validation(dataset, config, tmp_path / "out2")
    assert bad_report.matlab_status == "not_run"
    assert bad_report.matlab_error is not None
    assert "missing required columns" in bad_report.matlab_error


# ---------------------------------------------------------------------------
# input contract of the DSP estimators used by the cross-language validation
# ---------------------------------------------------------------------------
def test_dsp_estimator_input_contract():
    """The estimators exporting/consuming E15 signals must reject invalid input.

    These checks guard the validation layer against silently consuming
    malformed signals (e.g. mismatched lengths or ambiguous method selection).
    """
    from acousticbench.dsp.metrics import (
        estimate_filter_response,
        estimate_gain_db,
        estimate_snr_db,
        estimate_thd,
        estimate_thd_plus_n,
    )
    from acousticbench.dsp.signals import add_awgn, log_sweep, multi_tone, sine

    fs = 48000.0
    signal = sine(1000.0, fs=fs, duration_s=0.1, amplitude=0.1)

    # Gain: tone_hz and band_hz are mutually exclusive (neither -> RMS method).
    assert estimate_gain_db(signal, signal, fs).method == "rms"
    with pytest.raises(ValueError):
        estimate_gain_db(signal, signal, fs, tone_hz=1000.0, band_hz=(500.0, 2000.0))
    with pytest.raises(ValueError, match="equal length"):
        estimate_gain_db(signal, signal[:-100], fs, tone_hz=1000.0)
    with pytest.raises(ValueError, match="band_hz"):
        estimate_gain_db(signal, signal, fs, band_hz=(2000.0, 500.0))
    with pytest.raises(ValueError, match="Nyquist"):
        estimate_gain_db(signal, signal, fs, band_hz=(500.0, 30000.0))

    # SNR: invalid method and undefined noise power.
    with pytest.raises(ValueError, match="method"):
        estimate_snr_db(signal, fs, 1000.0, method="banana")
    with pytest.raises(Exception):
        estimate_snr_db(np.zeros(4800), fs, 1000.0, method="residual")

    # THD: harmonic count validation and Nyquist limit.
    with pytest.raises(ValueError, match="n_harmonics"):
        estimate_thd(signal, fs, 1000.0, n_harmonics=0)
    with pytest.raises(ValueError, match="n_harmonics"):
        estimate_thd(signal, fs, 1000.0, n_harmonics=True)
    with pytest.raises(ValueError, match="Nyquist"):
        estimate_thd(signal, fs, 1000.0, n_harmonics=50)
    with pytest.raises(Exception):
        estimate_thd_plus_n(np.zeros(4800), fs, 1000.0)

    # Filter response: mismatched lengths / invalid FFT size.
    with pytest.raises(ValueError, match="equal length"):
        estimate_filter_response(signal, signal[:-100], fs)
    with pytest.raises(ValueError, match="n_fft"):
        estimate_filter_response(signal, signal, fs, n_fft=3)
    with pytest.raises(ValueError, match="n_fft"):
        estimate_filter_response(signal, signal, fs, n_fft=True)

    # Signal generators: documented validation of their arguments.
    with pytest.raises(ValueError, match="Nyquist"):
        sine(24000.0, fs, 0.1)
    with pytest.raises(ValueError, match="duration_s"):
        sine(1000.0, fs, 0.0)
    with pytest.raises(ValueError, match="amplitude"):
        sine(1000.0, fs, 0.1, amplitude=float("nan"))
    with pytest.raises(ValueError, match="one-dimensional"):
        add_awgn(np.zeros((2, 10)), 10.0)
    with pytest.raises(ValueError, match="silent"):
        add_awgn(np.zeros(100), 10.0)
    with pytest.raises(ValueError, match="snr_db"):
        add_awgn(np.ones(100), float("nan"))
    with pytest.raises(ValueError, match="freqs_hz"):
        multi_tone([], fs, 0.1)
    with pytest.raises(ValueError, match="amplitudes"):
        multi_tone([1000.0, 2000.0], fs, 0.1, amplitudes=[1.0])
    with pytest.raises(ValueError, match="f_end_hz"):
        log_sweep(1000.0, 100.0, 0.1, fs)
    with pytest.raises(ValueError, match="duration_s"):
        log_sweep(100.0, 1000.0, 0.0, fs)
