"""E12 — Filter Response Estimation.

Evaluates the H1 cross-spectrum frequency-response estimator on 250 synthetic
cases in which the measured signal is produced by a known FIR or IIR filter.
The ground truth is the exact discrete-time filter response, evaluated on the
same logarithmic frequency grid.

The preset target (magnitude MAE ≤ 0.5 dB) is evaluated only on the documented
reference-condition frequency range (sweep 100 Hz–10 kHz, no noise); deep
stop-band frequencies are excluded using the documented 20 dB dynamic-range
mask, because no finite-dynamic-range measurement can resolve them.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp.metrics import estimate_filter_response
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.synthetic_common import (
    build_suite,
    category_cases,
    error_summary,
)
from acousticbench.report import figures as viz
from acousticbench.synthetic import render_case

CODE = "E12"
TITLE = "Filter Response Estimation"
DESCRIPTION = (
    "H1 frequency-response estimation on 250 synthetic sweep cases through known filters, "
    "compared with the exact analytic response."
)


def _estimate_magnitude_mae(data, estimate) -> tuple[float, np.ndarray, np.ndarray]:
    frequencies = np.asarray(data.ground_truth["evaluation_frequencies_hz"], dtype=float)
    truth = np.asarray(data.ground_truth["evaluation_magnitude_db"], dtype=float)
    estimated = np.interp(frequencies, estimate.frequencies_hz, estimate.magnitude_db)
    errors = estimated - truth
    return float(np.mean(np.abs(errors))), errors, frequencies


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    warnings: list[str] = []
    cases = build_suite(config)
    fr_cases = category_cases(cases, "frequency_response")

    rows = []
    example: dict[str, tuple] | None = None
    for case in fr_cases:
        data = render_case(case)
        estimate = estimate_filter_response(data.input, data.output, data.fs_hz)
        mae, errors, frequencies = _estimate_magnitude_mae(data, estimate)
        rows.append(
            {
                "case_id": case.case_id,
                "filter_type": str(data.ground_truth["filter_type"]),
                "cutoff_hz": str(data.ground_truth["cutoff_hz"]),
                "noise_snr_db": data.ground_truth.get("noise_snr_db"),
                "mae_db": mae,
                "max_abs_error_db": float(np.max(np.abs(errors))),
                "n_evaluation_points": int(len(errors)),
                "is_reference_condition": bool(case.is_reference_condition),
            }
        )
        if example is None and case.is_reference_condition:
            example = (data, estimate)
    results = pd.DataFrame(rows)
    reference = results.loc[results["is_reference_condition"]]
    target = float(config.synthetic.targets.get("frequency_response_mae_db", 0.5))
    reference_summary = error_summary(reference["mae_db"], target, unit="dB")
    full_summary = error_summary(results["mae_db"], target, unit="dB")
    by_filter = {
        str(filter_type): error_summary(group["mae_db"], target, unit="dB")
        for filter_type, group in results.groupby("filter_type")
    }
    metrics = {
        "n_cases": int(len(results)),
        "n_reference_cases": int(len(reference)),
        "target_mae_db": target,
        "reference_condition": config.synthetic.reference_conditions.get("frequency_response"),
        "reference_summary": reference_summary,
        "full_parameter_range_summary": full_summary,
        "by_filter_type": by_filter,
        "target_met_in_reference_condition": reference_summary["target_met"],
        "note": (
            "The magnitude error is evaluated on the documented logarithmic evaluation grid "
            "within a 20 dB dynamic range of the pass-band; the phase is estimated but not "
            "scored because absolute delay is not part of the ground truth."
        ),
    }
    if not reference_summary["target_met"]:
        warnings.append(
            f"Frequency-response target {target} dB not met: max MAE "
            f"{reference_summary['max_abs_error']:.4f} dB in the reference condition."
        )
    if full_summary["max_abs_error"] is not None and full_summary["max_abs_error"] > 2.0:
        warnings.append(
            "Some non-reference frequency-response cases exceed 2 dB MAE (noise / short "
            "sweep); they are reported separately from the target evaluation."
        )

    figures = {}
    if example is not None:
        data, estimate = example
        gt_f = np.asarray(data.ground_truth["evaluation_frequencies_hz"], dtype=float)
        gt_m = np.asarray(data.ground_truth["evaluation_magnitude_db"], dtype=float)
        all_f = np.asarray(data.ground_truth["frequencies_hz"], dtype=float)
        all_m = np.asarray(data.ground_truth["magnitude_db"], dtype=float)
        est_m = np.interp(gt_f, estimate.frequencies_hz, estimate.magnitude_db)
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        ax.plot(all_f, all_m, color="#7f7f7f", linewidth=0.9, label="analytic filter response")
        ax.plot(gt_f, est_m, "o", markersize=2.5, color="#d62728", label="H1 estimate")
        ax.set_xscale("log")
        ax.set_xlabel("Frequency [Hz]")
        ax.set_ylabel("Magnitude [dB]")
        ax.set_title(f"Example frequency-response case ({data.case.case_id})")
        ax.legend(frameon=False)
        figures["fr_example"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    span = max(0.1, np.max(np.abs(results["mae_db"])) * 1.1)
    bins = np.linspace(0.0, span, 41)
    ax.hist(reference["mae_db"], bins=bins, color="#1f77b4", alpha=0.8, label="reference")
    ax.hist(
        results.loc[~results["is_reference_condition"], "mae_db"],
        bins=bins,
        color="#ff7f0e",
        alpha=0.5,
        label="wider range",
    )
    ax.axvline(target, color="red", linestyle="--", linewidth=1.0, label=f"target {target} dB")
    ax.set_xlabel("Magnitude MAE [dB]")
    ax.set_ylabel("Number of cases")
    ax.set_title("Frequency-response MAE distribution")
    ax.legend(frameon=False)
    figures["fr_mae_histogram"] = fig

    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    summary_frame = pd.DataFrame(
        [
            {
                "filter_type": filter_type,
                "median_mae_db": summary["median_abs_error"],
                "n": summary["n"],
            }
            for filter_type, summary in by_filter.items()
        ]
    ).sort_values("median_mae_db")
    ax.bar(summary_frame["filter_type"], summary_frame["median_mae_db"], color="#1f77b4")
    ax.axhline(target, color="red", linestyle="--", linewidth=0.9)
    ax.set_ylabel("Median MAE [dB]")
    ax.set_title("Magnitude MAE by filter type")
    figures["fr_mae_by_filter"] = fig

    narrative = (
        "The H1 estimator recovers the magnitude response with a median MAE of "
        f"{reference_summary['median_abs_error']:.3g} dB in the reference condition "
        f"(target {target} dB). The wider range adds sweep bands and noise; those cases are "
        "reported separately. Deep stop bands are excluded by the documented dynamic-range "
        "mask, since a finite-dynamic-range measurement cannot resolve them."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"frequency_response_case_results": results},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
