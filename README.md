# TauMLTools

## Introduction

Tools to perform machine learning studies for tau lepton reconstruction and identification at CMS.

## How to install

```sh
cmsrel CMSSW_10_6_13
cd CMSSW_10_6_13/src
cmsenv
git clone -o cms-tau-pog git@github.com:cms-tau-pog/TauMLTools.git
scram b -j8
```

## How to produce inputs

Steps below describe how to process input datasets starting from MiniAOD up to the representation that can be directly used as an input for the training.

### Big root-tuples production

The big root-tuples, `TauTuple`, contain an extensive information about reconstructed tau, seeding jet, and all reco objects within tau signal and isolation cones: PF candidates, pat::Electrons and pat::Muons, and tracks.
`TauTuple` also contain the MC truth that can be used to identify the tau decay.
Each `TauTuple` entry corresponds to a single tau candidate.
Branches available within `TauTuple` are defined in [Analysis/interface/TauTuple.h](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/interface/TauTuple.h)
These branches are filled in CMSSW module [Production/plugins/TauTupleProducer.cc](https://github.com/cms-tau-pog/TauMLTools/blob/master/Production/plugins/TauTupleProducer.cc) that converts information stored in MiniAOD events into `TauTuple` format.

[Production/python/Production.py](https://github.com/cms-tau-pog/TauMLTools/blob/master/Production/python/Production.py) contains the configuration that allows to run `TauTupleProducer` with `cmsRun`.
Here is an example how to run `TauTupleProducer` on 1000 DY events using one MiniAOD file as an input:
```sh
cmsRun TauMLTools/Production/python/Production.py sampleType=MC_18 inputFiles=/store/mc/RunIIAutumn18MiniAOD/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/MINIAODSIM/102X_upgrade2018_realistic_v15-v1/00000/A788C40A-03F7-4547-B5BA-C1E01CEBB8D8.root maxEvents=1000 rerunTauReco=True
```

In order to run a large-scale production for the entire datasets, the CMS computing grid should be used via CRAB interface.
To submit jobs on CRAB following steps should be followed:
1. Go to directory [TauMLTools/Production/crab](https://github.com/cms-tau-pog/TauMLTools/tree/master/Production/crab)
1. Use submit.py to submit jobs on CRAB
   ```sh
   ./submit.py --workArea work-area --cfg ../python/Production.py --site STAGEOUT_SITE --output raw-tuples-v2 configs/2017/*.txt
   ```
   For more command line options use `submit.py --help`.
1. Follow usual CRAB workflow until all jobs are finished

The centrally produced `TauTuples` will be available in `/eos/cms/store/group/phys_tau/TauML`.

### Big tuples splitting

In order to be able to uniformly mix tau candidates from various datasets with various pt, eta and ground truth, the big tuples should be splitted into binned files.

For each input dataset run [CreateBinnedTuples](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/bin/CreateBinnedTuples.cxx):
```sh
DS=DY; CreateBinnedTuples --output tuples-v2/$DS --input-dir raw-tuples-v2/crab_$DS --n-threads 12 --pt-bins "20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000" --eta-bins "0., 0.575, 1.15, 1.725, 2.3"
```

Alternatively, you can use python script that iterates over all datasets in the directory:
```sh
python -u TauMLTools/Analysis/python/CreateBinnedTuples.py --input raw-tuples-v2 --output tuples-v2 --n-threads 12
```

Once all datasets are split, the raw files are no longer needed and can be removed to save the disc space.

In the root directory (e.g. `tuples-v2`) txt file with number of tau candidates in each bin should be created:
```sh
python3 -u TauMLTools/Analysis/python/CreateTupleSizeList.py --input /data/tau-ml/tuples-v2/ > /data/tau-ml/tuples-v2/size_list.txt
```

In case you need to update `size_list.txt` (for example you added new dataset), you can specify `--prev-output` to retrieve bin statistics from the previous run of `CreateTupleSizeList.py`:
```sh
python3 -u TauMLTools/Analysis/python/CreateTupleSizeList.py --input /data/tau-ml/tuples-v2/ --prev-output /data/tau-ml/tuples-v2/size_list.txt > size_list_new.txt
mv size_list_new.txt /data/tau-ml/tuples-v2/size_list.txt
```

Each split root file represents a signle bin.
The file naming convention is the following: *tauType*\_pt\_*minPtValue*\_eta\_*minEtaValue*.root, where *tauType* is { e, mu, tau, jet }, *minPtValue* and *minEtaValue* are lower pt and eta edges of the bin.
Please, note that the implementation of the following steps requires that this naming convention is respected, and the code will not function properly otherwise.

### Shuffle and merge

The goal of this step create input root file that contains uniform contribution from all input dataset, tau types, tau pt and tau eta bins in any interval of entries.
It is needed in order to have a smooth gradient descent during the training.

Steps described below are defined in [TauMLTools/Analysis/scripts/prepare_TauTuples.sh](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/scripts/prepare_TauTuples.sh).


#### Training inputs

Due to considerable number of bins (and therefore input files) merging is split into two steps.
1. Inputs from various datasets are merged together for each tau type. How the merging process should proceed is defined in `TauMLTools/Analysis/config/training_inputs_{e,mu,tau,jet}.cfg`.
   For each configuration [ShuffleMerge](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/bin/ShuffleMerge.cxx) is executed. E.g.:
   ```sh
   ShuffleMerge --cfg TauMLTools/Analysis/config/training_inputs_tau.cfg --input tuples-v2 \
                --output output/training_preparation/all/tau_pt_20_eta_0.000.root \
                --pt-bins "20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000" \
                --eta-bins "0., 0.575, 1.15, 1.725, 2.3" --mode MergeAll --calc-weights true --ensure-uniformity true \
                --max-bin-occupancy 500000 --n-threads 12  --disabled-branches "trainingWeight"
   ```
   Once finished, use `CreateTupleSizeList.py` to create `size_list.txt` in `output/training_preparation`.
1. Merge all 4 tau types together. 
   ```sh
   ShuffleMerge --cfg TauMLTools/Analysis/config/training_inputs_step2.cfg --input output/training_preparation \
                --output output/training_preparation/training_tauTuple.root --pt-bins "20, 1000" --eta-bins "0., 2.3" --mode MergeAll \
                --calc-weights false --ensure-uniformity true --max-bin-occupancy 100000000 --n-threads 12
   ```

#### Testing inputs

For testing inputs there is no need to merge different datasets and tau types. Therefore, merging can be done in a single step.
```sh
ShuffleMerge --cfg TauML/Analysis/config/testing_inputs.cfg --input tuples-v2 --output output/training_preparation/testing \
             --pt-bins "20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 225, 250, 275, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000" \
             --eta-bins "0., 0.575, 1.15, 1.725, 2.3" --mode MergePerEntry \
             --calc-weights false --ensure-uniformity false --max-bin-occupancy 20000 \
             --n-threads 12 --disabled-branches "trainingWeight"
```

### Production of flat inputs 

In this stage, `TauTuple`s are transformed into flat [TrainingTuples](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/interface/TrainingTuple.h) that are suitable as an input for the training.

The script to that performs conversion is defined in [TauMLTools/Analysis/scripts/prepare_TrainingTuples.sh](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/scripts/prepare_TrainingTuples.sh).

1. Run [TrainingTupleProducer](https://github.com/cms-tau-pog/TauMLTools/blob/master/Analysis/bin/TrainingTupleProducer.cxx) to produce root files with the flat tuples. In `prepare_TrainingTuples.sh` several instances of `TrainingTupleProducer` are run in parallel specifying `--start-entry` and `--end-entry`.
   ```sh
   TrainingTupleProducer --input /data/tau-ml/tuples-v2-training-v2/training_tauTuple.root --output output/tuples-v2-training-v2-t1-root/training-root/part_0.root
   ```
1. Convert root files into HDF5 format:
   ```sh
   python TauMLTools/Analysis/python/root_to_hdf.py --input output/tuples-v2-training-v2-t1-root/training-root/part_0.root \
                                                    --output output/tuples-v2-training-v2-t1-root/training/part_0.h5 \
                                                    --trees taus,inner_cells,outer_cells
   ```
   
## Training NN

1. The code to read the input grids from the file is implemented in cython in order to provide acceptable I/O performance.
   Cython code should be compiled before starting the training. To do that, you should go to `TauMLTools/Training/python/` directory and run
   ```sh
   python3 _fill_grid_setup.py build
   ```
1. DeepTau v2 training is defined in [TauMLTools/Training/python/2017v2/Training_p6.py](https://github.com/cms-tau-pog/TauMLTools/blob/master/Training/python/2017v2/Training_p6.py). You should modify input path, number of epoch and other parameters according to your needs in [L286](https://github.com/cms-tau-pog/TauMLTools/blob/master/Training/python/2017v2/Training_p6.py#L286) and then run the training in `TauMLTools/Training/python/2017v2` directory:
   ```sh
   python3 Training_p6.py
   ```
1. Once training is finished, the model can be converted to the constant graph suitable for inference:
   ```sh
   python3 TauMLTools/Training/python/deploy_model.py --input MODEL_FILE.hdf5
   ```

## Testing NN performance

1. Apply training for all testing dataset using [TauMLTools/Training/python/apply_training.py](https://github.com/cms-tau-pog/TauMLTools/blob/master/Training/python/apply_training.py):
   ```sh
   python3 TauMLTools/Training/python/apply_training.py --input "TUPLES_DIR" --output "PRED_DIR" \
           --model "MODEL_FILE.pb" --chunk-size 1000 --batch-size 100 --max-queue-size 20
   ```
1. Run [TauMLTools/Training/python/evaluate_performance.py](https://github.com/cms-tau-pog/TauMLTools/blob/master/Training/python/evaluate_performance.py) to produce ROC curves for each testing dataset and tau type:
   ```sh
   python3 TauMLTools/Training/python/evaluate_performance.py --input-taus "INPUT_TRUE_TAUS.h5" \
           --input-other "INPUT_FAKE_TAUS.h5" --other-type FAKE_TAUS_TYPE \
           --deep-results "PRED_DIR" --deep-results-label "RESULTS_LABEL" \
           --prev-deep-results "PREV_PRED_DIR" --prev-deep-results-label "PREV_LABEL" \
           --output "OUTPUT.pdf"
   ```
   Or modify [TauMLTools/Training/scripts/eval_perf.sh](https://github.com/cms-tau-pog/TauMLTools/blob/master/Training/scripts/eval_perf.sh) according to your needs to produce plots for multiple datasets.
