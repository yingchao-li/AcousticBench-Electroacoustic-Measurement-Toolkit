classdef testMeasurements < matlab.unittest.TestCase
%TESTMEASUREMENTS Tests for Hha / REOIG / PTPE on synthetic complex data.
%
%   The tests build a small synthetic dataset with analytically known
%   eardrum pressures and verify the measurement functions against the
%   exact ground truth.  Data.mat-dependent checks are guarded with
%   assumeTrue(exist(...,'file')==2) and are skipped when the published
%   dataset is not present.
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
        function testHhaSplUnits(testCase)
            data = testMeasurements.buildSyntheticData();
            levels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
                'Condition', 'measurement');
            expected = 20 * log10(0.0056 / 20e-6);
            finiteValues = levels(isfinite(levels));
            testCase.verifyNotEmpty(finiteValues);
            testCase.verifyEqual(finiteValues, expected * ones(size(finiteValues)), ...
                'AbsTol', 1e-9);
        end

        function testHhaPaPerVoltUnits(testCase)
            data = testMeasurements.buildSyntheticData();
            levels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
                'Condition', 'measurement', 'Units', 'pa_per_v');
            finiteValues = levels(isfinite(levels));
            % Measurement-condition eardrum pressure is 0.0056 Pa at 11.2 mV.
            expected = 20 * log10(0.0056 / 0.0112);
            testCase.verifyEqual(finiteValues, expected * ones(size(finiteValues)), ...
                'AbsTol', 1e-9);
        end

        function testHhaStructuralMasking(testCase)
            data = testMeasurements.buildSyntheticData();
            % M_ha2edR is not defined for domes (codes 9..14).
            levels = acousticbench.hha(data, 'Container', 'M_ha2edR');
            testCase.verifyTrue(all(isnan(levels(:, 9:14, :, :)), 'all'));
            % M_ha2edM is not defined in the reference condition (odd codes).
            probeLevels = acousticbench.hha(data, 'Container', 'M_ha2edM');
            testCase.verifyTrue(all(isnan(probeLevels(:, 1:2:end, :, :)), 'all'));
        end

        function testReoigKnownRatio(testCase)
            data = testMeasurements.buildSyntheticData();
            % M_ls2edM = 2 * M_REUR in the measurement condition.
            gain = acousticbench.reoig(data, 'Condition', 'measurement');
            expected = 20 * log10(2);
            finiteValues = gain(isfinite(gain));
            testCase.verifyNotEmpty(finiteValues);
            testCase.verifyEqual(finiteValues, expected * ones(size(finiteValues)), ...
                'AbsTol', 1e-9);
        end

        function testReoigReferenceCondition(testCase)
            data = testMeasurements.buildSyntheticData();
            % M_ls2edR = M_REUR for earmolds -> 0 dB in the reference condition.
            gain = acousticbench.reoig(data, 'Condition', 'reference');
            finiteValues = gain(isfinite(gain));
            testCase.verifyNotEmpty(finiteValues);
            testCase.verifyEqual(finiteValues, zeros(size(finiteValues)), 'AbsTol', 1e-9);
        end

        function testPtpeHhaKnown(testCase)
            data = testMeasurements.buildSyntheticData();
            out = acousticbench.ptpe(data, 'closed_earmold', 'Metric', 'hha', ...
                'Frequencies', [100, 250, 500, 1000]);
            testCase.verifyEqual(out.deviceCodes, [1, 2]);
            expected = 20 * log10(0.5);
            testCase.verifyEqual(out.medianDb, expected * ones(4, 1), 'AbsTol', 1e-9);
            testCase.verifyEqual(size(out.delta), [4, 14, 3]);
        end

        function testPtpeReoigKnown(testCase)
            data = testMeasurements.buildSyntheticData();
            out = acousticbench.ptpe(data, 'vented_earmold', 'Metric', 'reoig', ...
                'Frequencies', [100, 1000]);
            expected = 20 * log10(2);
            testCase.verifyEqual(out.medianDb, expected * ones(2, 1), 'AbsTol', 1e-9);
        end

        function testPtpeThresholdKnown(testCase)
            data = testMeasurements.buildSyntheticData();
            out = acousticbench.ptpe(data, 'closed_earmold', 'Metric', 'threshold', ...
                'Frequencies', 125);
            % T_ref = -90 dBV, T_meas = -88 dBV -> deltaT = -2 dB.
            testCase.verifyEqual(out.medianDb, -2, 'AbsTol', 1e-9);
            testCase.verifyEqual(out.frequenciesHz, 125);
        end

        function testPtpeThresholdWorksForDomes(testCase)
            data = testMeasurements.buildSyntheticData();
            out = acousticbench.ptpe(data, 'open_dome', 'Metric', 'threshold', ...
                'Frequencies', 125);
            testCase.verifyEqual(out.medianDb, -2, 'AbsTol', 1e-9);
        end

        function testPtpeHhaRejectsDomes(testCase)
            data = testMeasurements.buildSyntheticData();
            testCase.verifyError(@() acousticbench.ptpe(data, 'open_dome', ...
                'Metric', 'hha'), 'acousticbench:ptpe:notEarmold');
        end

        function testBandLevelsPowerAverage(testCase)
            freq = (0:1000)';
            values = 20 * ones(1001, 1);
            bands = acousticbench.octaveBands('Centers', 500);
            bandDb = acousticbench.bandLevels(values, freq, bands);
            testCase.verifyEqual(bandDb, 20, 'AbsTol', 1e-12);
            % Mix 10 dB and 20 dB inside the band and expect the power mean.
            values = 10 * ones(1001, 1);
            bandIndices = find(freq >= bands.lowHz & freq < bands.highHz);
            split = floor(numel(bandIndices) / 2);
            values(bandIndices(1:split)) = 20;
            nHigh = split;
            nLow = numel(bandIndices) - split;
            expected = 10 * log10((nHigh * 10 ^ 2 + nLow * 10 ^ 1) / (nHigh + nLow));
            bandDb = acousticbench.bandLevels(values, freq, bands);
            testCase.verifyEqual(bandDb, expected, 'AbsTol', 1e-12);
        end

        function testThresholdTableMedian(testCase)
            data = testMeasurements.buildSyntheticData();
            T = acousticbench.thresholdTable(data, 'DeviceCodes', [1, 2]);
            testCase.verifyEqual(height(T), 12);
            referenceRows = strcmp(T.Condition, 'reference');
            measurementRows = strcmp(T.Condition, 'measurement');
            testCase.verifyEqual(unique(T.ValueDbv(referenceRows)), -90, 'AbsTol', 1e-9);
            testCase.verifyEqual(unique(T.ValueDbv(measurementRows)), -88, 'AbsTol', 1e-9);
        end

        function testReferenceMetricsContract(testCase)
            data = testMeasurements.buildSyntheticData();
            refs = acousticbench.referenceMetrics(data);
            testCase.verifyEqual(numel(refs), 142);
            expectedHha = 20 * log10(0.0056 / 20e-6);
            expectedReoig = 20 * log10(2);
            expectedDeltaHha = 20 * log10(0.5);
            index = find(strcmp({refs.testId}, 'hha_band:2:1000'));
            testCase.verifyNotEmpty(index);
            testCase.verifyEqual(refs(index).value, expectedHha, 'AbsTol', 1e-9);
            testCase.verifyEqual(refs(index).quantity, 'hha_band_db');
            testCase.verifyEqual(refs(index).unit, 'dB');
            index = find(strcmp({refs.testId}, 'reoig_band:closed_earmold:1000'));
            testCase.verifyNotEmpty(index);
            testCase.verifyEqual(refs(index).value, expectedReoig, 'AbsTol', 1e-9);
            index = find(strcmp({refs.testId}, 'ptpe_hha_band:closed_earmold:1000'));
            testCase.verifyNotEmpty(index);
            testCase.verifyEqual(refs(index).value, expectedDeltaHha, 'AbsTol', 1e-9);
            index = find(strcmp({refs.testId}, 'delta_t_125:open_dome'));
            testCase.verifyNotEmpty(index);
            testCase.verifyEqual(refs(index).value, -2, 'AbsTol', 1e-9);
        end

        function testHhaOnRealDataset(testCase)
            dataPath = testCase.repoDataPath();
            testCase.assumeTrue(exist(dataPath, 'file') == 2, ...
                'Data.mat is not present; dataset-dependent test skipped.');
            data = acousticbench.loadData(dataPath);
            levels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
                'Condition', 'measurement');
            % Values must be in a physically plausible range and the invalid
            % entries must be NaN, never 0 or imputed.
            finiteValues = levels(isfinite(levels));
            testCase.verifyNotEmpty(finiteValues);
            testCase.verifyGreaterThan(min(finiteValues), 0);
            testCase.verifyLessThan(max(finiteValues), 140);
            testCase.verifyTrue(all(isnan(levels(:, 9:14, :, :)), 'all'));
        end

        function testPtpeSignsOnRealDataset(testCase)
            dataPath = testCase.repoDataPath();
            testCase.assumeTrue(exist(dataPath, 'file') == 2, ...
                'Data.mat is not present; dataset-dependent test skipped.');
            data = acousticbench.loadData(dataPath);
            out = acousticbench.ptpe(data, 'nugget_earmold', 'Metric', 'hha', ...
                'Frequencies', 100);
            testCase.verifyLessThan(out.medianDb, 0);
            thresholds = acousticbench.ptpe(data, 'closed_earmold', ...
                'Metric', 'threshold', 'Frequencies', 125);
            testCase.verifyLessThan(thresholds.medianDb, 0);
        end
    end

    methods (Access = private)
        function path = repoDataPath(testCase) %#ok<INUSD>
            here = fileparts(mfilename('fullpath'));
            matlabDir = fileparts(here);
            repoRoot = fileparts(matlabDir);
            path = fullfile(repoRoot, 'Data.mat');
        end
    end

    methods (Static, Access = private)
        function data = buildSyntheticData()
            % Synthetic dataset with analytically known values.
            nFrequency = 2049;
            frequency = (0:nFrequency - 1)' * (22050 / 2048);
            devices = acousticbench.deviceTable();
            nDevices = numel(devices);
            nSubjects = 14;
            nReinsertions = 3;

            data = struct();
            data.frequency = frequency;
            data.audiometricFrequency = [125, 250, 500, 750, 1000, 2000]';
            data.subjects = (1:nSubjects)';
            data.reinsertions = (1:nReinsertions)';
            data.devices = devices;

            ha2edR = complex(0.0112 * ones(nFrequency, nDevices, nSubjects, nReinsertions));
            ha2edM = complex(0.0112 * ones(size(ha2edR)));
            ls2edM = complex(2 * ones(size(ha2edR)));
            ls2edR = complex(1 * ones(size(ha2edR)));
            ha2haf = complex(0.001 * ones(size(ha2edR)));
            reur = complex(ones(nFrequency, nSubjects));
            threshold = -90 * ones(6, nDevices, nSubjects, nReinsertions);

            for code = 1:2:nDevices
                ha2edR(:, code + 1, :, :) = 0.0056;   % measurement condition
                threshold(:, code + 1, :, :) = -88;
            end

            data.variables = struct();
            data.variables.M_ha2edR = ha2edR;
            data.variables.M_ha2edM = ha2edM;
            data.variables.M_ls2edM = ls2edM;
            data.variables.M_ls2edR = ls2edR;
            data.variables.M_ha2haf = ha2haf;
            data.variables.M_REUR = reur;
            data.variables.M_thr_ha = threshold;

            data.structural = struct();
            data.structural.M_ha2edR = reshape([devices.isEarmold], 1, []);
            data.structural.M_ha2edM = reshape([devices.isMeasurement], 1, []);
            data.structural.M_ha2haf = true(1, nDevices);
            data.structural.M_ls2edM = reshape([devices.isMeasurement], 1, []);
            data.structural.M_ls2edR = reshape([devices.isEarmold], 1, []);
            data.structural.M_thr_ha = true(1, nDevices);
            data.structural.M_REUR = true;

            data.valid = struct();
            transferKeys = {'M_ha2edR', 'M_ha2edM', 'M_ha2haf', 'M_ls2edM', 'M_ls2edR'};
            for k = 1:numel(transferKeys)
                key = transferKeys{k};
                structural = reshape(data.structural.(key), 1, nDevices, 1, 1);
                data.valid.(key) = isfinite(data.variables.(key)) & structural;
            end
            data.valid.M_thr_ha = isfinite(threshold);
            data.valid.M_REUR = isfinite(reur);
            data.meta = struct('nFrequencies', nFrequency, 'nDevices', nDevices, ...
                'nSubjects', nSubjects, 'nReinsertions', nReinsertions);
        end
    end
end
