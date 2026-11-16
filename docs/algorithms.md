# Algorithms

This document specifies the measurement, statistical and signal-processing
algorithms implemented in AcousticBench, with the exact definitions used in the
code. All equations operate on the validated, validity-masked data described in
[`data.md`](data.md).

---

## 1. Transfer functions and levels

### 1.1 Hearing-aid driver response `Hha`

The stored complex pressure `p_ed` is referenced to a receiver drive voltage
`u_ha = 11.2 mV`. AcousticBench exposes two equivalent level definitions:

```
Hha_dBSPL(f) = 20 log10( |p_ed(f)| / 20 µPa )        # dB SPL at 11.2 mV
Hha_dBPaV(f) = 20 log10( |p_ed(f)| / 0.0112 V )      # dB re 1 Pa/V
Hha_dBSPL(f) = Hha_dBPaV(f) + 20 log10(0.0112 V / 20 µPa)
              = Hha_dBPaV(f) + 54.96 dB
```

`hha_db_spl` / `hha_db_pa_per_v` implement both; the level curves are
validity-masked before any aggregation.

### 1.2 Feedback path

```
Hfb_dBSPL(f) = 20 log10( |p_ha(f)| / 20 µPa )        # M_ha2haf
```

### 1.3 Real-ear gains

For loudspeaker-driven pressures, only ratios are calibrated (see
`data.md`). With `p_ff(f)` the in-situ free-field reference:

```
REOG(f) = 20 log10 |p_occluded(f)| − 20 log10 |p_ff(f)|       # M_ls2ed*, measurement
REUG(f) = 20 log10 |p_open(f)|     − 20 log10 |p_ff(f)|       # M_REUR (single insertion)
REOIG(f) = REOG(f) − REUG(f) = 20 log10 |p_occluded(f) / p_open(f)|
```

**In-situ free-field reference.** In the reference condition the measurement
probe tube hung loosely around the ear; its loudspeaker-driven response is
therefore a free-field probe at the ear position. For each frequency, subject
and reinsertion the median across the seven reference-condition devices is
used:

```
p_ff(f, s, r) = median_{d ∈ reference codes} M_ls2edM(f, d, s, r)
```

This reference cancels exactly in REOIG, so REOIG is independent of the scaling
ambiguity. REUG/REOG are reported relative to this reference and are labelled
accordingly.

The clinically relevant REOIG (measurement probe, measurement condition) uses
`M_ls2edM` (measurement) and `M_REUR`, i.e. the same probe type for both terms.
The reference-condition REOIG for earmolds uses `M_ls2edR` (reference probe) and
`M_REUR`; the documentation explains why a reference-probe open-ear response
does not exist.

## 2. Probe-tube presence effect (PTPE)

Inserting the measurement probe changes the acoustics (additional leakage).
For earmolds the reference probe is in the ear in both conditions, so the
cleanest estimators use it on both sides:

```
ΔHha(f)   = Hha_RPT(measurement, f) − Hha_RPT(reference, f)
ΔREOIG(f) = REOIG_RPT(measurement, f) − REOIG_RPT(reference, f)
ΔT        = T(reference) − T(measurement)              # dBV, at 125 Hz etc.
```

### 2.1 Threshold equivalence

At threshold the eardrum pressure equals a (fixed) threshold pressure
`p_thr`. With `p_ed = Hha · u_ha` and `T = 20 log10(u_ha)`:

```
Hha_dB + T = 20 log10(p_thr) = const
⇒ Hha_meas − Hha_ref = T_ref − T_meas = ΔT
```

Thus `ΔT` is directly the change of `Hha` at the eardrum: negative `ΔT` means
the probe reduced the driver output. This is how the PTPE is assessed for
domes, where no reference probe exists. The experiment E07 checks the
equivalence empirically on earmolds and reports the correlation and mean
offset, including the effect of 1 dB threshold quantisation.

### 2.2 Probe-to-probe bias

In the measurement condition both probes are in the ear:

```
bias(f) = Hha_MPT(measurement, f) − Hha_RPT(measurement, f)
```

This is a placement/calibration bias of the two probe tubes, not a PTPE; it is
reported separately (E02) and is expected to grow towards high frequencies.

## 3. Band levels and spectral aggregation

Octave and one-third-octave bands follow the nominal centre frequencies and
`√2` / `2^(1/6)` edge ratios (IEC 61260 preferred numbers), clamped to
≥ 50 Hz (sweep range) and ≤ Nyquist. For a band `B` with DFT bins `k ∈ B`, the
band level is the power average:

```
L_B = 10 log10( (1/|B|) Σ_{k∈B} |X(k)|² / X_ref² )
```

For complex transfer functions this is exact for ratio comparisons. A band is
valid if at least one bin is valid; subjects/sessions with no valid bin are
excluded (never imputed).

