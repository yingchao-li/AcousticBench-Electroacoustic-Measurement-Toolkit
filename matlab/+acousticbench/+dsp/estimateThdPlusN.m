function [thdnPercent, info] = estimateThdPlusN(signal, fs, toneHz, options)
%ESTIMATETHDPLUSN Total harmonic distortion plus noise (THD+N).
%
%   THDNPERCENT = acousticbench.dsp.estimateThdPlusN(SIGNAL, FS, TONEHZ)
%   estimates THD+N for a sinusoidal stimulus:
%
%       residual    = SIGNAL - fitted fundamental
%       THD+N [%]   = 100 * rms(residual) / rms(SIGNAL)
%
%   With 'RemoveHarmonics' = true the fitted model additionally contains the
%   harmonics 2..NHarmonics, so the residual contains only noise (THD
%   removed); the default false keeps the harmonics in the residual, which
%   is the standard THD+N definition (distortion plus noise relative to the
%   total signal RMS).
%
%   Name-Value arguments
%       'NHarmonics'       highest harmonic in the model (default 10)
%       'RemoveHarmonics'  remove harmonics 2..H from the residual
%                          (default false)
%       'RemoveDc'         remove the mean before analysis (default true)
%
%   Outputs
%       THDNPERCENT  THD+N in percent
%       INFO         struct with residualRms, signalRms, thdnFraction,
%                    nHarmonics, removeHarmonics and nSamples
%
%   Example
%       fs = 48000; t = (0:47999)' / fs;
%       x = sin(2 * pi * 1000 * t) + 0.1 * sin(2 * pi * 2000 * t);
%       thdn = acousticbench.dsp.estimateThdPlusN(x, fs, 1000)  % ~9.95 %
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:zeroSignal.
%
%   See also acousticbench.dsp.estimateThd.

arguments
    signal {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    toneHz double
    options.NHarmonics (1,1) double {mustBeInteger, mustBePositive} = 10
    options.RemoveHarmonics (1,1) logical = false
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
signalRms = sqrt(mean(x .^ 2));
if signalRms == 0
    error('acousticbench:dsp:zeroSignal', 'SIGNAL has zero RMS.');
end

modelHarmonics = 1;
if options.RemoveHarmonics
    modelHarmonics = options.NHarmonics;
end
columns = ones(n, 1);
for harmonic = 1:modelHarmonics
    frequency = harmonic * toneHz;
    if frequency >= fs / 2
        break;
    end
    omega = 2 * pi * frequency;
    columns = [columns, cos(omega * time), sin(omega * time)]; %#ok<AGROW>
end
coefficients = columns \ x;
fitted = columns * coefficients;
residual = x - fitted;
residualRms = sqrt(mean(residual .^ 2));
thdnFraction = residualRms / signalRms;

thdnPercent = 100 * thdnFraction;
info = struct( ...
    'residualRms', residualRms, ...
    'signalRms', signalRms, ...
    'thdnFraction', thdnFraction, ...
    'nHarmonics', options.NHarmonics, ...
    'removeHarmonics', options.RemoveHarmonics, ...
    'nSamples', n);
end
