function [amplitude, freq, spectrum] = fftSpectrum(x, fs, options)
%FFTSPECTRUM Single-sided amplitude spectrum without the SP Toolbox.
%
%   [AMPLITUDE, FREQ] = acousticbench.dsp.fftSpectrum(X, FS) returns the
%   single-sided amplitude spectrum of a real signal X sampled at FS Hz.
%   The signal is detrended (mean removed), windowed and FFT-transformed.
%   The scaling is chosen such that a sinusoid of amplitude A produces a
%   peak of amplitude A in AMPLITUDE.
%
%   [AMPLITUDE, FREQ, SPECTRUM] = ... also returns the complex spectrum
%   (single-sided when OneSided=true, two-sided otherwise).
%
%   Name-Value arguments
%       'Window'    'hann' (default) | 'rect' | 'hamming' | 'blackman'
%       'Nfft'      FFT length (default numel(X), must be >= numel(X))
%       'Detrend'   remove the mean before windowing (default true)
%       'OneSided'  return the non-negative half spectrum (default true)
%
%   Outputs
%       AMPLITUDE  nBins x 1 double amplitude spectrum (2|X|/sum(w) for
%                  interior bins, 1|X|/sum(w) for DC and Nyquist)
%       FREQ       nBins x 1 double frequency axis [Hz]
%       SPECTRUM   nBins x 1 complex FFT values
%
%   Example
%       fs = 48000; t = (0:4799)' / fs; x = 1.5 * sin(2 * pi * 1000 * t);
%       [a, f] = acousticbench.dsp.fftSpectrum(x, fs, 'Window', 'rect');
%       [~, k] = min(abs(f - 1000)); a(k)      % -> 1.5
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:badNfft.
%
%   See also acousticbench.dsp.welchPsd, acousticbench.dsp.stftSpectrum.

arguments
    x {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    options.Window {mustBeTextScalar} = 'hann'
    options.Nfft double = []
    options.Detrend (1,1) logical = true
    options.OneSided (1,1) logical = true
end

if ~isvector(x) || isempty(x)
    error('acousticbench:dsp:badSignal', 'X must be a non-empty real vector.');
end
x = x(:);
n = numel(x);
if isempty(options.Nfft)
    nfft = n;
else
    nfft = options.Nfft;
    if ~isscalar(nfft) || nfft < n || nfft ~= round(nfft)
        error('acousticbench:dsp:badNfft', ...
            'Nfft must be an integer >= numel(X) (%d), got %g.', n, nfft);
    end
end

if options.Detrend
    x = x - mean(x);
end
w = acousticbench.dsp.windowVector(options.Window, n);
X = fft(x .* w, nfft);

if options.OneSided
    nBins = floor(nfft / 2) + 1;
    freq = (0:nBins - 1)' * fs / nfft;
    spectrum = X(1:nBins);
    amplitude = abs(spectrum) * 2 / sum(w);
    amplitude(1) = abs(X(1)) / sum(w);
    if mod(nfft, 2) == 0
        amplitude(end) = abs(X(end)) / sum(w);
    end
else
    freq = (0:nfft - 1)' * fs / nfft;
    spectrum = X;
    amplitude = abs(X) / sum(w);
end
end
