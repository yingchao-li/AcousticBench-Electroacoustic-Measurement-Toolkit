function [sos, g, info] = designIir(type, cutoffHz, fs, order, options)
%DESIGNIIR Butterworth / peaking IIR filter design as second-order sections.
%
%   [SOS, G] = acousticbench.dsp.designIir(TYPE, CUTOFFHZ, FS, ORDER)
%   designs a digital IIR filter without the Signal Processing Toolbox and
%   returns its second-order sections SOS (nSections x 6, rows
%   [b0 b1 b2 a0 a1 a2] with a0 = 1) and the overall gain G.  The filter is
%   applied as y = G * cascade(SOS), see acousticbench.dsp.applyFilter.
%
%   NAME-VALUE arguments
%       'GainDb'  peaking-filter gain in dB (default 0)
%       'Q'       peaking-filter quality factor (default 1/sqrt(2))
%
%   TYPE is one of
%       'lowpass'   Butterworth lowpass, ORDER-th order, -3 dB at CUTOFFHZ
%       'highpass'  Butterworth highpass, ORDER-th order, -3 dB at CUTOFFHZ
%       'bandpass'  Butterworth bandpass, ORDER-th order prototype
%                   (2*ORDER-th order digital filter); CUTOFFHZ = [fLow fHigh]
%       'peaking'   RBJ audio peaking EQ biquad; CUTOFFHZ = centre frequency
%
%   Method (no toolbox):
%       The analog Butterworth prototype poles exp(j*pi*(2k+n+1)/(2n)) are
%       transformed with the bilinear transform after frequency prewarping
%       (tan(pi*f/fs)), the poles/zeros are paired into biquads and the gain
%       is normalised to unity at DC (lowpass), Nyquist (highpass) or the
%       warped band centre (bandpass).
%
%   Inputs
%       TYPE      filter type string
%       CUTOFFHZ  cutoff frequency in Hz (or [fLow fHigh] for bandpass)
%       FS        sample rate in Hz
%       ORDER     Butterworth order (positive integer, default 4)
%
%   Outputs
%       SOS    nSections x 6 double second-order sections
%       G      scalar overall gain
%       INFO   struct with type, method, order, cutoffHz, fs and design data
%
%   Example
%       [sos, g] = acousticbench.dsp.designIir('lowpass', 1000, 48000, 4);
%       H = acousticbench.dsp.freqResponse(struct('sos', sos, 'g', g), ...
%           48000, [0 500 1000 2000]);
%       abs(H)     % 1 at DC, 1/sqrt(2) at 1 kHz
%
%   Error identifiers: acousticbench:dsp:badCutoff,
%   acousticbench:dsp:badOrder.
%
%   See also acousticbench.dsp.designFir, acousticbench.dsp.applyFilter,
%   acousticbench.dsp.freqResponse.

arguments
    type {mustBeTextScalar}
    cutoffHz double {mustBePositive}
    fs (1,1) double {mustBePositive}
    order (1,1) double {mustBeInteger, mustBePositive, mustBeInRange(order, 1, 12)} = 4
    options.GainDb (1,1) double = 0
    options.Q (1,1) double {mustBePositive} = 0.7071067811865476
end

type = validatestring(char(type), ...
    {'lowpass', 'highpass', 'bandpass', 'peaking'}, mfilename, 'type');

if strcmp(type, 'peaking')
    if ~isscalar(cutoffHz)
        error('acousticbench:dsp:badCutoff', ...
            'CUTOFFHZ must be a scalar centre frequency for peaking.');
    end
    [sos, g] = peakingEq(cutoffHz, fs, options.GainDb, options.Q);
    info = struct( ...
        'type', type, ...
        'method', 'rbj_peaking_eq', ...
        'order', order, ...
        'cutoffHz', cutoffHz, ...
        'fs', fs, ...
        'gainDb', options.GainDb, ...
        'q', options.Q, ...
        'nSections', size(sos, 1));
    return;
end

cutoffHz = cutoffHz(:)';
switch type
    case {'lowpass', 'highpass'}
        if ~isscalar(cutoffHz)
            error('acousticbench:dsp:badCutoff', ...
                'CUTOFFHZ must be a scalar for %s.', type);
        end
        if cutoffHz <= 0 || cutoffHz >= fs / 2
            error('acousticbench:dsp:badCutoff', ...
                'Cutoff must lie strictly between 0 and FS/2 (got %g Hz).', cutoffHz);
        end
    otherwise
        if numel(cutoffHz) ~= 2
            error('acousticbench:dsp:badCutoff', ...
                'CUTOFFHZ must be [fLow fHigh] for bandpass.');
        end
        cutoffHz = sort(cutoffHz);
        if cutoffHz(1) <= 0 || cutoffHz(2) >= fs / 2 || cutoffHz(1) >= cutoffHz(2)
            error('acousticbench:dsp:badCutoff', ...
                'Bandpass edges must satisfy 0 < fLow < fHigh < FS/2.');
        end
end
if order < 1
    error('acousticbench:dsp:badOrder', 'ORDER must be a positive integer.');
end

