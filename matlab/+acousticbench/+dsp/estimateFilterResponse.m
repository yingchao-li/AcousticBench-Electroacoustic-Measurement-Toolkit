function [H, probeFreqs] = estimateFilterResponse(input, output, fs, probeFreqs, options)
%ESTIMATEFILTERRESPONSE Estimate a filter response from input/output signals.
%
%   [H, FREQ] = acousticbench.dsp.estimateFilterResponse(INPUT, OUTPUT, FS,
%   PROBEFREQS) estimates the complex transfer function H = OUTPUT/INPUT by
%   Welch cross-spectrum averaging:
%
%       H(f) = sum_segments conj(X_s(f)) .* Y_s(f) / sum_segments |X_s(f)|^2
%
%   with the same segment length, Hann window, overlap and detrending
%   convention as acousticbench.dsp.welchPsd.  The response is returned at
%   the DFT bin nearest to each requested probe frequency, so the estimate
%   is deterministic and reproducible.  This is the cross-language
%   definition used by results/validation/matlab_reference.csv.
%
%   Name-Value arguments
%       'SegmentLength'  samples per segment (default automatic, see welchPsd)
%       'Overlap'        fractional overlap in [0, 0.95] (default 0.5)
%       'Window'         'hann' (default) | 'rect' | 'hamming' | 'blackman'
%       'Detrend'        remove each segment mean (default true)
%
%   Outputs
%       H          nProbe x 1 complex response
%       PROBEFREQ  nProbe x 1 frequencies [Hz] (as requested)
%
%   Example
%       b = acousticbench.dsp.designFir(101, 4000, 48000);
%       x = randn(stream, 48000, 1); y = filter(b, 1, x);
%       H = acousticbench.dsp.estimateFilterResponse(x, y, 48000, [500 2000]);
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:badFrequencies.
%
%   See also acousticbench.dsp.welchPsd, acousticbench.dsp.freqResponse,
%   acousticbench.dsp.applyFilter.

arguments
    input {mustBeNumeric, mustBeReal}
    output {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    probeFreqs double
    options.SegmentLength double = []
    options.Overlap (1,1) double {mustBeInRange(options.Overlap, 0, 0.95)} = 0.5
    options.Window {mustBeTextScalar} = 'hann'
    options.Detrend (1,1) logical = true
end

x = input(:);
y = output(:);
if isempty(x) || numel(x) ~= numel(y)
    error('acousticbench:dsp:badSignal', ...
        'INPUT and OUTPUT must be non-empty and of equal length.');
end
if ~isvector(probeFreqs) || isempty(probeFreqs)
    error('acousticbench:dsp:badFrequencies', 'PROBEFREQS must be a non-empty vector.');
end
probeFreqs = probeFreqs(:);
n = numel(x);

if isempty(options.SegmentLength)
    nSeg = 2 ^ floor(log2(max(n / 8, 1)));
    nSeg = min(max(nSeg, 256), 4096);
    nSeg = min(nSeg, n);
else
    nSeg = min(options.SegmentLength, n);
end
if nSeg < 2
    error('acousticbench:dsp:badSignal', 'The signal is too short for response estimation.');
end
hop = max(round(nSeg * (1 - options.Overlap)), 1);
if n >= nSeg
    nSegments = floor((n - nSeg) / hop) + 1;
else
    nSegments = 1;
    nSeg = n;
end
w = acousticbench.dsp.windowVector(options.Window, nSeg);
nBins = floor(nSeg / 2) + 1;

crossSpectrum = zeros(nBins, 1);
autoSpectrum = zeros(nBins, 1);
for segment = 1:nSegments
    first = (segment - 1) * hop + 1;
    xBlock = x(first:first + nSeg - 1);
    yBlock = y(first:first + nSeg - 1);
    if options.Detrend
        xBlock = xBlock - mean(xBlock);
        yBlock = yBlock - mean(yBlock);
    end
    X = fft(xBlock .* w);
    Y = fft(yBlock .* w);
    X = X(1:nBins);
    Y = Y(1:nBins);
    crossSpectrum = crossSpectrum + conj(X) .* Y;
    autoSpectrum = autoSpectrum + abs(X) .^ 2;
end

response = crossSpectrum ./ autoSpectrum;
freqAxis = (0:nBins - 1)' * fs / nSeg;

H = complex(zeros(numel(probeFreqs), 1));
for k = 1:numel(probeFreqs)
    [~, which] = min(abs(freqAxis - probeFreqs(k)));
    if probeFreqs(k) >= fs / 2
        error('acousticbench:dsp:badFrequencies', ...
            'Probe frequency %g Hz is at or above the Nyquist frequency.', probeFreqs(k));
    end
    H(k) = response(which);
end
end
