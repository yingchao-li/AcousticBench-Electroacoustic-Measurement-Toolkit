"""MATLAB ↔ Python cross-language numerical validation.

Two independent questions are answered and kept strictly separate:

1. **Does the independent MATLAB-transcribed Python port reproduce the
   production Python implementation?**  This is executed *now*, on real data
   and on synthetic signals, and reported with explicit tolerances.
2. **Does the actual MATLAB implementation reproduce the Python results?**
   This requires MATLAB.  The input MAT-file and the exact CSV contract are
   produced/consumed here; when MATLAB is unavailable the status is recorded as
   ``not_run`` with the reason, and no MATLAB result is ever fabricated.

The report is therefore honest about what was executed and what remains
pending.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import scipy.io

from acousticbench.config import Config
from acousticbench.data.dataset import AcousticDataset
from acousticbench.dsp.metrics import estimate_gain_db, estimate_snr_db, estimate_thd
from acousticbench.measurements.ptpe import ptpe_hha_band_levels, ptpe_threshold_db
from acousticbench.measurements.transfer import hha_band_levels, reoig_band_levels
from acousticbench.synthetic import render_case
from acousticbench.synthetic.cases import build_cases
from acousticbench.stats.bands import bands_from_config
from acousticbench.types import Condition, Probe
from acousticbench.validation import matlab_port as port

__all__ = [
    "AgreementComparison",
    "CrossLanguageReport",
    "expected_dataset_values",
    "export_matlab_inputs",
    "matlab_executable",
    "run_cross_language_validation",
    "run_matlab_export",
]


@dataclass(frozen=True)
class AgreementComparison:
    """Agreement of one quantity between two implementations."""

    name: str
    unit: str
    n: int
    max_abs_diff: float
    median_abs_diff: float
    tolerance: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrossLanguageReport:
    """Complete cross-language validation report."""

    matlab_available: bool
    matlab_executable: str | None
    matlab_status: str  # executed | not_run
    matlab_reference_csv: str | None
    matlab_error: str | None
    matlab_comparisons: list[AgreementComparison] = field(default_factory=list)
    port_comparisons: list[AgreementComparison] = field(default_factory=list)
    inputs_mat: str | None = None
    expected_test_ids: int = 0
    matched_matlab_test_ids: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def port_agreement_passed(self) -> bool:
        return all(comparison.passed for comparison in self.port_comparisons)

    @property
    def matlab_agreement_passed(self) -> bool | None:
        if not self.matlab_comparisons:
            return None
        return all(comparison.passed for comparison in self.matlab_comparisons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matlab_available": self.matlab_available,
            "matlab_executable": self.matlab_executable,
            "matlab_status": self.matlab_status,
            "matlab_reference_csv": self.matlab_reference_csv,
            "matlab_error": self.matlab_error,
            "matlab_comparisons": [comparison.to_dict() for comparison in self.matlab_comparisons],
            "port_comparisons": [comparison.to_dict() for comparison in self.port_comparisons],
            "inputs_mat": self.inputs_mat,
            "expected_test_ids": self.expected_test_ids,
            "matched_matlab_test_ids": self.matched_matlab_test_ids,
            "port_agreement_passed": self.port_agreement_passed,
            "matlab_agreement_passed": self.matlab_agreement_passed,
            "notes": list(self.notes),
        }

    def save(self, output_dir: str | Path) -> Path:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "cross_language_report.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


def matlab_executable() -> str | None:
    """Return the MATLAB executable path if MATLAB is installed."""
    for name in ("matlab", "MATLAB"):
        executable = shutil.which(name)
        if executable:
            return executable
    return None


def _select_reference_cases(config: Config) -> list:
    cases = build_cases(
        n_cases=int(config.synthetic.n_cases),
        seed=int(config.synthetic.seed),
        fs_hz=int(config.synthetic.fs_hz),
    )
    selected = []
    per_category_reference = {"gain": 5, "snr": 5, "thd": 5, "frequency_response": 3}
    per_category_extra = {"gain": 2, "snr": 2, "thd": 2, "frequency_response": 1}
    for category, n_reference in per_category_reference.items():
        reference = [c for c in cases if c.category == category and c.is_reference_condition]
        selected.extend(reference[:n_reference])
        extra = [c for c in cases if c.category == category and not c.is_reference_condition]
        selected.extend(extra[: per_category_extra[category]])
    return selected


def export_matlab_inputs(
    dataset: AcousticDataset,  # noqa: ARG001 - part of the public contract
    config: Config,
    output_dir: str | Path,
) -> tuple[Path, pd.DataFrame]:
    """Write ``matlab_inputs.mat`` and the expected-value table.

    The MAT-file contains parallel arrays (``ids``, ``category``, ``fs``,
    ``input``, ``output``, ``clean_reference``, ``tone_hz``, ``gain_db``,
    ``snr_db``, ``thd_percent``, ``freq_start_hz``, ``freq_end_hz``) because
    they are the most robust representation across MATLAB and Octave.
    """
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cases = _select_reference_cases(config)
    signals = [render_case(case) for case in cases]
    n_cases = len(signals)
    n_samples = min(signal.input.size for signal in signals)
    ids = np.empty((n_cases, 1), dtype=object)
    categories = np.empty((n_cases, 1), dtype=object)
    fs = np.zeros(n_cases)
    input_matrix = np.zeros((n_samples, n_cases))
    output_matrix = np.zeros((n_samples, n_cases))
    clean_matrix = np.zeros((n_samples, n_cases))
    tone_hz = np.full(n_cases, np.nan)
    gain_db = np.full(n_cases, np.nan)
    snr_db = np.full(n_cases, np.nan)
    thd_percent = np.full(n_cases, np.nan)
    freq_start = np.full(n_cases, np.nan)
    freq_end = np.full(n_cases, np.nan)
    expected_rows = []
    for index, data in enumerate(signals):
        ids[index, 0] = data.case.case_id
        categories[index, 0] = data.case.category
        fs[index] = data.fs_hz
        input_matrix[:, index] = data.input[:n_samples]
        output_matrix[:, index] = data.output[:n_samples]
        clean_matrix[:, index] = data.clean_reference[:n_samples]
        truth = data.ground_truth
        if data.case.category == "gain":
            tone_hz[index] = float(truth["tone_hz"])
            gain_db[index] = float(truth["gain_db"])
            estimate = estimate_gain_db(
                data.input, data.output, data.fs_hz, tone_hz=float(truth["tone_hz"])
            )
            expected_rows.append(
                {
                    "test_id": data.case.case_id,
                    "quantity": "gain_db",
                    "unit": "dB",
                    "expected_python": estimate.gain_db,
                    "ground_truth": float(truth["gain_db"]),
                }
            )
        elif data.case.category == "snr":
            tone_hz[index] = float(truth["tone_hz"])
            snr_db[index] = float(truth["snr_db"])
            estimate = estimate_snr_db(
                data.output, data.fs_hz, float(truth["tone_hz"]), method="residual"
            )
            expected_rows.append(
                {
                    "test_id": data.case.case_id,
                    "quantity": "snr_db",
                    "unit": "dB",
                    "expected_python": estimate.snr_db,
                    "ground_truth": float(truth["snr_db"]),
                }
            )
        elif data.case.category == "thd":
            tone_hz[index] = float(truth["tone_hz"])
            thd_percent[index] = float(truth["thd_percent"])
            estimate = estimate_thd(
                data.output,
                data.fs_hz,
                float(truth["tone_hz"]),
                n_harmonics=int(truth["n_harmonics"]),
            )
            expected_rows.append(
                {
                    "test_id": data.case.case_id,
                    "quantity": "thd_percent",
                    "unit": "%",
                    "expected_python": estimate.thd_percent,
                    "ground_truth": float(truth["thd_percent"]),
                }
            )
        else:
            freq_start[index] = float(truth["f_start_hz"])
            freq_end[index] = float(truth["f_end_hz"])
            expected_rows.append(
                {
                    "test_id": data.case.case_id,
                    "quantity": "fr_mae_db",
                    "unit": "dB",
                    "expected_python": np.nan,
                    "ground_truth": np.nan,
                }
            )
    mat_path = directory / "matlab_inputs.mat"
    scipy.io.savemat(
        mat_path,
        {
            "ids": ids,
            "category": categories,
            "fs": fs,
            "input": input_matrix,
            "output": output_matrix,
            "clean_reference": clean_matrix,
            "tone_hz": tone_hz,
            "gain_db": gain_db,
            "snr_db": snr_db,
            "thd_percent": thd_percent,
            "freq_start_hz": freq_start,
            "freq_end_hz": freq_end,
            "contract": "AcousticBench E15; see src/acousticbench/validation/cross_language.py",
        },
        do_compression=True,
    )
    expected = pd.DataFrame(expected_rows)
    expected.to_csv(directory / "expected_synthetic_values.csv", index=False)
    return mat_path, expected


def run_matlab_export(
    repo_root: str | Path,
    *,
    timeout_s: float = 600.0,
) -> tuple[Path | None, str | None]:
    """Run ``matlab/run_cross_language_export.m`` unattended.

    Returns ``(csv_path, error_message)``.  If MATLAB is unavailable the
    function returns ``(None, reason)`` and never raises.
    """
    executable = matlab_executable()
    if executable is None:
        return None, "MATLAB executable not found on PATH; MATLAB-side comparison was not executed."
    root = Path(repo_root).resolve()
    script = root / "matlab" / "run_cross_language_export.m"
    if not script.is_file():
        return None, f"MATLAB export script not found: {script}"
    csv_path = root / "results" / "validation" / "matlab_reference.csv"
    command = [
        executable,
        "-batch",
        f"cd('{root.as_posix()}'); run('matlab/run_cross_language_export.m');",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, f"MATLAB execution failed: {type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = "\n".join(message[-5:]) if message else "no output"
        return None, f"MATLAB exited with code {completed.returncode}: {tail}"
    if not csv_path.is_file():
        return None, f"MATLAB finished but did not create {csv_path}"
    return csv_path, None


# ---------------------------------------------------------------------------
# Agrement comparisons
# ---------------------------------------------------------------------------
def _compare_series(
    name: str,
    expected: pd.Series,
    actual: pd.Series,
    *,
    tolerance: float,
    unit: str,
) -> AgreementComparison:
    joined = pd.concat([expected.rename("expected"), actual.rename("actual")], axis=1, join="inner")
    joined = joined.dropna()
    if joined.empty:
        return AgreementComparison(name, unit, 0, float("nan"), float("nan"), tolerance, False)
    differences = np.abs(joined["expected"].to_numpy(dtype=float) - joined["actual"].to_numpy(dtype=float))
    return AgreementComparison(
        name=name,
        unit=unit,
        n=int(len(joined)),
        max_abs_diff=float(np.max(differences)),
        median_abs_diff=float(np.median(differences)),
        tolerance=float(tolerance),
        passed=bool(np.max(differences) <= float(tolerance)),
    )


def _tolerances(config: Config) -> dict[str, float]:
    params = config.experiment_params("E15")
    defaults = {"magnitude_db": 0.01, "phase_deg": 0.01, "level_db": 0.01}
    configured = dict(defaults)
    configured.update({str(k): float(v) for k, v in dict(params.get("tolerances", {})).items()})
    return {
        "band_db": configured.get("level_db", 0.01),
        "gain_db": configured.get("magnitude_db", 0.01),
        "snr_db": 0.05,
        "thd_percent": 0.01,
        "fr_mae_db": 0.5,
    }


def _band_center_label(value: float) -> str:
    return f"{float(value):g}"


def _expected_dataset_values(
    dataset: AcousticDataset, config: Config
) -> pd.DataFrame:
    bands = bands_from_config(config)
    rows: list[dict[str, Any]] = []
    hha = hha_band_levels(dataset, bands, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT)
    hha = hha.loc[hha["valid"]]
    hha_median = (
        hha.groupby(["device_code", "band_center_hz"], as_index=False)["level_db"].median()
    )
    for row in hha_median.itertuples():
        rows.append(
            {
                "test_id": f"hha_band:{int(row.device_code)}:{_band_center_label(row.band_center_hz)}",
                "quantity": "hha_band_db",
                "unit": "dB",
                "expected_python": float(row.level_db),
            }
        )
    reoig = reoig_band_levels(
        dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    reoig = reoig.loc[reoig["valid"]]
    reoig_median = (
        reoig.groupby(["family", "band_center_hz"], as_index=False)["reoig_db"].median()
    )
    for row in reoig_median.itertuples():
        rows.append(
            {
                "test_id": f"reoig_band:{row.family}:{_band_center_label(row.band_center_hz)}",
                "quantity": "reoig_db",
                "unit": "dB",
                "expected_python": float(row.reoig_db),
            }
        )
    ptpe = ptpe_hha_band_levels(dataset, bands)
    ptpe = ptpe.loc[ptpe["valid"]]
    ptpe_median = (
        ptpe.groupby(["family", "band_center_hz"], as_index=False)["ptpe_db"].median()
    )
    for row in ptpe_median.itertuples():
        rows.append(
            {
                "test_id": f"ptpe_hha_band:{row.family}:{_band_center_label(row.band_center_hz)}",
                "quantity": "ptpe_hha_db",
                "unit": "dB",
                "expected_python": float(row.ptpe_db),
            }
        )
    threshold = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(threshold.freq_hz - 125.0)))
    values = threshold.masked[index]  # families × subjects × reinsertions
    for family_index, device in enumerate(threshold.devices):
        rows.append(
            {
                "test_id": f"delta_t_125:{device.family}",
                "quantity": "delta_t_db",
                "unit": "dB",
                "expected_python": float(np.nanmedian(values[family_index])),
            }
        )
    return pd.DataFrame(rows)


def expected_dataset_values(dataset: AcousticDataset, config: Config) -> pd.DataFrame:
    """Public wrapper returning the expected dataset reference values."""
    return _expected_dataset_values(dataset, config)


def _port_comparisons(
    dataset: AcousticDataset,
    config: Config,
    expected_synthetic: pd.DataFrame,
) -> list[AgreementComparison]:
    bands = bands_from_config(config)
    tolerances = _tolerances(config)
    comparisons: list[AgreementComparison] = []

    expected_dataset = _expected_dataset_values(dataset, config)
    expected_dataset = expected_dataset.set_index("test_id")["expected_python"]

    hha_port = port.hha_band_levels_port(dataset, bands)
    hha_port_series = pd.Series(
        hha_port["median_db"].to_numpy(),
        index=[
            f"hha_band:{int(row.device_code)}:{_band_center_label(row.band_center_hz)}"
            for row in hha_port.itertuples()
        ],
    )
    comparisons.append(
        _compare_series(
            "hha_band_db (port vs production)",
            expected_dataset.loc[expected_dataset.index.str.startswith("hha_band:")],
            hha_port_series,
            tolerance=tolerances["band_db"],
            unit="dB",
        )
    )

    reoig_port = port.reoig_band_levels_port(dataset, bands)
    reoig_port_series = pd.Series(
        reoig_port["median_db"].to_numpy(),
        index=[
            f"reoig_band:{row.family}:{_band_center_label(row.band_center_hz)}"
            for row in reoig_port.itertuples()
        ],
    )
    comparisons.append(
        _compare_series(
            "reoig_db (port vs production)",
            expected_dataset.loc[expected_dataset.index.str.startswith("reoig_band:")],
            reoig_port_series,
            tolerance=tolerances["band_db"],
            unit="dB",
        )
    )

    ptpe_port = port.ptpe_hha_band_levels_port(dataset, bands)
    ptpe_port_series = pd.Series(
        ptpe_port["median_db"].to_numpy(),
        index=[
            f"ptpe_hha_band:{row.family}:{_band_center_label(row.band_center_hz)}"
            for row in ptpe_port.itertuples()
        ],
    )
    comparisons.append(
        _compare_series(
            "ptpe_hha_db (port vs production)",
            expected_dataset.loc[expected_dataset.index.str.startswith("ptpe_hha_band:")],
            ptpe_port_series,
            tolerance=tolerances["band_db"],
            unit="dB",
        )
    )

    # Synthetic DSP port comparisons.
    cases = _select_reference_cases(config)
    gain_rows = []
    snr_rows = []
    thd_rows = []
    for case in cases:
        data = render_case(case)
        truth = data.ground_truth
        if case.category == "gain":
            production = estimate_gain_db(
                data.input, data.output, data.fs_hz, tone_hz=float(truth["tone_hz"])
            ).gain_db
            reference = port.gain_db_port(
                data.input, data.output, data.fs_hz, float(truth["tone_hz"])
            )
            gain_rows.append((case.case_id, production, reference))
        elif case.category == "snr":
            production = estimate_snr_db(
                data.output, data.fs_hz, float(truth["tone_hz"]), method="residual"
            ).snr_db
            reference = port.snr_db_port(data.output, data.fs_hz, float(truth["tone_hz"]))
            snr_rows.append((case.case_id, production, reference))
        elif case.category == "thd":
            production = estimate_thd(
                data.output,
                data.fs_hz,
                float(truth["tone_hz"]),
                n_harmonics=int(truth["n_harmonics"]),
            ).thd_percent
            reference = port.thd_percent_port(
                data.output, data.fs_hz, float(truth["tone_hz"])
            )
            thd_rows.append((case.case_id, production, reference))
    for name, rows, tolerance, unit in (
        ("gain_db (port vs production)", gain_rows, tolerances["gain_db"], "dB"),
        ("snr_db (port vs production)", snr_rows, tolerances["snr_db"], "dB"),
        ("thd_percent (port vs production)", thd_rows, tolerances["thd_percent"], "pp"),
    ):
        if not rows:
            continue
        expected = pd.Series([row[1] for row in rows], index=[row[0] for row in rows])
        actual = pd.Series([row[2] for row in rows], index=[row[0] for row in rows])
        comparisons.append(
            _compare_series(name, expected, actual, tolerance=tolerance, unit=unit)
        )
    return comparisons


def run_cross_language_validation(
    dataset: AcousticDataset,
    config: Config,
    output_dir: str | Path,
) -> CrossLanguageReport:
    """Run the full E15 validation workflow and return a report."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    tolerances = _tolerances(config)
    mat_path, expected_synthetic = export_matlab_inputs(dataset, config, directory)
    expected_dataset = _expected_dataset_values(dataset, config)
    expected_all = pd.concat([expected_synthetic, expected_dataset], ignore_index=True)

    expected_all.to_csv(directory / "expected_values.csv", index=False)
    port_comparisons = _port_comparisons(dataset, config, expected_synthetic)

    executable = matlab_executable()
    matlab_csv: Path | None = None
    matlab_error: str | None = None
    matlab_status = "not_run"
    matlab_comparisons: list[AgreementComparison] = []
    matched_ids = 0
    if executable is None:
        matlab_error = (
            "MATLAB is not installed in this environment. The MATLAB implementation, GUI and "
            "tests are provided (matlab/) but are explicitly NOT executed/verified here; see "
            "docs/matlab_status.md."
        )
        notes.append("MATLAB-side agreement not executed; only port-vs-production agreement is reported.")
    else:
        matlab_csv, matlab_error = run_matlab_export(
            config.root,
            timeout_s=float(config.experiment_params("E15").get("matlab_timeout_s", 600)),
        )
        if matlab_csv is not None:
            matlab_status = "executed"
            reference = pd.read_csv(matlab_csv)
            required = {"test_id", "quantity", "value", "unit"}
            if not required.issubset(reference.columns):
                matlab_error = f"MATLAB CSV missing required columns: {sorted(required - set(reference.columns))}"
                matlab_status = "not_run"
            else:
                merged = expected_all.merge(
                    reference[["test_id", "quantity", "value"]],
                    on=["test_id", "quantity"],
                    how="inner",
                )
                matched_ids = int(len(merged))
                for quantity, group in merged.groupby("quantity"):
                    tolerance = {
                        "gain_db": tolerances["gain_db"],
                        "snr_db": tolerances["snr_db"],
                        "thd_percent": tolerances["thd_percent"],
                        "fr_mae_db": tolerances["fr_mae_db"],
                        "hha_band_db": tolerances["band_db"],
                        "reoig_db": tolerances["band_db"],
                        "ptpe_hha_db": tolerances["band_db"],
                        "delta_t_db": tolerances["band_db"],
                    }.get(str(quantity), tolerances["band_db"])
                    unit = "%" if quantity == "thd_percent" else "dB"
                    matlab_comparisons.append(
                        _compare_series(
                            f"{quantity} (MATLAB vs Python)",
                            group["expected_python"],
                            group["value"],
                            tolerance=tolerance,
                            unit=unit,
                        )
                    )
                if matched_ids == 0:
                    notes.append(
                        "MATLAB CSV was produced but no test_id matched the Python expected table."
                    )
        else:
            notes.append(f"MATLAB execution failed: {matlab_error}")

    report = CrossLanguageReport(
        matlab_available=executable is not None,
        matlab_executable=executable,
        matlab_status=matlab_status,
        matlab_reference_csv=str(matlab_csv) if matlab_csv else None,
        matlab_error=matlab_error,
        matlab_comparisons=matlab_comparisons,
        port_comparisons=port_comparisons,
        inputs_mat=str(mat_path),
        expected_test_ids=int(len(expected_all)),
        matched_matlab_test_ids=matched_ids,
        notes=notes,
    )
    report.save(directory)
    return report
