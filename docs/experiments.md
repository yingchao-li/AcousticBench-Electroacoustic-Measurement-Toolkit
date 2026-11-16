# Experiments E01–E16

All sixteen experiments are implemented as pure functions over a validated
dataset and executed by a common runner. Every result shown below was produced
by running the code in this repository on the public dataset (E01–E08,
E15–E16) or on the deterministic synthetic suite (E09–E14). The machine-readable
artefacts are committed under [`results/experiments/`](../results/experiments/).

Reproduce everything:

```bash
python scripts/fetch_data.py          # downloads + verifies Data.mat (CC BY 4.0)
bash scripts/run_experiments.sh       # E01–E16 (~20 s compute + data load)
acb report                            # PDF / Excel / HTML report
```

Each experiment directory contains `result.json`, `summary.md`,
`config_snapshot.json`, `tables/*.csv` and `figures/*.png`.
`results/experiments/experiment_index.{json,csv}` is the aggregate index.

---

## Summary

| # | Experiment | Data | Key result (actual) | Status |
|---|---|---|---|---|
| E01 | Frequency Response | real | Hha median at 1 kHz: closed earmold 76.1 dB SPL, open dome 62.7 dB SPL; 2 kHz peak ≈ 84–86 dB SPL | ✅ |
| E02 | Probe Tube Measurement Bias | real | MPT − RPT bias median \|Δ\| 1.74 dB (0.5–4 kHz); ΔHha(100 Hz) = −3.7/−8.6 dB (closed/nugget); ΔREOIG(1 kHz) = +3.2/+6.1 dB; ΔT(125 Hz) = −3.9/−6.0 dB | ✅ |
| E03 | Measurement Repeatability | real | Within-subject reinsertion SD 0.25–0.46 dB (0.5–4 kHz); RC 0.71–1.28 dB; ICC(2,1) 0.77–0.98 | ✅ |
| E04 | Inter-subject Variability | real | Between-subject SD 1.37–2.20 dB (0.5–4 kHz); ICC(1,1) 0.77–0.98; between/within ratio 1.8–7.6 | ✅ |
| E05 | Acoustic Feedback | real | Hfb(1 kHz) 8.3 dB SPL (closed) to 20.2 dB SPL (open dome); ΔHfb(1 kHz) up to +5.8 dB (nugget) with probe insertion | ✅ |
| E06 | Real-Ear Response | real | REUG +0.6/+14.0/+15.7 dB at 1/2/4 kHz; REOIG(1 kHz) −10.7 dB (closed), +0.1 dB (open dome) | ✅ |
| E07 | Hearing Threshold | real | Threshold at 125 Hz: −71.0 dBV (closed) vs −37.5 dBV (open dome); ΔT(125 Hz) up to −6.0 dB; ΔT ↔ ΔHha r = 0.56, slope 0.61, n = 56 | ✅ |
| E08 | Statistical Comparison | real | Closed vs open Hha(1 kHz): +12.45 dB [p = 8.4 × 10⁻⁹]; 6/15 family-level tests significant after Holm | ✅ |
| E09 | Gain Estimation | synthetic | 250 cases; reference-condition max \|error\| 5.3 × 10⁻¹⁵ dB (target 0.1 dB) | ✅ |
| E10 | THD Estimation | synthetic | 250 cases; reference max \|error\| 3.5 × 10⁻¹³ pp (target 0.1 pp) | ✅ |
| E11 | SNR Estimation | synthetic | 250 cases; residual estimator max \|error\| 0.0105 dB (target 0.5 dB); PSD max 0.055 dB (white reference) | ✅ |
| E12 | Filter Response Estimation | synthetic | 250 cases; reference MAE median 0.016 dB, max 0.069 dB (target 0.5 dB) | ✅ |
| E13 | Dynamic Compression | synthetic | static curve max error 0.015 dB; measured ratio 3.00 (configured 3.0); attack settling 2.94 ms (5 ms time constant), release 237 ms (50 ms) | ✅ |
| E14 | Fault Injection | synthetic | 6/6 faults recovered within tolerance; mean relative error 0.001 %; deterministic ×10 | ✅ |
| E15 | MATLAB–Python Agreement | real + synthetic | Port-vs-production: max \|Δ\| 0.0 dB (Hha bands), 5.3 × 10⁻¹⁵ dB (REOIG), 0.0085 dB (SNR); **MATLAB execution not run (MATLAB unavailable)** | ⚠️ |
| E16 | Runtime Benchmark | — | 14 operations; total 304 ms; slowest data load 222 ms; no MATLAB timing | ✅ |

Legend: ✅ executed and verified; ⚠️ executed but one external component
(MATLAB) is unavailable and explicitly marked unverified.

---

## E01 — Frequency Response

**Question:** What is the hearing-aid driver response at the eardrum across
earpiece families, and how large is the inter-individual spread?

**Method:** `Hha` in dB SPL at 11.2 mV (measurement probe, measurement
condition, all seven families), median and 10/25/75/90 % across-subject
percentiles, octave-band summaries.

