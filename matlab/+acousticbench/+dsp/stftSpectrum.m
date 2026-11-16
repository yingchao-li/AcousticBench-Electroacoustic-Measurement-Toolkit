function [S, freq, time] = stftSpectrum(x, fs, options)
%STFTSPECTRUM Short-time Fourier transform without the SP Toolbox.
%
%   [S, FREQ, TIME] = acousticbench.dsp.stftSpectrum(X, FS) returns the
%   complex single-sided short-time Fourier transform of the real signal X
%   sampled at FS Hz, using a Hann window of 256 samples and 50 % overlap.
%
%   Name-Value arguments
%       'WindowLength'  frame length in samples (default 256)
%       'Overlap'       fractional overlap in [0, 0.95] (default 0.5)
%       'Nfft'          FFT length per frame (default WindowLength)
%       'Window'        'hann' (default) | 'rect' | 'hamming' | 'blackman'
%       'OneSided'      return the non-negative half spectrum (default true)
%
%   Outputs
%       S      nFreq x nFrames complex STFT scaled such that a sinusoid of
%              amplitude A gives |S| = A in its bin (2X/sum(w))
%       FREQ   nFreq x 1 frequency axis [Hz]
%       TIME   nFrames x 1 frame start times [s]
%
%   Signals shorter than one window are zero-padded to one window (one
%   frame).  No toolbox function is used.
%
%   Example
%       fs = 48000; t = (0:4799)' / fs; x = sin(2 * pi * 1000 * t);
%       [S, f, tt] = acousticbench.dsp.stftSpectrum(x, fs);
%       size(S)
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:badOverlap.
%
%   See also acousticbench.dsp.fftSpectrum, acousticbench.dsp.welchPsd.

arguments
    x {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    options.WindowLength (1,1) double {mustBeInteger, mustBePositive} = 256
    options.Overlap (1,1) double {mustBeInRange(options.Overlap, 0, 0.95)} = 0.5
    options.Nfft double = []
    options.Window {mustBeTextScalar} = 'hann'
    options.OneSided (1,1) logical = true
end

if ~isvector(x) || isempty(x)
    error('acousticbench:dsp:badSignal', 'X must be a non-empty real vector.');
end
x = x(:);
n = numel(x);
windowLength = options.WindowLength;
if windowLength > n
    x = [x; zeros(windowLength - n, 1)];
    n = windowLength;
end
if isempty(options.Nfft)
    nfft = windowLength;
else
    nfft = options.Nfft;
    if ~isscalar(nfft) || nfft < windowLength || nfft ~= round(nfft)
        error('acousticbench:dsp:badNfft', ...
            'Nfft must be an integer >= WindowLength (%d).', windowLength);
    end
end

hop = round(windowLength * (1 - options.Overlap));
hop = max(hop, 1);
nFrames = floor((n - windowLength) / hop) + 1;
w = acousticbench.dsp.windowVector(options.Window, windowLength);

if options.OneSided
    nBins = floor(nfft / 2) + 1;
else
    nBins = nfft;
end
S = complex(zeros(nBins, nFrames));
for frame = 1:nFrames
    first = (frame - 1) * hop + 1;
    segment = x(first:first + windowLength - 1);
    X = fft(segment .* w, nfft);
    if options.OneSided
        X = X(1:nBins);
        S(:, frame) = 2 * X / sum(w);
        S(1, frame) = X(1) / sum(w);
        if mod(nfft, 2) == 0
            S(end, frame) = X(end) / sum(w);
        end
    else
        S(:, frame) = X / sum(w);
    end
end

if options.OneSided
    freq = (0:nBins - 1)' * fs / nfft;
else
    freq = (0:nBins - 1)' * fs / nfft;
end
time = (0:nFrames - 1)' * hop / fs;
end
