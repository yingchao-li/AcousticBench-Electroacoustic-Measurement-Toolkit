function [pxx, freq] = welchPsd(x, fs, options)
%WELCHPSD Welch power spectral density without the SP Toolbox.
%
%   [PXX, FREQ] = acousticbench.dsp.welchPsd(X, FS) estimates the
%   one-sided power spectral density of the real signal X with the Welch
%   method (Hann window, 50 % overlap, segment length closest to N/8 and a
%   power of two, clamped to [256, 4096]).
%
%   Name-Value arguments
%       'SegmentLength'  segment length in samples (default automatic)
%       'Overlap'        fractional overlap in [0, 0.95] (default 0.5)
%       'Nfft'           FFT length per segment (default SegmentLength)
%       'Window'         'hann' (default) | 'rect' | 'hamming' | 'blackman'
%       'Detrend'        remove the segment mean (default true)
%       'OneSided'       one-sided PSD (default true)
%
%   Scaling
%       Pxx = mean_segments |X|^2 / (FS * sum(w.^2)), doubled for the
%       interior one-sided bins, so that the integral of PXX over FREQ
%       equals the mean square of X (Parseval).
%
%   Outputs
%       PXX   nBins x 1 double PSD [unit^2/Hz]
%       FREQ  nBins x 1 double frequency axis [Hz]
%
%   Example
%       fs = 48000; stream = RandStream('mt19937ar', 'Seed', 1);
%       x = randn(stream, 48000, 1);
%       [p, f] = acousticbench.dsp.welchPsd(x, fs);
%       bandPower = trapz(f, p);
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:badSegmentLength.
%
%   See also acousticbench.dsp.fftSpectrum, acousticbench.dsp.stftSpectrum.

arguments
    x {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    options.SegmentLength double = []
    options.Overlap (1,1) double {mustBeInRange(options.Overlap, 0, 0.95)} = 0.5
    options.Nfft double = []
    options.Window {mustBeTextScalar} = 'hann'
    options.Detrend (1,1) logical = true
    options.OneSided (1,1) logical = true
end

if ~isvector(x) || isempty(x)
    error('acousticbench:dsp:badSignal', 'X must be a non-empty real vector.');
end
x = x(:);
n = numel(x);

if isempty(options.SegmentLength)
    nSeg = 2 ^ floor(log2(max(n / 8, 1)));
    nSeg = min(max(nSeg, 256), 4096);
    nSeg = min(nSeg, n);
else
    nSeg = options.SegmentLength;
    if ~isscalar(nSeg) || nSeg ~= round(nSeg) || nSeg < 2
        error('acousticbench:dsp:badSegmentLength', ...
            'SegmentLength must be an integer >= 2.');
    end
    nSeg = min(nSeg, n);
end

if isempty(options.Nfft)
    nfft = nSeg;
else
    nfft = options.Nfft;
    if ~isscalar(nfft) || nfft < nSeg || nfft ~= round(nfft)
        error('acousticbench:dsp:badNfft', ...
            'Nfft must be an integer >= SegmentLength (%d).', nSeg);
    end
end

hop = max(round(nSeg * (1 - options.Overlap)), 1);
if n >= nSeg
    nSegments = floor((n - nSeg) / hop) + 1;
else
    nSegments = 1;
    nSeg = n;
    nfft = max(nfft, nSeg);
end
w = acousticbench.dsp.windowVector(options.Window, nSeg);
windowEnergy = sum(w .^ 2);

if options.OneSided
    nBins = floor(nfft / 2) + 1;
else
    nBins = nfft;
end
accumulator = zeros(nBins, 1);
for segment = 1:nSegments
    first = (segment - 1) * hop + 1;
    block = x(first:first + nSeg - 1);
    if options.Detrend
        block = block - mean(block);
    end
    X = fft(block .* w, nfft);
    if options.OneSided
        X = X(1:nBins);
        power = abs(X) .^ 2;
        scale = 1 / (fs * windowEnergy);
        power = power * scale;
        if mod(nfft, 2) == 0
            if nBins > 2
                power(2:end - 1) = 2 * power(2:end - 1);
            end
        else
            power(2:end) = 2 * power(2:end);
        end
    else
        power = abs(X) .^ 2 / (fs * windowEnergy);
    end
    accumulator = accumulator + power;
end
pxx = accumulator / nSegments;
if options.OneSided
    freq = (0:nBins - 1)' * fs / nfft;
else
    freq = (0:nBins - 1)' * fs / nfft;
end
end
