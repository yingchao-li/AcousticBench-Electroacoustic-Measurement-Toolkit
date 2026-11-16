function [gainDb, gainLinear, info] = estimateGain(output, input, options)
%ESTIMATEGAIN Estimate the gain of a system from input/output signals.
%
%   [GAINDB, GAINLINEAR] = acousticbench.dsp.estimateGain(OUTPUT, INPUT)
%   estimates the linear gain between two equal-length signals with the
%   least-squares (LS) scalar fit
%
%       g = (input' * output) / (input' * input),   gainDb = 20 log10(|g|)
%
%   which is exact for a noiseless scaled copy and unbiased in noise.
%
%   Name-Value arguments
%       'Method'  'ls' (default) | 'rms' | 'energy'
%                 'ls'     least-squares scalar fit (default)
%                 'rms'    gainDb = 20 log10(rms(output)/rms(input))
%                 'energy' gainDb = 10 log10(sum(output.^2)/sum(input.^2))
%
%   Outputs
%       GAINDB      gain in dB (20*log10 of the amplitude ratio)
%       GAINLINEAR  |g| amplitude ratio
%       INFO        struct with method, nSamples and the residual RMS
%
%   Signals must be non-empty, real, finite and of equal length.
%
%   Example
%       x = randn(stream, 48000, 1); y = 3 * x;
%       gdb = acousticbench.dsp.estimateGain(y, x)    % -> 9.5424 dB
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:zeroSignal.
%
%   See also acousticbench.dsp.estimateSnr, acousticbench.dsp.estimateFilterResponse.

arguments
    output {mustBeNumeric, mustBeReal}
    input {mustBeNumeric, mustBeReal}
    options.Method {mustBeTextScalar} = 'ls'
end

method = validatestring(char(options.Method), ...
    {'ls', 'rms', 'energy'}, mfilename, 'Method');
x = input(:);
y = output(:);
if isempty(x) || numel(x) ~= numel(y)
    error('acousticbench:dsp:badSignal', ...
        'INPUT and OUTPUT must be non-empty and of equal length.');
end

switch method
    case 'ls'
        denominator = x' * x;
        if denominator == 0
            error('acousticbench:dsp:zeroSignal', 'INPUT has zero energy.');
        end
        complexGain = (x' * y) / denominator;
        gainLinear = abs(complexGain);
        residual = y - complexGain * x;
    case 'rms'
        inputRms = sqrt(mean(x .^ 2));
        if inputRms == 0
            error('acousticbench:dsp:zeroSignal', 'INPUT has zero RMS.');
        end
        gainLinear = sqrt(mean(y .^ 2)) / inputRms;
        residual = y - gainLinear * x;
    otherwise
        inputEnergy = sum(x .^ 2);
        if inputEnergy == 0
            error('acousticbench:dsp:zeroSignal', 'INPUT has zero energy.');
        end
        gainLinear = sqrt(sum(y .^ 2) / inputEnergy);
        residual = y - gainLinear * x;
end

gainDb = 20 * log10(gainLinear);
info = struct( ...
    'method', method, ...
    'nSamples', numel(x), ...
    'residualRms', sqrt(mean(residual .^ 2)));
end
