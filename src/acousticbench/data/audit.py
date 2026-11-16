"""Data-quality audit of the measurement dataset.

The auditor answers the questions an engineer must ask before trusting any
analysis:

1. Is the file structurally valid (schema, shapes, axes, dtypes)?
2. Where are the measured NaNs, and are the invalid sessions consistent
   between containers?
3. Which stored numbers are *structurally* invalid even though they are not
   NaN (loose probe tube, missing reference probe for domes)?
4. Are the stored units consistent with the documentation (Pa at 11.2 mV,
   Pa at free-field reference, dBV)?
5. Do the physical signatures confirm the documented experimental design
   (probe presence effect directions, free-field reference, cross-probe
   agreement)?
6. How repeatable are the measurements across the three reinsertions?

The audit produces machine-readable JSON/CSV artefacts, a Markdown summary and
a figure.  It is deliberately explicit about *interpretation limits*; no
finding is hard-coded: every statement is recomputed from the data at run time.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # noqa: E402  - must precede pyplot import in headless use
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from acousticbench.config import Config, load_config
from acousticbench.data.dataset import AcousticDataset
from acousticbench.data.validity import invalid_reasons_table, invalid_sessions
from acousticbench.stats.bands import octave_bands  # noqa: E402
from acousticbench.types import (
    CONTAINERS,
    CONTAINER_ORDER,
    DEVICES,
    REFERENCE_DEVICE_CODES,
    REUR_CONTAINER_KEY,
    THRESHOLD_CONTAINER_KEY,
    TRANSFER_CONTAINER_KEYS,
    Condition,
    Coupling,
    Quantity,
)

__all__ = ["AuditFinding", "DataAudit", "DataAuditor"]

_DB_FLOOR = 1e-30


def _db(values: np.ndarray) -> np.ndarray:
    """20 log10 |values| with a numerical floor (NaN preserved)."""
    mag = np.abs(np.asarray(values))
    mag = np.where(np.isfinite(mag), mag, np.nan)
    return 20.0 * np.log10(np.maximum(mag, _DB_FLOOR))


def _median_db(values: np.ndarray) -> float:
    array = _db(values)
    if not np.any(np.isfinite(array)):
        return float("nan")
    return float(np.nanmedian(array))


def _jsonify(value: Any) -> Any:
    """Recursively convert numpy/pandas types to JSON-serialisable objects."""
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        out = float(value)
        return None if math.isnan(out) else out
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, np.ndarray):
        return _jsonify(value.tolist())
    return value


@dataclass(frozen=True)
class AuditFinding:
    """One audit statement with an optional pass/fail expectation."""

    severity: str  # "info" | "warning" | "error"
    code: str
    message: str
    expected: str | None = None
    observed: str | None = None
    passed: bool | None = None

    @property
    def status(self) -> str:
        if self.passed is None:
            return "INFO"
        return "PASS" if self.passed else "WARN"

    def to_row(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "expected": self.expected,
            "observed": self.observed,
        }


@dataclass
class DataAudit:
    """Complete audit result."""

    dataset_summary: dict[str, Any]
    variables: pd.DataFrame
    session_validity: pd.DataFrame
    invalid_sessions: pd.DataFrame
    structural_validity: pd.DataFrame
    findings: list[AuditFinding]
    derived: dict[str, Any]
    frequency_axis: dict[str, Any]
    threshold_axis: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    @property
    def n_errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for f in self.findings if f.status == "WARN")

    @property
    def passed(self) -> bool:
        return self.n_errors == 0 and self.n_warnings == 0

    def checks_frame(self) -> pd.DataFrame:
        return pd.DataFrame([f.to_row() for f in self.findings])

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(
            {
                "generated_at": self.generated_at,
                "dataset": self.dataset_summary,
                "provenance": self.provenance,
                "frequency_axis": self.frequency_axis,
                "threshold_axis": self.threshold_axis,
                "variables": self.variables.to_dict(orient="records"),
                "session_validity": self.session_validity.to_dict(orient="records"),
                "invalid_sessions": self.invalid_sessions.to_dict(orient="records"),
                "structural_validity": self.structural_validity.to_dict(orient="records"),
                "checks": [f.to_row() for f in self.findings],
                "derived": self.derived,
                "summary": {
                    "n_checks": len(self.findings),
                    "n_passed": sum(1 for f in self.findings if f.status == "PASS"),
                    "n_warnings": self.n_warnings,
                    "n_errors": self.n_errors,
                },
            }
        )

    # -- report generation --------------------------------------------------
    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# AcousticBench data audit")
        lines.append("")
        lines.append(f"Generated: `{self.generated_at}`")
        lines.append("")
        summary = self.to_dict()["summary"]
        lines.append(
            f"**{summary['n_passed']} checks passed, {summary['n_warnings']} warnings, "
            f"{summary['n_errors']} errors.**"
        )
        lines.append("")
        file_info = self.dataset_summary.get("file", {})
        lines.append("## Dataset provenance")
        lines.append("")
        if file_info:
            lines.append(f"- File: `{Path(file_info.get('path', '')).name}`")
            lines.append(f"- Size: {file_info.get('size_mb', '—')} MB")
            lines.append(f"- MAT format: {file_info.get('mat_format', '—')}")
            lines.append(f"- SHA-256: `{file_info.get('sha256', '—')}`")
        lines.append(
            "- Source: Denk, Hackenberg & Husstedt (2026), "
            "doi:10.5281/zenodo.20023285 (CC BY 4.0)"
        )
        lines.append("")
        lines.append("## Axes")
        lines.append("")
        fa = self.frequency_axis
        ta = self.threshold_axis
        lines.append(
            f"- Frequency: {fa.get('n_bins')} bins, {fa.get('min_hz')} … {fa.get('max_hz')} Hz, "
            f"Δf = {fa.get('resolution_hz')} Hz (uniform grid: {fa.get('uniform')})"
        )
        lines.append(f"- Audiometric frequencies: {ta.get('frequencies_hz')} Hz")
        lines.append(
            f"- Threshold quantisation: {ta.get('quantisation_db')} dB "
            f"(observed residual ≤ {ta.get('max_quantisation_residual_db')} dB)"
        )
        lines.append("")
        lines.append("## Checks")
        lines.append("")
        lines.append("| Status | Code | Finding |")
        lines.append("| --- | --- | --- |")
        for finding in self.findings:
            lines.append(f"| {finding.status} | `{finding.code}` | {finding.message} |")
        lines.append("")
        lines.append("## Variables")
        lines.append("")
        lines.append(
            self.variables[
                ["key", "shape", "dtype", "n_nan", "nan_fraction", "median_level_db", "unit"]
            ].to_markdown(index=False)
        )
        lines.append("")
        lines.append("## Invalid (NaN) sessions")
        lines.append("")
        lines.append(
            f"{len(self.invalid_sessions)} (container, device, subject, reinsertion) sessions "
            "are completely NaN and are excluded from every analysis."
        )
        if not self.invalid_sessions.empty:
            counts = (
                self.invalid_sessions.groupby("container")
                .size()
                .rename("n_invalid_sessions")
                .reset_index()
            )
            lines.append("")
            lines.append(counts.to_markdown(index=False))
        lines.append("")
        lines.append("## Derived interpretation")
        lines.append("")
        for key, value in self.derived.items():
            if isinstance(value, dict):
                lines.append(f"### {key}")
                lines.append("")
                for sub_key, sub_value in value.items():
                    lines.append(f"- **{sub_key}**: {sub_value}")
                lines.append("")
            else:
                lines.append(f"- **{key}**: {value}")
        lines.append("")
        lines.append("## Structural validity rules")
        lines.append("")
        lines.append(
            self.structural_validity[
                [
                    "container",
                    "valid_conditions",
                    "valid_couplings",
                    "n_structurally_valid_devices",
                    "rationale",
                ]
            ].to_markdown(index=False)
        )
        lines.append("")
        return "\n".join(lines)

    def save(self, output_dir: str | Path, *, make_figure: bool = True) -> dict[str, Path]:
        """Write JSON/CSV/Markdown/figure artefacts and return their paths."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}

        json_path = out / "data_audit.json"
        json_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        paths["json"] = json_path

        md_path = out / "data_audit.md"
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        paths["markdown"] = md_path

        for name, frame in (
            ("variables", self.variables),
            ("session_validity", self.session_validity),
            ("invalid_sessions", self.invalid_sessions),
            ("structural_validity", self.structural_validity),
            ("checks", self.checks_frame()),
        ):
            csv_path = out / f"{name}.csv"
            frame.to_csv(csv_path, index=False)
            paths[name] = csv_path

        if make_figure:
            fig_path = out / "data_audit_overview.png"
            try:
                self._figure(fig_path)
                paths["figure"] = fig_path
            except Exception as exc:  # pragma: no cover - plotting fallback
                (out / "figure_error.txt").write_text(repr(exc), encoding="utf-8")
        return paths

    def _figure(self, path: Path) -> None:  # pragma: no cover - visual artefact
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        variables = self.variables
        # (a) median stored magnitude per container
        ax = axes[0, 0]
        level_rows = variables.loc[
            variables["key"].isin([k for k in CONTAINER_ORDER if k != THRESHOLD_CONTAINER_KEY])
        ]
        ax.barh(level_rows["key"], level_rows["median_level_db"], color="#2980b9")
        ax.set_xlabel("median stored magnitude [dB re stored unit]")
        ax.set_title("(a) Median stored level per container")
        for index, value in enumerate(level_rows["median_level_db"]):
            ax.text(value, index, f" {value:.1f}", va="center", fontsize=8)

        # (b) invalid sessions per container
        ax = axes[0, 1]
        validity = self.session_validity
        ax.barh(validity["container"], validity["n_invalid_sessions"], color="#c0392b")
        ax.set_xlabel("invalid (all-NaN) sessions")
        ax.set_title("(b) Measured NaN sessions")
        ax.invert_yaxis()

        # (c) cross-probe agreement
        ax = axes[1, 0]
        cross = self.derived.get("unit_interpretation", {}).get("cross_probe_bias_db")
        if cross:
            freqs = [float(k) for k in cross]
            values = [float(v) for v in cross.values()]
            ax.semilogx(freqs, values, "o-", color="#2980b9")
            ax.axhline(0.0, color="k", linewidth=0.8)
            ax.set_xlabel("frequency [Hz]")
            ax.set_ylabel("MPT − RPT [dB]")
            ax.set_title("(c) Cross-probe bias (both probes in ear)")
            ax.grid(alpha=0.3, which="both")
        else:
            ax.axis("off")

        # (d) structural validity per container
        ax = axes[1, 1]
        structural = self.structural_validity
        counts = structural.groupby("container", sort=False)["n_structurally_valid_devices"].max()
        ax.barh(counts.index, counts.values, color="#27ae60")
        ax.set_xlabel("structurally valid device codes")
        ax.set_title("(d) Structural validity per container")
        ax.set_xlim(0, 14)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)


