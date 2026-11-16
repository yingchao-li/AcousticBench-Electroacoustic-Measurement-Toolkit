# Limitations and scope

AcousticBench is an engineering research toolkit. This page states clearly what
it does **not** do and where the results must be interpreted with care. No
medical-device certification, clinical validation or regulatory approval is
claimed or implied.

## 1. Scope of the evidence

* **Secondary analysis of one open dataset.** The real-data results come from
  the 14-ear study of Denk, Hackenberg & Husstedt (2026); they are not a new
  clinical trial. Each participant contributed one ear, so conclusions are about
  this sample, not about the population of hearing-aid users.
* **No clinical validation.** Hearing thresholds, real-ear gains and probe
  effects are research measurements. They are not a substitute for
  audiological diagnosis, fitting verification or medical advice.
* **No device certification.** The toolkit does not implement IEC/ANSI
  conformance test procedures, calibration laboratories, uncertainty budgets or
  regulatory reporting.
* **Real vs. synthetic evidence are kept separate.** E01–E08 and E15–E16 use
  the real dataset; E09–E14 use synthetic signals with known ground truth.
  Synthetic accuracy validates *algorithms under stated conditions*; it does not
  validate the physical measurement chain.

## 2. Dataset-specific limitations

* **Structural invalidity is excluded by design.** The measurement-probe
  eardrum pressure in the reference condition and the reference-probe eardrum
  pressure for domes are physically meaningless (documented in `data.md`); they
  are masked out, never used as if valid. This reduces the sample available for
  some comparisons.
* **18 invalid transfer-function sessions** (3.06 %) and 19 invalid threshold
  sessions are excluded. Exclusion is complete-session; no partial imputation is
  performed.
* **Absolute loudspeaker-source scaling is inferred.** The stored loudspeaker
  levels are not normalised to 1 Pa free field; AcousticBench derives an in-situ
  free-field reference from the loosely hanging measurement probe. REOIG is
  scale-invariant, but REUG/REOG absolute values depend on this inference
  (validated by the expected ear-canal resonance shape, but still an inference).
* **Frequency range.** The excitation sweep covered 50 Hz–22.05 kHz. Bins below
  50 Hz are excluded; above ~8 kHz probe-tube standing waves and the 1.3 mm
  tube geometry increase uncertainty. High-frequency probe bias is visible in
  the data (≈ 3 dB at 8 kHz) and is reported.
* **Probe placement is not randomised/quantified.** The measurement probe
  insertion depth was controlled visually to ~3 mm from the eardrum; the
  reference probe was routed through an earmold bore. Residual placement
  variability is part of the observed intra-subject scatter and is not
  separately modelled.
* **Threshold quantisation.** Audiometric thresholds were obtained with a 1 dB
  step. Threshold-based PTPE estimates are therefore quantised and have coarser
  resolution than the transfer-function estimates; the ΔT ↔ ΔHha agreement is
  reported with this caveat.
* **Reinsertions are not fully independent.** Probe tubes stayed in place
  between reinsertions and the three reinsertions are technical repeats, not
  independent ears. Statistics treat the subject as the independent unit.

## 3. Statistical limitations

* **Small n.** 14 subjects; effect estimates have wide confidence intervals.
  Bootstrap CIs are reported instead of relying on p-values alone, but n = 14
  limits precision and the validity of asymptotic approximations.
* **Multiple comparisons.** Family-level tests are Holm-corrected; the
  correction family is declared in E08. Uncorrected exploratory quantities in
  other experiments are descriptive.
* **Repeated measures are collapsed.** Averaging three reinsertions per subject
  is simple and robust but discards within-subject information; mixed-effects
  models were not used.
* **Normality.** Paired differences are not always normal (Shapiro–Wilk in
  E08); Wilcoxon results are reported alongside t-tests.
* **No causal claim.** The probe-tube presence effect is an association with
  the probe condition in this experimental design, not a controlled causal
  experiment on the ear.

## 4. Synthetic-validation limitations

* **Reference conditions are narrow by design.** The preset targets
  (≤ 0.1 dB gain, ≤ 0.5 dB SNR, ≤ 0.1 pp THD, ≤ 0.5 dB FR MAE) are evaluated
  only under the explicitly documented reference conditions; wider-range results
  are reported separately and may exceed the targets. This is intentional and
  transparent.
* **Synthetic signals are idealised.** No transducer nonlinearity/compression
  in the gain/SNR/THD cases, no room acoustics, no head/ear-canal transfer
  functions, no probe-tube acoustics. The virtual hearing aid is a simplified
  feed-forward multiband compressor, not a commercial fitting formula.
* **Frequency-response scoring excludes deep stop bands** using a documented
  20 dB dynamic-range mask: a finite-dynamic-range measurement cannot resolve
  them, and scoring them would be misleading.
* **THD/SNR estimators are coherent-sampling-friendly.** The synthetic tones
  are integer-Hz and the cases are 4 s; pathological non-coherent or very short
  records were not exhaustively covered.

## 5. MATLAB and GUI status

* MATLAB is **not installed** in the environment where this repository was
  built. The MATLAB implementation (`matlab/`), its unit tests and the
  programmatic GUI are authored but **not executed or verified**. See
  [`matlab_status.md`](matlab_status.md). E15 therefore reports
  `matlab_status = "not_run"` and compares the production Python implementation
  against an independent MATLAB-transcribed Python port; that agreement is
  **not** evidence that the MATLAB code runs correctly.
* The MATLAB GUI cannot be verified headlessly; it requires a desktop MATLAB
  session.
* The Streamlit dashboard was smoke-tested headlessly (server starts, health
  endpoint responds) but interactive browser behaviour is the user's
  responsibility to verify.

## 6. Software limitations

* **Single-machine benchmark.** E16 timings are wall-clock medians on the build
  machine; they are a regression baseline, not real-time guarantees.
* **No GPU / deep learning / external AI APIs** are used, by design.
* **Report generation is not a controlled document system.** PDF/Excel/HTML
  reports are engineering exports; they are not signed, version-controlled
  quality records.
* **Python version.** Developed and tested on Python 3.12; the code targets
  ≥ 3.10 and CI runs 3.10–3.12. Very new NumPy/Pandas releases may change minor
  formatting/behaviour.
* **Data redistribution.** The raw dataset is not committed; users must fetch
  it (CC BY 4.0) and comply with the attribution requirements in
  [`DATA_LICENSE.md`](../DATA_LICENSE.md).

## 7. What would be needed for a stronger claim

1. Execute and verify the MATLAB implementation and GUI on a licensed MATLAB
   installation, including the E15 cross-language comparison.
2. Multi-centre, larger-N measurements with randomised probe placement and
   independent probe calibration to quantify probe bias separately.
3. A metrology-grade uncertainty budget for the measurement chain (calibration,
   probe depth, tube acoustics, temperature).
4. Validation against a reference coupler / ear simulator and against clinical
   real-ear measurement systems.
5. Pre-registered statistical analysis for confirmatory claims.
