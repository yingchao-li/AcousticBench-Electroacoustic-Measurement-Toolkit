function [output, faultInfo] = injectFault(input, fs, faultType, options)
%INJECTFAULT Inject a known fault into a signal for validation experiments.
%
%   OUTPUT = acousticbench.synthetic.injectFault(INPUT, FS, FAULTTYPE)
%   corrupts INPUT with one of the documented faults and returns the
%   corrupted signal.  The fault parameters are known exactly, so the
%   detection and quantification algorithms can be validated against a
%   ground truth.
%
%   FAULTTYPE is one of
%       'clipping'               hard clipping at 'ClipLevel'
%       'dropout'                zeroed samples from 'DropoutStartS' for
%                                'DropoutDurationS' seconds
%       'dc_offset'              add 'DcOffset'
%       'gain_error'             multiply by 10^(GainErrorDb/20)
%       'harmonic_distortion'    add 2nd + 3rd harmonic so that the total
%                                THD is approximately 'ThdPercent'
%       'latency'                delay by 'LatencyMs' milliseconds (zero pad)
%
%   Name-Value arguments
%       'ClipLevel'         clipping level (default 0.5)
%       'DropoutStartS'     dropout start time in s (default 0.5)
%       'DropoutDurationS'  dropout duration in s (default 0.1)
%       'DcOffset'          DC offset (default 0.1)
%       'GainErrorDb'       gain error in dB (default 3)
%       'ThdPercent'        target THD in percent (default 5)
%       'ToneHz'            fundamental for harmonic_distortion (default 1000)
%       'LatencyMs'         latency in ms (default 5)
%       'Seed'              seed for the distortion phase (default 20260422)
%
%   Outputs
%       OUTPUT     corrupted signal (same shape as INPUT)
%       FAULTINFO  struct with faultType, the active parameters, nSamples
%                  and, for 'dropout', the affected sample range
%
%   Example
%       x = sin(2 * pi * 1000 * (0:47999)' / 48000);
%       y = acousticbench.synthetic.injectFault(x, 48000, 'clipping', ...
%           'ClipLevel', 0.3);
%
%   Error identifiers: acousticbench:synthetic:badInput,
%   acousticbench:synthetic:unknownFault, acousticbench:synthetic:badParameter.
%
%   See also acousticbench.synthetic.virtualHA,
%   acousticbench.dsp.estimateThd.

arguments
    input {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    faultType {mustBeTextScalar}
    options.ClipLevel (1,1) double {mustBePositive} = 0.5
    options.DropoutStartS (1,1) double {mustBeNonnegative} = 0.5
    options.DropoutDurationS (1,1) double {mustBeNonnegative} = 0.1
    options.DcOffset (1,1) double = 0.1
    options.GainErrorDb (1,1) double = 3
    options.ThdPercent (1,1) double {mustBeNonnegative} = 5
    options.ToneHz (1,1) double {mustBePositive} = 1000
    options.LatencyMs (1,1) double {mustBeNonnegative} = 5
    options.Seed (1,1) double {mustBeInteger} = 20260422
end

x = input(:);
if isempty(x)
    error('acousticbench:synthetic:badInput', 'INPUT must be non-empty.');
end
n = numel(x);
fault = lower(char(faultType));
faultInfo = struct('faultType', fault, 'nSamples', n, 'parameters', struct());

switch fault
    case 'clipping'
        output = max(min(x, options.ClipLevel), -options.ClipLevel);
        faultInfo.parameters = struct('clipLevel', options.ClipLevel);
    case 'dropout'
        startSample = max(1, round(options.DropoutStartS * fs) + 1);
        nDrop = round(options.DropoutDurationS * fs);
        stopSample = min(n, startSample + nDrop - 1);
        output = x;
        if startSample <= n && stopSample >= startSample
            output(startSample:stopSample) = 0;
        end
        faultInfo.parameters = struct( ...
            'startSample', startSample, ...
            'stopSample', stopSample, ...
            'startS', (startSample - 1) / fs, ...
            'durationS', max(stopSample - startSample + 1, 0) / fs);
    case 'dc_offset'
        output = x + options.DcOffset;
        faultInfo.parameters = struct('dcOffset', options.DcOffset);
    case 'gain_error'
        output = x * 10 ^ (options.GainErrorDb / 20);
        faultInfo.parameters = struct('gainErrorDb', options.GainErrorDb);
    case 'harmonic_distortion'
        t = (0:n - 1)' / fs;
        if options.ToneHz >= fs / 3
            error('acousticbench:synthetic:badParameter', ...
                'ToneHz must be below FS/3 for the 3rd-harmonic fault.');
        end
        stream = RandStream('mt19937ar', 'Seed', options.Seed);
        phase2 = 2 * pi * rand(stream);
        phase3 = 2 * pi * rand(stream);
        thdRatio = options.ThdPercent / 100;
        referenceAmplitude = sqrt(2) * sqrt(mean(x .^ 2));
        harmonic2 = referenceAmplitude * thdRatio / sqrt(2) * sin(2 * 2 * pi * options.ToneHz * t + phase2);
        harmonic3 = referenceAmplitude * thdRatio / sqrt(2) * sin(3 * 2 * pi * options.ToneHz * t + phase3);
        output = x + harmonic2 + harmonic3;
        faultInfo.parameters = struct( ...
            'thdPercent', options.ThdPercent, ...
            'toneHz', options.ToneHz, ...
            'phase2', phase2, ...
            'phase3', phase3);
    case 'latency'
        nDelay = round(options.LatencyMs / 1000 * fs);
        if nDelay >= n
            output = zeros(n, 1);
        else
            output = [zeros(nDelay, 1); x(1:n - nDelay)];
        end
        faultInfo.parameters = struct( ...
            'latencyMs', options.LatencyMs, ...
            'latencySamples', nDelay);
    otherwise
        error('acousticbench:synthetic:unknownFault', ...
            'Unknown fault "%s"; expected clipping, dropout, dc_offset, gain_error, harmonic_distortion or latency.', ...
            fault);
end

output = reshape(output, size(input));
faultInfo.faultType = fault;
faultInfo.nSamples = n;
end