## 4. Statistics

The **subject is the independent unit**. Reinsertions are averaged per subject
before inference; `n` always counts complete subject pairs.

### 4.1 Paired t-test

For paired subject values `a_i, b_i`, differences `d_i = a_i − b_i`:

```
t = mean(d) / (sd(d)/√n),   df = n − 1
95 % CI: mean(d) ± t_{0.975, n−1} · sd(d)/√n
Cohen's d_z = mean(d) / sd(d)
```

### 4.2 Wilcoxon signed-rank

Two-sided signed-rank test on the paired differences with Wilcoxon's zero
handling (default: discard zeros, no continuity correction). Effect size is the
rank-biserial correlation:

```
r_rb = (W+ − W−) / (W+ + W−)
```

### 4.3 Bootstrap confidence intervals

Subject-level **percentile bootstrap** (or BCa) with a fixed seed:

1. resample the `n` subject pairs with replacement `B` times (default 10 000);
2. compute the statistic (default: mean paired difference) on each resample;
3. take the `α/2` and `1−α/2` quantiles.

Deterministic: identical seeds produce identical intervals. BCa adjusts for
bias and skewness using the jackknife; finite-sample limitations apply for
`n = 14` and are noted in reports.

### 4.4 Multiple comparisons

Holm–Bonferroni (default) and Benjamini–Hochberg are applied to the
family-level test p-values; adjusted p-values are reported alongside raw
p-values. The correction family is explicit in every experiment.

### 4.5 Reliability

* **ICC(2,1)** (two-way random effects, single rater) for reinsertion
  reliability per subject: from the two-way ANOVA mean squares
  `MSR` (subjects), `MSC` (reinsertions), `MSE`:

  ```
  ICC(2,1) = (MSR − MSE) / (MSR + (k−1)MSE + k(MSC − MSE)/n)
  ```

* **ICC(1,1)** / variance components for between-subject vs within-subject
  variance (one-way random effects):

  ```
  σ²_between = (MSB − MSW)/k,   σ²_within = MSW
  ICC(1,1)   = σ²_between / (σ²_between + σ²_within)
  ```

* **Repeatability coefficient** `RC = 1.96 · √2 · SD_reinsertion` (95 % of
  differences between two reinsertions). Reinsertion SD uses `ddof=1`.

## 5. Signal processing

All DSP operates on `float64` 1-D signals sampled at `fs`.

### 5.1 FFT, STFT, Welch PSD

* `fft_spectrum`: detrend (default constant), optional Hann window, one-sided
  complex spectrum with amplitude/phase; the frequency axis is
  `np.fft.rfftfreq`.
* `stft`: segmented Hann-windowed STFT with overlap; returns complex
  `(frequency × time)`.
* `welch_psd`: Welch one-sided **power spectral density** with Hann window and
  50 % overlap; density scaling in units²/Hz.

### 5.2 Gain

Three methods, selected by the caller:

* **tone** (default for synthetic gain cases): Hann-windowed coherent
  projection of input and output onto the tone frequency,
  `gain = 20 log10(|A_out| / |A_in|)`;
* **band**: Welch band-power ratio;
* **rms**: broadband `20 log10(rms_out / rms_in)`.

### 5.3 SNR

* **residual** (primary): project out the tone, then
  `SNR = 10 log10(P_signal / P_residual)`; exact for any noise colour and
  insensitive to spectral shape.
* **PSD**: integrate the Welch noise density outside a narrow tone-exclusion
  band and scale to the full bandwidth. Exact for locally flat (white) noise;
  biased for pink noise (reported explicitly in E11).

### 5.4 THD and THD+N

With coherent Hann-windowed harmonic amplitudes `A_k` (`k = 1` fundamental,
`k = 2…K` harmonics):

```
THD    = 100 · sqrt(Σ_{k≥2} A_k²) / A_1      [%]
THD+N  = 100 · rms(residual) / rms(fundamental)   [%]
```

The threshold / noise floor is reported with `fundamental_dbfs`.

### 5.5 Frequency response (H1)

Cross-spectrum estimator averaged over Welch segments:

```
H1(f) = P_xy(f) / P_xx(f)
```

`P_xx` is the input auto-spectrum and `P_xy` the input–output cross-spectrum.
For a noise-free input this is the minimum-variance unbiased estimate; averaging
suppresses uncorrelated output noise. `estimate_filter_response` returns
frequency, magnitude in dB and unwrapped phase.

## 6. Virtual hearing aid

### 6.1 Multiband compressor

* Linkwitz–Riley crossover filters split the signal into
  `len(crossovers)+1` bands.
