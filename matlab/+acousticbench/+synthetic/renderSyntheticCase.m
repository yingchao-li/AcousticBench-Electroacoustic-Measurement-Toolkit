function [caseData, groundTruth] = renderSyntheticCase(caseSpec, options)
%RENDERSYNTHETICCASE Render one synthetic case with known ground truth.
%
%   [CASEDATA, GROUNDTRUTH] = acousticbench.synthetic.renderSyntheticCase(
%   CASESPEC) renders the signal pair described by a case from
%   acousticbench.synthetic.buildSyntheticCases.
%
%   CASEDATA has exactly the schema expected in
%   results/validation/matlab_inputs.mat (struct array `signals`):
%       id, fs, input, output, cleanReference, toneHz, thdPercent,
%       gainDb, snrDb, category
%   plus a `groundTruth` struct.
%
%   GROUNDTRUTH fields
%       category, gainDb, snrDb, thdPercent
%       frequencies     probe frequencies [Hz] (frequency-response cases)
%       magnitudeDb     exact filter magnitude at those frequencies [dB]
%       phaseDeg        exact filter phase at those frequencies [deg]
%
%   The per-case seed (CASESPEC.seed) makes every case reproducible.
%
%   Name-Value arguments
%       'ProbeFrequencies'  frequencies for the ground-truth response
%                           (default [100 250 500 1000 2000 4000 8000])
%
%   Example
%       cases = acousticbench.synthetic.buildSyntheticCases();
%       [c, gt] = acousticbench.synthetic.renderSyntheticCase(cases(1));
%       g = acousticbench.dsp.estimateGain(c.output, c.input);
%
%   Error identifiers: acousticbench:synthetic:badCase,
%   acousticbench:synthetic:unknownCategory.
%
%   See also acousticbench.synthetic.buildSyntheticCases,
%   acousticbench.synthetic.injectFault, acousticbench.synthetic.virtualHA.

arguments
    caseSpec struct
    options.ProbeFrequencies double = [100 250 500 1000 2000 4000 8000]
end

requiredFields = {'id', 'category', 'seed', 'fs', 'durationS', 'toneHz', ...
    'gainDb', 'snrDb', 'thdPercent', 'inputLevelDbfs', 'noiseColor', ...
    'filterType', 'filterCutoffHz', 'filterOrder'};
if ~all(isfield(caseSpec, requiredFields))
    error('acousticbench:synthetic:badCase', ...
        'CASESPEC is missing required fields (%s).', strjoin(requiredFields, ', '));
end

fs = caseSpec.fs;
n = round(caseSpec.durationS * fs);
t = (0:n - 1)' / fs;
stream = RandStream('mt19937ar', 'Seed', caseSpec.seed);
amplitude = 10 ^ (caseSpec.inputLevelDbfs / 20);

groundTruth = struct('category', caseSpec.category, ...
    'gainDb', caseSpec.gainDb, ...
    'snrDb', caseSpec.snrDb, ...
    'thdPercent', caseSpec.thdPercent, ...
    'frequencies', [], ...
    'magnitudeDb', [], ...
    'phaseDeg', []);

switch lower(char(caseSpec.category))
    case 'gain'
        toneHz = caseSpec.toneHz;
        input = amplitude * sin(2 * pi * toneHz * t);
        output = (10 ^ (caseSpec.gainDb / 20)) * input;
        cleanReference = output;
        toneHzOut = toneHz;
        thdPercent = 0;
        snrDb = Inf;
    case 'snr'
        toneHz = caseSpec.toneHz;
        cleanReference = amplitude * sin(2 * pi * toneHz * t);
        [output, ~] = acousticbench.dsp.addAwgn(cleanReference, caseSpec.snrDb, ...
            'Seed', caseSpec.seed, 'NoiseColor', caseSpec.noiseColor);
        input = cleanReference;
        toneHzOut = toneHz;
        thdPercent = 0;
        snrDb = caseSpec.snrDb;
    case 'thd'
        toneHz = caseSpec.toneHz;
        omega = 2 * pi * toneHz;
        thdRatio = caseSpec.thdPercent / 100;
        harmonic2Amplitude = amplitude * thdRatio / sqrt(2);
        harmonic3Amplitude = amplitude * thdRatio / sqrt(2);
        phase2 = 2 * pi * rand(stream);
        phase3 = 2 * pi * rand(stream);
        cleanReference = amplitude * sin(omega * t);
        output = cleanReference ...
            + harmonic2Amplitude * sin(2 * omega * t + phase2) ...
            + harmonic3Amplitude * sin(3 * omega * t + phase3);
        input = cleanReference;
        toneHzOut = toneHz;
        thdPercent = caseSpec.thdPercent;
        snrDb = Inf;
    case 'frequency_response'
        [sweep, ~] = acousticbench.dsp.logSweep(fs, caseSpec.durationS, ...
            100, min(10000, 0.4 * fs), 'Amplitude', amplitude);
        switch caseSpec.filterType
            case {'lowpass', 'highpass'}
                [sos, g] = acousticbench.dsp.designIir(caseSpec.filterType, ...
                    caseSpec.filterCutoffHz, fs, caseSpec.filterOrder);
                coefficients = struct('sos', sos, 'g', g);
            otherwise
                [b] = acousticbench.dsp.designFir(101, caseSpec.filterCutoffHz, fs, ...
                    'Type', 'bandpass');
                coefficients = b;
        end
        input = sweep;
        output = acousticbench.dsp.applyFilter(sweep, coefficients, 'Method', 'filter');
        cleanReference = output;
        toneHzOut = 0;
        thdPercent = 0;
        snrDb = NaN;
        probeFrequencies = options.ProbeFrequencies(:);
        probeFrequencies = probeFrequencies(probeFrequencies < fs / 2);
        response = acousticbench.dsp.freqResponse(coefficients, fs, probeFrequencies);
        groundTruth.frequencies = probeFrequencies;
        groundTruth.magnitudeDb = 20 * log10(abs(response));
        groundTruth.phaseDeg = 180 / pi * angle(response);
    otherwise
        error('acousticbench:synthetic:unknownCategory', ...
            'Unknown case category "%s".', caseSpec.category);
end

caseData = struct( ...
    'id', caseSpec.id, ...
    'fs', fs, ...
    'input', input(:), ...
    'output', output(:), ...
    'cleanReference', cleanReference(:), ...
    'toneHz', toneHzOut, ...
    'thdPercent', thdPercent, ...
    'gainDb', caseSpec.gainDb, ...
    'snrDb', snrDb, ...
    'category', caseSpec.category, ...
    'groundTruth', groundTruth);
end
