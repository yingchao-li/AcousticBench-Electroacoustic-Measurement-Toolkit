function y = applyFilter(x, coeff, options)
%APPLYFILTER Apply an FIR, IIR-transfer-function or SOS filter.
%
%   Y = acousticbench.dsp.applyFilter(X, B) filters X with the FIR filter B
%   (causal, y = filter(B, 1, X)).
%
%   Y = acousticbench.dsp.applyFilter(X, SOS) filters X with the
%   second-order sections SOS (nSections x 6, rows [b0 b1 b2 a0 a1 a2]).
%
%   Y = acousticbench.dsp.applyFilter(X, SPEC) where SPEC is a struct with
%   fields b/a (transfer function) or sos/g (sections plus gain).
%
%   Y = acousticbench.dsp.applyFilter(..., 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Method'  'filter' (default, causal) or 'filtfilt' (zero-phase
%                 forward-backward filtering with odd reflection padding;
%                 an independent approximation of the Signal Processing
%                 Toolbox filtfilt, not bit-identical to it)
%       'Gain'    overall gain applied to the filter output (empty = use
%                 the gain stored in SPEC, or 1)
%
%   The input may be real or complex and is filtered along its first
%   non-singleton dimension (column vectors are the normal case).  The
%   output has the same shape as X.  No toolbox function is used.
%
%   Example
%       b = acousticbench.dsp.designFir(51, 4000, 48000);
%       y = acousticbench.dsp.applyFilter(x, b);
%       [sos, g] = acousticbench.dsp.designIir('lowpass', 1000, 48000, 4);
%       y2 = acousticbench.dsp.applyFilter(x, struct('sos', sos, 'g', g), ...
%           'Method', 'filtfilt');
%
%   Error identifiers: acousticbench:dsp:badCoefficients,
%   acousticbench:dsp:unknownMethod.
%
%   See also acousticbench.dsp.designFir, acousticbench.dsp.designIir,
%   acousticbench.dsp.freqResponse.

arguments
    x {mustBeNumeric}
    coeff
    options.Method {mustBeTextScalar} = 'filter'
    options.Gain double = []
end

method = validatestring(char(options.Method), ...
    {'filter', 'filtfilt'}, mfilename, 'Method');
[b, a, sos, g] = parseCoefficients(coeff, options.Gain);

originalShape = size(x);
signal = x(:);
if isempty(signal)
    y = x;
    return;
end

if isempty(sos)
    if strcmp(method, 'filter')
        filtered = filter(b, a, signal);
    else
        filtered = zeroPhaseTransferFunction(b, a, signal);
    end
    filtered = g * filtered;
else
    if strcmp(method, 'filter')
        filtered = sosFilter(sos, g, signal);
    else
        filtered = signal;
        for k = 1:size(sos, 1)
            filtered = zeroPhaseTransferFunction(sos(k, 1:3), sos(k, 4:6), filtered);
        end
        filtered = g * filtered;
    end
end
y = reshape(filtered, originalShape);
end

% =======================================================================
function [b, a, sos, g] = parseCoefficients(coeff, requestedGain)
b = [];
a = [];
sos = [];
g = 1;
if isnumeric(coeff)
    if isvector(coeff)
        b = coeff(:)';
        a = 1;
    elseif size(coeff, 2) == 6
        sos = coeff;
    else
        error('acousticbench:dsp:badCoefficients', ...
            ['Numeric coefficient input must be an FIR vector or an ' ...
             'nSections x 6 SOS matrix.']);
    end
elseif isstruct(coeff)
    if isfield(coeff, 'sos')
        sos = coeff.sos;
        if isfield(coeff, 'g') && ~isempty(coeff.g)
            g = coeff.g;
        end
    elseif isfield(coeff, 'b') && isfield(coeff, 'a')
        b = coeff.b(:)';
        a = coeff.a(:)';
    else
        error('acousticbench:dsp:badCoefficients', ...
            'Coefficient struct must have fields (b, a) or (sos, g).');
    end
else
    error('acousticbench:dsp:badCoefficients', ...
        'COEFF must be a numeric vector/matrix or a coefficient struct.');
end

if ~isempty(sos)
    if ~ismatrix(sos) || size(sos, 2) ~= 6
        error('acousticbench:dsp:badCoefficients', 'SOS must be nSections x 6.');
    end
end
if ~isempty(b)
    if isempty(a) || ~isvector(a)
        error('acousticbench:dsp:badCoefficients', 'A must be a non-empty vector.');
    end
    if all(a == 0)
        error('acousticbench:dsp:badCoefficients', 'A must not be all zeros.');
    end
    if a(1) ~= 1
        b = b / a(1);
        a = a / a(1);
    end
end
if ~isempty(requestedGain)
    if ~isscalar(requestedGain) || ~isfinite(requestedGain) || requestedGain == 0
        error('acousticbench:dsp:badCoefficients', 'Gain must be a finite non-zero scalar.');
    end
    g = requestedGain;
end
end

% =======================================================================
function y = sosFilter(sos, g, x)
y = g * x;
for k = 1:size(sos, 1)
    y = filter(sos(k, 1:3), sos(k, 4:6), y);
end
end

% =======================================================================
function y = zeroPhaseTransferFunction(b, a, x)
signal = x(:);
n = numel(signal);
order = max(numel(b), numel(a));
pad = min(3 * order, max(n - 1, 0));
if pad > 0
    left = signal(pad + 1:-1:2);
    right = signal(n - 1:-1:n - pad);
    extended = [left; signal; right];
else
    extended = signal;
end
forward = filter(b, a, extended);
backward = flipud(filter(b, a, flipud(forward)));
y = backward(pad + 1:pad + n);
end
