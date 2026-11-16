function [thdPercent, info] = estimateThd(signal, fs, toneHz, options)
%ESTIMATETHD Total harmonic distortion from coherent harmonic analysis.
%
%   THDPERCENT = acousticbench.dsp.estimateThd(SIGNAL, FS, TONEHZ) estimates
%   the total harmonic distortion of a sinusoidal signal:
%
%       THD = 100 * sqrt(sum_{h=2..H} A_h^2) / A_1     [percent]
%
%   where A_h is the amplitude of the h-th harmonic estimated by coherent
%   projection onto cos/sin at h*TONEHZ (exact for an integer number of
%   periods in the record), and H = 'NHarmonics'.
%
%   Name-Value arguments
%       'NHarmonics'  highest harmonic to include (default 10); harmonics
%                     at or above the Nyquist frequency are skipped
%       'RemoveDc'    remove the signal mean before analysis (default true)
%
%   Outputs
%       THDPERCENT  THD in percent
%       INFO        struct with harmonicAmplitudes (H x 1), harmonicFrequencies,
%                   fundamentalAmplitude, nHarmonics and thdFraction
%
%   Example
%       fs = 48000; t = (0:47999)' / fs;
%       x = sin(2 * pi * 1000 * t) + 0.03 * sin(2 * pi * 2000 * t);
%       thd = acousticbench.dsp.estimateThd(x, fs, 1000)    % -> 3 %
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:noFundamental.
%
%   See also acousticbench.dsp.estimateThdPlusN, acousticbench.dsp.estimateSnr.

arguments
    signal {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    toneHz double
    options.NHarmonics (1,1) double {mustBeInteger, mustBePositive} = 10
    options.RemoveDc (1,1) logical = true
end

if isempty(toneHz) || ~isscalar(toneHz) || toneHz <= 0
    error('acousticbench:dsp:badSignal', 'TONEHZ must be a positive scalar.');
end
if toneHz >= fs / 2
    error('acousticbench:dsp:badSignal', ...
        'TONEHZ must be below the Nyquist frequency.');
end
x = signal(:);
if isempty(x)
    error('acousticbench:dsp:badSignal', 'SIGNAL must be non-empty.');
end
if options.RemoveDc
    x = x - mean(x);
end
n = numel(x);
time = (0:n - 1)' / fs;
nHarmonics = options.NHarmonics;

harmonicAmplitudes = zeros(nHarmonics, 1);
harmonicFrequencies = (1:nHarmonics)' * toneHz;
for harmonic = 1:nHarmonics
    frequency = harmonic * toneHz;
    if frequency >= fs / 2
        harmonicAmplitudes(harmonic) = 0;
        continue;
    end
    omega = 2 * pi * frequency;
    cosine = cos(omega * time);
    sine = sin(omega * time);
    coefficientCosine = 2 / n * (cosine' * x);
    coefficientSine = 2 / n * (sine' * x);
    harmonicAmplitudes(harmonic) = hypot(coefficientCosine, coefficientSine);
end

fundamental = harmonicAmplitudes(1);
if fundamental <= 0 || ~isfinite(fundamental)
    error('acousticbench:dsp:noFundamental', ...
        'No fundamental component was found at %g Hz.', toneHz);
end
distortionAmplitudes = harmonicAmplitudes(2:end);
thdFraction = sqrt(sum(distortionAmplitudes .^ 2)) / fundamental;
thdPercent = 100 * thdFraction;

info = struct( ...
    'harmonicAmplitudes', harmonicAmplitudes, ...
    'harmonicFrequencies', harmonicFrequencies, ...
    'fundamentalAmplitude', fundamental, ...
    'nHarmonics', nHarmonics, ...
    'thdFraction', thdFraction, ...
    'nSamples', n);
end
