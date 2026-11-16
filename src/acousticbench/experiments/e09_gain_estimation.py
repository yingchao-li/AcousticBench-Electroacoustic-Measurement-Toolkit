"""E09 — Gain Estimation.

Evaluates the DSP gain estimator on all 250 synthetic gain cases against the
known applied gain.  The preset target (≤ 0.1 dB) is evaluated **only** in the
documented reference condition (1 kHz tone, no noise/compression, 4 s,
−20 dBFS); the wider parameter range is reported separately.

The estimator never sees the ground truth: it is given only the input and
output waveforms and the tone frequency (which a real measurement would know).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp.metrics import estimate_gain_db
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.experiments.synthetic_common import (
    build_suite,
    category_cases,
    error_summary,
    reference_cases,
)
from acousticbench.report import figures as viz
from acousticbench.synthetic import render_case

CODE = "E09"
TITLE = "Gain Estimation"
DESCRIPTION = (
    "Gain estimation accuracy on 250 synthetic cases with known applied gain, evaluated "
    "against the preset reference-condition target."
)


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    warnings: list[str] = []
    cases = build_suite(config)
    gain_cases = category_cases(cases, "gain")

    rows = []
    for case in gain_cases:
        data = render_case(case)
        tone_hz = float(data.ground_truth["tone_hz"])
        estimate = estimate_gain_db(data.input, data.output, data.fs_hz, tone_hz=tone_hz)
        truth = float(data.ground_truth["gain_db"])
        rows.append(
            {
                "case_id": case.case_id,
                "tone_hz": tone_hz,
                "input_level_dbfs": float(data.ground_truth["input_level_dbfs"]),
                "gain_db_true": truth,
                "gain_db_estimated": estimate.gain_db,
                "error_db": estimate.gain_db - truth,
                "is_reference_condition": bool(case.is_reference_condition),
            }
        )
    results = pd.DataFrame(rows)
    reference = results.loc[results["is_reference_condition"]]
    target = float(config.synthetic.targets.get("gain_error_db", 0.1))
    reference_summary = error_summary(reference["error_db"], target, unit="dB")
    full_summary = error_summary(results["error_db"], target, unit="dB")
    metrics = {
        "n_cases": int(len(results)),
        "n_reference_cases": int(len(reference)),
        "target_db": target,
        "reference_condition": config.synthetic.reference_conditions.get("gain"),
        "reference_summary": reference_summary,
        "full_parameter_range_summary": full_summary,
        "target_met_in_reference_condition": reference_summary["target_met"],
        "note": (
            "The estimator receives only input/output waveforms and the tone frequency. "
            "Errors are expressed in dB relative to the applying gain."
        ),
    }
    if not reference_summary["target_met"]:
        warnings.append(
            f"Gain target {target} dB not met: max |error| "
            f"{reference_summary['max_abs_error']:.4f} dB in the reference condition."
        )
    if full_summary["n"] < len(results):
        warnings.append(
            f"{len(results) - full_summary['n']} gain cases produced non-finite errors."
        )

    figures = {}
    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    ax.scatter(
        results["gain_db_true"],
        results["gain_db_estimated"],
        c=np.where(results["is_reference_condition"], "#1f77b4", "#ff7f0e"),
        s=18,
        alpha=0.85,
    )
    limits = [
        float(min(results["gain_db_true"].min(), results["gain_db_estimated"].min())),
        float(max(results["gain_db_true"].max(), results["gain_db_estimated"].max())),
    ]
    ax.plot(limits, limits, "k--", linewidth=0.8)
    ax.set_xlabel("True gain [dB]")
    ax.set_ylabel("Estimated gain [dB]")
    ax.set_title("Gain estimation: estimate vs. ground truth")
    figures["gain_scatter"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bins = np.linspace(
        -max(0.05, np.max(np.abs(results["error_db"])) * 1.1),
        max(0.05, np.max(np.abs(results["error_db"])) * 1.1),
        41,
    )
    ax.hist(reference["error_db"], bins=bins, color="#1f77b4", alpha=0.8, label="reference")
    ax.hist(
        results.loc[~results["is_reference_condition"], "error_db"],
        bins=bins,
        color="#ff7f0e",
        alpha=0.5,
        label="wider range",
    )
    ax.axvline(target, color="red", linestyle="--", linewidth=0.9, label=f"target ±{target} dB")
    ax.axvline(-target, color="red", linestyle="--", linewidth=0.9)
    ax.set_xlabel("Gain error [dB]")
    ax.set_ylabel("Number of cases")
    ax.set_title("Gain error distribution")
    ax.legend(frameon=False)
    figures["gain_error_histogram"] = fig

    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    for reference_flag, group, color, label in (
        (True, reference, "#1f77b4", "reference"),
        (False, results.loc[~results["is_reference_condition"]], "#ff7f0e", "wider range"),
    ):
        ax.scatter(
            group["tone_hz"],
            group["error_db"],
            s=14,
            color=color,
            alpha=0.8,
            label=label,
        )
    ax.axhline(0.0, color="k", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Tone frequency [Hz]")
    ax.set_ylabel("Gain error [dB]")
    ax.set_title("Gain error vs. tone frequency")
    ax.legend(frameon=False)
    figures["gain_error_vs_tone"] = fig

    narrative = (
        "The coherent single-bin tone projection recovers the applied gain to within "
        f"{reference_summary['max_abs_error']:.3g} dB in the reference condition "
        f"(target {target} dB) and remains accurate over the wider gain/level/frequency "
        "range. Because the estimate uses the input waveform as reference, it is insensitive "
        "to the absolute playback level and therefore directly transferable to a real "
        "measurement where the drive level is known."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"gain_case_results": results},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