n = order;
prototypePoles = exp(1j * pi * ((2 * (0:n - 1)' + n + 1) / (2 * n)));

switch type
    case 'lowpass'
        r = tan(pi * cutoffHz / fs);
        poles = (1 + r * prototypePoles) ./ (1 - r * prototypePoles);
        zerosVec = -ones(n, 1);
        referenceHz = 0;
        method = 'butterworth_bilinear_lowpass';
    case 'highpass'
        r = tan(pi * cutoffHz / fs);
        poles = (1 + r * prototypePoles) ./ (1 - r * prototypePoles);
        zerosVec = ones(n, 1);
        referenceHz = fs / 2;
        method = 'butterworth_bilinear_highpass';
    otherwise
        analogLow = 2 * fs * tan(pi * cutoffHz(1) / fs);
        analogHigh = 2 * fs * tan(pi * cutoffHz(2) / fs);
        analogCentre = sqrt(analogLow * analogHigh);
        bandwidth = analogHigh - analogLow;
        analogPoles = zeros(2 * n, 1);
        for k = 1:n
            halfTerm = (bandwidth / 2) * prototypePoles(k);
            rootTerm = sqrt(halfTerm ^ 2 - analogCentre ^ 2);
            analogPoles(2 * k - 1) = halfTerm + rootTerm;
            analogPoles(2 * k) = halfTerm - rootTerm;
        end
        poles = (1 + analogPoles / (2 * fs)) ./ (1 - analogPoles / (2 * fs));
        zerosVec = [ones(n, 1); -ones(n, 1)];
        referenceHz = (2 * fs / (2 * pi)) * atan(analogCentre / (2 * fs));
        method = 'butterworth_bilinear_bandpass';
end

sos = zpkToSos(zerosVec, poles);

% Normalise the cascade to unity magnitude at the reference frequency.
zinv = exp(-1j * 2 * pi * referenceHz / fs);
response = 1;
for k = 1:size(sos, 1)
    numerator = sos(k, 1) + sos(k, 2) * zinv + sos(k, 3) * zinv ^ 2;
    denominator = sos(k, 4) + sos(k, 5) * zinv + sos(k, 6) * zinv ^ 2;
    response = response * (numerator / denominator);
end
if response == 0 || ~isfinite(response)
    error('acousticbench:dsp:badOrder', ...
        'Filter normalisation failed (degenerate design at ORDER=%d).', order);
end
g = 1 / abs(response);

info = struct( ...
    'type', type, ...
    'method', method, ...
    'order', order, ...
    'cutoffHz', cutoffHz, ...
    'fs', fs, ...
    'referenceFrequencyHz', referenceHz, ...
    'nSections', size(sos, 1));
end

% =======================================================================
function [sos, g] = peakingEq(centreHz, fs, gainDb, q)
if centreHz <= 0 || centreHz >= fs / 2
    error('acousticbench:dsp:badCutoff', ...
        'Centre frequency must lie strictly between 0 and FS/2.');
end
a = 10 ^ (gainDb / 40);
w0 = 2 * pi * centreHz / fs;
alpha = sin(w0) / (2 * q);
b0 = 1 + alpha * a;
b1 = -2 * cos(w0);
b2 = 1 - alpha * a;
a0 = 1 + alpha / a;
a1 = -2 * cos(w0);
a2 = 1 - alpha / a;
sos = [b0, b1, b2, a0, a1, a2] / a0;
g = 1;
end

% =======================================================================
function sos = zpkToSos(zerosVec, polesVec)
% Pair roots into (possibly first-order) sections and build SOS rows.
zeroGroups = pairRoots(zerosVec);
poleGroups = pairRoots(polesVec);
if isempty(poleGroups)
    sos = zeros(0, 6);
    return;
end
while numel(zeroGroups) < numel(poleGroups)
    zeroGroups{end + 1} = 0; %#ok<AGROW>
end
while numel(poleGroups) < numel(zeroGroups)
    poleGroups{end + 1} = 0; %#ok<AGROW>
end
sos = zeros(numel(poleGroups), 6);
for k = 1:numel(poleGroups)
    b = poly(zeroGroups{k});
    a = poly(poleGroups{k});
    b = real(b(:)');
    a = real(a(:)');
    b = [b, zeros(1, 3 - numel(b))];
    a = [a, zeros(1, 3 - numel(a))];
    sos(k, :) = [b, a];
end
end

% =======================================================================
function groups = pairRoots(rootsVec)
rootsVec = rootsVec(:);
groups = {};
if isempty(rootsVec)
    return;
end
tolerance = 1e-8 * max(1, max(abs(rootsVec)));
used = false(numel(rootsVec), 1);
for i = 1:numel(rootsVec)
    if used(i)
        continue;
    end
    root = rootsVec(i);
    if abs(imag(root)) <= tolerance
        continue;
    end
    partner = 0;
    for j = i + 1:numel(rootsVec)
        if ~used(j) && abs(rootsVec(j) - conj(root)) <= tolerance
            partner = j;
            break;
        end
    end
    if partner > 0
        used(i) = true;
        used(partner) = true;
        groups{end + 1} = [root; rootsVec(partner)]; %#ok<AGROW>
    else
        used(i) = true;
        groups{end + 1} = root; %#ok<AGROW>
    end
end
realIndices = find(~used);
k = 1;
while k <= numel(realIndices)
    if k + 1 <= numel(realIndices)
        groups{end + 1} = [rootsVec(realIndices(k)); rootsVec(realIndices(k + 1))]; %#ok<AGROW>
        k = k + 2;
    else
        groups{end + 1} = rootsVec(realIndices(k)); %#ok<AGROW>
        k = k + 1;
    end
end
end
