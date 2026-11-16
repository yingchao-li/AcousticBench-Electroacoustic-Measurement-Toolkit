"""Page 8 — Validation.

Synthetic-benchmark accuracy versus acceptance targets (E09–E12), MATLAB–Python
agreement status (E15 — MATLAB is not available in this environment), the data
audit check count, and the experiment status index.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import theme, ui
from app.components.data import (
    get_audit_state,
    get_config,
    get_results_state,
    run_audit_now,
)

TITLE = "Validation"
SUBTITLE = (
    "Synthetic-benchmark accuracy against acceptance targets, cross-language MATLAB status, "
    "data-audit checks and the experiment status index."
)

#: Known experiment titles (used when the registry/result directory is incomplete).
_EXPECTED_TITLES: dict[str, str] = {
    "E01": "Frequency Response",
    "E02": "Probe Tube Measurement Bias",
    "E03": "Measurement Repeatability",
    "E04": "Inter-subject Variability",
    "E05": "Acoustic Feedback",
    "E06": "Real-Ear Response",
    "E07": "Hearing Threshold",
    "E08": "Statistical Comparison",
    "E09": "Synthetic Gain Validation",
    "E10": "Synthetic THD Validation",
    "E11": "Synthetic SNR Validation",
    "E12": "Synthetic Frequency-Response Validation",
    "E13": "Dynamic Compression",
    "E14": "Fault Injection",
    "E15": "MATLAB-Python Agreement",
    "E16": "Performance Benchmark",
}

_EXPECTED_CODES = [f"E{index:02d}" for index in range(1, 17)]


def _registry_titles() -> dict[str, str]:
    try:
        from acousticbench.experiments.registry import EXPERIMENTS

        return {code: spec.title for code, spec in EXPERIMENTS.items()}
    except Exception:  # noqa: BLE001 - registry is optional for this page
        return {}


def _status_table() -> tuple[pd.DataFrame, str | None, str | None]:
    """Merge the persisted index and the discovered result directories."""
    state = get_results_state()
    by_code = state.by_code
    titles = {**_EXPECTED_TITLES, **_registry_titles()}
    index_entries: dict[str, dict] = {}
    index_generated: str | None = None
    index_error: str | None = None
    if state.index is not None:
        index_generated = str(state.index.get("generated", ""))
        for entry in state.index.get("experiments", []):
            if isinstance(entry, dict) and entry.get("code"):
                index_entries[str(entry["code"])] = entry
    elif state.error:
        index_error = state.error

    codes = sorted(set(_EXPECTED_CODES) | set(by_code) | set(index_entries))
    rows = []
    for code in codes:
        result = by_code.get(code)
        entry = index_entries.get(code, {})
        if result is not None:
            rows.append(
                {
                    "Code": code,
                    "Title": result.title or titles.get(code, ""),
                    "Status": result.status,
                    "Source": "results directory",
                    "Runtime [s]": round(float(result.duration_s), 2),
                    "Tables": len(result.tables),
                    "Figures": len(getattr(result, "figure_paths", {}) or {}),
                    "Warnings": len(result.warnings),
                    "Error": result.error or "",
                }
            )
        elif entry:
            rows.append(
                {
                    "Code": code,
                    "Title": entry.get("title", titles.get(code, "")),
                    "Status": entry.get("status", "unknown"),
                    "Source": "experiment_index.json",
                    "Runtime [s]": entry.get("duration_s", ""),
                    "Tables": len(entry.get("tables", {}) or {}),
                    "Figures": len(entry.get("figures", []) or []),
                    "Warnings": len(entry.get("warnings", []) or []),
                    "Error": entry.get("error") or "",
                }
            )
        else:
            rows.append(
                {
                    "Code": code,
                    "Title": titles.get(code, ""),
                    "Status": "not run",
                    "Source": "\u2014",
                    "Runtime [s]": "",
                    "Tables": 0,
                    "Figures": 0,
                    "Warnings": 0,
                    "Error": "",
                }
            )
    return pd.DataFrame(rows), index_generated, index_error


def _synthetic_tab(results_state) -> None:
    theme.section_title(
        "Synthetic benchmark accuracy versus targets (E09\u2013E12)",
        "The synthetic suite has known ground truth; the acceptance targets below are only "
        "evaluated under the documented reference conditions (config/default.yaml).",
    )
    config = get_config()
    targets = dict(config.synthetic.targets or {})
    if targets:
        st.markdown("**Acceptance targets**")
        st.dataframe(
            pd.DataFrame(
                [{"Metric": key, "Target": value} for key, value in targets.items()]
            ),
            width="stretch",
            hide_index=True,
        )
        with st.expander("Reference conditions", expanded=False):
            st.json(dict(config.synthetic.reference_conditions or {}))

    for code, label in (
        ("E09", "Gain"),
        ("E10", "THD"),
        ("E11", "SNR"),
        ("E12", "Frequency response"),
    ):
        result = results_state.by_code.get(code)
        theme.section_title(f"{code} \u2014 synthetic {label} validation")
        if result is None:
            theme.info_panel(
                f"Experiment <strong>{code}</strong> ({label}) has not been run yet, so no "
                "accuracy metrics are available. Run the synthetic validation experiments to "
                "populate <code>results/experiments/</code>; the page will then show the measured "
                "errors against the targets above."
            )
            continue
        ui.result_summary_panel(result, code=code, title=label, expanded=False)
        metrics = ui.result_metrics_frame(result)
        if not metrics.empty:
            st.dataframe(metrics, width="stretch", hide_index=True, height=min(420, 60 + 28 * len(metrics)))
            ui.download_frame(metrics, f"{code}_metrics.csv", f"Download {code} metrics (CSV)")

    theme.section_title("Other DSP/validation experiments")
    for code in ("E13", "E14", "E16"):
        result = results_state.by_code.get(code)
        ui.result_summary_panel(result, code=code, title=_EXPECTED_TITLES.get(code, ""))


def _matlab_tab(results_state) -> None:
    theme.section_title(
        "MATLAB\u2013Python agreement (E15)",
        "Cross-language numerical consistency checks require a local MATLAB installation.",
    )
    theme.error_panel(
        "<strong>MATLAB is not available in this environment.</strong> Experiment E15 "
        "(MATLAB\u2013Python agreement) therefore cannot be executed and the numerical "
        "agreement between the reference MATLAB implementation and this Python implementation "
        "is <strong>not verified</strong> by this toolkit. No agreement result is claimed or "
        "fabricated here.",
        title="MATLAB status",
    )
    config = get_config()
    tolerances = config.get("experiments.params.E15.tolerances", {}) or {}
    if tolerances:
        st.markdown("**Configured agreement tolerances (not evaluated)**")
        st.dataframe(
            pd.DataFrame(
                [{"Quantity": key, "Tolerance": value} for key, value in tolerances.items()]
            ),
            width="stretch",
            hide_index=True,
        )
    matlab_dir = config.root / "matlab"
    if matlab_dir.is_dir():
        scripts = sorted(path.name for path in matlab_dir.rglob("*") if path.is_file())
        st.markdown(
            f"Reference MATLAB material is present under `{matlab_dir}` "
            f"({len(scripts)} file(s)); it was not executed because MATLAB is unavailable."
        )
        with st.expander("Reference MATLAB files (not executed)", expanded=False):
            st.code("\n".join(scripts) or "(empty)", language="text")
    result = results_state.by_code.get("E15")
    if result is None:
        theme.info_panel(
            "No E15 result artefact exists. When MATLAB becomes available, run E15 and this panel "
            "will show the measured magnitude/phase/level agreement against the tolerances above."
        )
    else:
        ui.result_summary_panel(result, code="E15", title="MATLAB-Python Agreement", expanded=True)


def _audit_tab(audit_state) -> None:
    theme.section_title(
        "Data audit checks",
        "Number of automated data-quality checks, their outcome and the invalid-session summary.",
    )
    audit = audit_state.audit
    if audit is None:
        theme.warning_panel(
            "No persisted audit is available. Run the audit below to display the check count. "
            "The computed audit is held in memory only.",
            title="Audit not persisted",
        )
        if st.button("Run data audit now", type="primary", key="val_run_audit"):
            with st.spinner("Running the data-quality audit ..."):
                state = run_audit_now()
            st.session_state["val_audit_override"] = state
            st.rerun()
        override = st.session_state.get("val_audit_override")
        if override is not None and override.error:
            theme.error_panel(override.error, title="Audit failed")
        elif override is not None:
            audit = override.audit
        if audit is None:
            return
    n_passed = sum(1 for item in audit.findings if item.status == "PASS")
    theme.metric_cards(
        [
            ("Automated checks", str(len(audit.findings)), None),
            ("Passed", str(n_passed), None),
            ("Warnings", str(audit.n_warnings), None),
            ("Errors", str(audit.n_errors), None),
            (
                "Invalid (NaN) sessions",
                str(0 if audit.invalid_sessions is None else len(audit.invalid_sessions)),
                "Excluded from all analyses.",
            ),
        ]
    )
    st.markdown("**Checks**")
    st.dataframe(audit.checks_frame(), width="stretch", hide_index=True, height=360)
    if audit.session_validity is not None and not audit.session_validity.empty:
        st.markdown("**Session validity per container**")
        st.dataframe(audit.session_validity, width="stretch", hide_index=True)


def render() -> None:
    """Render the Validation page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Verification & validation")
    config = get_config()
    audit_state = get_audit_state()
    results_state = get_results_state()
    status_frame, index_generated, index_error = _status_table()

    completed = int((status_frame["Status"] == "completed").sum())
    failed = int((status_frame["Status"] == "failed").sum())
    not_run = int((status_frame["Status"] == "not run").sum())
    audit = audit_state.audit
    audit_label = f"{len(audit.findings)} checks" if audit is not None else "not persisted"
    theme.metric_cards(
        [
            ("Experiments completed", str(completed), "Across all discovered result artefacts."),
            ("Failed experiments", str(failed), "Failures are reported, never hidden."),
            ("Not run", str(not_run), "No result artefact found yet."),
            ("Data audit", audit_label, "Persisted at results/audit/data_audit.json."),
            ("MATLAB", "unavailable", "Cross-language agreement cannot be verified here."),
        ]
    )

    if index_error:
        theme.warning_panel(
            f"The experiment index could not be read: {index_error}. The status table below was "
            "reconstructed from the result directories instead.",
            title="Index unavailable",
        )
    if index_generated:
        theme.footnote(
            f"Experiment index generated at {index_generated}. "
            "The table merges the persisted index with the result directories that exist now."
        )

    tabs = st.tabs(
        [
            "Synthetic benchmark (E09\u2013E12)",
            "MATLAB agreement (E15)",
            "Data audit checks",
            "Experiment status index",
        ]
    )
    with tabs[0]:
        _synthetic_tab(results_state)
    with tabs[1]:
        _matlab_tab(results_state)
    with tabs[2]:
        _audit_tab(audit_state)
    with tabs[3]:
        theme.section_title(
            "Experiment status",
            "Status of every expected experiment. A missing result means the experiment has not "
            "been run in this checkout; it is never reported as passed or failed.",
        )
        st.dataframe(status_frame, width="stretch", hide_index=True, height=560)
        ui.download_frame(status_frame, "experiment_status.csv", "Download status table (CSV)")
        st.caption(
            f"Synthetic suite configuration: {config.synthetic.n_cases} cases, seed "
            f"{config.synthetic.seed}, fs {config.synthetic.fs_hz} Hz, duration "
            f"{config.synthetic.duration_s:g} s."
        )
