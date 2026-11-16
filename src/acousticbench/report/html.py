"""Self-contained HTML report generation (jinja2 + inline CSS).

The generated document is a single ``.html`` file: CSS is inlined and every
figure is base64-embedded, so the report can be archived or e-mailed without
side files.  Content mirrors the PDF report: provenance, data audit, one
section per experiment (metrics, narrative, figures, table previews),
limitations and the explicit MATLAB-availability statement.
"""

from __future__ import annotations

import base64
import html as html_module
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from jinja2 import Environment, select_autoescape

from acousticbench.config import Config, load_config
from acousticbench.data.audit import DataAudit
from acousticbench.exceptions import ReportError
from acousticbench.experiments.base import ExperimentResult

__all__ = ["build_html_report"]

_MAX_TABLE_ROWS = 15
_MAX_TABLE_COLUMNS = 10
_MAX_METRIC_ROWS = 80

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ title }}</title>
<style>
:root { --bg:#f4f6f8; --panel:#ffffff; --ink:#1e2a33; --muted:#5b6770; --accent:#1f77b4; --line:#d9e1e8; --warn:#b06000; }
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }
header.hero { background:#1b2733; color:#f3f6f8; padding:38px 6vw 30px; border-bottom:4px solid var(--accent); }
header.hero h1 { margin:0 0 6px; font-size:1.9rem; letter-spacing:.2px; }
header.hero p { margin:2px 0; color:#c3ced8; }
main { max-width:1180px; margin:0 auto; padding:28px 4vw 60px; }
nav.toc { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px 22px; margin:0 0 26px; }
nav.toc strong { display:block; margin-bottom:6px; color:var(--muted); text-transform:uppercase; font-size:.74rem; letter-spacing:.12em; }
nav.toc a { color:var(--accent); text-decoration:none; margin-right:18px; font-size:.92rem; }
nav.toc a:hover { text-decoration:underline; }
section.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:22px 26px; margin:0 0 24px; box-shadow:0 1px 2px rgba(16,32,48,.04); }
h2 { color:var(--ink); border-bottom:2px solid var(--accent); padding-bottom:6px; margin:4px 0 16px; font-size:1.25rem; }
h3 { color:var(--accent); margin:20px 0 8px; font-size:1.02rem; }
h4 { color:var(--muted); margin:16px 0 6px; font-size:.92rem; text-transform:uppercase; letter-spacing:.06em; }
p { margin:8px 0; }
table { border-collapse:collapse; width:100%; margin:8px 0 14px; font-size:.84rem; }
th { background:var(--accent); color:#fff; text-align:left; padding:6px 8px; font-weight:600; }
td { border:1px solid var(--line); padding:5px 8px; vertical-align:top; }
tbody tr:nth-child(even) { background:#f7fafc; }
.metrics td:first-child { width:42%; }
.badge { display:inline-block; border-radius:999px; padding:2px 10px; font-size:.76rem; font-weight:600; }
.badge.completed { background:#e3f4e8; color:#1d6b35; }
.badge.failed { background:#fbe4e4; color:#9b2222; }
.badge.skipped { background:#fdf0d8; color:#8a5a00; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px,1fr)); gap:14px; margin:6px 0 14px; }
.kpi { border:1px solid var(--line); border-radius:8px; padding:12px 14px; background:#fbfcfd; }
.kpi .label { color:var(--muted); font-size:.74rem; text-transform:uppercase; letter-spacing:.08em; }
.kpi .value { font-size:1.3rem; font-weight:650; }
figure { margin:14px 0; }
figure img { max-width:100%; border:1px solid var(--line); border-radius:6px; background:#fff; }
figcaption { color:var(--muted); font-size:.8rem; margin-top:4px; }
.note { color:var(--muted); font-size:.85rem; }
.warn { border-left:4px solid var(--warn); background:#fff8ec; padding:10px 14px; border-radius:4px; margin:10px 0; }
footer { text-align:center; color:var(--muted); font-size:.8rem; padding:22px 0 8px; }
@media print { body { background:#fff; } section.card { box-shadow:none; border:1px solid #ccc; page-break-inside:avoid; } nav.toc { display:none; } header.hero { background:#fff; color:#000; border-bottom:2px solid #000; } }
</style>
</head>
<body>
<header class="hero">
  <h1>{{ title }}</h1>
  <p>{{ subtitle }}</p>
  <p>{{ organisation }} &middot; {{ project }} {{ version }} &middot; generated {{ generated }}</p>
</header>
<main>
<nav class="toc">
  <strong>Contents</strong>
  {% if audit %}<a href="#audit">Data audit</a>{% endif %}
  {% for experiment in experiments %}<a href="#{{ experiment.code }}">{{ experiment.code }}</a>{% endfor %}
  <a href="#limitations">Limitations</a><a href="#matlab">MATLAB status</a>
</nav>

<section class="card" id="provenance">
  <h2>Report provenance</h2>
  <div class="grid">
    <div class="kpi"><div class="label">Experiments</div><div class="value">{{ experiments|length }}</div></div>
    <div class="kpi"><div class="label">Formats</div><div class="value">HTML</div></div>
    <div class="kpi"><div class="label">Audit checks</div><div class="value">{{ audit_summary.n_checks if audit_summary else "n/a" }}</div></div>
    <div class="kpi"><div class="label">Audit warnings</div><div class="value">{{ audit_summary.n_warnings if audit_summary else "n/a" }}</div></div>
  </div>
  <table class="metrics">
    <tbody>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Dataset</td><td>{{ dataset_name }}</td></tr>
      <tr><td>Dataset size</td><td>{{ dataset_size }}</td></tr>
      <tr><td>MAT format</td><td>{{ mat_format }}</td></tr>
      <tr><td>SHA-256</td><td class="note">{{ sha256 }}</td></tr>
      <tr><td>Source</td><td>{{ source }}</td></tr>
      <tr><td>Licence</td><td>{{ licence }}</td></tr>
      <tr><td>Invalid policy</td><td>{{ invalid_policy }}</td></tr>
    </tbody>
  </table>
</section>

{% if audit %}
<section class="card" id="audit">
  <h2>Data quality audit</h2>
  <p>{{ audit_note }}</p>
  <div class="grid">
    <div class="kpi"><div class="label">Checks passed</div><div class="value">{{ audit_summary.n_passed }}</div></div>
    <div class="kpi"><div class="label">Warnings</div><div class="value">{{ audit_summary.n_warnings }}</div></div>
    <div class="kpi"><div class="label">Errors</div><div class="value">{{ audit_summary.n_errors }}</div></div>
    <div class="kpi"><div class="label">Invalid sessions</div><div class="value">{{ n_invalid_sessions }}</div></div>
  </div>
  <h3>Automated checks</h3>
  {{ checks_table|safe }}
  <h3>Session validity</h3>
  {{ session_table|safe }}
  <h3>Structural validity rules</h3>
  {{ structural_table|safe }}
</section>
{% endif %}

{% for experiment in experiments %}
<section class="card" id="{{ experiment.code }}">
  <h2>{{ experiment.code }} &mdash; {{ experiment.title }}
    <span class="badge {{ experiment.status }}">{{ experiment.status }}</span>
  </h2>
  <p class="note">Runtime {{ "%.2f"|format(experiment.duration_s) }} s &middot; {{ experiment.n_tables }} tables &middot; {{ experiment.n_figures }} figures</p>
  {% if experiment.error %}<div class="warn"><strong>Error:</strong> {{ experiment.error }}</div>{% endif %}
  {% if experiment.warnings %}
    <h4>Warnings</h4>
    <ul>{% for warning in experiment.warnings %}<li>{{ warning }}</li>{% endfor %}</ul>
  {% endif %}
  {% if experiment.narrative %}
    <h3>Summary</h3>
    {% for paragraph in experiment.narrative_paragraphs %}<p>{{ paragraph }}</p>{% endfor %}
  {% endif %}
  {% if experiment.metric_rows %}
    <h3>Metrics</h3>
    <table class="metrics"><thead><tr><th>Metric</th><th>Value</th></tr></thead>
      <tbody>{% for label, value in experiment.metric_rows %}<tr><td>{{ label }}</td><td>{{ value }}</td></tr>{% endfor %}</tbody>
    </table>
  {% endif %}
  <h3>Figures</h3>
  {% if experiment.figures %}
    {% for figure in experiment.figures %}
      <figure><img src="{{ figure.data_uri }}" alt="{{ figure.caption }}"/>
      <figcaption>{{ figure.caption }}</figcaption></figure>
    {% endfor %}
  {% else %}<p class="note">No figure was persisted for this experiment.</p>{% endif %}
  <h3>Tables</h3>
  {% if experiment.tables %}
    {% for table in experiment.tables %}
      <h4>{{ table.name }} ({{ table.rows }} rows &times; {{ table.columns }} columns)</h4>
      {{ table.html|safe }}
      {% if table.note %}<p class="note">{{ table.note }}</p>{% endif %}
    {% endfor %}
  {% else %}<p class="note">No table was persisted for this experiment.</p>{% endif %}
</section>
{% endfor %}

<section class="card" id="limitations">
  <h2>Limitations and interpretation</h2>
  <ul>
    <li>The dataset is observational (14 ears); statements are descriptive of this study sample and are not population estimates.</li>
    <li>The subject is the independent statistical unit; reinsertions are technical repeats and are averaged within subject before inference.</li>
    <li>Measured NaNs are excluded and structurally invalid entries are masked; no value is imputed anywhere in the pipeline.</li>
    <li>Thresholds are quantised to 1 dB, limiting the resolution of threshold-based effect estimates.</li>
    <li>Transfer-function levels refer to the fixed 11.2&nbsp;mV receiver drive; they are not an in-situ speech level or a prescribed gain target.</li>
    <li>Figures and tables are reproduced from persisted artefacts and may lag behind a newer data file or a newer experiment run.</li>
    <li>Inferential settings: alpha = {{ alpha }}, {{ correction }} correction, {{ bootstrap_n }} bootstrap resamples, confidence {{ confidence }}.</li>
  </ul>
</section>

<section class="card" id="matlab">
  <h2>MATLAB verification status</h2>
  <div class="warn"><strong>MATLAB is not available in this environment.</strong>
  The cross-language consistency check (experiment E15) could not be executed; numerical agreement
  between the original MATLAB reference implementation and this Python implementation is
  <strong>not verified</strong> by this report.</div>
  <p>All Python results were produced and validated against the dataset's documented structural
  properties and the persisted data audit. They are not a MATLAB-verified reproduction claim.</p>
</section>

<footer>Generated by {{ project }} {{ version }} &mdash; Electroacoustic Measurement, Validation &amp; Reporting Toolkit.</footer>
</main>
</body>
</html>
"""


def _format_value(value: Any, max_chars: int = 120) -> str:
    if value is None:
        return "\u2014"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "\u2014"
        if value == int(value) and abs(value) < 1e9:
            return str(int(value))
        return f"{value:.4g}"
    if isinstance(value, (list, tuple)):
        text = ", ".join(_format_value(item, 50) for item in value[:8])
        return text + (", \u2026" if len(value) > 8 else "")
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_format_value(item, 50)}" for key, item in list(value.items())[:8])
    text = str(value)
    return text[: max_chars - 1] + "\u2026" if len(text) > max_chars else text


def _metric_rows(metrics: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in metrics.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_metric_rows(value, prefix=f"{label} \u00b7 "))
        else:
            rows.append((label, _format_value(value)))
        if len(rows) >= _MAX_METRIC_ROWS:
            rows.append(("\u2026", "additional metrics omitted"))
            break
    return rows


def _frame_html(frame: pd.DataFrame) -> tuple[str, str]:
    """Return ``(html_table, note)`` for the first rows of a DataFrame."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return "<p class='note'>No rows available.</p>", ""
    preview = frame.iloc[:_MAX_TABLE_ROWS, :_MAX_TABLE_COLUMNS].copy()
    for column in preview.columns:
        preview[column] = preview[column].map(_format_value)
    html_table = preview.to_html(index=False, border=0, na_rep="\u2014", escape=True)
    html_table = html_table.replace('<table border="0" class="dataframe">', '<table>')
    notes = []
    if len(frame) > _MAX_TABLE_ROWS:
        notes.append(f"{len(frame) - _MAX_TABLE_ROWS} further rows omitted")
    if frame.shape[1] > _MAX_TABLE_COLUMNS:
        notes.append(f"{frame.shape[1] - _MAX_TABLE_COLUMNS} further columns omitted")
    return html_table, ("First rows shown (" + ", ".join(notes) + ")" if notes else "First rows shown")


def _figure_data_uri(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _paragraphs(text: str) -> list[str]:
    cleaned: list[str] = []
    for block in str(text).split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        cleaned.append(block)
    return cleaned[:12]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_html_report(
    results: Sequence[ExperimentResult],
    output_path: str | Path,
    *,
    config: Config | None = None,
    audit: DataAudit | None = None,
) -> Path:
    """Build a self-contained single-file HTML report.

    Parameters
    ----------
    results:
        Experiment results in presentation order.
    output_path:
        Destination ``.html`` path; parent directories are created.
    config:
        Configuration providing report metadata.
    audit:
        Optional persisted :class:`~acousticbench.data.audit.DataAudit`.

    Returns
    -------
    Path
        The written HTML path.

    Raises
    ------
    ReportError
        If no results are supplied or the document cannot be rendered.
    """
    cfg = config or load_config()
    sequence = list(results)
    if not sequence:
        raise ReportError("build_html_report requires at least one experiment result")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    file_info: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    if audit is not None:
        file_info = (audit.dataset_summary or {}).get("file", {}) or {}
        provenance = audit.provenance or {}

    audit_summary: dict[str, int] | None = None
    checks_table = session_table = structural_table = ""
    n_invalid_sessions = 0
    audit_note = ""
    if audit is not None:
        n_passed = sum(1 for item in audit.findings if item.status == "PASS")
        audit_summary = {
            "n_checks": len(audit.findings),
            "n_passed": n_passed,
            "n_warnings": audit.n_warnings,
            "n_errors": audit.n_errors,
        }
        checks_table, _ = _frame_html(audit.checks_frame())
        session_table, _ = _frame_html(audit.session_validity)
        structural_table, _ = _frame_html(audit.structural_validity)
        n_invalid_sessions = 0 if audit.invalid_sessions is None else len(audit.invalid_sessions)
        audit_note = (
            f"Audit generated {audit.generated_at or 'without timestamp'}; loaded from the "
            "persisted artefact results/audit/data_audit.json."
        )

    experiments_payload: list[dict[str, Any]] = []
    for result in sequence:
        figures: list[dict[str, str]] = []
        for name, path in sorted((getattr(result, "figure_paths", {}) or {}).items()):
            data_uri = _figure_data_uri(Path(path))
            if data_uri is None:
                continue
            figures.append({"caption": str(name), "data_uri": data_uri})
        tables_payload: list[dict[str, Any]] = []
        for name, frame in result.tables.items():
            table_html, note = _frame_html(frame)
            tables_payload.append(
                {
                    "name": str(name),
                    "rows": len(frame),
                    "columns": len(frame.columns),
                    "html": table_html,
                    "note": note,
                }
            )
        experiments_payload.append(
            {
                "code": result.code,
                "title": result.title,
                "status": result.status,
                "duration_s": float(result.duration_s),
                "error": result.error or "",
                "warnings": [str(item) for item in result.warnings],
                "narrative_paragraphs": _paragraphs(result.narrative),
                "metric_rows": _metric_rows(result.metrics),
                "figures": figures,
                "tables": tables_payload,
                "n_tables": len(result.tables),
                "n_figures": len(figures),
            }
        )

    environment = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = environment.from_string(_TEMPLATE)
    try:
        document = template.render(
            title=cfg.report.title,
            subtitle=cfg.project.description or cfg.dashboard.subtitle,
            organisation=cfg.report.organisation or cfg.project.name,
            project=cfg.project.name,
            version=cfg.project.version,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            experiments=experiments_payload,
            audit=audit is not None,
            audit_summary=audit_summary,
            audit_note=audit_note,
            checks_table=checks_table,
            session_table=session_table,
            structural_table=structural_table,
            n_invalid_sessions=n_invalid_sessions,
            dataset_name=Path(str(file_info.get("path", "Data.mat"))).name,
            dataset_size=f"{float(file_info.get('size_mb', 0.0)):.1f} MB",
            mat_format=str(file_info.get("mat_format", "\u2014")),
            sha256=str(file_info.get("sha256", "\u2014")),
            source=str(provenance.get("dataset_doi") or "Denk, Hackenberg & Husstedt (2026)"),
            licence=str(provenance.get("licence") or "CC BY 4.0"),
            invalid_policy=cfg.data.invalid_policy,
            alpha=cfg.analysis.alpha,
            correction=cfg.analysis.correction,
            bootstrap_n=cfg.analysis.bootstrap.n_resamples,
            confidence=f"{cfg.analysis.bootstrap.confidence:.0%}",
        )
    except Exception as exc:  # noqa: BLE001 - wrap renderer failures with context
        raise ReportError(f"HTML report rendering failed: {exc}") from exc

    try:
        destination.write_text(document, encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"HTML report could not be written: {exc}") from exc
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ReportError(f"HTML report was not written: {destination}")
    return destination


def _escape(text: str) -> str:  # pragma: no cover - convenience for external callers
    """Escape ``text`` for safe HTML inclusion."""
    return html_module.escape(str(text))
