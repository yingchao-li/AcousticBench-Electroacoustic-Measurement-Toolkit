function cases = buildSyntheticCases(options)
%BUILDSYNTHETICCASSES Build the reproducible synthetic validation case set.
%
%   CASES = acousticbench.synthetic.buildSyntheticCases() returns a 1x1000
%   struct array (250 gain, 250 SNR, 250 THD, 250 frequency-response cases)
%   generated with the master project seed 20260422.
%
%   CASES = acousticbench.synthetic.buildSyntheticCases('Name', VALUE, ...)
%
%   Name-Value arguments
%       'NumCases'    total number of cases (default 1000); the cases are
%                     split evenly over the categories, the remainder goes
%                     to the first categories
%       'Seed'        master seed (default 20260422)
%       'Fs'          sample rate in Hz (default 48000)
%       'DurationS'   duration in seconds (default 4)
%       'Categories'  cell array of categories, in order
%                     (default gain, snr, thd, frequency_response)
%
%   CASE fields
%       id               1..NumCases
%       category         'gain' | 'snr' | 'thd' | 'frequency_response'
%       seed             per-case deterministic seed (master seed + id)
%       fs, durationS
%       toneHz           tone frequency (0 for frequency-response cases)
%       gainDb           designed gain in dB
%       snrDb            designed SNR in dB (NaN if not applicable)
%       thdPercent       designed THD in percent (0 if not applicable)
%       inputLevelDbfs   input level in dBFS
%       noiseColor       'white' (SNR cases)
%       filterType       'lowpass' | 'highpass' | 'bandpass' | '' (FR cases)
%       filterCutoffHz   scalar or [fLow fHigh] cutoff in Hz
%       filterOrder      filter order (FR cases)
%
%   The generator uses a local mt19937ar stream; the output is identical
%   for identical arguments and independent of the caller's global RNG.
%
%   Example
%       a = acousticbench.synthetic.buildSyntheticCases();
%       b = acousticbench.synthetic.buildSyntheticCases();
%       isequal(a, b)                        % true
%       numel(a)                             % 1000
%
%   Error identifiers: acousticbench:synthetic:badCategories,
%   acousticbench:synthetic:badCount.
%
%   See also acousticbench.synthetic.renderSyntheticCase.

arguments
    options.NumCases (1,1) double {mustBeInteger, mustBePositive} = 1000
    options.Seed (1,1) double {mustBeInteger} = 20260422
    options.Fs (1,1) double {mustBePositive} = 48000
    options.DurationS (1,1) double {mustBePositive} = 4
    options.Categories cell = {'gain', 'snr', 'thd', 'frequency_response'}
end

categories = options.Categories;
if isempty(categories) || ~iscell(categories)
    error('acousticbench:synthetic:badCategories', ...
        'Categories must be a non-empty cell array of strings.');
end
nCategories = numel(categories);
for k = 1:nCategories
    categories{k} = lower(char(categories{k}));
    if ~any(strcmp(categories{k}, {'gain', 'snr', 'thd', 'frequency_response'}))
        error('acousticbench:synthetic:badCategories', ...
            'Unknown case category "%s".', categories{k});
    end
end
numCases = options.NumCases;
if numCases < nCategories
    error('acousticbench:synthetic:badCount', ...
        'NumCases must be at least the number of categories (%d).', nCategories);
end
perCategory = floor(numCases / nCategories);
remainder = numCases - perCategory * nCategories;
categoryOfCase = cell(1, numCases);
first = 1;
for k = 1:nCategories
    count = perCategory;
    if k <= remainder
        count = count + 1;
    end
    for j = 1:count
        categoryOfCase{first} = categories{k};
        first = first + 1;
    end
end

stream = RandStream('mt19937ar', 'Seed', options.Seed);
template = struct( ...
    'id', 0, ...
    'category', '', ...
    'seed', 0, ...
    'fs', options.Fs, ...
    'durationS', options.DurationS, ...
    'toneHz', 0, ...
    'gainDb', 0, ...
    'snrDb', NaN, ...
    'thdPercent', 0, ...
    'inputLevelDbfs', -20, ...
    'noiseColor', 'white', ...
    'filterType', '', ...
    'filterCutoffHz', 0, ...
    'filterOrder', 0);
cases = repmat(template, 1, numCases);

for id = 1:numCases
    category = categoryOfCase{id};
    entry = template;
    entry.id = id;
    entry.category = category;
    entry.seed = options.Seed + id;
    entry.fs = options.Fs;
    entry.durationS = options.DurationS;
    entry.inputLevelDbfs = -30 + 20 * rand(stream);
    switch category
        case 'gain'
            entry.toneHz = 1000;
            entry.gainDb = -20 + 60 * rand(stream);
        case 'snr'
            entry.toneHz = 1000;
            entry.snrDb = 40 * rand(stream);
            if rand(stream) < 0.5
                entry.noiseColor = 'pink';
            else
                entry.noiseColor = 'white';
            end
        case 'thd'
            entry.toneHz = 1000;
            entry.thdPercent = 0.1 + 9.9 * rand(stream);
        otherwise
            entry.toneHz = 0;
            filterIndex = 1 + floor(3 * rand(stream));
            filterTypes = {'lowpass', 'highpass', 'bandpass'};
            entry.filterType = filterTypes{filterIndex};
            entry.filterOrder = 2 + 2 * floor(2 * rand(stream));
            switch entry.filterType
                case {'lowpass', 'highpass'}
                    entry.filterCutoffHz = 500 + 3500 * rand(stream);
                otherwise
                    lowEdge = 200 + 1300 * rand(stream);
                    highEdge = lowEdge + 500 + 3500 * rand(stream);
                    highEdge = min(highEdge, 0.4 * options.Fs);
                    entry.filterCutoffHz = [lowEdge, highEdge];
            end
    end
    cases(id) = entry;
end
end
