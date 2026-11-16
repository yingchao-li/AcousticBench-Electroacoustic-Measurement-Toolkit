function [x, t, info] = logSweep(fs, durationS, fLow, fHigh, options)
%LOGSWEEP Exponential (logarithmic) sine sweep with inverse filter.
%
%   [X, T] = acousticbench.dsp.logSweep(FS, DURATIONS, FLOW, FHIGH) returns
%   an exponential sine sweep from FLOW to FHIGH Hz over DURATIONS seconds
%   at sample rate FS, together with the time vector T.
%
%   The analytic phase is
%       phi(t) = 2*pi*fLow*T/L * (exp(t/T*L) - 1),  L = log(fHigh/fLow)
%   so the instantaneous frequency rises exponentially from FLOW to FHIGH.
%
%   Name-Value arguments
%       'Amplitude'  peak amplitude (default 1)
%       'FadeMs'     half-cosine fade in/out length in ms (default 0)
%
%   Outputs
%       X     Nx1 sweep signal
%       T     Nx1 time vector [s]
%       INFO  struct with fs, durationS, fLow, fHigh, amplitude, fadeMs,
%             nSamples and inverseFilter
%
%   The inverse filter is the conventional time-reversed sweep with an
%   exponential amplitude decay, suitable for linear deconvolution:
%       y = conv(SWEEP, INFO.INVERSEFILTER)
%   It is not normalised (the convolution gain depends on N); see
%   acousticbench.dsp.estimateFilterResponse for the Welch-based estimator
%   used by the cross-language export.
%
%   Example
%       [x, t, info] = acousticbench.dsp.logSweep(48000, 4, 100, 10000);
%       plot(t, x)
%
%   Error identifiers: acousticbench:dsp:badSweep,
%   acousticbench:dsp:badFade.
%
%   See also acousticbench.dsp.fftSpectrum, acousticbench.dsp.welchPsd.

arguments
    fs (1,1) double {mustBePositive}
    durationS (1,1) double {mustBePositive}
    fLow (1,1) double {mustBePositive}
    fHigh (1,1) double {mustBePositive}
    options.Amplitude (1,1) double {mustBePositive} = 1
    options.FadeMs (1,1) double {mustBeNonnegative} = 0
end

if fHigh <= fLow
    error('acousticbench:dsp:badSweep', 'FHIGH must be greater than FLOW.');
end
if fHigh >= fs / 2
    error('acousticbench:dsp:badSweep', ...
        'FHIGH (%g Hz) must be below the Nyquist frequency (%g Hz).', fHigh, fs / 2);
end
n = round(durationS * fs);
if n < 2
    error('acousticbench:dsp:badSweep', 'The sweep is shorter than two samples.');
end
t = (0:n - 1)' / fs;
logRatio = log(fHigh / fLow);
phase = 2 * pi * fLow * (durationS / logRatio) * ...
    (exp(t / durationS * logRatio) - 1);
x = options.Amplitude * sin(phase);

if options.FadeMs > 0
    fadeSamples = round(options.FadeMs / 1000 * fs);
    fadeSamples = min(fadeSamples, floor(n / 2));
    if fadeSamples > 0
        ramp = 0.5 - 0.5 * cos(pi * (0:fadeSamples - 1)' / fadeSamples);
        x(1:fadeSamples) = x(1:fadeSamples) .* ramp;
        x(end - fadeSamples + 1:end) = x(end - fadeSamples + 1:end) .* flipud(ramp);
    end
end

inverseFilter = flipud(x) .* exp(-t / durationS * logRatio);
info = struct( ...
    'fs', fs, ...
    'durationS', durationS, ...
    'fLow', fLow, ...
    'fHigh', fHigh, ...
    'amplitude', options.Amplitude, ...
    'fadeMs', options.FadeMs, ...
    'nSamples', n, ...
    'inverseFilter', inverseFilter);
end
