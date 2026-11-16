function [noisy, noise, achievedSnrDb] = addAwgn(signal, snrDb, options)
%ADDAWGN Add white or pink Gaussian noise at a specified SNR.
%
%   [NOISY, NOISE] = acousticbench.dsp.addAwgn(SIGNAL, SNRDB) adds
%   additive Gaussian noise so that the signal-to-noise ratio, defined as
%       10 log10(mean(SIGNAL.^2) / mean(NOISE.^2)),
%   equals SNRDB.
%
%   [NOISY, NOISE] = acousticbench.dsp.addAwgn(SIGNAL, SNRDB, 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Seed'        integer seed for the mt19937ar random stream
%                     (default 20260422; the stream is local, so this
%                     function has no global side effects)
%       'NoiseColor'  'white' (default) or 'pink' (1/f amplitude shaping)
%
%   Outputs
%       NOISY           SIGNAL + NOISE (same shape as SIGNAL)
%       NOISE           generated noise (same shape as SIGNAL)
%       ACHIEVEDSNRDB   realised SNR in dB (useful for pink noise and for
%                       verifying the scaling)
%
%   Example
%       x = sin(2 * pi * 1000 * (0:47999)' / 48000);
%       y = acousticbench.dsp.addAwgn(x, 20);
%       snr = acousticbench.dsp.estimateSnr(y, 48000, 'Reference', x);
%
%   Error identifiers: acousticbench:dsp:badSignal,
%   acousticbench:dsp:zeroSignal, acousticbench:dsp:unknownNoiseColor.
%
%   See also acousticbench.dsp.estimateSnr.

arguments
    signal {mustBeNumeric, mustBeReal}
    snrDb (1,1) double {mustBeReal}
    options.Seed (1,1) double {mustBeInteger} = 20260422
    options.NoiseColor {mustBeTextScalar} = 'white'
end

x = signal(:);
if isempty(x)
    error('acousticbench:dsp:badSignal', 'SIGNAL must be non-empty.');
end
signalPower = mean(x .^ 2);
if signalPower == 0
    error('acousticbench:dsp:zeroSignal', 'SIGNAL has zero power.');
end

noiseColor = lower(char(options.NoiseColor));
stream = RandStream('mt19937ar', 'Seed', options.Seed);
switch noiseColor
    case 'white'
        raw = randn(stream, numel(x), 1);
    case 'pink'
        raw = pinkNoise(stream, numel(x));
    otherwise
        error('acousticbench:dsp:unknownNoiseColor', ...
            'Unknown noise color "%s"; expected white or pink.', noiseColor);
end
raw = raw - mean(raw);
rawPower = mean(raw .^ 2);
targetNoisePower = signalPower / (10 ^ (snrDb / 10));
noise = raw * sqrt(targetNoisePower / rawPower);
noisy = reshape(x + noise, size(signal));
noise = reshape(noise, size(signal));
achievedSnrDb = 10 * log10(signalPower / mean(noise(:) .^ 2));
end

% =======================================================================
function noise = pinkNoise(stream, n)
% 1/f-amplitude shaping of white Gaussian noise in the frequency domain.
white = randn(stream, n, 1);
spectrum = fft(white);
signedBin = (0:n - 1)';
signedBin(signedBin > n / 2) = signedBin(signedBin > n / 2) - n;
signedBin(1) = 1;                    % avoid a division by zero at DC
shaping = 1 ./ sqrt(abs(signedBin));
noise = real(ifft(spectrum .* shaping));
end
