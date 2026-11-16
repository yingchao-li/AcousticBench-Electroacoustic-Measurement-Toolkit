"""E11 — SNR Estimation.

Evaluates tone-in-noise SNR estimation on all 250 synthetic SNR cases.  The
exact additive noise waveform is known, so the ground-truth SNR is computed
from the generated signals rather than from the requested parameter.

Two estimators are compared:

* ``residual`` — fits and removes the tone in the time domain, then measures
  the residual power (exact for any noise colour);
* ``psd`` — integrates the Welch noise density outside the tone and scales it
  to the analysis bandwidth (best for locally flat white noise; a bias for
  pink noise is expected and reported).

The preset target (≤ 0.5 dB) is evaluated in the documented reference condition
(white noise, 10–40 dB SNR).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp.metrics import estimate_snr_db
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.synthetic_common import (
    build_suite,
    category_cases,
    error_summary,
)
from acousticbench.report import figures as viz
from acousticbench.synthetic import render_case

CODE = "E11"
TITLE = "SNR Estimation"
DESCRIPTION = (
    "SNR estimation on 250 synthetic tone-in-noise cases with exact noise waveforms and "
    "two independent estimators."
)


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    warnings: list[str] = []
    cases = build_suite(config)
    snr_cases = category_cases(cases, "snr")

    rows = []
    for case in snr_cases:
        data = render_case(case)
        tone_hz = float(data.ground_truth["tone_hz"])
        truth = float(data.ground_truth["snr_db"])
        residual = estimate_snr_db(data.output, data.fs_hz, tone_hz, method="residual")
        psd = estimate_snr_db(data.output, data.fs_hz, tone_hz, method="psd")
        rows.append(
            {
                "case_id": case.case_id,
                "tone_hz": tone_hz,
                "noise_color": str(data.ground_truth["noise_color"]),
                "input_level_dbfs": float(data.ground_truth["input_level_dbfs"]),
                "snr_db_true": truth,
                "snr_db_estimated_residual": residual.snr_db,
                "error_residual_db": residual.snr_db - truth,
                "snr_db_estimated_psd": psd.snr_db,
                "error_psd_db": psd.snr_db - truth,
                "is_reference_condition": bool(case.is_reference_condition),
            }
        )
    results = pd.DataFrame(rows)
    reference = results.loc[results["is_reference_condition"]]
    target = float(config.synthetic.targets.get("snr_error_db", 0.5))
    reference_residual = error_summary(reference["error_residual_db"], target, unit="dB")
    reference_psd = error_summary(reference["error_psd_db"], target, unit="dB")
    full_residual = error_summary(results["error_residual_db"], target, unit="dB")
    by_color = {}
    for color, group in results.groupby("noise_color"):
        by_color[str(color)] = {
            "residual": error_summary(group["error_residual_db"], target, unit="dB"),
            "psd": error_summary(group["error_psd_db"], target, unit="dB"),
        }

    metrics = {
        "n_cases": int(len(results)),
        "n_reference_cases": int(len(reference)),
        "target_db": target,
        "reference_condition": config.synthetic.reference_conditions.get("snr"),
        "reference_residual_summary": reference_residual,
        "reference_psd_summary": reference_psd,
        "full_range_residual_summary": full_residual,
        "by_noise_color": by_color,
        "target_met_in_reference_condition": reference_residual["target_met"],
        "psd_target_met_in_reference_condition": reference_psd["target_met"],
        "note": (
            "The residual estimator is primary; the PSD estimator is reported to expose "
            "the expected bias for non-flat (pink) noise."
        ),
    }
    if not reference_residual["target_met"]:
        warnings.append(
            f"SNR target {target} dB not met by the residual estimator: max |error| "
            f"{reference_residual['max_abs_error']:.4f} dB."
        )
    pink = results.loc[results["noise_color"] == "pink"]
    if len(pink):
        pink_psd_bias = float(np.nanmedian(pink["error_psd_db"]))
        if abs(pink_psd_bias) > target:
            warnings.append(
                f"PSD SNR estimator shows a {pink_psd_bias:+.2f} dB median bias for pink "
                "noise, as expected for a locally-flat-noise assumption; the residual "
                "estimator is unbiased."
            )

    figures = {}
    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    ax.scatter(
        results["snr_db_true"],
        results["snr_db_estimated_residual"],
        c=np.where(results["is_reference_condition"], "#1f77b4", "#ff7f0e"),
        s=16,
        alpha=0.85,
    )
    limits = [
        float(min(results["snr_db_true"].min(), results["snr_db_estimated_residual"].min())),
        float(max(results["snr_db_true"].max(), results["snr_db_estimated_residual"].max())),
    ]
    ax.plot(limits, limits, "k--", linewidth=0.8)
    ax.set_xlabel("True SNR [dB]")
    ax.set_ylabel("Estimated SNR (residual) [dB]")
    ax.set_title("SNR estimation: residual estimator")
    figures["snr_scatter"] = fig

    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    for color, group in results.groupby("noise_color"):
        ax.scatter(
            group["snr_db_true"],
            group["error_psd_db"],
            s=14,
            alpha=0.7,
            label=f"PSD, {color}",
        )
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.axhspan(-target, target, color="#27ae60", alpha=0.08, label=f"target ±{target} dB")
    ax.set_xlabel("True SNR [dB]")
    ax.set_ylabel("SNR error (PSD) [dB]")
    ax.set_title("PSD estimator error by noise colour")
    ax.legend(frameon=False, fontsize=7)
    figures["snr_psd_by_color"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    bins = np.linspace(
        -max(0.1, np.max(np.abs(results["error_residual_db"])) * 1.2),
        max(0.1, np.max(np.abs(results["error_residual_db"])) * 1.2),
        41,
    )
    ax.hist(
        reference["error_residual_db"], bins=bins, color="#1f77b4", alpha=0.8, label="reference (residual)"
    )
    ax.hist(
        reference["error_psd_db"], bins=bins, color="#2ca02c", alpha=0.5, label="reference (PSD)"
    )
    ax.axvline(target, color="red", linestyle="--", linewidth=0.9)
    ax.axvline(-target, color="red", linestyle="--", linewidth=0.9)
    ax.set_xlabel("SNR error [dB]")
    ax.set_ylabel("Number of cases")
    ax.set_title("SNR error distribution (reference condition)")
    ax.legend(frameon=False)
    figures["snr_error_histogram"] = fig

    narrative = (
        "Using the exact noise waveform as ground truth, the residual estimator recovers the "
        f"SNR to within {reference_residual['max_abs_error']:.3g} dB in the reference "
        f"condition (target {target} dB), whereas the PSD estimator is accurate for white "
        "noise but biased for pink noise. Reporting both makes the estimator's validity "
        "domain explicit rather than hiding it."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"snr_case_results": results},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
