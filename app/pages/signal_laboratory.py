"""Page 7 — Signal Laboratory.

Interactive synthetic signal-processing workbench: signal generation, FIR/IIR
filter design, a configurable virtual hearing aid (multiband compressor, noise,
faults) and known-ground-truth metric estimation (gain, SNR, THD, THD+N,
frequency response).

The page uses the ``acousticbench.dsp`` and ``acousticbench.virtual_ha``
modules; both are imported through a guarded loader so a missing module yields
an actionable notice instead of a page crash.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import plotting, theme, ui

TITLE = "Signal Laboratory"
SUBTITLE = (
    "Generate deterministic synthetic signals, design filters, configure a virtual hearing aid "
    "with faults, and compare estimated metrics against the known ground truth."
)

_MAX_PLOT_POINTS = 4000


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------
@dataclass
class LabSettings:
    """All interactive settings of the Signal Laboratory."""

    fs: int
    duration_s: float
    signal_type: str
    tone_hz: float
    sweep_start_hz: float
    sweep_end_hz: float
    level_dbfs: float
    add_awgn: bool
    snr_db: float
    seed: int
    filter_enabled: bool
    filter_design: str
    filter_kind: str
    cutoff_low: float
    cutoff_high: float
    fir_numtaps: int
    fir_window: str
    iir_order: int
    zero_phase: bool
    ha_enabled: bool
    ha_input_gain_db: float
    crossover_hz: float
    low_threshold_dbfs: float
    low_ratio: float
    high_threshold_dbfs: float
    high_ratio: float
    attack_ms: float
    release_ms: float
    makeup_db: float
    limiter_enabled: bool
    limiter_dbfs: float
    ha_noise_enabled: bool
    ha_noise_dbfs: float
    ha_noise_color: str
    fault_type: str
    fault_params: dict[str, Any]


def _sidebar_controls() -> LabSettings:
    """Render the sidebar controls and return the parsed settings."""
    st.sidebar.markdown("### Signal")
    fs = st.sidebar.selectbox(
        "Sampling rate [Hz]", options=[8000, 16000, 24000, 32000, 44100, 48000], index=5, key="lab_fs"
    )
    duration_s = st.sidebar.slider(
        "Duration [s]", min_value=0.25, max_value=4.0, value=2.0, step=0.25, key="lab_duration"
    )
    signal_type = st.sidebar.radio(
        "Signal type",
        options=["Tone", "Logarithmic sweep", "White noise", "Pink noise"],
        index=0,
        key="lab_signal",
    )
    tone_hz = st.sidebar.number_input(
        "Tone frequency [Hz]", min_value=20.0, max_value=min(20000.0, fs / 2 - 100), value=1000.0,
        step=50.0, key="lab_tone_hz",
    )
    sweep_start_hz = st.sidebar.number_input(
        "Sweep start [Hz]", min_value=20.0, max_value=fs / 2 - 100, value=100.0, step=10.0,
        key="lab_sweep_start",
    )
    sweep_end_hz = st.sidebar.number_input(
        "Sweep end [Hz]", min_value=40.0, max_value=fs / 2 - 100, value=min(10000.0, fs / 2 - 100),
        step=100.0, key="lab_sweep_end",
    )
    level_dbfs = st.sidebar.slider(
        "Signal level [dBFS RMS]", min_value=-60.0, max_value=-3.0, value=-20.0, step=1.0,
        key="lab_level",
    )
    add_awgn_flag = st.sidebar.checkbox("Add white Gaussian noise", value=False, key="lab_awgn")
    snr_db = st.sidebar.slider(
        "Configured SNR [dB]", min_value=-10.0, max_value=60.0, value=20.0, step=1.0, key="lab_snr"
    )
    seed = int(
        st.sidebar.number_input(
            "Noise seed", min_value=0, max_value=2**31 - 1, value=0, step=1, key="lab_seed"
        )
    )

    st.sidebar.markdown("### Filter")
    filter_enabled = st.sidebar.checkbox("Enable filter", value=False, key="lab_filter_on")
    filter_design = st.sidebar.radio(
        "Design", options=["FIR (window method)", "IIR (Butterworth)"], index=0, key="lab_filter_design"
    )
    filter_kind = st.sidebar.selectbox(
        "Filter type", options=["lowpass", "highpass", "bandpass", "bandstop"], index=0,
        key="lab_filter_kind",
    )
    nyquist = fs / 2
    cutoff_low = st.sidebar.number_input(
        "Lower / single cutoff [Hz]", min_value=20.0, max_value=nyquist - 20, value=min(1000.0, nyquist / 4),
        step=50.0, key="lab_cutoff_low",
    )
    cutoff_high = st.sidebar.number_input(
        "Upper cutoff (band filters) [Hz]", min_value=40.0, max_value=nyquist - 10,
        value=min(4000.0, nyquist / 2), step=100.0, key="lab_cutoff_high",
    )
    fir_numtaps = int(
        st.sidebar.slider("FIR taps", min_value=15, max_value=501, value=101, step=2, key="lab_fir_taps")
    )
    fir_window = st.sidebar.selectbox(
        "FIR window", options=["hamming", "hann", "blackman", "kaiser"], index=0, key="lab_fir_window"
    )
    iir_order = int(
        st.sidebar.slider("IIR order", min_value=1, max_value=8, value=4, key="lab_iir_order")
    )
    zero_phase = st.sidebar.checkbox(
        "Zero-phase filtering", value=False, key="lab_zero_phase",
        help="Doubles the magnitude response in dB (standard filtfilt semantics).",
    )

    st.sidebar.markdown("### Virtual hearing aid")
    ha_enabled = st.sidebar.checkbox("Enable virtual hearing aid", value=True, key="lab_ha_on")
    ha_input_gain_db = st.sidebar.slider(
        "Input gain [dB]", min_value=-20.0, max_value=30.0, value=6.0, step=1.0, key="lab_ha_gain"
    )
    crossover_hz = st.sidebar.selectbox(
        "Crossover [Hz]", options=[500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0],
        index=3, key="lab_crossover",
    )
    st.sidebar.caption("Low band compressor")
    low_threshold_dbfs = st.sidebar.slider(
        "Low threshold [dBFS]", min_value=-60.0, max_value=-10.0, value=-35.0, step=1.0, key="lab_low_thr"
    )
    low_ratio = st.sidebar.slider(
        "Low ratio", min_value=1.0, max_value=6.0, value=3.0, step=0.25, key="lab_low_ratio"
    )
    st.sidebar.caption("High band compressor")
    high_threshold_dbfs = st.sidebar.slider(
        "High threshold [dBFS]", min_value=-60.0, max_value=-10.0, value=-30.0, step=1.0, key="lab_high_thr"
    )
    high_ratio = st.sidebar.slider(
        "High ratio", min_value=1.0, max_value=6.0, value=2.0, step=0.25, key="lab_high_ratio"
    )
    st.sidebar.caption("Dynamics")
    attack_ms = st.sidebar.slider(
        "Attack [ms]", min_value=1.0, max_value=50.0, value=5.0, step=1.0, key="lab_attack"
    )
    release_ms = st.sidebar.slider(
        "Release [ms]", min_value=10.0, max_value=300.0, value=50.0, step=10.0, key="lab_release"
    )
    makeup_db = st.sidebar.slider(
        "Make-up gain [dB]", min_value=-12.0, max_value=12.0, value=0.0, step=0.5, key="lab_makeup"
    )
    limiter_enabled = st.sidebar.checkbox("Output limiter", value=True, key="lab_limiter")
    limiter_dbfs = st.sidebar.slider(
        "Limiter level [dBFS]", min_value=-20.0, max_value=0.0, value=-1.0, step=1.0, key="lab_limiter_level"
    )
    ha_noise_enabled = st.sidebar.checkbox("Add device sensor noise", value=False, key="lab_ha_noise")
    ha_noise_dbfs = st.sidebar.slider(
        "Sensor noise level [dBFS]", min_value=-110.0, max_value=-40.0, value=-80.0, step=5.0,
        key="lab_ha_noise_level",
    )
    ha_noise_color = st.sidebar.selectbox(
        "Sensor noise colour", options=["white", "pink"], index=0, key="lab_ha_noise_color"
    )

    st.sidebar.markdown("### Fault injection")
    fault_options = ["none", "clipping", "dropout", "dc_offset", "gain_error", "harmonic_distortion", "latency"]
    fault_type = st.sidebar.selectbox(
        "Fault type", options=fault_options, index=0, key="lab_fault_type",
        help="Faults are applied after the compressor, exactly as in the validation experiments.",
    )
    fault_params: dict[str, Any] = {}
    if fault_type == "clipping":
        fault_params["clip_level_dbfs"] = st.sidebar.slider(
            "Clip level [dBFS]", min_value=-30.0, max_value=0.0, value=-6.0, step=1.0, key="lab_clip_level"
        )
    elif fault_type == "dropout":
        fault_params["start_s"] = st.sidebar.number_input(
            "Dropout start [s]", min_value=0.0, max_value=max(0.0, duration_s - 0.05),
            value=min(0.5, duration_s / 2), step=0.05, key="lab_dropout_start",
        )
        fault_params["stop_s"] = st.sidebar.number_input(
            "Dropout stop [s]", min_value=0.05, max_value=duration_s,
            value=min(1.0, duration_s), step=0.05, key="lab_dropout_stop",
        )
    elif fault_type == "dc_offset":
        fault_params["offset"] = st.sidebar.number_input(
            "DC offset (linear)", min_value=0.0, max_value=0.5, value=0.05, step=0.01, key="lab_dc_offset"
        )
    elif fault_type == "gain_error":
        fault_params["gain_db"] = st.sidebar.slider(
            "Gain error [dB]", min_value=-20.0, max_value=20.0, value=6.0, step=1.0, key="lab_gain_error"
        )
    elif fault_type == "harmonic_distortion":
        fault_params["percentage"] = st.sidebar.slider(
            "Harmonic distortion [%]", min_value=0.1, max_value=10.0, value=2.0, step=0.1,
            key="lab_hd_percent",
        )
        fault_params["tone_hz"] = float(tone_hz)
    elif fault_type == "latency":
        fault_params["delay_ms"] = st.sidebar.slider(
            "Latency [ms]", min_value=0.1, max_value=20.0, value=5.0, step=0.5, key="lab_latency"
        )

    return LabSettings(
        fs=int(fs),
        duration_s=float(duration_s),
        signal_type=signal_type,
        tone_hz=float(tone_hz),
        sweep_start_hz=float(sweep_start_hz),
        sweep_end_hz=float(sweep_end_hz),
        level_dbfs=float(level_dbfs),
        add_awgn=bool(add_awgn_flag),
        snr_db=float(snr_db),
        seed=seed,
        filter_enabled=bool(filter_enabled),
        filter_design=filter_design,
        filter_kind=filter_kind,
        cutoff_low=float(cutoff_low),
        cutoff_high=float(cutoff_high),
        fir_numtaps=int(fir_numtaps),
        fir_window=fir_window,
        iir_order=int(iir_order),
        zero_phase=bool(zero_phase),
        ha_enabled=bool(ha_enabled),
        ha_input_gain_db=float(ha_input_gain_db),
        crossover_hz=float(crossover_hz),
        low_threshold_dbfs=float(low_threshold_dbfs),
        low_ratio=float(low_ratio),
        high_threshold_dbfs=float(high_threshold_dbfs),
        high_ratio=float(high_ratio),
        attack_ms=float(attack_ms),
        release_ms=float(release_ms),
        makeup_db=float(makeup_db),
        limiter_enabled=bool(limiter_enabled),
        limiter_dbfs=float(limiter_dbfs),
        ha_noise_enabled=bool(ha_noise_enabled),
        ha_noise_dbfs=float(ha_noise_dbfs),
        ha_noise_color=ha_noise_color,
        fault_type=fault_type,
        fault_params=fault_params,
    )


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
@dataclass
class LabResult:
    """Generated, processed and analysed signals."""

    time_s: np.ndarray
    x: np.ndarray
    x_input: np.ndarray
    y: np.ndarray
    noise: np.ndarray | None
    filt: Any | None
    ha_result: Any | None
    fault_result: Any | None
    metrics: dict[str, Any]
    notes: list[str]


def _amplitude_from_dbfs(level_dbfs: float) -> float:
    """Peak amplitude of a sine whose RMS level equals ``level_dbfs``."""
    return math.sqrt(2.0) * 10.0 ** (level_dbfs / 20.0)


def _process(settings: LabSettings, modules: dict[str, Any]) -> LabResult | None:
    signals = modules["signals"]
    filters = modules.get("filters")
    metrics = modules.get("metrics")
    ha_module = modules.get("virtual_ha")

    fs = settings.fs
    duration = settings.duration_s
    if settings.signal_type == "Tone":
        x = signals.sine(settings.tone_hz, fs, duration, amplitude=_amplitude_from_dbfs(settings.level_dbfs))
    elif settings.signal_type == "Logarithmic sweep":
        start = min(settings.sweep_start_hz, settings.sweep_end_hz - 1.0)
        end = max(settings.sweep_end_hz, start + 1.0)
        x = signals.log_sweep(start, end, duration, fs, amplitude=_amplitude_from_dbfs(settings.level_dbfs))
    elif settings.signal_type == "White noise":
        x = signals.white_noise(int(round(fs * duration)), seed=settings.seed, level_dbfs=settings.level_dbfs)
    else:
        x = signals.pink_noise(int(round(fs * duration)), seed=settings.seed, level_dbfs=settings.level_dbfs)

    noise = None
    x_input = x
    if settings.add_awgn:
        x_input = signals.add_awgn(x, settings.snr_db, seed=settings.seed)
        noise = x_input - x

    filt = None
    stage = x_input
    if settings.filter_enabled and filters is not None:
        cutoff = (
            (settings.cutoff_low, settings.cutoff_high)
            if settings.filter_kind in {"bandpass", "bandstop"}
            else settings.cutoff_low
        )
        if settings.filter_design.startswith("FIR"):
            filt = filters.design_fir(
                settings.filter_kind, fs, cutoff, numtaps=settings.fir_numtaps, window=settings.fir_window
            )
        else:
            filt = filters.design_iir(settings.filter_kind, fs, cutoff, order=settings.iir_order)
        stage = filters.apply_filter(stage, filt, zero_phase=settings.zero_phase)

    ha_result = None
    fault_result = None
    notes: list[str] = []
    if settings.ha_enabled and ha_module is not None:
        from acousticbench.virtual_ha import (
            CompressorConfig,
            FaultInjectionConfig,
            NoiseInjectionConfig,
            VirtualHearingAid,
            VirtualHearingAidConfig,
        )

        fault_chain = ()
        if settings.fault_type != "none":
            fault_chain = (
                FaultInjectionConfig(fault_type=settings.fault_type, parameters=settings.fault_params),
            )
        config = VirtualHearingAidConfig(
            input_gain_db=settings.ha_input_gain_db,
            crossovers_hz=(settings.crossover_hz,),
            compressor_configs=(
                CompressorConfig(
                    threshold_dbfs=settings.low_threshold_dbfs,
                    ratio=settings.low_ratio,
                    attack_s=settings.attack_ms / 1000.0,
                    release_s=settings.release_ms / 1000.0,
                    makeup_db=settings.makeup_db,
                ),
                CompressorConfig(
                    threshold_dbfs=settings.high_threshold_dbfs,
                    ratio=settings.high_ratio,
                    attack_s=settings.attack_ms / 1000.0,
                    release_s=settings.release_ms / 1000.0,
                    makeup_db=settings.makeup_db,
                ),
            ),
            output_limit_dbfs=settings.limiter_dbfs if settings.limiter_enabled else None,
            noise=(
                NoiseInjectionConfig(level_dbfs=settings.ha_noise_dbfs, color=settings.ha_noise_color)
                if settings.ha_noise_enabled
                else None
            ),
            faults=fault_chain,
        )
        device = VirtualHearingAid(config)
        ha_result = device.process_detailed(stage, fs, seed=settings.seed)
        y = ha_result.output
        if ha_result.fault_results:
            fault_result = ha_result.fault_results[-1]
        if settings.fault_type != "none":
            notes.append(
                "The fault chain is applied after compression; the reported fault parameters are "
                "the true values used by the generator."
            )
    elif settings.fault_type != "none" and ha_module is not None:
        fault_result = ha_module.inject_fault(stage, fs, settings.fault_type, **settings.fault_params)
        y = fault_result.output
    else:
        y = stage
        if settings.fault_type != "none":
            notes.append("Enable the virtual hearing aid or the DSP fault module to inject a fault.")
        if settings.ha_enabled and ha_module is None:
            notes.append("Virtual hearing aid requested but the module is unavailable.")

    time_s = np.arange(x.size, dtype=np.float64) / fs

    # -- metrics -----------------------------------------------------------
    metric_values: dict[str, Any] = {}
    if metrics is not None:
        is_tone = settings.signal_type == "Tone"
        tone_hz = settings.tone_hz if is_tone else None
        try:
            gain = metrics.estimate_gain_db(x_input, y, fs, tone_hz=tone_hz)
            metric_values["gain_db"] = gain.gain_db
            metric_values["gain_method"] = gain.method
        except Exception as exc:  # noqa: BLE001 - metric may be undefined
            metric_values["gain_error"] = f"{type(exc).__name__}: {exc}"
        if is_tone:
            if settings.add_awgn:
                try:
                    snr = metrics.estimate_snr_db(y, fs, settings.tone_hz, method="residual")
                    metric_values["snr_db"] = snr.snr_db
                    metric_values["snr_method"] = snr.method
                except Exception as exc:  # noqa: BLE001
                    metric_values["snr_error"] = f"{type(exc).__name__}: {exc}"
            try:
                thd = metrics.estimate_thd(y, fs, settings.tone_hz, n_harmonics=5)
                metric_values["thd_percent"] = thd.thd_percent
                metric_values["thd_plus_n_percent"] = thd.thd_plus_n_percent
                metric_values["fundamental_dbfs"] = thd.fundamental_dbfs
                metric_values["n_harmonics"] = thd.n_harmonics
            except Exception as exc:  # noqa: BLE001
                metric_values["thd_error"] = f"{type(exc).__name__}: {exc}"
        if filt is not None and filters is not None:
            try:
                analytic = filters.frequency_response(filt, fs, n_freqs=1024)
                metric_values["filter_response"] = analytic
            except Exception as exc:  # noqa: BLE001
                metric_values["filter_response_error"] = f"{type(exc).__name__}: {exc}"
        try:
            estimated = metrics.estimate_filter_response(x_input, y, fs)
            metric_values["system_response"] = estimated
        except Exception as exc:  # noqa: BLE001
            metric_values["system_response_error"] = f"{type(exc).__name__}: {exc}"
    return LabResult(
        time_s=time_s,
        x=x,
        x_input=x_input,
        y=y,
        noise=noise,
        filt=filt,
        ha_result=ha_result,
        fault_result=fault_result,
        metrics=metric_values,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def _decimate(frequencies: np.ndarray, values: np.ndarray, max_points: int = _MAX_PLOT_POINTS):
    if frequencies.size <= max_points:
        return frequencies, values
    step = int(math.ceil(frequencies.size / max_points))
    return frequencies[::step], values[::step]


def _ground_truth_table(settings: LabSettings, result: LabResult) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    is_tone = settings.signal_type == "Tone"
    metrics = result.metrics
    if "gain_db" in metrics:
        rows.append(
            {
                "Quantity": "Gain",
                "Measured/estimated": f"{metrics['gain_db']:.2f} dB",
                "Known ground truth": (
                    f"{settings.ha_input_gain_db:+.1f} dB input gain"
                    + ("; compressor active (level dependent)" if settings.ha_enabled else "")
                ),
                "Method": metrics.get("gain_method", "\u2014"),
            }
        )
    if is_tone and settings.add_awgn and "snr_db" in metrics:
        rows.append(
            {
                "Quantity": "SNR",
                "Measured/estimated": f"{metrics['snr_db']:.2f} dB",
                "Known ground truth": f"{settings.snr_db:.1f} dB configured",
                "Method": metrics.get("snr_method", "\u2014"),
            }
        )
    if is_tone and "thd_percent" in metrics:
        configured_thd = (
            f"{settings.fault_params.get('percentage', 0.0):.2f} % injected"
            if settings.fault_type == "harmonic_distortion"
            else "clean tone (no harmonic fault injected)"
        )
        rows.append(
            {
                "Quantity": "THD",
                "Measured/estimated": f"{metrics['thd_percent']:.3f} %",
                "Known ground truth": configured_thd,
                "Method": "harmonic projection",
            }
        )
        rows.append(
            {
                "Quantity": "THD+N",
                "Measured/estimated": f"{metrics['thd_plus_n_percent']:.3f} %",
                "Known ground truth": (
                    f"{settings.fault_params.get('percentage', 0.0):.2f} % + configured noise"
                    if settings.fault_type == "harmonic_distortion" and settings.add_awgn
                    else "depends on noise/fault chain"
                ),
                "Method": "residual after fundamental removal",
            }
        )
    if result.fault_result is not None:
        rows.append(
            {
                "Quantity": "Fault",
                "Measured/estimated": result.fault_result.fault_type,
                "Known ground truth": str(dict(result.fault_result.true_params)),
                "Method": "true generator parameters",
            }
        )
    return pd.DataFrame(rows)


def _render_waveforms(result: LabResult) -> None:
    series = {"Input (conditioned)": result.x_input, "Output (processed)": result.y}
    if result.noise is not None:
        series["Injected noise"] = result.noise
    figure = plotting.time_series_figure(result.time_s, series, title="Time waveform", height=360)
    st.plotly_chart(figure, width="stretch")


def _render_spectrum(result: LabResult, fs: int) -> None:
    spectra = ui.optional_import("acousticbench.dsp.spectra", feature="Spectral analysis")
    if spectra is None:
        return
    try:
        input_spectrum = spectra.fft_spectrum(result.x_input, fs)
        output_spectrum = spectra.fft_spectrum(result.y, fs)
    except Exception as exc:  # noqa: BLE001 - UI state
        theme.error_panel(f"FFT analysis failed: {exc}")
        return
    frequencies, input_db = _decimate(input_spectrum.frequencies_hz, input_spectrum.magnitude_db)
    _, output_db = _decimate(output_spectrum.frequencies_hz, output_spectrum.magnitude_db)
    mask = frequencies >= 20.0
    figure = plotting.spectrum_figure(
        frequencies[mask],
        {"Input": input_db[mask], "Output": output_db[mask]},
        title="One-sided FFT magnitude (Hann window)",
    )
    figure.update_yaxes(range=[-160, 20])
    st.plotly_chart(figure, width="stretch")


def _render_spectrogram(result: LabResult, fs: int) -> None:
    spectra = ui.optional_import("acousticbench.dsp.spectra", feature="Spectral analysis")
    if spectra is None:
        return
    n = result.y.size
    nperseg = min(1024, max(64, n // 4))
    noverlap = nperseg // 2
    try:
        stft_result = spectra.stft(result.y, fs, nperseg=nperseg, noverlap=noverlap)
    except Exception as exc:  # noqa: BLE001
        theme.error_panel(f"STFT analysis failed: {exc}")
        return
    figure = plotting.stft_figure(
        stft_result.frequencies_hz,
        stft_result.times_s,
        stft_result.magnitude_db,
        title=f"STFT magnitude (nperseg={nperseg}, overlap {noverlap})",
    )
    st.plotly_chart(figure, width="stretch")
    st.caption("The logarithmic frequency axis is used for consistency with the other spectra.")


def _render_psd(result: LabResult, fs: int) -> None:
    spectra = ui.optional_import("acousticbench.dsp.spectra", feature="Spectral analysis")
    if spectra is None:
        return
    try:
        psd_result = spectra.welch_psd(result.y, fs, nperseg=min(4096, result.y.size))
    except Exception as exc:  # noqa: BLE001
        theme.error_panel(f"Welch PSD analysis failed: {exc}")
        return
    with np.errstate(divide="ignore"):
        psd_db = 10.0 * np.log10(np.maximum(psd_result.psd, 1e-30))
    frequencies, values = _decimate(psd_result.frequencies_hz, psd_db)
    mask = frequencies >= 20.0
    figure = plotting.spectrum_figure(
        frequencies[mask],
        {"Welch PSD": values[mask]},
        title=f"Welch power spectral density (nperseg={psd_result.nperseg})",
        y_title="PSD [dB re 1/Hz]",
    )
    st.plotly_chart(figure, width="stretch")


def _render_filter_response(settings: LabSettings, result: LabResult) -> None:
    metrics = result.metrics
    analytic = metrics.get("filter_response")
    estimated = metrics.get("system_response")
    if analytic is None and estimated is None:
        st.info("Enable the filter and/or virtual hearing aid to inspect the system response.")
        return
    figure = go.Figure()
    if analytic is not None:
        figure.add_trace(
            go.Scatter(
                x=analytic.frequencies_hz,
                y=analytic.magnitude_db,
                mode="lines",
                name="Designed filter response (analytic)",
                line=dict(color=plotting.COLORWAY[0], width=1.8),
            )
        )
    if estimated is not None:
        figure.add_trace(
            go.Scatter(
                x=estimated.frequencies_hz,
                y=estimated.magnitude_db,
                mode="lines",
                name="Estimated input\u2192output response (H1)",
                line=dict(color=plotting.COLORWAY[1], width=1.8, dash="dash"),
            )
        )
    figure.update_xaxes(type="log", title_text="Frequency [Hz]")
    figure.update_yaxes(title_text="Magnitude [dB]")
    figure.update_layout(
        template=plotting.PLOTLY_TEMPLATE,
        title="System frequency response",
        height=420,
    )
    st.plotly_chart(figure, width="stretch")
    if analytic is not None and estimated is not None and not settings.ha_enabled:
        common = np.intersect1d(
            np.round(analytic.frequencies_hz, 6), np.round(estimated.frequencies_hz, 6)
        )
        if common.size:
            analytic_db = np.interp(common, analytic.frequencies_hz, analytic.magnitude_db)
            estimated_db = np.interp(common, estimated.frequencies_hz, estimated.magnitude_db)
            mask = (common >= 100.0) & (common <= 8000.0)
            if mask.any():
                mae = float(np.mean(np.abs(analytic_db[mask] - estimated_db[mask])))
                st.caption(
                    f"Mean absolute error between designed and estimated response "
                    f"(100\u20138000 Hz): {mae:.3f} dB."
                )
    if settings.ha_enabled:
        st.caption(
            "The virtual hearing aid is a nonlinear, level-dependent system, so the estimated "
            "response is not a single linear transfer function; it is shown for orientation only."
        )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def render() -> None:
    """Render the Signal Laboratory page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Synthetic DSP workbench")

    modules: dict[str, Any] = {"signals": ui.optional_import("acousticbench.dsp.signals", feature="Signal generation")}
    if modules["signals"] is None:
        return
    modules["spectra"] = ui.optional_import("acousticbench.dsp.spectra", feature="Spectral analysis")
    modules["filters"] = ui.optional_import("acousticbench.dsp.filters", feature="Filter design")
    modules["metrics"] = ui.optional_import("acousticbench.dsp.metrics", feature="Signal metrics")
    modules["virtual_ha"] = ui.optional_import("acousticbench.virtual_ha", feature="Virtual hearing aid")

    settings = _sidebar_controls()
    if settings.sweep_end_hz <= settings.sweep_start_hz:
        theme.warning_panel(
            "Sweep end frequency must exceed the start frequency; adjust the sidebar controls.",
            title="Invalid sweep configuration",
        )
        return

    result, error = ui.safe_call(_process, settings, modules)
    if error is not None or result is None:
        theme.error_panel(f"Signal processing failed: {error}")
        return

    input_rms = float(np.sqrt(np.mean(np.square(result.x_input))))
    output_rms = float(np.sqrt(np.mean(np.square(result.y))))
    metric_cards = [
        (
            "Gain",
            f"{result.metrics['gain_db']:.2f} dB" if "gain_db" in result.metrics else "\u2014",
            result.metrics.get("gain_method", ""),
        ),
        (
            "SNR",
            f"{result.metrics['snr_db']:.1f} dB" if "snr_db" in result.metrics else "n/a",
            "Requires a tone plus added noise.",
        ),
        (
            "THD",
            f"{result.metrics['thd_percent']:.3f} %" if "thd_percent" in result.metrics else "n/a",
            "Requires a tone signal.",
        ),
        (
            "THD+N",
            f"{result.metrics['thd_plus_n_percent']:.3f} %" if "thd_plus_n_percent" in result.metrics else "n/a",
            "Residual after removing the fundamental.",
        ),
        ("Output RMS", f"{output_rms:.4f}", f"Input RMS {input_rms:.4f}"),
    ]
    theme.metric_cards(metric_cards)
    st.caption(
        f"Sampling rate {settings.fs} Hz \u00b7 {result.x.size} samples \u00b7 "
        f"{result.x.size / settings.fs:.2f} s \u00b7 signal {settings.signal_type.lower()} at "
        f"{settings.level_dbfs:g} dBFS RMS."
    )

    for note in result.notes:
        theme.warning_panel(note, title="Processing note")

    if result.ha_result is not None:
        st.caption(
            "Virtual hearing aid active: "
            f"input gain {settings.ha_input_gain_db:+.1f} dB, crossover {settings.crossover_hz:g} Hz, "
            f"compressors {settings.low_ratio:g}:1 / {settings.high_ratio:g}:1, "
            f"limiter {'on' if settings.limiter_enabled else 'off'}."
        )
    if result.fault_result is not None:
        theme.info_panel(
            f"Fault injected: <strong>{result.fault_result.fault_type}</strong> \u2014 "
            f"{result.fault_result.description}"
        )

    ground_truth = _ground_truth_table(settings, result)
    theme.section_title(
        "Ground truth versus estimate",
        "Configured generator parameters are the known ground truth; the estimate is computed "
        "from the measured signals with the acousticbench DSP metrics.",
    )
    if ground_truth.empty:
        st.info("No metric is defined for the current signal configuration.")
    else:
        st.dataframe(ground_truth, width="stretch", hide_index=True)
        ui.download_frame(ground_truth, "signal_lab_metrics.csv", "Download metric table (CSV)")

    tabs = st.tabs(["Waveforms", "FFT spectrum", "STFT spectrogram", "Welch PSD", "Filter response"])
    with tabs[0]:
        _render_waveforms(result)
    with tabs[1]:
        _render_spectrum(result, settings.fs)
    with tabs[2]:
        _render_spectrogram(result, settings.fs)
    with tabs[3]:
        _render_psd(result, settings.fs)
    with tabs[4]:
        _render_filter_response(settings, result)

    with st.expander("Synthetic validation cases (reference preview)", expanded=False):
        from app.components.data import optional_module

        cases_module, cases_error = optional_module("acousticbench.synthetic.cases")
        if cases_module is None:
            theme.warning_panel(
                f"Synthetic case generation is not available (<code>{cases_error}</code>). "
                "Run the experiments/tests once the module is present.",
                title="Module not yet available",
            )
        else:
            try:
                cases = cases_module.build_cases(n_cases=8, seed=20260422)
                st.dataframe(pd.DataFrame([case.to_dict() for case in cases]), width="stretch", hide_index=True)
                st.caption(
                    "Preview of the synthetic validation suite (E09\u2013E12). Full case generation "
                    "and evaluation is performed by the experiment pipeline."
                )
            except Exception as exc:  # noqa: BLE001 - preview only
                theme.warning_panel(f"Synthetic cases could not be generated: {exc}")

    theme.footnote(
        "All signals are deterministic given the seed. The page illustrates the DSP building "
        "blocks; the acceptance targets of the synthetic benchmark are evaluated by experiments "
        "E09\u2013E12 and summarised on the Validation page."
    )
