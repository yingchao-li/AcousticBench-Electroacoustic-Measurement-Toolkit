function w = windowVector(name, n)
%WINDOWVECTOR Symmetric analysis window without the Signal Processing Toolbox.
%
%   W = acousticbench.dsp.windowVector(NAME, N) returns an N-point symmetric
%   window column vector.  NAME is one of 'rect'/'boxcar', 'hann',
%   'hamming' or 'blackman' (case-insensitive).  This is a base-MATLAB
%   helper used by acousticbench.dsp.fftSpectrum, stftSpectrum, welchPsd,
%   designFir and estimateFilterResponse.
%
%   Inputs
%       NAME  window name
%       N     window length (positive integer)
%
%   Output
%       W     Nx1 double window
%
%   Example
%       w = acousticbench.dsp.windowVector('hann', 8);
%       sum(w)          % coherent gain
%
%   Error identifiers: acousticbench:dsp:unknownWindow,
%   acousticbench:dsp:badWindowLength.

arguments
    name {mustBeTextScalar}
    n (1,1) double {mustBeInteger, mustBePositive}
end

name = lower(char(name));
if n == 1
    w = 1;
    return;
end
k = (0:n - 1)' / (n - 1);
switch name
    case {'rect', 'boxcar', 'rectangular'}
        w = ones(n, 1);
    case {'hann', 'hanning'}
        w = 0.5 - 0.5 * cos(2 * pi * k);
    case 'hamming'
        w = 0.54 - 0.46 * cos(2 * pi * k);
    case 'blackman'
        w = 0.42 - 0.5 * cos(2 * pi * k) + 0.08 * cos(4 * pi * k);
    otherwise
        error('acousticbench:dsp:unknownWindow', ...
            'Unknown window "%s"; expected rect, hann, hamming or blackman.', name);
end
end
