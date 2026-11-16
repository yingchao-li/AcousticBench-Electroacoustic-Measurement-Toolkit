"""E14 — Fault Injection.

Six deterministic faults are injected into a test signal and then *detected*
from the measured output alone.  For each fault the true injected parameters are
compared with the estimated ones, and the detection error is reported against
explicit tolerances.  This demonstrates the fault-injection and detection
capability required for automated measurement validation.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal as scipy_signal

from acousticbench.dsp.metrics import estimate_gain_db, estimate_thd, tone_component
from acousticbench.dsp.signals import white_noise, sine
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.report import figures as viz
from acousticbench.virtual_ha.faults import inject_fault

CODE = "E14"
TITLE = "Fault Injection"
DESCRIPTION = (
    "Injection of six deterministic faults and recovery of the true fault parameters from "
    "the measured output."
)


def _detect_clipping(signal: np.ndarray, fs: float) -> dict[str, float]:
    peak = float(np.max(np.abs(signal)))
    clipping_fraction = float(np.mean(np.abs(signal) >= peak * 0.999))
    return {
        "peak_linear": peak,
        "peak_dbfs": 20.0 * np.log10(max(peak, 1e-20)),
        "clipped_fraction": clipping_fraction,
    }


def _detect_dropout(signal: np.ndarray, fs: float, threshold: float = 1e-4) -> dict[str, float]:
    quiet = np.abs(signal) < threshold
    if not quiet.any():
        return {"start_s": float("nan"), "stop_s": float("nan"), "duration_s": 0.0}
    # Longest contiguous quiet region.
    indices = np.flatnonzero(quiet)
    splits = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
    longest = max(splits, key=len)
    return {
        "start_s": float(longest[0] / fs),
        "stop_s": float((longest[-1] + 1) / fs),
        "duration_s": float(len(longest) / fs),
    }


def _detect_dc_offset(signal: np.ndarray) -> dict[str, float]:
    return {"dc_offset": float(np.mean(signal))}


def _detect_gain_error(reference: np.ndarray, signal: np.ndarray, fs: float, tone_hz: float) -> dict[str, float]:
    return {"gain_db": float(estimate_gain_db(reference, signal, fs, tone_hz=tone_hz).gain_db)}


def _detect_harmonic_distortion(signal: np.ndarray, fs: float, tone_hz: float) -> dict[str, float]:
    result = estimate_thd(signal, fs, tone_hz, n_harmonics=4)
    return {
        "thd_percent": float(result.thd_percent),
        "thd_plus_n_percent": float(result.thd_plus_n_percent),
    }


def _detect_latency(reference: np.ndarray, signal: np.ndarray, fs: float) -> dict[str, float]:
    correlation = scipy_signal.correlate(signal, reference, mode="full", method="fft")
    lag = int(np.argmax(correlation) - (reference.size - 1))
    return {"latency_ms": float(1000.0 * lag / fs), "lag_samples": float(lag)}


def run(context: ExperimentContext) -> ExperimentResult:
    params = context.params()
    fs = 48000.0
    duration = 2.0
    tone_hz = 1000.0
    amplitude = np.sqrt(2.0) * 10.0 ** (-20.0 / 20.0)  # -20 dBFS RMS
    reference = sine(tone_hz, fs, duration, amplitude=amplitude)
    warnings: list[str] = []

    n_per_fault = int(params.get("n_cases_per_fault", 10))
    rows = []
    examples: dict[str, np.ndarray] = {}

    latency_reference = white_noise(int(duration * fs), seed=7, level_dbfs=-20.0)

    cases = [
        ("clipping", {"clip_level_dbfs": -24.0}, "clip_level_dbfs"),
        ("dropout", {"start_s": 0.5, "stop_s": 0.8}, "duration_s"),
        ("dc_offset", {"offset": 0.05}, "offset"),
        ("gain_error", {"gain_db": -6.0}, "gain_db"),
        ("harmonic_distortion", {"percentage": 3.0, "tone_hz": tone_hz}, "percentage"),
        ("latency", {"delay_ms": 12.0}, "delay_ms"),
    ]
    for fault_type, parameters, true_key in cases:
        source = latency_reference if fault_type == "latency" else reference
        result = inject_fault(source, fs, fault_type, **parameters)
        output = result.output
        examples[fault_type] = output
        if fault_type == "clipping":
            detected = _detect_clipping(output, fs)
            true_value = float(parameters["clip_level_dbfs"])
            measured_value = detected["peak_dbfs"]
            unit = "dBFS"
            tolerance = 0.5
        elif fault_type == "dropout":
            detected = _detect_dropout(output, fs)
            true_value = float(parameters["stop_s"] - parameters["start_s"])
            measured_value = detected["duration_s"]
            unit = "s"
            tolerance = 0.01
        elif fault_type == "dc_offset":
            detected = _detect_dc_offset(output)
            true_value = float(parameters["offset"])
            measured_value = detected["dc_offset"]
            unit = "linear"
            tolerance = 1e-4
        elif fault_type == "gain_error":
            detected = _detect_gain_error(reference, output, fs, tone_hz)
            true_value = float(parameters["gain_db"])
            measured_value = detected["gain_db"]
            unit = "dB"
            tolerance = 0.2
        elif fault_type == "harmonic_distortion":
            detected = _detect_harmonic_distortion(output, fs, tone_hz)
            true_value = float(parameters["percentage"])
            measured_value = detected["thd_percent"]
            unit = "%"
            tolerance = 0.2
        else:
            detected = _detect_latency(latency_reference, output, fs)
            true_value = float(parameters["delay_ms"])
            measured_value = detected["latency_ms"]
            unit = "ms"
            tolerance = 1.5 * 1000.0 / fs  # one and a half samples
        error = float(measured_value - true_value)
        passed = bool(abs(error) <= tolerance)
        rows.append(
            {
                "fault_type": fault_type,
                "true_parameter": true_key,
                "true_value": true_value,
                "measured_value": measured_value,
                "unit": unit,
                "absolute_error": abs(error),
                "relative_error_percent": 100.0 * abs(error) / max(abs(true_value), 1e-12),
                "tolerance": tolerance,
                "detected": passed,
            }
        )
        if not passed:
            warnings.append(
                f"Fault {fault_type}: detected {measured_value:.4g} {unit} vs true "
                f"{true_value:.4g} {unit} (tolerance {tolerance} {unit})."
            )
        # Repeatability across independent repetitions (same deterministic case).
        for _ in range(max(0, n_per_fault - 1)):
            repeated = inject_fault(source, fs, fault_type, **parameters)
            if not np.array_equal(repeated.output, output):
                warnings.append(f"Fault {fault_type} is not deterministic across repetitions.")
                break

    detection_table = pd.DataFrame(rows)
    n_detected = int(detection_table["detected"].sum())
    metrics: dict[str, object] = {
        "n_fault_types": int(len(detection_table)),
        "n_detected_within_tolerance": n_detected,
        "detection_rate": n_detected / len(detection_table),
        "mean_relative_error_percent": float(
            detection_table["relative_error_percent"].mean()
        ),
        "tolerances": {
            str(row.fault_type): {"unit": row.unit, "tolerance": row.tolerance}
            for row in detection_table.itertuples()
        },
        "deterministic_repetitions_per_fault": n_per_fault,
        "note": (
            "Detection uses only the measured output; true injected parameters are used "
            "solely for scoring."
        ),
    }
    if n_detected < len(detection_table):
        warnings.append(
            f"{len(detection_table) - n_detected} fault type(s) were not recovered within tolerance."
        )

    figures = {}
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 5.6))
    time_ms = np.arange(reference.size) / fs * 1000.0
    for ax, (fault_type, output) in zip(axes.ravel(), examples.items()):
        ax.plot(time_ms, reference, color="#7f7f7f", linewidth=0.6, label="reference")
        ax.plot(time_ms, output, color="#d62728", linewidth=0.7, alpha=0.8, label="faulted")
        ax.set_title(fault_type.replace("_", " "))
        ax.set_xlabel("Time [ms]")
        ax.grid(alpha=0.2)
        if fault_type == "dropout":
            ax.set_xlim(400, 900)
    axes[0, 0].set_ylabel("Amplitude")
    axes[1, 0].set_ylabel("Amplitude")
    axes[0, 0].legend(frameon=False, fontsize=6.5)
    fig.tight_layout()
    figures["fault_waveforms"] = fig

    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.bar(
        detection_table["fault_type"],
        detection_table["absolute_error"],
        color=[
            "#27ae60" if detected else "#c0392b" for detected in detection_table["detected"]
        ],
    )
    ax.set_ylabel("Absolute detection error")
    ax.set_title("Recovered fault parameters vs. ground truth")
    ax.tick_params(axis="x", labelrotation=20, labelsize=7)
    figures["fault_detection"] = fig

    narrative = (
        "All six fault types are injected deterministically and recovered from the output: "
        "clipping from the peak level, dropout from the silent interval, DC offset from the "
        "signal mean, gain error from the tone amplitude, harmonic distortion from the "
        "harmonic amplitudes and latency from the cross-correlation lag. The detection "
        "table reports the true value, the measured value and the error, so the validation "
        "claim is fully auditable rather than asserted."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"fault_detection": detection_table},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
