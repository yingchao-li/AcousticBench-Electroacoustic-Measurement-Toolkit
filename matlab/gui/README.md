# AcousticBench MATLAB GUI

Programmatic `uifigure` application (no `.mlapp` binary, fully
code-reviewable). It exposes the independent MATLAB implementation for
interactive data exploration, plot inspection and PNG/CSV export.

Status: **authored but NOT EXECUTED / NOT VERIFIED** in the authoring
environment (MATLAB is not installed). No screenshot or runtime output
exists; see `docs/matlab_status.md`.

## Launch

```
addpath(genpath('matlab'));
app = AcousticBenchGUI;                 % loads <repo>/Data.mat automatically
app = AcousticBenchGUI('DataPath', '/path/to/Data.mat', 'Visible', 'on');
app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);   % automated checks
```

`Data.mat` is looked up at the repository root if no `DataPath` is given.
The GUI adds `<repo>/matlab` to the path itself (based on its own location).

## Tabs

| Tab | Controls | Plot |
| --- | --- | --- |
| Data Explorer | container (M_ha2edR / M_ha2edM / M_ha2haf), condition, subset (all / earmolds / domes), statistic (median / mean) | median/mean level per device code versus frequency (log x) |
| Frequency Response | family, metric (Hha reference probe / Hha measurement probe / feedback path), condition | family reference vs measurement curves |
| Acoustic Feedback | device code, condition | median feedback path level `|M_ha2haf|` [dB SPL] |
| Repeatability | container, condition | within-subject reinsertion standard deviation (median and 95th percentile) versus frequency |
| Hearing Threshold | family, statistic | median threshold [dBV] versus audiometric frequency, reference vs measurement |
| Validation | none (populated from Data.mat) | 98-row structural-validity table plus measured-NaN session counts per container |

## Export

Each analysis tab has "Export PNG ..." and "Export CSV ..." buttons. They
open a save dialog (default name derived from the current plot) and use
`exportgraphics` for PNG and `writetable` for CSV. The Validation tab's
table is available through the same CSV mechanism after a plot (it is stored
as the current plotted table).

## Behaviour and limitations

- The GUI masks measured NaNs and structurally invalid entries exactly like
  the analysis functions (`acousticbench.loadData` validity masks); it never
  imputes values.
- A failed load or plot is reported in the status label instead of raising a
  modal error, so the app remains usable.
- Requires a MATLAB desktop session (`uifigure`/`uiaxes`); in a headless
  `matlab -batch` session the automated construction tests are skipped via
  `assumeTrue(usejava('desktop'))`.
- The app is a viewer only; all numerical definitions live in
  `+acousticbench/` and are documented in `../README.md`.