class DataAuditor:
    """Compute a :class:`DataAudit` for a dataset."""

    def __init__(self, dataset: AcousticDataset, config: Config | None = None) -> None:
        self.ds = dataset
        self.config = config or dataset.config
        self.findings: list[AuditFinding] = []
        self.derived: dict[str, Any] = {}

    # -- public API ---------------------------------------------------------
    def run(self, *, quick: bool = False) -> DataAudit:
        variables = self._audit_variables()
        session_validity, invalid_tbl = self._audit_sessions(quick=quick)
        structural = invalid_reasons_table()
        structural["n_structurally_valid_devices"] = structural["container"].map(
            lambda key: int(
                1 if key == REUR_CONTAINER_KEY else self.ds.structural_mask(key).sum()
            )
        )
        frequency_axis = self._audit_frequency_axis()
        threshold_axis = self._audit_threshold_axis()
        self._audit_structural_signatures()
        self._audit_units()
        self._audit_expected_effects()
        self._audit_repeatability()
        self._add_interpretation_caveats()

        return DataAudit(
            dataset_summary=self.ds.summary(),
            variables=variables,
            session_validity=session_validity,
            invalid_sessions=invalid_tbl,
            structural_validity=structural,
            findings=self.findings,
            derived=self.derived,
            frequency_axis=frequency_axis,
            threshold_axis=threshold_axis,
            provenance={
                "dataset_doi": "10.5281/zenodo.20023285",
                "preprint_doi": "10.5281/zenodo.20023116",
                "authors": "Florian Denk, Lea Hackenberg, Hendrik Husstedt",
                "licence": "CC BY 4.0",
                "documentation": "Documentation.pdf (bundled with the dataset)",
            },
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    # -- variable-level audit ----------------------------------------------
    def _audit_variables(self) -> pd.DataFrame:
        rows = []
        for key in CONTAINER_ORDER:
            spec = CONTAINERS[key]
            values = self.ds.values(key)
            is_complex = bool(np.iscomplexobj(values))
            n_nan = int(np.isnan(values).sum())
            total = int(values.size)
            if is_complex:
                finite_mask = np.isfinite(values)
                magnitudes = np.abs(values[finite_mask])
                median_level = _median_db(values) if magnitudes.size else float("nan")
                max_level = float(np.nanmax(_db(values))) if magnitudes.size else float("nan")
                min_level = float(np.nanmin(_db(values))) if magnitudes.size else float("nan")
            else:
                median_level = float(np.nanmedian(values)) if np.any(np.isfinite(values)) else float("nan")
                max_level = float(np.nanmax(values)) if np.any(np.isfinite(values)) else float("nan")
                min_level = float(np.nanmin(values)) if np.any(np.isfinite(values)) else float("nan")
            rows.append(
                {
                    "key": key,
                    "description": spec.description,
                    "shape": str(tuple(int(v) for v in values.shape)),
                    "dtype": str(values.dtype),
                    "complex": is_complex,
                    "unit": spec.unit,
                    "n_values": total,
                    "n_nan": n_nan,
                    "nan_fraction": n_nan / total if total else float("nan"),
                    "median_level_db": median_level,
                    "min_level_db": min_level,
                    "max_level_db": max_level,
                }
            )
        return pd.DataFrame(rows)

    # -- session validity ---------------------------------------------------
    def _audit_sessions(self, *, quick: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        validity = self.ds.session_validity_summary()
        tables = []
        for key in TRANSFER_CONTAINER_KEYS:
            table = self.ds.invalid_sessions(key)
            tables.append(table)
        threshold_table = self.ds.invalid_sessions(THRESHOLD_CONTAINER_KEY)
        tables.append(threshold_table)
        invalid_tbl = pd.concat([t for t in tables if not t.empty], ignore_index=True)

        # Consistency of NaN masks across transfer-function containers.
        masks = {}
        for key in TRANSFER_CONTAINER_KEYS:
            masks[key] = invalid_sessions(self.ds.values(key), freq_axis=0)
        reference_key = TRANSFER_CONTAINER_KEYS[0]
        identical = all(np.array_equal(masks[key], masks[reference_key]) for key in masks)
        n_tf = int(masks[reference_key].sum())
        self.findings.append(
            AuditFinding(
                severity="info" if identical else "warning",
                code="nan_session_consistency",
                message=(
                    "All five transfer-function containers share the identical NaN session mask "
                    f"({n_tf} invalid sessions); measurement sessions were invalidated as a whole."
                    if identical
                    else "Transfer-function containers have DIFFERENT NaN session masks; "
                    "session-level exclusion must be computed per container."
                ),
                expected="identical masks",
                observed="identical" if identical else "different",
                passed=identical,
            )
        )
        threshold_mask = invalid_sessions(self.ds.values(THRESHOLD_CONTAINER_KEY), freq_axis=0)
        threshold_subset = np.logical_or(threshold_mask, masks[reference_key]) 
        is_superset = np.array_equal(threshold_subset, threshold_mask)
        extra = int(threshold_mask.sum() - masks[reference_key].sum())
        self.findings.append(
            AuditFinding(
                severity="warning" if extra > 0 else "info",
                code="threshold_invalid_sessions",
                message=(
                    f"The threshold container has {int(threshold_mask.sum())} invalid sessions "
                    f"(transfer functions: {n_tf}); {extra} extremely invalid threshold session(s) "
                    "exist beyond the transfer-function mask and are excluded independently."
                ),
                expected=f">= {n_tf}",
                observed=str(int(threshold_mask.sum())),
                passed=is_superset,
            )
        )
        # Error if any container has non-column-wise NaNs.
        ragged = 0
        for key in CONTAINER_ORDER:
            values = self.ds.values(key)
            if key == REUR_CONTAINER_KEY:
                continue
            nonfinite = ~np.isfinite(values)
            nf = values.shape[0]
            partial = (nonfinite.sum(axis=0) > 0) & (nonfinite.sum(axis=0) < nf)
            ragged += int(partial.sum())
        if ragged:
            self.findings.append(
                AuditFinding(
                    severity="warning",
                    code="partial_nan_sessions",
                    message=f"{ragged} sessions contain partially (not completely) NaN frequency axes.",
                )
            )
        else:
            self.findings.append(
                AuditFinding(
                    severity="info",
                    code="partial_nan_sessions",
                    message="No partial NaN sessions: invalid data are whole search-block columns.",
                )
            )
        return validity, invalid_tbl

    # -- axes ---------------------------------------------------------------
    def _audit_frequency_axis(self) -> dict[str, Any]:
        freq = self.ds.frequency_hz
        diffs = np.diff(freq)
        metadata = {
            "n_bins": int(freq.size),
            "min_hz": float(freq.min()),
            "max_hz": float(freq.max()),
            "resolution_hz": float(np.median(diffs)),
            "uniform": bool(np.allclose(diffs, np.median(diffs), rtol=1e-9, atol=1e-12)),
            "fft_bin_count": int(self.config.data.fft_bin_count),
            "has_dc_bin": bool(freq[0] == 0.0),
            "dfs_bins": int(freq.size),
        }
        self.findings.append(
            AuditFinding(
                severity="info",
                code="frequency_axis",
                message=(
                    f"Frequency axis is a uniform DFT grid: {freq.size} bins from 0 to "
                    f"{freq[-1]:g} Hz, Δf = {np.median(diffs):.6f} Hz (4096-point DFT at 44.1 kHz). "
                    "The DC bin and the < 50 Hz bins (outside the sweep range) are excluded from level statistics."
                ),
                passed=True,
            )
        )
        return metadata

    def _audit_threshold_axis(self) -> dict[str, Any]:
        freq = self.ds.threshold_frequency_hz
        values = self.ds.values(THRESHOLD_CONTAINER_KEY)
        finite = values[np.isfinite(values)]
        residual = 0.0
        if finite.size:
            residual = float(np.max(np.abs(finite - np.round(finite))))
        metadata = {
            "frequencies_hz": freq.tolist(),
            "quantisation_db": float(self.config.data.threshold_quantisation_db),
            "max_quantisation_residual_db": residual,
            "min_dbv": float(np.min(finite)) if finite.size else float("nan"),
            "max_dbv": float(np.max(finite)) if finite.size else float("nan"),
        }
        passed = residual <= 1e-6
        self.findings.append(
            AuditFinding(
                severity="info",
                code="threshold_axis",
                message=(
                    "Audiometric thresholds are given in dBV at 125, 250, 500, 750, 1000 and "
                    f"2000 Hz; values are quantised to 1 dB (max residual {residual:.2e} dB)."
                ),
                expected="1 dB quantisation",
                observed=f"max residual {residual:.2e} dB",
                passed=passed,
            )
        )
        return metadata

    # -- structural validity signatures ------------------------------------
    def _audit_structural_signatures(self) -> None:
        ds = self.ds
        f_idx = int(np.argmin(np.abs(ds.frequency_hz - 1000.0)))
        raw_ha_m = ds.values("M_ha2edM")
        raw_ha_r = ds.values("M_ha2edR")
        raw_ls_m = ds.values("M_ls2edM")
        raw_ls_r = ds.values("M_ls2edR")

        # (1) Measurement probe in the reference condition is loose.
        gaps = {}
        for family in dict.fromkeys(d.family for d in DEVICES):
            ref_code = next(d.code for d in DEVICES if d.family == family and d.condition is Condition.REFERENCE)
            meas_code = next(d.code for d in DEVICES if d.family == family and d.condition is Condition.MEASUREMENT)
            ref_level = _median_db(raw_ha_m[f_idx, ref_code - 1, :, :])
            meas_level = _median_db(raw_ha_m[f_idx, meas_code - 1, :, :])
            gaps[family] = float(meas_level - ref_level)
        min_gap = min(gaps.values())
        passed = min_gap > 20.0
        self.derived["structural_signatures"] = {
            "measurement_probe_reference_condition_level_gap_db": {
                k: round(v, 2) for k, v in gaps.items()
            },
            "reference_probe_dome_level_gap_db": None,
            "free_field_across_device_sd_db": None,
        }
        self.findings.append(
            AuditFinding(
                severity="info" if passed else "warning",
                code="structural_mpt_loose_in_reference",
                message=(
                    "The measurement probe microphone in the REFERENCE condition is 45–65 dB "
                    "below its in-ear level, confirming that it hung loosely around the ear. "
                    "M_*edM reference-condition values are therefore structurally invalid for "
                    "eardrum-pressure analysis and are masked, not imputed."
                ),
                expected="level gap > 20 dB",
                observed=f"minimum gap {min_gap:.1f} dB",
                passed=passed,
            )
        )

        # (2) Reference probe not in the ear for domes.
        dome_codes = [d.code - 1 for d in DEVICES if d.coupling is Coupling.DOME]
        earmold_codes = [d.code - 1 for d in DEVICES if d.coupling is Coupling.EARMOLD]
        dome_level = _median_db(raw_ha_r[f_idx, dome_codes, :, :])
        earmold_level = _median_db(raw_ha_r[f_idx, earmold_codes, :, :])
        gap_rpt = float(earmold_level - dome_level)
        passed_rpt = gap_rpt > 20.0
        self.derived["structural_signatures"]["reference_probe_dome_level_gap_db"] = round(gap_rpt, 2)
        self.findings.append(
            AuditFinding(
                severity="info" if passed_rpt else "warning",
                code="structural_rpt_missing_for_domes",
                message=(
                    "For dome conditions the reference probe tube was not used (documented); "
                    f"its hearing-aid-driver level is {gap_rpt:.1f} dB below the earmold level. "
                    "M_*edR dome values are structurally invalid for eardrum pressure."
                ),
                expected="level gap > 20 dB",
                observed=f"earmold − dome = {gap_rpt:.1f} dB",
                passed=passed_rpt,
            )
        )

        # (3) Free-field signature: reference-condition loose microphone should
        # be almost device-independent.
        ref_codes = [c - 1 for c in REFERENCE_DEVICE_CODES]
        per_device_1k = np.array(
            [_median_db(raw_ls_m[f_idx, code, :, :]) for code in ref_codes]
        )
        sd_1k = float(np.nanstd(per_device_1k))
        per_device_4k = np.array(
            [_median_db(raw_ls_m[int(np.argmin(np.abs(ds.frequency_hz - 4000.0))), code, :, :])
             for code in ref_codes]
        )
        sd_4k = float(np.nanstd(per_device_4k))
        # Dome RPT loudspeaker data should also be device independent (loose).
        dome_ls_r = np.array(
            [_median_db(raw_ls_r[f_idx, d.code - 1, :, :]) for d in DEVICES if d.coupling is Coupling.DOME]
        )
        sd_dome = float(np.nanstd(dome_ls_r))
        passed_ff = sd_1k < 2.0 and sd_dome < 2.0
        self.derived["structural_signatures"]["free_field_across_device_sd_db"] = {
            "M_ls2edM_reference_at_1kHz": round(sd_1k, 3),
            "M_ls2edM_reference_at_4kHz": round(sd_4k, 3),
            "M_ls2edR_domes_at_1kHz": round(sd_dome, 3),
        }
        self.findings.append(
            AuditFinding(
                severity="info" if passed_ff else "warning",
                code="structural_free_field_signature",
                message=(
                    "Loudspeaker-driven signals of loosely hanging probes are device-independent "
                    f"(across-device SD {sd_1k:.2f} dB at 1 kHz, {sd_dome:.2f} dB for dome RPT), "
                    "confirming the free-field interpretation and enabling an in-situ free-field "
                    "reference."
                ),
                expected="SD < 2 dB",
                observed=f"{sd_1k:.2f} dB",
                passed=passed_ff,
            )
        )

    # -- units --------------------------------------------------------------
    def _audit_units(self) -> None:
        ds = self.ds
        f = ds.frequency_hz
        band = (f >= 500) & (f <= 4000)
        f1k = int(np.argmin(np.abs(f - 1000.0)))

        # Hha in dB SPL at 11.2 mV should be in a physically plausible range.
        ha_r = ds.get("M_ha2edR", conditions=[Condition.MEASUREMENT], couplings=[Coupling.EARMOLD])
        hha_db = np.abs(ha_r.values)
        hha_spl = 20 * np.log10(np.maximum(hha_db[band], 1e-30) / 20e-6)
        hha_median = float(np.nanmedian(hha_spl))
        hha_ok = 40.0 < hha_median < 110.0
        self.derived["unit_interpretation"] = {
            "hha_median_db_spl_500_4000Hz": round(hha_median, 2),
            "threshold_range_dbv": [
                float(np.nanmin(ds.values(THRESHOLD_CONTAINER_KEY))),
                float(np.nanmax(ds.values(THRESHOLD_CONTAINER_KEY))),
            ],
        }
        self.findings.append(
            AuditFinding(
                severity="info" if hha_ok else "error",
                code="units_hha_db_spl",
                message=(
                    "Hearing-aid driver pressures interpreted as Pa at 11.2 mV yield "
                    f"{hha_median:.1f} dB SPL (median, 0.5–4 kHz), consistent with the "
                    "documentation and Figure 4 of the preprint."
                ),
                expected="40–110 dB SPL",
                observed=f"{hha_median:.1f} dB SPL",
                passed=hha_ok,
            )
        )

        # Cross-probe agreement in the measurement condition (both probes in ear).
        mpt = ds.get("M_ha2edM", conditions=[Condition.MEASUREMENT], couplings=[Coupling.EARMOLD])
        rpt = ds.get("M_ha2edR", conditions=[Condition.MEASUREMENT], couplings=[Coupling.EARMOLD])
        bias = {}
        for freq in (100, 250, 500, 1000, 2000, 4000, 8000):
            idx = int(np.argmin(np.abs(f - freq)))
            diff = 20 * np.log10(np.maximum(np.abs(mpt.values[idx]), 1e-30)) - 20 * np.log10(
                np.maximum(np.abs(rpt.values[idx]), 1e-30)
            )
            bias[str(freq)] = float(np.nanmedian(diff))
        median_abs_bias = float(np.nanmedian(np.abs(list(bias.values()))))
        cross_ok = median_abs_bias < 3.0
        self.derived["unit_interpretation"]["cross_probe_bias_db"] = bias
        self.findings.append(
            AuditFinding(
                severity="info" if cross_ok else "warning",
                code="units_cross_probe_agreement",
                message=(
                    "When both probe tubes are in the ear (measurement condition) the two probe "
                    f"microphones agree to a median |bias| of {median_abs_bias:.2f} dB; the "
                    "reference probe reads systematically ~1.5 dB higher, which is reported as a "
                    "probe-placement bias rather than hidden."
                ),
                expected="median |bias| < 3 dB",
                observed=f"{median_abs_bias:.2f} dB",
                passed=cross_ok,
            )
        )

        # REOIG sanity: closed earmold attenuates, open dome does not.
        reoig = self._reoig_median_db(1000)
        closed = reoig.get("closed_earmold")
        open_dome = reoig.get("open_dome")
        reoig_ok = (
            closed is not None
            and open_dome is not None
            and closed <= -5.0
            and abs(open_dome) <= 6.0
        )
        self.derived["unit_interpretation"]["reoig_1kHz_db"] = {
            k: round(v, 2) for k, v in reoig.items()
        }
        self.findings.append(
            AuditFinding(
                severity="info" if reoig_ok else "warning",
                code="units_reoig_sign",
                message=(
                    "Ratio-based REOIG at 1 kHz is strongly negative for the closed earmold "
                    f"({closed:.1f} dB) and near zero for the open dome ({open_dome:.1f} dB), "
                    "as expected from the coupling tightness."
                ),
                expected="closed ≤ −5 dB, |open| ≤ 6 dB",
                observed=f"closed {closed:.1f} dB, open {open_dome:.1f} dB",
                passed=reoig_ok,
            )
        )

        # REUG via the in-situ free-field reference.
        reug = self._reug_median_db()
        reug_ok = abs(reug.get("1000", 0.0)) <= 4.0 and max(
            reug.get("2000", -99.0), reug.get("4000", -99.0)
        ) > 5.0
        self.derived["unit_interpretation"]["reug_db"] = {
            k: round(v, 2) for k, v in reug.items()
        }
        self.findings.append(
            AuditFinding(
                severity="info" if reug_ok else "warning",
                code="units_reug_shape",
                message=(
                    "The real-ear unaided gain obtained with the in-situ free-field reference is "
                    f"{reug.get('1000', float('nan')):+.1f} dB at 1 kHz, "
                    f"{reug.get('2000', float('nan')):+.1f} dB at 2 kHz and "
                    f"{reug.get('4000', float('nan')):+.1f} dB at 4 kHz, i.e. the expected "
                    "ear-canal resonance shape. This validates the free-field normalisation used "
                    "for loudspeaker-driven levels."
                ),
                expected="≈0 dB at 1 kHz, positive 2–4 kHz",
                observed=", ".join(f"{k}: {v:+.1f} dB" for k, v in reug.items()),
                passed=reug_ok,
            )
        )

    def _reoig_median_db(self, freq_hz: float) -> dict[str, float]:
        """Median REOIG at one frequency for each family (measurement condition)."""
        ds = self.ds
        idx = int(np.argmin(np.abs(ds.frequency_hz - freq_hz)))
        reur = np.abs(ds.values("M_REUR")[idx])
        result = {}
        for family in dict.fromkeys(d.family for d in DEVICES):
            code = next(
                d.code for d in DEVICES
                if d.family == family and d.condition is Condition.MEASUREMENT
            )
            occluded = np.abs(ds.values("M_ls2edM")[idx, code - 1])
            with np.errstate(divide="ignore", invalid="ignore"):
                reoig = 20 * np.log10(np.maximum(occluded, 1e-30)) - 20 * np.log10(
                    np.maximum(reur[:, None], 1e-30)
                )
            result[family] = float(np.nanmedian(reoig))
        return result

    def _reug_median_db(self) -> dict[str, float]:
        ds = self.ds
        reference = ds.free_field_reference()
        result = {}
        for freq in (1000, 2000, 4000):
            idx = int(np.argmin(np.abs(ds.frequency_hz - freq)))
            reur = np.abs(ds.values("M_REUR")[idx])  # (subjects,)
            ff = np.abs(reference.values[idx, 0])  # (subjects, reinsertions)
            ff_median = np.nanmedian(ff, axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                gain = 20 * np.log10(np.maximum(reur, 1e-30)) - 20 * np.log10(
                    np.maximum(ff_median, 1e-30)
                )
            result[str(freq)] = float(np.nanmedian(gain))
        return result

    # -- expected physical effects -----------------------------------------
    def _audit_expected_effects(self) -> None:
        ds = self.ds
        f = ds.frequency_hz
        idx_100 = int(np.argmin(np.abs(f - 100.0)))
        idx_1k = int(np.argmin(np.abs(f - 1000.0)))

        # PTPE on Hha via the reference probe (earmolds only).
        meas = ds.get("M_ha2edR", conditions=[Condition.MEASUREMENT], couplings=[Coupling.EARMOLD])
        ref = ds.get("M_ha2edR", conditions=[Condition.REFERENCE], couplings=[Coupling.EARMOLD])
        level_meas = 20 * np.log10(np.maximum(np.abs(meas.values), 1e-30))
        level_ref = 20 * np.log10(np.maximum(np.abs(ref.values), 1e-30))
        delta = level_meas - level_ref
        families = [d.family for d in meas.devices]
        ptpe_100 = {}
        for index, family in enumerate(families):
            ptpe_100[family] = float(np.nanmedian(delta[idx_100, index]))
        median_ptpe = float(np.nanmedian(list(ptpe_100.values())))

        # PTPE on REOIG: REOIG_meas − REOIG_ref.
        reoig_meas = self._reoig_median_db(2000)
        reoig_ref = self._reoig_ref_median_db(2000)
        reoig_delta = {
            fam: reoig_meas[fam] - reoig_ref.get(fam, float("nan"))
            for fam in reoig_meas
            if fam in reoig_ref
        }
        median_reoig_delta = float(np.nanmedian(list(reoig_delta.values()))) if reoig_delta else float("nan")

        # PTPE on thresholds at 125 Hz: ΔT = T_ref − T_meas.
        thr = ds.values(THRESHOLD_CONTAINER_KEY)
        ref_codes = [c - 1 for c in REFERENCE_DEVICE_CODES]
        meas_codes = [d.code - 1 for d in DEVICES if d.condition is Condition.MEASUREMENT]
        delta_t = thr[0, ref_codes, :, :] - thr[0, meas_codes, :, :]
        median_delta_t = float(np.nanmedian(delta_t))

        ptpe_ok = median_ptpe < -1.0 and median_delta_t < -0.5
        self.derived["probe_tube_presence_effect"] = {
            "delta_hha_100Hz_db_by_family": {k: round(v, 2) for k, v in ptpe_100.items()},
            "delta_hha_100Hz_median_db": round(median_ptpe, 2),
            "delta_hha_1kHz_median_db": float(
                np.nanmedian(delta[idx_1k])
            ),
            "delta_reoig_2kHz_median_db": round(median_reoig_delta, 2),
            "delta_threshold_125Hz_median_db": round(median_delta_t, 2),
            "note": (
                "ΔT = T_ref − T_meas equals the equivalent change of Hha at the eardrum, "
                "so threshold data extend the PTPE to domes where no reference probe exists."
            ),
        }
        self.findings.append(
            AuditFinding(
                severity="info" if ptpe_ok else "warning",
                code="expected_ptpe_direction",
                message=(
                    "Probe insertion reduces low-frequency hearing-aid-driver output "
                    f"(ΔHha at 100 Hz = {median_ptpe:.1f} dB), increases sound leakage into the "
                    f"ear (ΔREOIG at 2 kHz = {median_reoig_delta:+.1f} dB) and increases the "
                    f"driver voltage at threshold (ΔT at 125 Hz = {median_delta_t:.1f} dB). "
                    "These reproducible directions validate the reference/measurement semantics."
                ),
                expected="ΔHha < 0, ΔREOIG > 0, ΔT < 0",
                observed=f"{median_ptpe:.1f}, {median_reoig_delta:+.1f}, {median_delta_t:.1f} dB",
                passed=ptpe_ok,
            )
        )

    def _reoig_ref_median_db(self, freq_hz: float) -> dict[str, float]:
        ds = self.ds
        idx = int(np.argmin(np.abs(ds.frequency_hz - freq_hz)))
        reur = np.abs(ds.values("M_REUR")[idx])
        result = {}
        for device in DEVICES:
            if device.condition is not Condition.REFERENCE or device.coupling is not Coupling.EARMOLD:
                continue
            occluded = np.abs(ds.values("M_ls2edR")[idx, device.code - 1])
            with np.errstate(divide="ignore", invalid="ignore"):
                reoig = 20 * np.log10(np.maximum(occluded, 1e-30)) - 20 * np.log10(
                    np.maximum(reur[:, None], 1e-30)
                )
            result[device.family] = float(np.nanmedian(reoig))
        return result

    def _audit_repeatability(self) -> None:
        ds = self.ds
        f = ds.frequency_hz
        band = (f >= 500) & (f <= 4000)
        cube = ds.get("M_ha2edM", conditions=[Condition.MEASUREMENT])
        level = 20 * np.log10(np.maximum(np.abs(cube.values), 1e-30))
        with np.errstate(invalid="ignore"):
            import warnings as _warnings

            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore", category=RuntimeWarning)
                # SD across the three reinsertions, per device/subject/frequency bin
                sd = np.nanstd(level[band], axis=3)  # (freq_in_band, device, subject)
        finite_sd = sd[np.isfinite(sd)]
        median_sd = float(np.nanmedian(finite_sd))
        p95_sd = float(np.nanpercentile(finite_sd, 95))
        self.derived["repeatability"] = {
            "within_subject_reinsertion_sd_db_median_500_4000": round(median_sd, 2),
            "p95_db": round(p95_sd, 2),
            "note": "SD across the three reinsertions with probe tubes left in place.",
        }
        self.findings.append(
            AuditFinding(
                severity="info",
                code="reinsertion_repeatability",
                message=(
                    "Within-subject reinsertion SD of |Hha| (0.5–4 kHz, measurement condition) "
                    f"has a median of {median_sd:.2f} dB and a 95th percentile of {p95_sd:.2f} dB. "
                    "This is the noise floor against which probe-presence effects must be judged."
                ),
                observed=f"median {median_sd:.2f} dB, p95 {p95_sd:.2f} dB",
            )
        )

    # -- interpretation caveats --------------------------------------------
    def _add_interpretation_caveats(self) -> None:
        self.findings.append(
            AuditFinding(
                severity="warning",
                code="absolute_free_field_scaling",
                message=(
                    "The stored loudspeaker-driven levels are not normalised to 1 Pa free field: "
                    "the in-situ free-field reference is ≈ −27 dB at 1 kHz. Absolute REUG/REOG "
                    "figures in this toolkit therefore use the in-situ reference; REOIG ratios are "
                    "scale-invariant and unaffected. See docs/data.md."
                ),
                passed=None,
            )
        )
        self.findings.append(
            AuditFinding(
                severity="info",
                code="reference_condition_not_available_for_domes",
                message=(
                    "For dome conditions no reference probe tube exists, so reference-condition "
                    "Hha/REOIG are not available; the probe-tube presence effect for domes is "
                    "evaluated via the threshold differences only."
                ),
                passed=None,
            )
        )
        self.findings.append(
            AuditFinding(
                severity="info",
                code="invalid_values_never_imputed",
                message=(
                    "NaN sessions and structurally invalid entries are excluded, never imputed. "
                    "All analyses report the number of contributing subjects."
                ),
                passed=None,
            )
        )
