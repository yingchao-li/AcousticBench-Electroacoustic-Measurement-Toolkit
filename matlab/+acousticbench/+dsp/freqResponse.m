function [H, freq] = freqResponse(coeff, fs, freqs, options)
%FREQRESPONSE Complex frequency response of a filter at given frequencies.
%
%   [H, FREQ] = acousticbench.dsp.freqResponse(COEFF, FS, FREQS) evaluates
%   the complex transfer function H(e^{j2*pi*f/FS}) of the filter COEFF at
%   the requested frequencies FREQS (Hz).
%
%   COEFF may be
%       - a numeric FIR coefficient vector B,
%       - an nSections x 6 SOS matrix,
%       - a struct with fields b/a or sos/g.
%
%   Name-Value arguments
%       'Gain'  overall gain override (empty = from COEFF or 1)
%
%   Outputs
%       H     nFreq x 1 complex frequency response
%       FREQ  nFreq x 1 frequencies [Hz]
%
%   The response is evaluated analytically as
%       H(z) = G * (b0 + b1 z^-1 + b2 z^-2) / (a0 + a1 z^-1 + a2 z^-2),
%   cascaded over the SOS sections, with z = exp(j2*pi*f/FS).  No toolbox
%   function is used.
%
%   Example
%       b = acousticbench.dsp.designFir(101, 4000, 48000);
%       [H, f] = acousticbench.dsp.freqResponse(b, 48000, [0 1000 4000 8000]);
%       abs(H)
%
%   Error identifiers: acousticbench:dsp:badCoefficients.
%
%   See also acousticbench.dsp.applyFilter, acousticbench.dsp.designFir,
%   acousticbench.dsp.designIir.

arguments
    coeff
    fs (1,1) double {mustBePositive}
    freqs double
    options.Gain double = []
end

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
            'Numeric COEFF must be an FIR vector or an nSections x 6 SOS matrix.');
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
if ~isempty(options.Gain)
    g = options.Gain;
end

if ~isvector(freqs) || isempty(freqs)
    error('acousticbench:dsp:badFrequencies', 'FREQS must be a non-empty vector.');
end
freq = freqs(:);
zinv = exp(-1j * 2 * pi * freq / fs);
if isempty(sos)
    H = g * (polyval(flip(b), zinv) ./ polyval(flip(a), zinv));
else
    H = g * ones(numel(freq), 1);
    for k = 1:size(sos, 1)
        numerator = polyval(flip(sos(k, 1:3)), zinv);
        denominator = polyval(flip(sos(k, 4:6)), zinv);
        H = H .* (numerator ./ denominator);
    end
end
end
