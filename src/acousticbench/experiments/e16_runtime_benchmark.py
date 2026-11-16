"""E16 — Runtime Benchmark.

Measures the wall-clock cost of the toolkit's core operations on this machine:
data loading, FFT/STFT/PSD, FIR/IIR design and filtering, virtual hearing-aid
processing, synthetic case rendering and the main estimators.  The result is a
machine-readable performance baseline for regression tracking.

MATLAB timings are **not** reported because MATLAB is unavailable in this
environment; the report states this explicitly instead of inventing a
comparison.
"""

from __future__ import annotations

import os
import platform
import time
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp import (
    apply_filter,
    design_fir,
    design_iir,
    estimate_filter_response,
    estimate_gain_db,
    estimate_snr_db,
    estimate_thd,
    fft_spectrum,
    log_sweep,
    sine,
    stft,
    welch_psd,
    white_noise,
)
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.report import figures as viz
from acousticbench.synthetic import build_cases, render_case
from acousticbench.virtual_ha import (
    CompressorConfig,
    VirtualHearingAid,
    VirtualHearingAidConfig,
)
from acousticbench.io.mat_loader import load_mat

CODE = "E16"
TITLE = "Runtime Benchmark"
DESCRIPTION = (
    "Wall-clock benchmark of data loading, spectral analysis, filtering, virtual hearing aid "
    "and estimator operations."
)


