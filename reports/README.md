# Reports

Generated engineering reports for the AcousticBench experiments. Each report
covers all sixteen experiments, the data-quality audit, the synthetic validation
targets, the MATLAB verification status and the project limitations.

| File | Format | Notes |
|---|---|---|
| `AcousticBench_Report_<timestamp>.pdf` | PDF | Title page, provenance, audit, per-experiment metrics/narrative/figures, limitations, MATLAB status |
| `AcousticBench_Report_<timestamp>.xlsx` | Excel | Summary, Data Audit, per-experiment tables (large tables capped with a pointer to the full CSV), Statistics |
| `AcousticBench_Report_<timestamp>.html` | HTML | Self-contained single file with embedded figures (opens in any browser) |

## Regenerate

```bash
acb report                                   # all three formats
acb report --formats pdf html                # subset
acb report --results results/experiments --output reports
```

The report engine reads the persisted experiment artefacts
(`results/experiments/*/result.json`, `tables/*.csv[.gz]`, `figures/*.png`) and
the persisted audit (`results/audit/data_audit.json`); it never re-runs the
analysis and never requires MATLAB. MATLAB-side results are reported as
`not_run` with the reason, exactly as in the E15 experiment.
