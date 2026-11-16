# Architecture

AcousticBench is a layered, dependency-light Python package with three
complementary front-ends (CLI, Streamlit dashboard, automated reports) and an
independent MATLAB implementation. This document explains the module map, the
data flow, the artefact contract and the extension points.

```
config/default.yaml ─┐
                     ▼
              acousticbench.config ──► logging / exceptions
                     │
   Data.mat ──► io.mat_loader ──► data.dataset (TransferCube)
                     │                 │
                     │                 ├─ data.validity / data.audit
                     │                 └─ data.units
                     ▼
        measurements.{transfer, ptpe, threshold,
                      repeatability, variability}
                     │
          ┌──────────┼──────────────┬───────────────┐
          ▼          ▼              ▼               ▼
      stats.*   dsp.* / virtual_ha  synthetic.*   validation.*
          │          │              │               │
          └──────────┴──────┬───────┴───────────────┘
                            ▼
                 experiments (E01–E16 registry/runner)
                            │
          ┌─────────────────┼──────────────────────┐
          ▼                 ▼                      ▼
       CLI (`acb`)     Streamlit app        report.{pdf,excel,html}
```

## 1. Layers

| Layer | Package | Responsibility |
|---|---|---|
| Domain metadata | `acousticbench.types` | Device codes, families, conditions, probes, containers, structural validity rules, physical constants |
| I/O & provenance | `acousticbench.io` | MAT v5/v7.3 loading, schema validation, SHA-256/size/header provenance |
| Data model | `acousticbench.data` | `AcousticDataset`, labelled `TransferCube`, validity masks, units, free-field reference, audit |
| Measurement science | `acousticbench.measurements` | Hha, REOG/REUG/REOIG, feedback path, PTPE, thresholds, repeatability, variability |
| Statistics | `acousticbench.stats` | Bands, descriptive statistics, paired tests, bootstrap, effect sizes, Holm/BH, ICC |
| DSP | `acousticbench.dsp` | Signals, FFT/STFT/Welch PSD, FIR/IIR design & filtering, gain/SNR/THD/THD+N/H1 estimators |
| Virtual device | `acousticbench.virtual_ha` | Multiband compressor, noise, deterministic fault injection |
| Synthetic validation | `acousticbench.synthetic` | 1000-case deterministic suite with analytic ground truth |
| Cross-language | `acousticbench.validation` | MATLAB-transcribed Python port, MAT/CSV exchange with MATLAB, agreement reporting |
| Experiments | `acousticbench.experiments` | Context/result/runner, common analysis helpers, E01–E16 modules |
| Reporting | `acousticbench.report` | Matplotlib figure helpers, PDF (reportlab), Excel (xlsxwriter), HTML (jinja2), builder |
| Interfaces | `acousticbench.cli`, `app/` | Command line and nine-page Streamlit dashboard |

Design rules:

* **No implicit validity.** Every stored array is wrapped in a `TransferCube`
  with an explicit `valid` mask. Aggregations use the masked array; structurally
  invalid entries can only be accessed by a function that documents why
  (e.g. `AcousticDataset.free_field_reference`).
* **No imputation.** NaNs and structural invalids are excluded, never filled.
* **Subject is the statistical unit.** Reinsertions are technical repeats and
  are averaged within subject before any inferential test.
* **Experiments are pure functions.** An experiment receives an
  `ExperimentContext` and returns an `ExperimentResult` (metrics, tidy tables,
  matplotlib figures, narrative, warnings). The runner persists everything, so
  experiments are testable without I/O.
* **Configuration over hard-coding.** YAML drives paths, seeds, bands, alpha,
  bootstrap settings, experimental parameters and report options.
* **Honest status.** Failed experiments are recorded as `failed` with the
  traceback; unavailable MATLAB is recorded as `not_run`; synthetic targets are
  evaluated only under their documented reference conditions.

## 2. The `TransferCube`

Shape is always `(frequency, device, subject, reinsertion)`; derived axes use a
length-1 dimension. Each cube carries values, a boolean validity mask,
labelled devices, unit metadata, a `kind`
(`transfer`, `level_db`, `threshold_dbv`, `phase_deg`) and provenance metadata.

Key operations:

| Method | Purpose |
|---|---|
| `select(...)` | Filter devices/conditions/families/couplings/subjects/reinsertions/frequency range |
| `masked` | Values with invalid entries set to NaN |
| `magnitude_db(reference)` | Complex → dB levels (`reference=20e-6` gives dB SPL) |
| `phase_deg()` | Phase in degrees |
| `median_level_curve()` | Median across subjects/reinsertions per frequency/device (tidy DataFrame) |
| `band_levels(bands, reference)` | Power-averaged octave/third-octave levels (tidy DataFrame) |
| `mean_reinsertions()` / `std_reinsertions()` | Collapse the reinsertion axis |
| `to_dataframe()` / `to_level_dataframe()` | Full tidy export |

