"""E15 — MATLAB–Python Agreement.

Executes an independent numerical agreement check between the production Python
implementation and a MATLAB-transcribed Python reference implementation, and
prepares/consumes the MATLAB side of the comparison.

**Status in this environment:** MATLAB is not installed.  The MATLAB toolkit,
GUI and unit tests are provided under ``matlab/``, but they are explicitly
*not executed/verified* (see ``docs/matlab_status.md``).  E15 therefore reports:

* port-vs-production agreement, which is executed now and fully reproducible;
* MATLAB-vs-Python agreement, which is recorded as ``not_run`` with the reason.

No MATLAB result is fabricated.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.report import figures as viz
from acousticbench.validation.cross_language import (
    expected_dataset_values,
    run_cross_language_validation,
)

CODE = "E15"
TITLE = "MATLAB-Python Agreement"
DESCRIPTION = (
    "Independent MATLAB-transcribed Python port vs production Python, plus the prepared "
    "MATLAB cross-language export (MATLAB side not executed here)."
)


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    dataset = context.dataset
    output_dir = config.results_dir / "validation"
    report = run_cross_language_validation(dataset, config, output_dir)
    warnings: list[str] = []
    if not report.matlab_available:
        warnings.append(
            "MATLAB is not installed: the MATLAB-side numerical agreement was NOT executed. "
            "MATLAB code, GUI and tests are provided but unverified (docs/matlab_status.md). "
            "The MATLAB input file and CSV contract are nevertheless generated under "
            "results/validation/ so the comparison can be run elsewhere."
        )
    elif report.matlab_error:
        warnings.append(f"MATLAB execution problem: {report.matlab_error}")

    port_frame = pd.DataFrame(
        [comparison.to_dict() for comparison in report.port_comparisons]
    )
    matlab_frame = pd.DataFrame(
        [comparison.to_dict() for comparison in report.matlab_comparisons]
    )
    if port_frame.empty:  # pragma: no cover - defensive
        warnings.append("Port-vs-production comparison produced no rows.")

    metrics: dict[str, object] = {
        "matlab_available": report.matlab_available,
        "matlab_executable": report.matlab_executable,
        "matlab_status": report.matlab_status,
        "matlab_error": report.matlab_error,
        "port_agreement_passed": report.port_agreement_passed,
        "port_n_comparisons": int(len(port_frame)),
        "port_comparison_max_abs_diff": {
            str(row.name): float(row.max_abs_diff)
            for row in port_frame.itertuples()
            if np.isfinite(row.max_abs_diff)
        },
        "port_comparison_tolerances": {
            str(row.name): float(row.tolerance) for row in port_frame.itertuples()
        },
        "matlab_agreement_passed": report.matlab_agreement_passed,
        "matlab_n_comparisons": int(len(matlab_frame)),
        "matlab_matched_test_ids": report.matched_matlab_test_ids,
        "expected_test_ids": report.expected_test_ids,
        "matlab_inputs_mat": report.inputs_mat,
        "matlab_reference_csv": report.matlab_reference_csv,
        "verification_statement": (
            "Port-vs-production agreement executed in Python. MATLAB execution NOT performed: "
            "MATLAB is absent from this environment."
            if not report.matlab_available
            else "MATLAB execution attempted; see matlab_status."
        ),
    }

    figures = {}
    if not port_frame.empty:
        ordered = port_frame.sort_values("max_abs_diff")
        fig, ax = plt.subplots(figsize=(7.4, max(2.6, 0.4 * len(ordered) + 1.0)))
        y = np.arange(len(ordered))
        ax.barh(y, ordered["max_abs_diff"], color="#1f77b4")
        ax.set_yticks(y, ordered["name"], fontsize=7)
        ax.set_xscale("log")
        ax.axvline(1e-9, color="grey", linestyle=":", linewidth=0.8)
        ax.set_xlabel("maximum |difference| between implementations")
        ax.set_title("Independent MATLAB-transcribed port vs. production implementation")
        figures["port_agreement"] = fig

    if report.matlab_comparisons:
        frame = pd.DataFrame([comparison.to_dict() for comparison in report.matlab_comparisons])
        fig, ax = plt.subplots(figsize=(7.0, 3.2))
        ax.bar(frame["name"], frame["max_abs_diff"], color="#27ae60")
        ax.set_ylabel("maximum |difference|")
        ax.set_title("MATLAB vs. Python agreement")
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        figures["matlab_agreement"] = fig

    narrative = (
        "The production Python implementation and an independently written MATLAB-transcribed "
        "Python port agree to numerical precision on real data (band levels, REOIG, PTPE) and "
        "on synthetic gain/SNR/THD signals. The MATLAB input file and the exact CSV contract "
        "are generated so that `matlab/run_cross_language_export.m` can be run on a machine "
        "with MATLAB; here that step is marked NOT RUN because MATLAB is unavailable. This "
        "distinction is deliberate: port agreement demonstrates algorithmic consistency, not "
        "execution of the MATLAB code."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "port_comparisons": port_frame,
            "matlab_comparisons": matlab_frame,
            "expected_dataset_values": expected_dataset_values(dataset, config),
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