* Per band: static gain curve with threshold `T`, ratio `R`, soft knee `K`,
  make-up gain:

  ```
  over = L_in − T
  reduction = over · (1 − 1/R)                       if over ≥ K/2
            = (1 − 1/R)(over + K/2)² / (2K)          if −K/2 < over < K/2
            = 0                                       otherwise
  gain_dB = makeup − reduction
  ```

* Level detector: one-pole attack/release envelope (two one-pole filters,
  fast attack / slow release, maximum selected). The configured attack/release
  values are **detector time constants applied to signal power**, not the
  observed output-level settling times; E13 reports both and explains the
  difference.
* Output limiter (optional) clips at `output_limit_dbfs`.

### 6.2 Fault injection

Six deterministic faults are implemented, each returning the true applied
parameters: hard clipping (`clip_level_dbfs`/`clip_level`), dropout
(`start_s`, `stop_s`), DC offset, gain error, harmonic distortion (percentage of
the dominant tone) and latency (ms, whole samples). The same input and
parameters always produce exactly the same output.

## 7. Synthetic validation suite

`build_cases(n_cases=1000, seed=20260422, fs=48 kHz)` produces a deterministic
4 × 250 factorial (gain, SNR, THD, frequency response). Forty percent of each
category is generated inside its documented reference condition; the remaining
sixty percent probe wider gain/level/frequency/noise ranges.

The ground truth is computed **from the generated waveforms**, not from the
requested parameters:

```
gain_db = 20 log10(rms(out) / rms(in))
snr_db  = 10 log10(P_clean / P_noise)
thd_%   = 100 · sqrt(Σ A_harm²) / A_fund
FR      = analytic discrete-time response of the known filter
```

Reference conditions and acceptance targets (config `synthetic.targets`):

| Metric | Reference condition | Target |
|---|---|---|
| Gain | 1 kHz tone, no noise/compression, 4 s, −20 dBFS | ≤ 0.1 dB |
| SNR | 1 kHz in white noise, 10–40 dB SNR | ≤ 0.5 dB |
| THD | 1 kHz, 0.5–5 % THD, no noise | ≤ 0.1 pp |
| Frequency response | 100 Hz–10 kHz sweep, no noise, 20 dB dynamic-range mask | ≤ 0.5 dB MAE |

Only cases in the reference condition count toward the target; all-case
statistics are reported separately. The target is never silently relaxed.

## 8. Cross-language validation

`validation/matlab_port.py` is an **independent** implementation of the core
estimators using direct FFT/DTFT sums (mirroring the MATLAB code):
coherent tone projection, Parseval-based SNR, harmonic THD, band-power
averages of transfer arrays, and DTFT of FIR filters.

The production implementation and the port are compared on:

* Hha band levels (reference probe, measurement condition, earmolds);
* REOIG band levels (measurement condition);
* ΔHha band levels (earmolds);
* synthetic gain/SNR/THD signals.

Tolerances live in `config/default.yaml` (`experiments.params.E15.tolerances`)
and are applied per quantity. The MATLAB exchange contract is:

* input `results/validation/matlab_inputs.mat` (parallel arrays `ids`,
  `category`, `fs`, `input`, `output`, `clean_reference`, `tone_hz`,
  `gain_db`, `snr_db`, `thd_percent`, `freq_start_hz`, `freq_end_hz`);
* output `results/validation/matlab_reference.csv` with header
  `test_id,quantity,value,unit` and documented `test_id` naming.

When MATLAB is unavailable the report records `matlab_status = "not_run"` and
**no** MATLAB numbers are invented. Port agreement is reported as algorithmic
consistency evidence, not as MATLAB execution.

## 9. References

1. Denk, F., Hackenberg, L., Husstedt, H. (2026). *On the effect of probe tube
   presence on measured hearing aid transmission behavior.*
   doi:10.5281/zenodo.20023116.
2. Denk, F., Hackenberg, L., Husstedt, H. (2026). *Original data for the above.*
   doi:10.5281/zenodo.20023285 (CC BY 4.0).
3. IEC 61260-1:2014, *Electroacoustics — Octave-band and fractional-octave-band
   filters*.
4. Bendat, J. S., Piersol, A. G. (2010). *Random Data: Analysis and Measurement
   Procedures.* Wiley (H1 estimator, coherence).
5. Efron, B., Tibshirani, R. J. (1993). *An Introduction to the Bootstrap.*
   Chapman & Hall (percentile/BCa bootstrap).
6. Shrout, P. E., Fleiss, J. L. (1979). *Intraclass correlations: uses in
   assessing rater reliability.* Psychological Bulletin 86(2), 420–428.
7. Holm, S. (1979). *A simple sequentially rejective multiple test procedure.*
   Scandinavian Journal of Statistics 6, 65–70.
8. Benjamini, Y., Hochberg, Y. (1995). *Controlling the false discovery rate.*
   JRSS B 57(1), 289–300.
