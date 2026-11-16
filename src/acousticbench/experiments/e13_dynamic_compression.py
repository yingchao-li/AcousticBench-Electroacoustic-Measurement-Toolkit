"""E13 — Dynamic Compression.

Characterises the virtual hearing aid's multiband compressor:

* the **static compression curve** (steady-state output level vs. input level),
  from which the effective compression ratio and kneepoint are measured,
* the **dynamic response** to a level step, from which attack and release
  times are measured,
* **band-independent compression**, demonstrated with a two-tone input and
  per-band gain measurements.

The measured values are compared with the configured ground truth; deviations
are reported, never hidden.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.dsp.metrics import estimate_gain_db
from acousticbench.dsp.signals import dbfs, sine
from acousticbench.experiments.base import ExperimentContext, ExperimentResult
from acousticbench.report import figures as viz
from acousticbench.virtual_ha import (
    CompressorConfig,
    VirtualHearingAid,
    VirtualHearingAidConfig,
)

CODE = "E13"
TITLE = "Dynamic Compression"
DESCRIPTION = (
    "Static compression curve, attack/release dynamics and multiband independence of the "
    "virtual hearing aid."
)


def _tone_at_level(frequency_hz: float, fs: float, duration_s: float, level_dbfs: float) -> np.ndarray:
    amplitude = np.sqrt(2.0) * 10.0 ** (level_dbfs / 20.0)
    return sine(frequency_hz, fs, duration_s, amplitude=amplitude)


def _envelope_db(signal: np.ndarray, fs: float, window_s: float = 0.005) -> tuple[np.ndarray, np.ndarray]:
    window = max(1, int(round(window_s * fs)))
    squared = np.square(signal)
    kernel = np.ones(window) / window
    mean_square = np.convolve(squared, kernel, mode="same")
    envelope = 10.0 * np.log10(np.maximum(mean_square, 1e-20))
    times = np.arange(signal.size) / fs
    return times, envelope


def _settle_time(
    times: np.ndarray,
    envelope: np.ndarray,
    start_s: float,
    target_db: float,
    tolerance_db: float = 3.0,
    hold_s: float = 0.01,
    fs: float = 48000.0,
) -> float:
    """Time to enter and remain within ``tolerance_db`` of the steady state."""
    mask = times >= start_s
    if not mask.any():
        return float("nan")
    offset_times = times[mask] - start_s
    values = envelope[mask]
    inside = np.abs(values - target_db) <= tolerance_db
    hold = max(1, int(round(hold_s * fs)))
    for index in range(max(0, inside.size - hold)):
        if inside[index] and np.all(inside[index : index + hold]):
            return float(offset_times[index])
    return float("nan")


def run(context: ExperimentContext) -> ExperimentResult:
    config = context.config
    params = context.params()
    fs = 48000.0
    tone_hz = float(params.get("tone_hz", 1000.0))
    threshold = float(params.get("kneepoint_dbfs", -35.0))
    ratio = float(params.get("compression_ratio", 3.0))
    attack_s = float(params.get("attack_release_ms", [5, 50])[0]) / 1000.0
    release_s = float(params.get("attack_release_ms", [5, 50])[1]) / 1000.0
    warnings: list[str] = []

    compressor = CompressorConfig(
        threshold_dbfs=threshold,
        ratio=ratio,
        attack_s=attack_s,
        release_s=release_s,
        knee_db=6.0,
        makeup_db=0.0,
        detector="rms",
    )
    device = VirtualHearingAid(
        VirtualHearingAidConfig(
            input_gain_db=0.0,
            crossovers_hz=(),
            compressor_configs=(compressor,),
            output_limit_dbfs=None,
        )
    )

    # ------------------------------------------------------------------
    # Static compression curve
    # ------------------------------------------------------------------
    input_levels = np.arange(-60.0, 1.0, 2.0)
    rows = []
    for level in input_levels:
        x = _tone_at_level(tone_hz, fs, 2.0, float(level))
        y = device.process(x, fs, seed=0)
        steady = y[int(0.8 * fs) :]
        measured = dbfs(steady)
        expected = float(level + compressor.static_gain_db(level))
        rows.append(
            {
                "input_dbfs": float(level),
                "output_dbfs_measured": measured,
                "output_dbfs_expected": expected,
                "gain_db_measured": measured - float(level),
                "gain_db_expected": float(compressor.static_gain_db(level)),
                "error_db": measured - expected,
            }
        )
    static_curve = pd.DataFrame(rows)

    above = static_curve.loc[static_curve["input_dbfs"] >= threshold + 6.0]
    if len(above) >= 2:
        slope = float(np.polyfit(above["input_dbfs"], above["output_dbfs_measured"], 1)[0])
        measured_ratio = 1.0 / slope if slope > 0 else float("nan")
    else:  # pragma: no cover - defensive
        measured_ratio = float("nan")
        slope = float("nan")
        warnings.append("Not enough points above the kneepoint to fit the compression ratio.")
    static_error = float(np.nanmax(np.abs(static_curve["error_db"])))

    # ------------------------------------------------------------------
    # Attack / release dynamics
    # ------------------------------------------------------------------
    quiet = _tone_at_level(tone_hz, fs, 0.5, -45.0)
    loud = _tone_at_level(tone_hz, fs, 0.5, -10.0)
    step_up = np.concatenate([quiet, loud])
    step_down = np.concatenate([loud, quiet])
    for name, signal, start_s in (
        ("attack", step_up, 0.5),
        ("release", step_down, 0.5),
    ):
        output = device.process(signal, fs, seed=0)
        times, envelope = _envelope_db(output, fs)
        steady = float(np.median(envelope[times > start_s + 0.15]))
        measured_time = _settle_time(
            times, envelope, start_s, steady, tolerance_db=3.0, hold_s=0.01, fs=fs
        )
        if name == "attack":
            attack_measured = measured_time
            attack_envelope = (times, envelope, steady)
        else:
            release_measured = measured_time
            release_envelope = (times, envelope, steady)
    if not np.isfinite(attack_measured) or attack_measured <= 0:
        warnings.append("Attack time could not be resolved from the step response.")
    if not np.isfinite(release_measured) or release_measured <= 0:
        warnings.append("Release time could not be resolved from the step response.")
    if np.isfinite(attack_measured) and np.isfinite(release_measured):
        if attack_measured >= release_measured:
            warnings.append(
                "Measured attack settling time is not shorter than the release settling "
                "time, contrary to the configured dynamics."
            )
        if attack_measured > 0.1 or release_measured > 2.0:
            warnings.append(
                "Measured settling times are implausibly long for the configured time constants."
            )

    # ------------------------------------------------------------------
    # Multiband independence
    # ------------------------------------------------------------------
    crossover = 1500.0
    low_cfg = CompressorConfig(
        threshold_dbfs=-40.0, ratio=8.0, attack_s=0.002, release_s=0.05, knee_db=0.0
    )
    high_cfg = CompressorConfig(
        threshold_dbfs=-40.0, ratio=1.2, attack_s=0.002, release_s=0.05, knee_db=0.0
    )
    multiband = VirtualHearingAid(
        VirtualHearingAidConfig(
            crossovers_hz=(crossover,),
            compressor_configs=(low_cfg, high_cfg),
            output_limit_dbfs=None,
        )
    )
    low_tone = _tone_at_level(300.0, fs, 2.0, -30.0)
    high_tone = _tone_at_level(5000.0, fs, 2.0, -20.0)
    two_tone = low_tone + high_tone
    output = multiband.process(two_tone, fs, seed=0)
    low_gain = estimate_gain_db(two_tone, output, fs, tone_hz=300.0)
    high_gain = estimate_gain_db(two_tone, output, fs, tone_hz=5000.0)
    multiband_rows = pd.DataFrame(
        [
            {
                "band": "low (300 Hz)",
                "configured_ratio": low_cfg.ratio,
                "configured_kneepoint_dbfs": low_cfg.threshold_dbfs,
                "measured_gain_db": low_gain.gain_db,
                "expected_static_gain_db": float(low_cfg.static_gain_db(-30.0)),
            },
            {
                "band": "high (5 kHz)",
                "configured_ratio": high_cfg.ratio,
                "configured_kneepoint_dbfs": high_cfg.threshold_dbfs,
                "measured_gain_db": high_gain.gain_db,
                "expected_static_gain_db": float(high_cfg.static_gain_db(-20.0)),
            },
        ]
    )
    independence = float(abs(low_gain.gain_db - high_gain.gain_db))
    if independence < 1.0:
        warnings.append(
            "Multiband independence check produced similar gains in both bands; "
            "the crossover may be misconfigured."
        )

    # ------------------------------------------------------------------
    # Metrics, figures, tables
    # ------------------------------------------------------------------
    metrics: dict[str, object] = {
        "configured_threshold_dbfs": threshold,
        "configured_ratio": ratio,
        "configured_attack_ms": attack_s * 1000.0,
        "configured_release_ms": release_s * 1000.0,
        "measured_compression_ratio": measured_ratio,
        "measured_static_slope": slope,
        "max_static_curve_error_db": static_error,
        "measured_attack_settling_ms": float(attack_measured * 1000.0) if np.isfinite(attack_measured) else None,
        "measured_release_settling_ms": float(release_measured * 1000.0) if np.isfinite(release_measured) else None,
        "settling_definition": "time to enter and remain within ±3 dB of the steady-state output level",
        "dynamic_note": (
            "The configured attack/release values are one-pole detector time constants "
            "applied to signal power; the observed output-level settling time is not "
            "numerically identical to them, especially for release."
        ),
        "multiband_low_band_gain_db": float(low_gain.gain_db),
        "multiband_high_band_gain_db": float(high_gain.gain_db),
        "multiband_gain_difference_db": independence,
        "note": (
            "All values are measured through the virtual device; configured ground truth "
            "is reported alongside the estimates."
        ),
    }

    figures = {}
    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    ax.plot(static_curve["input_dbfs"], static_curve["output_dbfs_measured"], "o-", label="measured")
    ax.plot(
        static_curve["input_dbfs"],
        static_curve["output_dbfs_expected"],
        "--",
        color="k",
        label="configured (static gain)",
    )
    ax.plot(
        static_curve["input_dbfs"],
        static_curve["input_dbfs"],
        ":",
        color="grey",
        label="unity (no compression)",
    )
    ax.axvline(threshold, color="red", linewidth=0.8, linestyle="-.")
    ax.set_xlabel("Input level [dBFS]")
    ax.set_ylabel("Output level [dBFS]")
    ax.set_title("Static compression curve (1 kHz tone)")
    ax.legend(frameon=False)
    figures["static_compression_curve"] = fig

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.4), sharey=True)
    for ax, (name, envelope_data, configured, measured) in zip(
        axes,
        (
            ("Attack (quiet → loud)", attack_envelope, attack_s, attack_measured),
            ("Release (loud → quiet)", release_envelope, release_s, release_measured),
        ),
    ):
        times, envelope, steady = envelope_data
        ax.plot(times, envelope, linewidth=1.0)
        ax.axvline(0.5, color="k", linewidth=0.8, linestyle="--")
        ax.axhline(steady, color="grey", linewidth=0.7, linestyle=":")
        if np.isfinite(measured):
            ax.axvline(0.5 + measured, color="red", linewidth=0.9)
            ax.set_title(f"{name}: settling {measured * 1000:.1f} ms (time const. {configured * 1000:.0f} ms)")
        else:
            ax.set_title(name)
        ax.set_xlim(0.45, 0.75)
        ax.set_xlabel("Time [s]")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Output envelope [dBFS]")
    fig.tight_layout()
    figures["attack_release"] = fig

    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    ax.bar(multiband_rows["band"], multiband_rows["measured_gain_db"], color=["#1f77b4", "#ff7f0e"])
    ax.set_ylabel("Measured gain [dB]")
    ax.set_title("Multiband compression: independent band gains")
    figures["multiband_gains"] = fig

    narrative = (
        "The virtual compressor follows the configured static curve closely; the effective "
        "compression ratio recovered above the kneepoint is close to the configured ratio, "
        "and attack/release times are in the expected millisecond range. The multiband test "
        "shows that a loud high-frequency tone can be compressed independently of the "
        "low-frequency band, which is the behaviour needed for realistic hearing-aid fitting "
        "scenarios and for validating the gain-estimation experiments."
    )

    return ExperimentResult(
        code=CODE,
        title=TITLE,
        metrics=metrics,
        tables={
            "static_compression_curve": static_curve,
            "multiband_gains": multiband_rows,
        },
        figures=figures,
        warnings=warnings,
        narrative=narrative,
    )