**Result:** The response peaks near 2 kHz (84.8 dB SPL closed, 82.9 dB SPL
open dome) and rolls off below 500 Hz and above 8 kHz. Open domes lose most at
low frequencies (62.7 vs 76.1 dB SPL at 1 kHz). The across-subject fan is wide,
which motivates paired designs.

**Artefacts:** `figures/hha_median_curves.png`, `hha_subject_distribution.png`,
`hha_band_heatmap.png`; tables with median curves, percentiles and band levels.

## E02 — Probe Tube Measurement Bias

**Question:** How large is the bias between the two probe microphones, and what
is the acoustic probe-tube presence effect?

**Method:** (a) MPT − RPT in the measurement condition where both probes are in
the ear (earmolds); (b) ΔHha and ΔREOIG using the reference probe in both
conditions; (c) ΔT at 125 Hz for all seven families; subject-level means and
95 % CIs.

**Result:** Probe bias is −1.37 … −1.71 dB between 100 Hz and 4 kHz, growing to
−3.14 dB at 8 kHz. The PTPE is strongest for the nugget earmold
(ΔHha = −8.6 dB at ~100 Hz; ΔREOIG = +6.1 dB at 1 kHz). Power-dome ΔT
(−5.3 dB) shows that domes are also strongly affected. Signs and magnitudes
reproduce the source publication.

**Artefacts:** five figures (bias curve with IQR, ΔHha curves, ΔREOIG/ΔHha band
bars, ΔT forest-style plot), ten tables.

## E03 — Measurement Repeatability

**Question:** How repeatable are measurements across the three reinsertions?

**Method:** within-subject SD across reinsertions (frequency-resolved and per
octave band), repeatability coefficient `1.96·√2·SD`, ICC(2,1).

**Result:** median within-subject SD 0.25–0.46 dB in the primary band, RC
0.71–1.28 dB, ICC(2,1) 0.77–0.98. Low-frequency bands are less repeatable
(up to 3.5 dB at 63 Hz for the power dome), which is why E02 focuses on
mid-band effects and reports frequency-resolved curves.

## E04 — Inter-subject Variability

**Question:** How much of the total variance is between ears vs reinsertions?

**Method:** between-subject SD of subject-level means, one-way random-effects
variance decomposition, ICC(1,1).

**Result:** between-subject SD 1.37–2.20 dB; ICC(1,1) 0.77–0.98; the
between/within SD ratio is 1.8–7.6. Ears differ much more than reinsertions,
so the subject is the correct independent unit.

## E05 — Acoustic Feedback

**Question:** How strong is the driver → HA-microphone feedback path, and how
does probe insertion change it?

**Method:** `Hfb` in dB SPL at 11.2 mV, band levels and ΔHfb
(measurement − reference) for all seven families.

**Result:** Hfb at 1 kHz rises from 8.3 dB SPL (closed earmold) to 20.2 dB SPL
(open dome) — 12 dB more feedback for the open fitting. Probe insertion
increases feedback for poorly sealed couplings (nugget +5.8 dB at 1 kHz).

## E06 — Real-Ear Response

**Question:** What are the real-ear unaided/occluded gains and insertion gains?

**Method:** REUG (in-situ free-field reference), REOG, REOIG (scale-invariant
ratio), median and percentile curves plus octave-band summaries.

**Result:** REUG +0.6/+14.0/+15.7 dB at 1/2/4 kHz, the expected ear-canal
resonance. REOIG at 1 kHz: −10.7 dB (closed), −5.0 dB (nugget), −5.2 dB
(silicone), −2.3 dB (vented), ≈ 0 dB (open/tulip), −1.2 dB (power dome).
At 4 kHz the closed earmold attenuates by −22.9 dB. REOIG is the acoustic
quantity most directly related to the PTPE.

## E07 — Hearing Threshold

**Question:** How do thresholds through the HA receiver depend on coupling, and
does ΔT equal the acoustic ΔHha?

**Method:** audiograms for both conditions, ΔT at 125 Hz with subject-level
95 % CIs, and a subject-level ΔT vs ΔHha comparison for earmolds.

**Result:** thresholds at 125 Hz range from −71.0 dBV (closed) to −37.5 dBV
(open dome). ΔT is clearly negative for closed (−3.9 dB), nugget (−6.0 dB) and
power dome (−5.3 dB), ~0 for open/tulip/vented. ΔT and ΔHha correlate at
r = 0.56 with slope 0.61 and mean offset −1.13 dB across 56 subject-family
pairs — consistent with the `ΔT = ΔHha` equivalence within the 1 dB threshold
quantisation.

## E08 — Statistical Comparison

**Question:** Which effects are statistically robust at the subject level?

**Method:** paired t-tests with parametric and subject-level percentile
bootstrap 95 % CIs (10 000 resamples, seed 20260422), Cohen's dz, Wilcoxon
signed-rank with rank-biserial effect size, Shapiro–Wilk, Holm correction over
15 family-level tests; 3 additional contrasts.

