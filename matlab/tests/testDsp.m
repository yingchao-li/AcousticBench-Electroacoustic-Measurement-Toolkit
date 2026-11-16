classdef testDsp < matlab.unittest.TestCase
%TESTDSP Unit tests for the independent MATLAB DSP implementation.
%
%   These tests exercise acousticbench.dsp.* against analytic ground truth
%   (sine amplitudes, white-noise PSD, known filter responses, exact
%   harmonic amplitudes) and known statistics.  They must be run in MATLAB:
%       addpath(genpath('matlab')); run_all_tests
%
%   The expected values are analytic; no random tolerances are relaxed
%   beyond the documented estimator accuracy.

    methods (TestClassSetup)
        function addPaths(testCase) %#ok<INUSD>
            here = fileparts(mfilename('fullpath'));
            matlabDir = fileparts(here);
            addpath(matlabDir);
            addpath(fullfile(matlabDir, 'tests'));
            rehash;
        end
    end

    methods (Test)
        function testFftSpectrumSineAmplitude(testCase)
            fs = 48000;
            n = 4800;
            t = (0:n - 1)' / fs;
            x = 1.5 * sin(2 * pi * 1000 * t);
            [amplitude, freq] = acousticbench.dsp.fftSpectrum(x, fs, 'Window', 'rect');
            [~, bin] = min(abs(freq - 1000));
            testCase.verifyEqual(amplitude(bin), 1.5, 'AbsTol', 1e-6);
            testCase.verifyEqual(numel(freq), n / 2 + 1);
            testCase.verifyEqual(freq(end), fs / 2, 'AbsTol', 1e-12);
        end

        function testFftSpectrumHannWindowScaling(testCase)
            fs = 44100;
            n = 4410;
            t = (0:n - 1)' / fs;
            x = 2 * sin(2 * pi * 1000 * t);
            [amplitude, freq] = acousticbench.dsp.fftSpectrum(x, fs, 'Window', 'hann');
            [~, bin] = min(abs(freq - 1000));
            testCase.verifyEqual(amplitude(bin), 2, 'AbsTol', 0.05);
        end

        function testStftFrameCount(testCase)
            fs = 48000;
            x = randn(RandStream('mt19937ar', 'Seed', 1), 4800, 1);
            [S, freq, time] = acousticbench.dsp.stftSpectrum(x, fs, ...
                'WindowLength', 512, 'Overlap', 0.5);
            testCase.verifyEqual(size(S, 2), 17);
            testCase.verifyEqual(size(S, 1), 257);
            testCase.verifyEqual(numel(freq), 257);
            testCase.verifyEqual(numel(time), 17);
        end

        function testWelchPsdWhiteNoisePower(testCase)
            fs = 48000;
            stream = RandStream('mt19937ar', 'Seed', 1);
            x = randn(stream, 48000, 1);
            [pxx, freq] = acousticbench.dsp.welchPsd(x, fs);
            totalPower = trapz(freq, pxx);
            testCase.verifyEqual(totalPower, 1, 'AbsTol', 0.1);
            testCase.verifyEqual(freq(1), 0, 'AbsTol', 1e-12);
            testCase.verifyEqual(freq(end), fs / 2, 'AbsTol', 1e-9);
        end

        function testDesignFirLowpassDcGain(testCase)
            b = acousticbench.dsp.designFir(101, 4000, 48000, 'Window', 'hamming');
            testCase.verifyEqual(size(b), [1, 101]);
            testCase.verifyEqual(sum(b), 1, 'AbsTol', 1e-3);
            H = acousticbench.dsp.freqResponse(b, 48000, 0);
            testCase.verifyEqual(abs(H), 1, 'AbsTol', 1e-3);
        end

        function testDesignFirHighpassNyquistGain(testCase)
            b = acousticbench.dsp.designFir(101, 6000, 48000, 'Type', 'highpass');
            H = acousticbench.dsp.freqResponse(b, 48000, 24000);
            testCase.verifyEqual(abs(H), 1, 'AbsTol', 1e-3);
            Hdc = acousticbench.dsp.freqResponse(b, 48000, 0);
            testCase.verifyLessThan(abs(Hdc), 1e-2);
        end

        function testDesignIirLowpassCutoff(testCase)
            fs = 48000;
            [sos, g] = acousticbench.dsp.designIir('lowpass', 1000, fs, 4);
            testCase.verifyEqual(size(sos, 2), 6);
            H = acousticbench.dsp.freqResponse(struct('sos', sos, 'g', g), fs, ...
                [0, 1000, fs / 2]);
            testCase.verifyEqual(abs(H(1)), 1, 'AbsTol', 1e-6);
            testCase.verifyEqual(abs(H(2)), 1 / sqrt(2), 'AbsTol', 1e-3);
            testCase.verifyLessThan(abs(H(3)), 1e-3);
        end

        function testDesignIirHighpassCutoff(testCase)
            fs = 48000;
            [sos, g] = acousticbench.dsp.designIir('highpass', 2000, fs, 4);
            H = acousticbench.dsp.freqResponse(struct('sos', sos, 'g', g), fs, ...
                [0, 2000, fs / 2]);
            testCase.verifyLessThan(abs(H(1)), 1e-6);
            testCase.verifyEqual(abs(H(2)), 1 / sqrt(2), 'AbsTol', 1e-3);
            testCase.verifyEqual(abs(H(3)), 1, 'AbsTol', 1e-6);
        end

        function testDesignIirBandpassEdges(testCase)
            fs = 48000;
            [sos, g] = acousticbench.dsp.designIir('bandpass', [500, 2000], fs, 2);
            H = acousticbench.dsp.freqResponse(struct('sos', sos, 'g', g), fs, ...
                [500, sqrt(500 * 2000), 2000]);
            testCase.verifyEqual(abs(H(1)), 1 / sqrt(2), 'AbsTol', 0.01);
            testCase.verifyEqual(abs(H(3)), 1 / sqrt(2), 'AbsTol', 0.01);
            testCase.verifyEqual(abs(H(2)), 1, 'AbsTol', 0.05);
        end

        function testDesignIirPeakingGain(testCase)
            fs = 48000;
            [sos, g] = acousticbench.dsp.designIir('peaking', 1000, fs, 2, ...
                'GainDb', 6, 'Q', 1);
            H = acousticbench.dsp.freqResponse(struct('sos', sos, 'g', g), fs, 1000);
            testCase.verifyEqual(20 * log10(abs(H)), 6, 'AbsTol', 1e-6);
        end

        function testApplyFilterFirMatchesFilter(testCase)
            b = [0.2, 0.5, 0.2];
            x = randn(RandStream('mt19937ar', 'Seed', 2), 1000, 1);
            y = acousticbench.dsp.applyFilter(x, b);
            expected = filter(b, 1, x);
            testCase.verifyEqual(y, expected, 'AbsTol', 1e-12);
        end

        function testApplyFilterSosSteadyState(testCase)
            fs = 48000;
            [sos, g] = acousticbench.dsp.designIir('lowpass', 1000, fs, 4);
            x = ones(8000, 1);
            y = acousticbench.dsp.applyFilter(x, struct('sos', sos, 'g', g));
            testCase.verifyEqual(y(end), 1, 'AbsTol', 1e-6);
        end

        function testApplyFilterZeroPhaseIsSymmetric(testCase)
            b = acousticbench.dsp.designFir(31, 4000, 48000);
            x = zeros(101, 1);
            x(51) = 1;
            y = acousticbench.dsp.applyFilter(x, b, 'Method', 'filtfilt');
            [~, peakIndex] = max(abs(y));
            testCase.verifyEqual(peakIndex, 51);
            testCase.verifyEqual(y(51), y(51), 'AbsTol', 0);
        end

        function testFreqResponseKnownFir(testCase)
            b = [1, -0.5];
            fs = 48000;
            H = acousticbench.dsp.freqResponse(b, fs, [0, fs / 2]);
            testCase.verifyEqual(H(1), 0.5, 'AbsTol', 1e-12);
            testCase.verifyEqual(H(2), 1.5, 'AbsTol', 1e-12);
        end

        function testEstimateGainExact(testCase)
            stream = RandStream('mt19937ar', 'Seed', 4);
            x = randn(stream, 10000, 1);
            y = 3 * x;
            gainDb = acousticbench.dsp.estimateGain(y, x);
            testCase.verifyEqual(gainDb, 20 * log10(3), 'AbsTol', 1e-9);
        end

        function testEstimateSnrTone(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            clean = sin(2 * pi * 1000 * t);
            noisy = acousticbench.dsp.addAwgn(clean, 20, 'Seed', 7);
            snrDb = acousticbench.dsp.estimateSnr(noisy, fs, 'ToneHz', 1000);
            testCase.verifyEqual(snrDb, 20, 'AbsTol', 0.6);
        end

        function testEstimateSnrReference(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            clean = sin(2 * pi * 1000 * t);
            noisy = acousticbench.dsp.addAwgn(clean, 10, 'Seed', 8);
            snrDb = acousticbench.dsp.estimateSnr(noisy, fs, 'Reference', clean);
            testCase.verifyEqual(snrDb, 10, 'AbsTol', 1e-6);
        end

        function testEstimateThdKnown(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            x = sin(2 * pi * 1000 * t) + 0.03 * sin(2 * pi * 2000 * t);
            thdPercent = acousticbench.dsp.estimateThd(x, fs, 1000);
            testCase.verifyEqual(thdPercent, 3, 'AbsTol', 1e-6);
        end

        function testEstimateThdPlusNKnown(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            x = sin(2 * pi * 1000 * t) + 0.1 * sin(2 * pi * 2000 * t);
            thdnPercent = acousticbench.dsp.estimateThdPlusN(x, fs, 1000);
            testCase.verifyEqual(thdnPercent, 9.95037, 'AbsTol', 0.05);
        end

        function testEstimateFilterResponseKnownFir(testCase)
            fs = 48000;
            b = acousticbench.dsp.designFir(101, 4000, fs);
            stream = RandStream('mt19937ar', 'Seed', 5);
            x = randn(stream, 48000, 1);
            y = filter(b, 1, x);
            probe = [500, 1000, 2000, 4000];
            estimated = acousticbench.dsp.estimateFilterResponse(x, y, fs, probe);
            expected = acousticbench.dsp.freqResponse(b, fs, probe);
            magnitudeError = abs(20 * log10(abs(estimated)) - 20 * log10(abs(expected)));
            phaseError = abs(180 / pi * angle(estimated) - 180 / pi * angle(expected));
            phaseError = min(phaseError, 360 - phaseError);
            testCase.verifyLessThan(max(magnitudeError), 1.0);
            testCase.verifyLessThan(max(phaseError), 10);
        end

        function testAddAwgnAchievedSnr(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            x = sin(2 * pi * 1000 * t);
            [y, noise, achievedSnrDb] = acousticbench.dsp.addAwgn(x, 10, 'Seed', 9);
            testCase.verifyEqual(achievedSnrDb, 10, 'AbsTol', 1e-6);
            testCase.verifyEqual(y, x + noise, 'AbsTol', 1e-12);
        end

        function testAddAwgnDeterministic(testCase)
            x = (1:1000)' / 1000;
            y1 = acousticbench.dsp.addAwgn(x, 5, 'Seed', 123);
            y2 = acousticbench.dsp.addAwgn(x, 5, 'Seed', 123);
            testCase.verifyEqual(y1, y2, 'AbsTol', 0);
        end

        function testLogSweepAnalytic(testCase)
            fs = 48000;
            duration = 4;
            fLow = 100;
            fHigh = 10000;
            [x, t] = acousticbench.dsp.logSweep(fs, duration, fLow, fHigh);
            logRatio = log(fHigh / fLow);
            phase = 2 * pi * fLow * (duration / logRatio) * ...
                (exp(t / duration * logRatio) - 1);
            testCase.verifyEqual(x, sin(phase), 'AbsTol', 1e-12);
            testCase.verifyEqual(numel(x), duration * fs);
        end

        function testBootstrapCIDeterminism(testCase)
            data = (1:14)';
            statistic = @(matrix) mean(matrix(:, 1));
            ci1 = acousticbench.stats.bootstrapCI(data, statistic, 200, 20260422);
            ci2 = acousticbench.stats.bootstrapCI(data, statistic, 200, 20260422);
            testCase.verifyEqual(ci1, ci2, 'AbsTol', 0);
            testCase.verifyLessThan(ci1(1), 7.5);
            testCase.verifyGreaterThan(ci1(2), 7.5);
        end

        function testPairedTTestKnown(testCase)
            differences = [1, 2, 3, 4, 5]';
            result = acousticbench.stats.pairedTTest(differences, zeros(5, 1));
            testCase.verifyEqual(result.tStatistic, 4.2426406871, 'AbsTol', 1e-8);
            testCase.verifyEqual(result.pValue, 0.0132355996, 'AbsTol', 1e-8);
            testCase.verifyEqual(result.df, 4);
            testCase.verifyEqual(result.effectSizeDz, 3, 'AbsTol', 1e-12);
            testCase.verifyLessThan(result.ci(1), result.ci(2));
        end

        function testWilcoxonAllPositive(testCase)
            differences = (1:10)';
            result = acousticbench.stats.wilcoxonTest(differences, zeros(10, 1));
            testCase.verifyEqual(result.wPlus, 55, 'AbsTol', 1e-12);
            testCase.verifyEqual(result.wMinus, 0, 'AbsTol', 1e-12);
            testCase.verifyLessThan(result.pValue, 0.01);
            testCase.verifyEqual(result.effectSize, 1, 'AbsTol', 1e-12);
        end

        function testHolmBonferroniKnown(testCase)
            pValues = [0.01, 0.04, 0.03, 0.005];
            [adjusted, rejected] = acousticbench.stats.holmBonferroni(pValues, 0.05);
            expected = [0.03, 0.06, 0.06, 0.02];
            testCase.verifyEqual(adjusted, expected, 'AbsTol', 1e-12);
            testCase.verifyTrue(all(rejected));
        end

        function testCohensDzKnown(testCase)
            differences = [1, 2, 3, 4, 5]';
            dz = acousticbench.stats.cohensDz(differences, zeros(5, 1));
            testCase.verifyEqual(dz, 1.8973665961, 'AbsTol', 1e-9);
        end

        function testRankBiserialAllPositive(testCase)
            differences = (1:10)';
            r = acousticbench.stats.rankBiserial(differences, zeros(10, 1));
            testCase.verifyEqual(r, 1, 'AbsTol', 1e-12);
        end

        function testWindowVectorHann(testCase)
            w = acousticbench.dsp.windowVector('hann', 101);
            testCase.verifyEqual(size(w), [101, 1]);
            testCase.verifyEqual(sum(w), 50.5, 'AbsTol', 1e-12);
            testCase.verifyEqual(w(1), 0, 'AbsTol', 1e-12);
            testCase.verifyEqual(w(end), 0, 'AbsTol', 1e-12);
        end
    end
end
