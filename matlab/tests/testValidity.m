classdef testValidity < matlab.unittest.TestCase
%TESTVALIDITY Tests for the dataset loader, schema validation and masks.
%
%   Data.mat-dependent tests are guarded with
%   assumeTrue(exist(...,'file')==2) and are skipped when the published
%   dataset is absent.
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
        function testDeviceTable(testCase)
            devices = acousticbench.deviceTable();
            testCase.verifyEqual(numel(devices), 14);
            testCase.verifyEqual([devices.code], 1:14);
            testCase.verifyTrue(all([devices(1:2:end).isReference]));
            testCase.verifyTrue(all([devices(2:2:end).isMeasurement]));
            testCase.verifyTrue(all([devices(1:8).isEarmold]));
            testCase.verifyTrue(all([devices(9:14).isDome]));
            testCase.verifyEqual(devices(2).pairCode, 1);
            testCase.verifyEqual(devices(1).pairCode, 2);
            testCase.verifyEqual(numel(unique({devices.family})), 7);
        end

        function testStructuralValidityTableSize(testCase)
            T = acousticbench.structuralValidityTable();
            testCase.verifyEqual(height(T), 98);
            testCase.verifyEqual(width(T), 7);
            expectedNames = {'Container', 'DeviceCode', 'Family', 'Coupling', ...
                'Condition', 'StructurallyValid', 'Rationale'};
            testCase.verifyEqual(T.Properties.VariableNames, expectedNames);
        end

        function testStructuralValidityRules(testCase)
            T = acousticbench.structuralValidityTable('M_ha2edM');
            validCodes = T.DeviceCode(T.StructurallyValid);
            testCase.verifyEqual(validCodes(:)', 2:2:14);
            T = acousticbench.structuralValidityTable('M_ha2edR');
            validCodes = T.DeviceCode(T.StructurallyValid);
            testCase.verifyEqual(validCodes(:)', 1:8);
            T = acousticbench.structuralValidityTable('M_ha2haf');
            testCase.verifyEqual(nnz(T.StructurallyValid), 14);
            T = acousticbench.structuralValidityTable('M_ls2edR');
            testCase.verifyEqual(nnz(T.StructurallyValid), 8);
        end

        function testStructuralValidityTableUnknownContainer(testCase)
            testCase.verifyError(@() acousticbench.structuralValidityTable('nope'), ...
                'acousticbench:structuralValidityTable:unknownContainer');
        end

        function testLoadDataMissingFile(testCase)
            testCase.verifyError(@() acousticbench.loadData('this_file_does_not_exist.mat'), ...
                'acousticbench:loadData:fileNotFound');
        end

        function testLoadDataRealDataset(testCase)
            dataPath = repoDataPath();
            testCase.assumeTrue(exist(dataPath, 'file') == 2, ...
                'Data.mat is not present; dataset-dependent test skipped.');
            data = acousticbench.loadData(dataPath);

            testCase.verifyEqual(size(data.frequency), [2049, 1]);
            testCase.verifyEqual(size(data.audiometricFrequency), [6, 1]);
            testCase.verifyEqual(data.audiometricFrequency(:)', [125, 250, 500, 750, 1000, 2000]);
            testCase.verifyEqual(numel(data.devices), 14);
            testCase.verifyEqual(numel(data.subjects), 14);
            testCase.verifyEqual(numel(data.reinsertions), 3);

            transferKeys = {'M_ha2edM', 'M_ha2edR', 'M_ha2haf', 'M_ls2edM', 'M_ls2edR'};
            for k = 1:numel(transferKeys)
                key = transferKeys{k};
                values = data.variables.(key);
                testCase.verifyEqual(size(values), [2049, 14, 14, 3]);
                testCase.verifyFalse(isreal(values));
                testCase.verifyEqual(nnz(data.nanSession.(key)), 18);
                testCase.verifyEqual(size(data.valid.(key)), [2049, 14, 14, 3]);
            end
            testCase.verifyEqual(nnz(data.nanSession.M_thr_ha), 19);
            testCase.verifyEqual(size(data.variables.M_thr_ha), [6, 14, 14, 3]);
            testCase.verifyEqual(size(data.variables.M_REUR), [2049, 14]);

            % Structural masks are applied in the combined valid mask.
            testCase.verifyTrue(all(~data.valid.M_ha2edM(:, 1:2:end, :, :), 'all'));
            testCase.verifyTrue(all(~data.valid.M_ha2edR(:, 9:14, :, :), 'all'));
            testCase.verifyEqual(nnz(data.valid.M_ha2haf), nnz(isfinite(data.variables.M_ha2haf)));
        end

        function testLoadDataMaskingOptions(testCase)
            dataPath = repoDataPath();
            testCase.assumeTrue(exist(dataPath, 'file') == 2, ...
                'Data.mat is not present; dataset-dependent test skipped.');
            data = acousticbench.loadData(dataPath, ...
                'ApplyStructuralMask', true, 'ApplyNaNMask', true);
            testCase.verifyTrue(isfield(data.masked, 'M_ha2edR'));
            masked = data.masked.M_ha2edR;
            valid = data.valid.M_ha2edR;
            testCase.verifyTrue(all(isnan(masked(~valid))));
            testCase.verifyTrue(all(isfinite(masked(valid))));
        end

        function testStructuralMaskMatchesLoader(testCase)
            dataPath = repoDataPath();
            testCase.assumeTrue(exist(dataPath, 'file') == 2, ...
                'Data.mat is not present; dataset-dependent test skipped.');
            data = acousticbench.loadData(dataPath);
            T = acousticbench.structuralValidityTable('M_ha2edM');
            testCase.verifyEqual(T.StructurallyValid(:)', data.structural.M_ha2edM(:)');
            probeReference = data.valid.M_ha2edM(:, 1:2:end, :, :);
            testCase.verifyTrue(all(~probeReference, 'all'));
        end
    end
end

% =======================================================================
function path = repoDataPath()
here = fileparts(mfilename('fullpath'));
matlabDir = fileparts(here);
repoRoot = fileparts(matlabDir);
path = fullfile(repoRoot, 'Data.mat');
end
