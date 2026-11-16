classdef testSynthetic < matlab.unittest.TestCase
%TESTSYNTHETIC Tests for the reproducible synthetic case engine.
%
%   Run in MATLAB:
%       addpath(genpath('matlab')); run_all_tests

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
        function testBuildSyntheticCasesReproducible(testCase)
            first = acousticbench.synthetic.buildSyntheticCases();
            second = acousticbench.synthetic.buildSyntheticCases();
            testCase.verifyEqual(first, second);
        end

        function testBuildSyntheticCaseCounts(testCase)
            cases = acousticbench.synthetic.buildSyntheticCases();
            testCase.verifyEqual(numel(cases), 1000);
            categories = {cases.category};
            testCase.verifyEqual(nnz(strcmp(categories, 'gain')), 250);
            testCase.verifyEqual(nnz(strcmp(categories, 'snr')), 250);
            testCase.verifyEqual(nnz(strcmp(categories, 'thd')), 250);
            testCase.verifyEqual(nnz(strcmp(categories, 'frequency_response')), 250);
            testCase.verifyEqual([cases.id], 1:1000);
        end

        function testBuildSyntheticCasesCustomSeed(testCase)
            first = acousticbench.synthetic.buildSyntheticCases('NumCases', 40, 'Seed', 1);
            second = acousticbench.synthetic.buildSyntheticCases('NumCases', 40, 'Seed', 2);
            testCase.verifyFalse(isequal(first, second));
            testCase.verifyEqual(numel(first), 40);
        end

        function testRenderGainCase(testCase)
            cases = acousticbench.synthetic.buildSyntheticCases();
            gainCases = cases(strcmp({cases.category}, 'gain'));
            rendered = acousticbench.synthetic.renderSyntheticCase(gainCases(1));
            measuredGain = acousticbench.dsp.estimateGain(rendered.output, rendered.input);
            testCase.verifyEqual(measuredGain, gainCases(1).gainDb, 'AbsTol', 1e-9);
            testCase.verifyEqual(rendered.output, rendered.cleanReference, 'AbsTol', 0);
        end

        function testRenderSnrCase(testCase)
            cases = acousticbench.synthetic.buildSyntheticCases();
            snrCases = cases(strcmp({cases.category}, 'snr'));
            rendered = acousticbench.synthetic.renderSyntheticCase(snrCases(1));
            measuredSnr = acousticbench.dsp.estimateSnr(rendered.output, ...
                rendered.fs, 'ToneHz', rendered.toneHz);
            testCase.verifyEqual(measuredSnr, snrCases(1).snrDb, 'AbsTol', 0.6);
        end

        function testRenderThdCase(testCase)
            cases = acousticbench.synthetic.buildSyntheticCases();
            thdCases = cases(strcmp({cases.category}, 'thd'));
            rendered = acousticbench.synthetic.renderSyntheticCase(thdCases(1));
            measuredThd = acousticbench.dsp.estimateThd(rendered.output, ...
                rendered.fs, rendered.toneHz);
            testCase.verifyEqual(measuredThd, thdCases(1).thdPercent, 'AbsTol', 0.05);
        end

        function testRenderFrequencyResponseCase(testCase)
            cases = acousticbench.synthetic.buildSyntheticCases();
            frCases = cases(strcmp({cases.category}, 'frequency_response'));
            rendered = acousticbench.synthetic.renderSyntheticCase(frCases(1));
            groundTruth = rendered.groundTruth;
            testCase.verifyNotEmpty(groundTruth.frequencies);
            probe = groundTruth.frequencies;
            keep = probe >= 500 & probe <= 2000;
            estimated = acousticbench.dsp.estimateFilterResponse( ...
                rendered.input, rendered.output, rendered.fs, probe(keep));
            expected = groundTruth.magnitudeDb(keep);
            errorDb = abs(20 * log10(abs(estimated)) - expected);
            testCase.verifyLessThan(max(errorDb), 1.5);
        end

        function testVirtualHaCompression(testCase)
            fs = 48000;
            duration = 0.5;
            t = (0:round(duration * fs) - 1)' / fs;
            quiet = 0.01 * sin(2 * pi * 1000 * t);
            loud = 0.1 * sin(2 * pi * 1000 * t);
            quietOut = acousticbench.synthetic.virtualHA(quiet, fs, ...
                'CrossoverHz', [500, 2000], 'KneeDbfs', -35, 'CompressionRatio', 3);
            loudOut = acousticbench.synthetic.virtualHA(loud, fs, ...
                'CrossoverHz', [500, 2000], 'KneeDbfs', -35, 'CompressionRatio', 3);
            settle = round(0.25 * fs):numel(t);
            gainQuiet = 20 * log10(sqrt(mean(quietOut(settle) .^ 2)) / ...
                sqrt(mean(quiet(settle) .^ 2)));
            gainLoud = 20 * log10(sqrt(mean(loudOut(settle) .^ 2)) / ...
                sqrt(mean(loud(settle) .^ 2)));
            testCase.verifyGreaterThan(gainQuiet, gainLoud);
            testCase.verifyGreaterThan(gainQuiet - gainLoud, 3);
            testCase.verifyLessThan(gainQuiet - gainLoud, 12);
        end

        function testInjectFaultClipping(testCase)
            fs = 48000;
            t = (0:4799)' / fs;
            x = sin(2 * pi * 1000 * t);
            y = acousticbench.synthetic.injectFault(x, fs, 'clipping', 'ClipLevel', 0.3);
            testCase.verifyLessThanOrEqual(max(abs(y)), 0.3 + 1e-12);
        end

        function testInjectFaultDropout(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            x = sin(2 * pi * 1000 * t);
            [y, info] = acousticbench.synthetic.injectFault(x, fs, 'dropout', ...
                'DropoutStartS', 0.5, 'DropoutDurationS', 0.1);
            expectedZero = round(0.5 * fs) + 1:round(0.6 * fs);
            testCase.verifyEqual(y(expectedZero), zeros(numel(expectedZero), 1), 'AbsTol', 0);
            testCase.verifyEqual(info.parameters.startSample, expectedZero(1));
        end

        function testInjectFaultGainError(testCase)
            fs = 48000;
            x = randn(RandStream('mt19937ar', 'Seed', 1), 1000, 1);
            y = acousticbench.synthetic.injectFault(x, fs, 'gain_error', 'GainErrorDb', 6);
            measured = acousticbench.dsp.estimateGain(y, x);
            testCase.verifyEqual(measured, 6, 'AbsTol', 1e-9);
        end

        function testInjectFaultLatency(testCase)
            fs = 48000;
            x = randn(RandStream('mt19937ar', 'Seed', 2), 1000, 1);
            y = acousticbench.synthetic.injectFault(x, fs, 'latency', 'LatencyMs', 1);
            nDelay = round(0.001 * fs);
            testCase.verifyEqual(y(nDelay + 1:end), x(1:end - nDelay), 'AbsTol', 0);
        end

        function testInjectFaultHarmonicDistortion(testCase)
            fs = 48000;
            t = (0:47999)' / fs;
            x = 0.05 * sin(2 * pi * 1000 * t);
            y = acousticbench.synthetic.injectFault(x, fs, 'harmonic_distortion', ...
                'ThdPercent', 5, 'ToneHz', 1000);
            measuredThd = acousticbench.dsp.estimateThd(y, fs, 1000);
            testCase.verifyEqual(measuredThd, 5, 'AbsTol', 0.1);
        end
    end
end
