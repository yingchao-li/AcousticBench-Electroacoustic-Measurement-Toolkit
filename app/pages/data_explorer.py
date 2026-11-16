"""Page 1 — Data Explorer.

Dataset provenance, persisted/fresh data-quality audit, validity masks, NaN
sessions, structural-validity rules, interactive filtering and raw/curve
inspection with CSV download.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import streamlit as st

from acousticbench.types import CONTAINER_ORDER, CONTAINERS, DEVICES, P_REF_PA, Probe
from app.components import filters, plotting, theme, ui
from app.components.data import (
    get_audit_state,
    get_config,
    get_dataset_state,
    get_results_state,
    run_audit_now,
)

TITLE = "Data Explorer"
SUBTITLE = (
    "Dataset provenance and audit, measured-NaN and structural validity masks, and "
    "interactive raw-data inspection."
)


def _reference_for(container: str) -> float:
    """dB reference of a container (Pa for pressure data, 1.0 otherwise)."""
    unit = CONTAINERS[container].unit
    return P_REF_PA if "Pa" in unit else 1.0


def _metrics(state, audit, results_count: int) -> None:
    dataset = state.dataset
    if dataset is not None:
        info = dataset.info
        dimension_text = (
            f"{dataset.frequency_hz.size} \u00d7 {len(dataset.devices)} \u00d7 "
            f"{dataset.subjects.size} \u00d7 {dataset.reinsertions.size}"
        )
        sha = (info.sha256 or "\u2014")[:12]
        n_invalid = int(dataset.session_validity_summary()["n_invalid_sessions"].sum())
        file_label = f"{info.path.name} \u00b7 {state.size_mb:.0f} MB"
    else:
        dimension_text = "\u2014"
        sha = "\u2014"
        n_invalid = 0
        file_label = "not loaded"
    if audit is not None:
        n_passed = sum(1 for item in audit.findings if item.status == "PASS")
        audit_label = f"{n_passed} / {len(audit.findings)} passed"
    else:
        audit_label = "not persisted"
    theme.metric_cards(
        [
            ("Dataset file", file_label, "Loaded from the path configured in config/default.yaml."),
            ("Axes (freq \u00d7 devices \u00d7 subjects \u00d7 reinsertions)", dimension_text, None),
            ("Invalid (all-NaN) sessions", f"{n_invalid}", "Excluded everywhere; never imputed."),
            ("Data audit checks", audit_label, "Persisted audit at results/audit/data_audit.json."),
            ("Saved experiments", f"{results_count}", "Directories with result.json under results/experiments."),
        ]
    )
    st.caption(f"Data fingerprint (SHA-256, first 12 characters): `{sha}`")


def _provenance_tab(dataset, audit) -> None:
    theme.section_title(
        "Provenance",
        "Source publication, file fingerprint and the documented interpretation of the study design.",
    )
    provenance = (audit.provenance if audit is not None else {}) or {}
    file_info = (audit.dataset_summary.get("file", {}) if audit is not None else {}) or {}
    if dataset is not None and not file_info:
        file_info = dataset.info.to_dict()
    rows = [
        ("Dataset", "Denk, Hackenberg & Husstedt (2026)"),
        ("Dataset DOI", provenance.get("dataset_doi", "doi:10.5281/zenodo.20023285")),
        ("Preprint DOI", provenance.get("preprint_doi", "\u2014")),
        ("Authors", provenance.get("authors", "Denk, Hackenberg & Husstedt")),
        ("Licence", provenance.get("licence", "CC BY 4.0")),
        ("Documentation", provenance.get("documentation", "Documentation.pdf")),
        ("Data file", str(file_info.get("path", get_config().data_path))),
        ("Size [MB]", f"{float(file_info.get('size_mb', 0.0)):.1f}"),
        ("MAT format", str(file_info.get("mat_format", "\u2014"))),
        ("SHA-256", str(file_info.get("sha256", "\u2014"))),
    ]
    st.dataframe(
        pd.DataFrame(rows, columns=["Field", "Value"]),
        width="stretch",
        hide_index=True,
    )
    if dataset is not None:
        with st.expander("Dataset description", expanded=False):
            st.code(dataset.describe(), language="text")
    theme.footnote(
        "Structural validity is a property of the study design, not of the data quality: "
        "values may exist in the file yet be physically meaningless for the analysed quantity. "
        "AcousticBench never imputes and never silently drops such values."
    )


def _validity_tab(dataset, audit) -> None:
    theme.section_title(
        "Validity masks and NaN sessions",
        "Two independent validity dimensions are combined: measured NaN (data provider) and "
        "structural validity (documented physical meaning).",
    )
    if audit is not None:
        checks = audit.checks_frame()
        if not checks.empty:
            st.markdown("**Persisted audit checks**")
            st.dataframe(checks, width="stretch", hide_index=True, height=300)
        validity = audit.session_validity
        if validity is not None and not validity.empty:
            st.markdown("**Session validity per container**")
            st.dataframe(validity, width="stretch", hide_index=True)
            invalid = audit.invalid_sessions
            st.markdown(
                f"**Invalid (all-NaN) sessions**: {0 if invalid is None else len(invalid)} rows. "
                "They are excluded from every analysis."
            )
            if invalid is not None and not invalid.empty:
                groups = (
                    invalid.groupby(["container", "device"], as_index=False)
                    .size()
                    .rename(columns={"size": "n_invalid_sessions"})
                )
                st.dataframe(groups, width="stretch", hide_index=True, height=280)
        structural = audit.structural_validity
        if structural is not None and not structural.empty:
            st.markdown("**Structural validity rules**")
            columns = [
                column
                for column in (
                    "container",
                    "description",
                    "valid_conditions",
                    "valid_couplings",
                    "n_structurally_valid_devices",
                    "valid_device_codes",
                    "rationale",
                )
                if column in structural.columns
            ]
            st.dataframe(structural[columns], width="stretch", hide_index=True, height=340)
        return

    if dataset is None:
        theme.warning_panel(
            "Neither a persisted audit nor the measurement dataset is available, so validity "
            "information cannot be displayed. Provide <code>Data.mat</code> and run the audit."
        )
        return
    st.markdown("**Session validity per container (computed from the dataset)**")
    st.dataframe(dataset.session_validity_summary(), width="stretch", hide_index=True)
    st.markdown("**Structural validity rules**")
    rows = []
    for key in CONTAINER_ORDER:
        spec = CONTAINERS[key]
        valid_codes = [device.code for device in DEVICES if spec.structural_valid(device)]
        rows.append(
            {
                "container": key,
                "description": spec.description,
                "valid_conditions": (
                    ", ".join(sorted(condition.value for condition in spec.valid_conditions))
                    if spec.valid_conditions
                    else "all"
                ),
                "valid_couplings": (
                    ", ".join(sorted(coupling.value for coupling in spec.valid_couplings))
                    if spec.valid_couplings
                    else "all"
                ),
                "n_structurally_valid_devices": len(valid_codes),
                "valid_device_codes": ", ".join(str(code) for code in valid_codes),
                "rationale": spec.rationale,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=360)


def _build_cube(dataset, key: str, probe: Probe | None, conditions, families, subjects, devices):
    """Select the inspection cube, applying the probe override if requested."""
    if key == "M_REUR":
        cube, error = ui.safe_call(dataset.reur, subjects=subjects or None)
        return cube, error
    selection = {
        "conditions": conditions or None,
        "families": families or None,
        "subjects": subjects or None,
        "device_codes": devices or None,
    }
    return ui.safe_call(dataset.get, key, **selection)


def _curves_tab(cube, key: str, reference: float) -> None:
    theme.section_title(
        "Filtered level curves",
        "Median across the selected subjects and reinsertions; the frequency axis is "
        "logarithmic and bins below 50 Hz (not excited by the sweep) are hidden.",
    )
    levels = cube.level_array(reference=reference)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        median = np.nanmedian(levels, axis=(2, 3))
    frequencies = np.asarray(cube.freq_hz, dtype=float)
    keep = frequencies >= max(50.0, float(frequencies[1]) if frequencies.size > 1 else 50.0)
    if not keep.any():
        keep = np.ones_like(frequencies, dtype=bool)
    rows = []
    for device_index, device in enumerate(cube.devices):
        rows.append(
            pd.DataFrame(
                {
                    "frequency_hz": frequencies[keep],
                    "device_code": device.code,
                    "family": device.family,
                    "device": device.short_label,
                    "level_db": median[keep, device_index],
                }
            )
        )
    frame = pd.concat(rows, ignore_index=True).dropna(subset=["level_db"])
    if frame.empty:
        st.info("No finite levels are available for the current selection.")
        return
    unit_label = CONTAINERS[key].unit_label
    figure = plotting.curves_figure(
        frame,
        x="frequency_hz",
        y="level_db",
        series="family",
        title=f"Median level per device \u2014 {key}",
        y_title=f"Level [{unit_label}]",
    )
    st.plotly_chart(figure, width="stretch")
    ui.download_frame(
        frame, f"{key}_filtered_median_curves.csv", "Download filtered median curves (CSV)"
    )


def _raw_tab(cube, key: str, reference: float) -> None:
    theme.section_title(
        "Raw values",
        "Filtered, validity-masked values in long format. Use the checkbox to load the table; "
        "the full filtered frame is downloadable as CSV.",
    )
    load_raw = st.checkbox(
        "Load filtered raw value table",
        value=False,
        help="May contain several hundred thousand rows for broad selections.",
    )
    if not load_raw:
        st.caption("Enable the checkbox to build the filtered long-format table.")
        return
    levels = cube.level_array(reference=reference)
    n_freq, n_dev, n_subj, n_re = levels.shape
    finite = np.isfinite(levels)
    if not finite.any():
        st.info("The current selection contains no valid values.")
        return
    freq_index, device_index, subject_index, reinsertion_index = np.nonzero(finite)
    axis_name = cube.axis_name
    device_codes = np.asarray([device.code for device in cube.devices])
    family_names = np.asarray([device.family for device in cube.devices])
    condition_names = np.asarray(
        [device.condition.value if device.condition is not None else "" for device in cube.devices]
    )
    frame = pd.DataFrame(
        {
            axis_name: np.asarray(cube.freq_hz)[freq_index],
            "device_code": device_codes[device_index],
            "family": family_names[device_index],
            "condition": condition_names[device_index],
            "subject": np.asarray(cube.subjects)[subject_index],
            "reinsertion": np.asarray(cube.reinsertions)[reinsertion_index],
            "level_db": levels[finite],
        }
    )
    st.caption(f"{len(frame)} valid rows for the current filter selection.")
    st.dataframe(frame.head(5000), width="stretch", hide_index=True, height=380)
    ui.download_frame(frame, f"{key}_filtered_values.csv", "Download filtered raw values (CSV)")


def _audit_tab(audit, audit_state) -> None:
    theme.section_title(
        "Data-quality audit",
        "Persisted audit artefact if available; otherwise the audit can be run in memory "
        "(fast, ~1–2 s) without modifying files on disk.",
    )
    if audit is None:
        theme.info_panel(
            "No persisted audit is available. Run the audit below to display the full "
            "data-quality report. The computed audit is held in memory only; the persisted "
            "artefact is produced by the data-audit command."
        )
        if st.button("Run data audit now", type="primary"):
            with st.spinner("Running the data-quality audit ..."):
                state = run_audit_now()
            st.session_state["de_audit_override"] = state
            st.rerun()
    override = st.session_state.get("de_audit_override")
    current = audit if audit is not None else (override.audit if override is not None else None)
    if current is None:
        if override is not None and override.error:
            theme.error_panel(override.error, title="Audit failed")
        return
    summary = current.to_dict()["summary"]
    theme.metric_cards(
        [
            ("Checks", str(summary["n_checks"]), None),
            ("Passed", str(summary["n_passed"]), None),
            ("Warnings", str(summary["n_warnings"]), None),
            ("Errors", str(summary["n_errors"]), None),
        ]
    )
    source = "persisted artefact" if audit is not None else "computed in memory"
    theme.footnote(f"Audit source: {source} \u00b7 generated {current.generated_at or '\u2014'}")
    st.markdown("**Automated checks**")
    st.dataframe(current.checks_frame(), width="stretch", hide_index=True, height=320)
    if current.variables is not None and not current.variables.empty:
        with st.expander("Variables", expanded=False):
            st.dataframe(current.variables, width="stretch", hide_index=True)
    if current.derived:
        with st.expander("Derived interpretation", expanded=False):
            st.json(current.derived)


def render() -> None:
    """Render the Data Explorer page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Explore the dataset")
    config = get_config()
    state = get_dataset_state()
    audit_state = get_audit_state()
    results_state = get_results_state()
    dataset = ui.ensure_dataset()
    audit = audit_state.audit

    _metrics(state, audit, len(results_state.results))

    # Sidebar inspection filters -------------------------------------------------
    st.sidebar.markdown("### Inspection filters")
    available_containers = [key for key in CONTAINER_ORDER]
    container = st.sidebar.selectbox(
        "Data container",
        options=available_containers,
        index=0,
        format_func=lambda key: f"{key} \u2014 {CONTAINERS[key].description[:52]}",
        key="de_container",
    )
    probe = filters.probe_widget("de", default=None)
    key = container
    if probe is not None:
        key = "M_ha2edM" if probe is Probe.MEASUREMENT else "M_ha2edR"
        st.sidebar.caption(
            f"Probe filter overrides the container: showing `{key}` "
            f"({probe.label} eardrum pressure)."
        )
    conditions = filters.condition_widget("de")
    families = filters.families_widget("de")
    subjects = filters.subjects_widget("de", dataset)
    device_options = (
        [device for device in DEVICES if device.family in set(families)]
        if families
        else list(DEVICES)
    )
    devices = filters.device_widget("de", device_options)

    cube = None
    cube_error = None
    if dataset is not None:
        cube, cube_error = _build_cube(dataset, key, probe, conditions, families, subjects, devices)
        if cube_error:
            theme.warning_panel(
                f"The current filter selection could not be applied: {cube_error}. "
                "Adjust the family/condition/device selection.",
                title="Empty selection",
            )

    tabs = st.tabs(
        ["Overview & provenance", "Validity & NaN sessions", "Curves", "Raw values", "Audit"]
    )
    with tabs[0]:
        _provenance_tab(dataset, audit)
        if dataset is not None:
            theme.section_title("Containers")
            rows = []
            for container_key in CONTAINER_ORDER:
                spec = CONTAINERS[container_key]
                value = dataset.values(container_key)
                rows.append(
                    {
                        "container": container_key,
                        "shape": str(tuple(value.shape)),
                        "dtype": str(value.dtype),
                        "description": spec.description,
                        "unit": spec.unit,
                    }
                )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with tabs[1]:
        _validity_tab(dataset, audit)
    with tabs[2]:
        if cube is None:
            theme.info_panel(
                "No measurement cube is available for the current selection. The dataset "
                "must be loaded to inspect curves."
            )
        else:
            _curves_tab(cube, key, _reference_for(key))
    with tabs[3]:
        if cube is None:
            theme.info_panel("No measurement cube is available for the current selection.")
        else:
            _raw_tab(cube, key, _reference_for(key))
    with tabs[4]:
        _audit_tab(audit, audit_state)

    theme.footnote(
        "All values are shown exactly as measured: NaN entries and structurally invalid entries "
        "are masked, never imputed. "
        f"Configured analysis floor: {config.analysis.level_floor_db:g} dB."
    )
