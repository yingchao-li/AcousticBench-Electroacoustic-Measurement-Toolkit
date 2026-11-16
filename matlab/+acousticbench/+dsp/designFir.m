function [b, info] = designFir(nTaps, cutoffHz, fs, options)
%DESIGNFIR Windowed-sinc FIR filter design (no Signal Processing Toolbox).
%
%   B = acousticbench.dsp.designFir(NTAPS, CUTOFFHZ, FS) designs a
%   linear-phase lowpass FIR filter with NTAPS coefficients and cutoff
%   CUTOFFHZ at sample rate FS, using the windowed-sinc method.
%
%   B = acousticbench.dsp.designFir(NTAPS, CUTOFFHZ, FS, 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Type'    'lowpass' (default) | 'highpass' | 'bandpass'
%       'Window'  'hamming' (default) | 'rect' | 'hann' | 'blackman'
%
%   For 'bandpass', CUTOFFHZ must be [fLow fHigh] with 0 < fLow < fHigh.
%   'highpass' and 'bandpass' with spectral inversion require an odd number
%   of taps (linear-phase type I).  The ideal responses are
%       lowpass : h[n] = 2 fc sinc(2 fc (n - M))
%       highpass: delta[n - M] - lowpass
%       bandpass: lowpass(fHigh) - lowpass(fLow)
%   with fc = CUTOFFHZ / FS and M = (NTAPS - 1) / 2; the chosen window is
%   applied after the ideal response has been formed.
%
%   Outputs
%       B     1 x NTAPS row vector of filter coefficients
%       INFO  struct with type, method, nTaps, cutoffHz, fs, window,
%             normalizedCutoff and the exact passband/stopband edges
%
%   Example
%       b = acousticbench.dsp.designFir(101, 4000, 48000);
%       sum(b)                            % ~ 1 (unity DC gain)
%       [H, f] = acousticbench.dsp.freqResponse(b, 48000, 1000);
%
%   Error identifiers: acousticbench:dsp:badCutoff,
%   acousticbench:dsp:evenTapsForInversion.
%
%   See also acousticbench.dsp.designIir, acousticbench.dsp.applyFilter.

arguments
    nTaps (1,1) double {mustBeInteger, mustBePositive}
    cutoffHz double {mustBePositive}
    fs (1,1) double {mustBePositive}
    options.Type {mustBeTextScalar} = 'lowpass'
    options.Window {mustBeTextScalar} = 'hamming'
end

type = validatestring(char(options.Type), ...
    {'lowpass', 'highpass', 'bandpass'}, mfilename, 'Type');
if nTaps < 3
    error('acousticbench:dsp:badCutoff', 'NTAPS must be >= 3, got %d.', nTaps);
end
if nTaps > 10001
    error('acousticbench:dsp:badCutoff', 'NTAPS must be <= 10001, got %d.', nTaps);
end
if ~isvector(cutoffHz)
    error('acousticbench:dsp:badCutoff', 'CUTOFFHZ must be a scalar or a two-element vector.');
end
cutoffHz = cutoffHz(:)';

switch type
    case {'lowpass', 'highpass'}
        if numel(cutoffHz) ~= 1
            error('acousticbench:dsp:badCutoff', ...
                'CUTOFFHZ must be a scalar for %s.', type);
        end
        normalized = cutoffHz / fs;
        if normalized <= 0 || normalized >= 0.5
            error('acousticbench:dsp:badCutoff', ...
                'Cutoff must lie strictly between 0 and FS/2 (got %g Hz at FS=%g Hz).', ...
                cutoffHz, fs);
        end
    otherwise
        if numel(cutoffHz) ~= 2
            error('acousticbench:dsp:badCutoff', ...
                'CUTOFFHZ must be [fLow fHigh] for bandpass.');
        end
        cutoffHz = sort(cutoffHz);
        normalized = cutoffHz / fs;
        if normalized(1) <= 0 || normalized(2) >= 0.5 || normalized(1) >= normalized(2)
            error('acousticbench:dsp:badCutoff', ...
                'Bandpass edges must satisfy 0 < fLow < fHigh < FS/2.');
        end
end

if ~strcmp(type, 'lowpass') && mod(nTaps, 2) == 0
    error('acousticbench:dsp:evenTapsForInversion', ...
        ['Type "%s" uses spectral inversion and requires an odd number of ' ...
         'taps (got %d).'], type, nTaps);
end

n = (0:nTaps - 1)';
centre = (nTaps - 1) / 2;

switch type
    case 'lowpass'
        b = idealLowpass(normalized(1), n, centre);
    case 'highpass'
        b = -idealLowpass(normalized(1), n, centre);
        b(centre + 1) = b(centre + 1) + 1;
    otherwise
        b = idealLowpass(normalized(2), n, centre) - idealLowpass(normalized(1), n, centre);
end

w = acousticbench.dsp.windowVector(options.Window, nTaps);
b = (b .* w)';
b = b(:)';   % ensure a row vector

info = struct( ...
    'type', type, ...
    'method', 'windowed_sinc', ...
    'nTaps', nTaps, ...
    'cutoffHz', cutoffHz, ...
    'fs', fs, ...
    'window', lower(char(options.Window)), ...
    'normalizedCutoff', normalized, ...
    'delaySamples', centre);
end

% =======================================================================
function h = idealLowpass(normalizedCutoff, n, centre)
% Ideal (non-causal, centred) lowpass impulse response at sample indices n.
argument = 2 * normalizedCutoff * (n - centre);
h = 2 * normalizedCutoff * sincNormalized(argument);
end

% =======================================================================
function y = sincNormalized(x)
% sin(pi x) / (pi x) with the limit value 1 at x = 0.
y = ones(size(x));
nonzero = x ~= 0;
y(nonzero) = sin(pi * x(nonzero)) ./ (pi * x(nonzero));
end