Band aggregation uses a **power average** over DFT bins, which is the correct
operation for levels and preserves ratios (e.g. REOIG) regardless of the
arbitrary free-field scaling.

## 3. Data flow of an analysis

```python
ds = load_dataset()                                  # validated + provenance
cube = ds.get("M_ha2edR",
              conditions=["measurement"],
              couplings=["earmold"])                 # structural + NaN mask
level = hha_db_spl(ds, probe="reference",
                   condition="measurement")          # dB SPL cube
curve = level.median_level_curve()                   # tidy curve
bands = level.band_levels(octave_bands())            # tidy band levels
```

Measurements are implemented as functions over the dataset (not methods), so
that container selection, structural rules and unit conversions are explicit.
The `--codes` CLI and the dashboard consume the same functions.

## 4. Artefact contract

Each experiment writes to `results/experiments/<CODE>_<slug>/`:

```
result.json          # status, metrics, warnings, parameters, provenance
summary.md           # human-readable summary with metric and table previews
config_snapshot.json # analysis + experiment parameters (reproducibility)
tables/*.csv         # every tidy table returned by the experiment
figures/*.png        # every figure returned by the experiment
```

`results/experiments/experiment_index.{json,csv}` summarises all runs.
`results/audit/` holds the data audit, `results/validation/` the E15 exchange
files, `results/synthetic/` the synthetic case manifest, and `reports/` the
generated PDF/Excel/HTML reports.

## 5. Reproducibility

* One master seed (`project.seed`, default `20260422`) seeds the bootstrap,
  the synthetic suite and the fault/noise generators.
* Bootstrap draws use `numpy.random.default_rng(seed)`; the same seed produces
  identical confidence intervals.
* Synthetic cases are generated from `SeedSequence([seed, stream])`; each case
  records its own seed and the suite manifest is written to disk.
* Experiment results record the dataset SHA-256, configuration snapshot,
  parameters and runtime.
* The audit is deterministic (medians/quantiles only).

## 6. Tests

| Layer | Location |
|---|---|
| Unit tests | `tests/unit/` — config, I/O, data, DSP, stats, measurements, synthetic, virtual HA, experiments, validation, reports |
| Integration | `tests/integration/` — dataset → measurements → statistics → experiment artefacts |
| Regression | `tests/regression/` — pinned real-data values and data SHA-256 |
| CI | `.github/workflows/ci.yml` (data-free matrix), `experiments.yml` (manual, downloads data) |

`pyproject.toml` configures pytest markers (`requires_data`, `integration`,
`regression`, `slow`) and coverage.

## 7. Extension points

* **New container/quantity:** add a `ContainerSpec` in `types.py`, loading and
  validity are automatic.
* **New measurement:** add a function in `measurements/`, returning a
  `TransferCube` or tidy DataFrame; build on `AcousticDataset.get`.
* **New experiment:** create `experiments/eXX_name.py` with `CODE`, `TITLE`,
  `DESCRIPTION`, `run(context)`, add it to `experiments/registry.py` and the
  enabled list in `config/default.yaml`. The runner and reports pick it up
  automatically.
* **New report format:** implement a builder in `report/` and register it in
  `report/builder.py`.
* **New dashboard page:** add a module under `app/pages/` and register it in
  `app/dashboard.py` navigation.
* **New synthetic category:** extend `synthetic/cases.py`,
  `synthetic/generator.py` and the ground-truth helpers; experiments can then
  select the new category.

## 8. MATLAB implementation

`matlab/` contains an **independent** implementation (namespace
`+acousticbench`, programmatic `uifigure` GUI, `matlab.unittest` tests and a
cross-language export script). It mirrors the Python algorithms but shares no
code. MATLAB is not installed in the environment where this repository was
built; the MATLAB code, tests and GUI are therefore **authored but not
executed/verified** — see [`matlab_status.md`](matlab_status.md). The E15
experiment prepares the exact MAT/CSV exchange and records the MATLAB status
honestly.

## 9. Dashboard

The Streamlit app (`app/dashboard.py`) uses `st.navigation` with nine pages.
Expensive operations are cached (`st.cache_resource` for the dataset), filters
are centralised in `app/components/filters.py`, Plotly is used for interactive
curves/heatmaps, and the Report Center calls the same `report.builder` as the
CLI. Run it with `bash scripts/start_dashboard.sh`.
