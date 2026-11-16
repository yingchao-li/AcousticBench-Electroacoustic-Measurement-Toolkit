function [output, info] = virtualHA(input, fs, options)
%VIRTUALHA Multiband compressor model of a virtual hearing aid.
%
%   OUTPUT = acousticbench.synthetic.virtualHA(INPUT, FS) passes the input
%   signal through a three-band dynamic-range compressor with attack and
%   release smoothing, a static compression curve and optional gain/makeup
%   gain.  This is a simplified but complete model of a hearing-aid
%   compression channel; it is used to generate synthetic cases with a known
%   nonlinear characteristic, not as a clinically valid fitting model.
%
%   Name-Value arguments
%       'CrossoverHz'       two crossover frequencies (default [500 2000])
%       'CompressionRatio'  compression ratio above the knee (default 3)
%       'KneeDbfs'          compression knee in dBFS (default -35)
%       'AttackMs'          envelope attack time (default 5)
%       'ReleaseMs'         envelope release time (default 50)
%       'GainDb'            linear pre-gain in dB (default 0)
%       'MakeupGainDb'      output makeup gain in dB (default 0)
%       'FilterOrder'       crossover Butterworth order (default 2)
%
%   Outputs
%       OUTPUT  same-size output signal
%       INFO    struct with crossovers, band levels, compressor settings and
%               the per-band envelope ranges
%
%   Signal flow: pre-gain -> 3-band Linkwitz-Riley-style split (zero-phase
%   Butterworth low/high sections) -> per-band envelope follower (one-pole
%   attack/release) -> static gain computer -> band gain -> sum -> makeup
%   gain.  The bands are causal/zero-phase filtered approximations, so the
%   band sum is not perfectly flat; this is documented and intentional for a
%   synthetic generator.
%
%   Example
%       fs = 48000; t = (0:23999)' / fs;
%       x = 0.1 * sin(2 * pi * 1000 * t);
%       y = acousticbench.synthetic.virtualHA(x, fs);
%
%   Error identifiers: acousticbench:synthetic:badInput,
%   acousticbench:synthetic:badCrossover.
%
%   See also acousticbench.synthetic.injectFault,
%   acousticbench.dsp.designIir, acousticbench.dsp.applyFilter.

arguments
    input {mustBeNumeric, mustBeReal}
    fs (1,1) double {mustBePositive}
    options.CrossoverHz double = [500 2000]
    options.CompressionRatio (1,1) double {mustBePositive} = 3
    options.KneeDbfs (1,1) double = -35
    options.AttackMs (1,1) double {mustBePositive} = 5
    options.ReleaseMs (1,1) double {mustBePositive} = 50
    options.GainDb (1,1) double = 0
    options.MakeupGainDb (1,1) double = 0
    options.FilterOrder (1,1) double {mustBeInteger, mustBePositive} = 2
end

x = input(:);
if isempty(x)
    error('acousticbench:synthetic:badInput', 'INPUT must be non-empty.');
end
crossovers = sort(options.CrossoverHz(:)');
if numel(crossovers) ~= 2 || crossovers(1) <= 0 || crossovers(2) >= fs / 2 ...
        || crossovers(1) >= crossovers(2)
    error('acousticbench:synthetic:badCrossover', ...
        'CrossoverHz must be [fLow fHigh] with 0 < fLow < fHigh < FS/2.');
end

x = x * 10 ^ (options.GainDb / 20);
n = numel(x);
order = options.FilterOrder;

% Three-band split with zero-phase Butterworth sections.
[lowSos, lowGain] = acousticbench.dsp.designIir('lowpass', crossovers(1), fs, order);
[highSos, highGain] = acousticbench.dsp.designIir('highpass', crossovers(1), fs, order);
[lowSos2, lowGain2] = acousticbench.dsp.designIir('lowpass', crossovers(2), fs, order);
[highSos2, highGain2] = acousticbench.dsp.designIir('highpass', crossovers(2), fs, order);

bandLow = acousticbench.dsp.applyFilter(x, struct('sos', lowSos, 'g', lowGain), ...
    'Method', 'filtfilt');
bandHigh = acousticbench.dsp.applyFilter(x, struct('sos', highSos2, 'g', highGain2), ...
    'Method', 'filtfilt');
bandMid = acousticbench.dsp.applyFilter(x, struct('sos', highSos, 'g', highGain), ...
    'Method', 'filtfilt');
bandMid = acousticbench.dsp.applyFilter(bandMid, ...
    struct('sos', lowSos2, 'g', lowGain2), 'Method', 'filtfilt');
bands = {bandLow, bandMid, bandHigh};
nBands = numel(bands);

attackCoefficient = exp(-1 / (fs * options.AttackMs / 1000));
releaseCoefficient = exp(-1 / (fs * options.ReleaseMs / 1000));
ratio = options.CompressionRatio;
knee = options.KneeDbfs;

output = zeros(n, 1);
bandEnvelopes = zeros(nBands, 1);
bandGainRange = zeros(nBands, 2);
for k = 1:nBands
    bandSignal = bands{k};
    envelope = 0;
    minimumGain = Inf;
    maximumGain = -Inf;
    for i = 1:n
        rectified = abs(bandSignal(i));
        if rectified > envelope
            envelope = attackCoefficient * envelope + (1 - attackCoefficient) * rectified;
        else
            envelope = releaseCoefficient * envelope + (1 - releaseCoefficient) * rectified;
        end
        levelDb = 20 * log10(max(envelope, 1e-12));
        if levelDb <= knee
            gainDb = 0;
        else
            gainDb = (knee + (levelDb - knee) / ratio) - levelDb;
        end
        minimumGain = min(minimumGain, gainDb);
        maximumGain = max(maximumGain, gainDb);
        output(i) = output(i) + bandSignal(i) * 10 ^ (gainDb / 20);
    end
    bandEnvelopes(k) = envelope;
    bandGainRange(k, :) = [minimumGain, maximumGain];
end
output = output * 10 ^ (options.MakeupGainDb / 20);

info = struct( ...
    'crossoverHz', crossovers, ...
    'nBands', nBands, ...
    'compressionRatio', ratio, ...
    'kneeDbfs', knee, ...
    'attackMs', options.AttackMs, ...
    'releaseMs', options.ReleaseMs, ...
    'gainDb', options.GainDb, ...
    'makeupGainDb', options.MakeupGainDb, ...
    'bandGainRangeDb', bandGainRange, ...
    'bandEnvelopes', bandEnvelopes, ...
    'nSamples', n);
end