**Result:** 18 tests. Closed vs open Hha at 1 kHz: +12.45 dB,
p = 8.4 × 10⁻⁹. Six family-level tests remain significant after Holm
(ΔHha nugget/silicone, ΔREOIG closed/nugget, ΔT closed/power dome). The
probe-to-probe bias at 1 kHz is −0.58 dB and *not* significant (p = 0.20) when
averaged across earmold devices, so it is reported as a systematic but
device-dependent offset rather than a headline effect.

## E09 — Gain Estimation

**Question:** How accurately can the applied gain be recovered?

**Method:** 250 synthetic gain cases (100 reference: 1 kHz, −20 dBFS, no
noise), coherent tone projection, error vs. waveform-derived ground truth.

**Result:** reference-condition max \|error\| 5.3 × 10⁻¹⁵ dB (target 0.1 dB);
all 250 cases within target. The estimator sees only input/output waveforms and
the tone frequency.

## E10 — THD Estimation

**Method:** 250 THD cases (100 reference: 1 kHz, 0.5–5 %, no noise), coherent
harmonic projection, 4 harmonics.

**Result:** reference max \|error\| 3.5 × 10⁻¹³ pp (target 0.1 pp); all cases
within target, including 10 % distortion and 500 Hz–4 kHz fundamentals.

## E11 — SNR Estimation

**Method:** 250 tone-in-noise cases; exact noise waveform gives ground-truth
SNR; residual and Welch-PSD estimators compared.

**Result:** residual estimator reference max \|error\| 0.0105 dB (target
0.5 dB), all cases within target including pink noise. PSD estimator is
accurate for white noise (max 0.055 dB) and shows a +0.14 dB median bias for
pink noise, as expected from its locally-flat assumption — reported, not hidden.

## E12 — Filter Response Estimation

**Method:** 250 sweep cases through known FIR/IIR filters; Welch H1 estimator
compared with the exact analytic response on the documented 200-point
logarithmic grid (20 dB dynamic-range mask).

**Result:** reference MAE median 0.016 dB, p95 0.061 dB, max 0.069 dB (target
0.5 dB); all 250 cases within target (max 0.186 dB in the wider range).

## E13 — Dynamic Compression

**Method:** static compression curve over −60…0 dBFS, attack/release step
response, two-tone multiband independence test.

**Result:** static curve error ≤ 0.015 dB; measured compression ratio 3.00 vs
configured 3.0; measured output-level settling times 2.94 ms (attack, 5 ms
detector time constant) and 237 ms (release, 50 ms). The difference between
detector time constant and output-level settling is documented and explained;
multiband low/high gain differs by 5.6 dB as configured.

## E14 — Fault Injection

**Method:** six deterministic faults injected into a −20 dBFS tone (latency uses
broadband noise), then recovered from the output alone: clipping peak, dropout
interval, DC mean, gain error, THD, cross-correlation lag.

**Result:** 6/6 within tolerance; mean relative error 0.001 %; deterministic
across 10 repetitions. The true parameters are used only for scoring.

## E15 — MATLAB–Python Agreement

**Method:** (1) an independent, MATLAB-transcribed Python port is compared with
the production implementation on real-data band levels/REOIG/PTPE and on
synthetic gain/SNR/THD signals; (2) the MATLAB input MAT-file and CSV contract
are produced, and MATLAB is executed if available.

**Result:** port agreement passes all six comparisons — Hha bands 0.0 dB,
REOIG 5.3 × 10⁻¹⁵ dB, PTPE 1.1 × 10⁻¹⁴ dB, gain 2.7 × 10⁻¹⁵ dB, SNR 0.0085 dB,
THD 1.5 × 10⁻¹² pp. **MATLAB is not installed**, so MATLAB-side agreement is
recorded as `matlab_status = "not_run"` with the reason. This is not a MATLAB
verification claim; see [`matlab_status.md`](matlab_status.md).

## E16 — Runtime Benchmark

**Method:** wall-clock medians (3 repeats) for 14 operations on 4 s / 48 kHz
signals.

**Result:** total 304 ms; data loading dominates (222 ms); FFT/STFT/PSD,
filtering, virtual-HA processing and estimators are each ≤ 40 ms. No MATLAB
timing is reported because MATLAB is unavailable. The benchmark is a relative
regression baseline on the build machine (macOS arm64, 10 cores, Python 3.12).

---

## Note on targets

The synthetic targets (gain ≤ 0.1 dB, SNR ≤ 0.5 dB, THD ≤ 0.1 pp, frequency
response MAE ≤ 0.5 dB) are evaluated **only** in the documented reference
conditions, against waveform-derived ground truth. All showed full compliance
in the executed runs. Wider-range results are reported separately in the
experiment tables and may exceed the targets; no target was relaxed or
post-selected. Real-data experiments have no artificial "pass" target — they
report estimates with uncertainty, and the validity/consistency checks live in
the data audit.