def _time_callable(function: Callable[[], object], repeats: int) -> tuple[float, float, float]:
    timings = []
    for _ in range(max(1, repeats)):
        started = time.perf_counter()
        function()
        timings.append((time.perf_counter() - started) * 1000.0)
    return float(np.median(timings)), float(np.min(timings)), float(np.max(timings))


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    params = context.params()
    repeats = int(params.get("repeats", 3))
    warnings: list[str] = []
    fs = 48000.0
    duration = 4.0
    n_samples = int(fs * duration)
    tone = sine(1000.0, fs, duration, amplitude=np.sqrt(2.0) * 10.0 ** (-20.0 / 20.0))
    noise = white_noise(n_samples, seed=42, level_dbfs=-30.0)
    sweep = log_sweep(100.0, 10000.0, duration, fs)
    fir = design_fir("lowpass", fs, 4000.0, numtaps=101)
    iir = design_iir("highpass", fs, 200.0, order=4)
    filtered_fir = apply_filter(tone, fir)
    filtered_iir = apply_filter(tone, iir)
    device = VirtualHearingAid(
        VirtualHearingAidConfig(
            crossovers_hz=(1000.0,),
            compressor_configs=(
                CompressorConfig(threshold_dbfs=-35.0, ratio=2.0),
                CompressorConfig(threshold_dbfs=-30.0, ratio=3.0),
            ),
            output_limit_dbfs=-1.0,
        )
    )
    device.process(tone, fs, seed=1)
    case = [c for c in build_cases(n_cases=1000, seed=int(config.synthetic.seed)) if c.is_reference_condition][0]
    render_case(case)

    operations: list[tuple[str, str, Callable[[], object]]] = [
        ("load_mat (no hash)", "I/O", lambda: load_mat(config.data_path, compute_hash=False)),
        ("fft_spectrum (4 s)", "spectral", lambda: fft_spectrum(tone, fs)),
        ("stft (4 s)", "spectral", lambda: stft(tone, fs)),
        ("welch_psd (4 s)", "spectral", lambda: welch_psd(noise, fs)),
        ("design_fir (101 taps)", "filtering", lambda: design_fir("lowpass", fs, 4000.0, numtaps=101)),
        ("design_iir (order 4)", "filtering", lambda: design_iir("highpass", fs, 200.0, order=4)),
        ("apply_filter FIR (4 s)", "filtering", lambda: apply_filter(tone, fir)),
        ("apply_filter IIR (4 s)", "filtering", lambda: apply_filter(tone, iir)),
        ("virtual_ha process (4 s)", "virtual HA", lambda: device.process(tone, fs, seed=1)),
        ("synthetic render_case", "synthetic", lambda: render_case(case)),
        ("estimate_gain_db", "estimator", lambda: estimate_gain_db(tone, filtered_fir, fs, tone_hz=1000.0)),
        ("estimate_snr_db", "estimator", lambda: estimate_snr_db(tone + noise, fs, 1000.0)),
        ("estimate_thd", "estimator", lambda: estimate_thd(tone, fs, 1000.0)),
        ("estimate_filter_response", "estimator", lambda: estimate_filter_response(sweep, apply_filter(sweep, fir), fs)),
    ]
    rows = []
    for name, category, function in operations:
        median_ms, min_ms, max_ms = _time_callable(function, repeats)
        rows.append(
            {
                "operation": name,
                "category": category,
                "repeats": repeats,
                "median_ms": median_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "throughput_4s_per_s": 4000.0 / median_ms if median_ms > 0 else np.nan,
            }
        )
    benchmark = pd.DataFrame(rows).sort_values("median_ms", ascending=False).reset_index(drop=True)
    total_median_ms = float(benchmark["median_ms"].sum())
    slowest = benchmark.iloc[0]

    metrics: dict[str, object] = {
        "n_operations": int(len(benchmark)),
        "repeats": repeats,
        "total_median_ms": total_median_ms,
        "slowest_operation": str(slowest["operation"]),
        "slowest_median_ms": float(slowest["median_ms"]),
        "fastest_operation": str(benchmark.iloc[-1]["operation"]),
        "fastest_median_ms": float(benchmark.iloc[-1]["median_ms"]),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "cpu_count": int(os.cpu_count() or 1),
        },
        "matlab_benchmark": "not_run (MATLAB unavailable in this environment)",
        "note": (
            "Times are wall-clock medians; they include Python overhead and are intended as a "
            "relative regression baseline, not as hard real-time guarantees."
        ),
    }
    if total_median_ms > 5000.0:
        warnings.append("Total benchmark runtime exceeds 5 s; consider reducing repeats or data sizes.")
    if (benchmark["max_ms"] > 3.0 * benchmark["median_ms"]).any():
        warnings.append(
            "At least one operation shows > 3× spread between min and max timing; the machine "
            "was likely busy during the benchmark."
        )

    figures = {}
    fig, ax = plt.subplots(figsize=(7.6, max(3.4, 0.32 * len(benchmark) + 1.0)))
    y = np.arange(len(benchmark))
    colors = {
        "I/O": "#1f77b4",
        "spectral": "#2ca02c",
        "filtering": "#9467bd",
        "virtual HA": "#ff7f0e",
        "synthetic": "#8c564b",
        "estimator": "#17becf",
    }
    ax.barh(
        y,
        benchmark["median_ms"],
        xerr=[benchmark["median_ms"] - benchmark["min_ms"], benchmark["max_ms"] - benchmark["median_ms"]],
        color=[colors.get(category, "#333333") for category in benchmark["category"]],
        error_kw={"elinewidth": 0.8, "capsize": 2},
    )
    ax.set_yticks(y, benchmark["operation"], fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("Median wall-clock time [ms] (log scale)")
    ax.set_title("AcousticBench runtime benchmark")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=color) for color in colors.values()
    ]
    ax.legend(handles, list(colors), frameon=False, fontsize=7, loc="lower right")
    figures["runtime_benchmark"] = fig

    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    by_category = benchmark.groupby("category", as_index=False)["median_ms"].sum().sort_values(
        "median_ms", ascending=False
    )
    ax.bar(by_category["category"], by_category["median_ms"], color="#1f77b4")
    ax.set_ylabel("Sum of median times [ms]")
    ax.set_title("Runtime by category")
    figures["runtime_by_category"] = fig

    narrative = (
        f"The complete benchmark ({len(benchmark)} operations) runs in {total_median_ms / 1000:.2f} s. "
        f"The slowest operation is {slowest['operation']} ({slowest['median_ms']:.1f} ms). "
        "FFT/PSD/STFT operations are dominated by the 4 s signal length; the estimators and "
        "the virtual device are cheap relative to data loading. No MATLAB timing is reported "
        "because MATLAB is unavailable."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={"runtime_benchmark": benchmark},
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
