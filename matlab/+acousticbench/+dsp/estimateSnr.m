function [snrDb, info] = estimateSnr(signal, fs, options)
%ESTIMATESNR Estimate the signal-to-noise ratio of a tone or a signal.
%
%   SNRDB = acousticbench.dsp.estimateSnr(SIGNAL, FS, 'ToneHz', F0)
%   estimates the SNR of a sinusoid at F0 Hz in additive noise:
%
%       the fundamental is fitted by least squares (DC + cos + sin), the
%       residual is the noise, and
%       SNR = 10 log10(P_signal / P_residual)
%
%   SNRDB = acousticbench.dsp.estimateSnr(SIGNAL, FS, 'Reference', CLEAN)
%   estimates the SNR against a known clean reference:
%
%       SNR = 10 log10(mean(CLEAN.^2) / mean((SIGNAL - CLEAN).^2))
%
%   Name-Value arguments
%       'ToneHz'     tone frequency in Hz (enables the 'tone' method)
%       'Reference'  clean reference signal (enables the 'reference' method)
%       'Method'     'auto' (default) | 'tone' | 'reference'
%
%   Outputs
%       SNRDB  estimated SNR in dB (Inf if the residual is exactly zero)
%       INFO   struct with method, signalPower, noisePower, fitted
%              fundamental amplitude (tone method) and sample count
%
%   Example
%       fs = 48000; t = (0:47999)' / fs;
%       clean = sin(2 * pi * 1000 * t);
%       noisy = acousticbench.dsp.addAwgn(clean, 20);
%       snr = acousticbench.dsp.estimateSnr(noisy, fs, 'ToneHz', 1000);
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:missingMethodArgument, acousticbench:dsp:zeroSignal.
%
%   See also acousticbench.dsp.addAwgn, acousticbench.dsp.estimateGain.

arguments
    signal {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    options.ToneHz double = []
    options.Reference double = []
    options.Method {mustBeTextScalar} = 'auto'
end

method = validatestring(char(options.Method), ...
    {'auto', 'tone', 'reference'}, mfilename, 'Method');
x = signal(:);
if isempty(x)
    error('acousticbench:dsp:badSignal', 'SIGNAL must be non-empty.');
end
if strcmp(method, 'auto')
    if ~isempty(options.ToneHz)
        method = 'tone';
    elseif ~isempty(options.Reference)
        method = 'reference';
    else
        error('acousticbench:dsp:missingMethodArgument', ...
            'Provide ToneHz (tone method) or Reference (reference method).');
    end
end

switch method
    case 'tone'
        if isempty(options.ToneHz)
            error('acousticbench:dsp:missingMethodArgument', ...
                'The tone method requires the ToneHz name-value argument.');
        end
        toneHz = options.ToneHz;
        if toneHz <= 0 || toneHz >= fs / 2
            error('acousticbench:dsp:badSignal', ...
                'ToneHz must lie strictly between 0 and FS/2.');
        end
        x = x - mean(x);
        n = numel(x);
        time = (0:n - 1)' / fs;
        omega = 2 * pi * toneHz;
        design = [cos(omega * time), sin(omega * time), ones(n, 1)];
        coefficients = design \ x;
        fittedTone = design(:, 1:2) * coefficients(1:2);
        residual = x - fittedTone;
        signalPower = mean(fittedTone .^ 2);
        noisePower = mean(residual .^ 2);
        fundamentalAmplitude = hypot(coefficients(1), coefficients(2));
    otherwise
        if isempty(options.Reference)
            error('acousticbench:dsp:missingMethodArgument', ...
                'The reference method requires the Reference name-value argument.');
        end
        reference = options.Reference(:);
        if numel(reference) ~= numel(x)
            error('acousticbench:dsp:badSignal', ...
                'SIGNAL and Reference must have equal length.');
        end
        residual = x - reference;
        signalPower = mean(reference .^ 2);
        noisePower = mean(residual .^ 2);
        fundamentalAmplitude = NaN;
end

if signalPower == 0
    error('acousticbench:dsp:zeroSignal', 'The estimated signal power is zero.');
end
if noisePower == 0
    snrDb = Inf;
else
    snrDb = 10 * log10(signalPower / noisePower);
end

info = struct( ...
    'method', method, ...
    'signalPower', signalPower, ...
    'noisePower', noisePower, ...
    'fundamentalAmplitude', fundamentalAmplitude, ...
    'nSamples', numel(x));
end
