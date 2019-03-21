#!/usr/bin/env python

import argparse
parser = argparse.ArgumentParser(description='Apply training and store results.')
parser.add_argument('--input', required=True, type=str, help="Input directory")
parser.add_argument('--filelist', required=False, type=str, default=None, help="Txt file with input tuple list")
parser.add_argument('--output', required=True, type=str, help="Output file")
parser.add_argument('--model', required=True, type=str, help="Model file")
parser.add_argument('--tree', required=False, type=str, default="taus", help="Tree name")
parser.add_argument('--chunk-size', required=False, type=int, default=1000, help="Chunk size")
parser.add_argument('--batch-size', required=False, type=int, default=250, help="Batch size")
parser.add_argument('--max-queue-size', required=False, type=int, default=8, help="Maximal queue size")
parser.add_argument('--max-n-files', required=False, type=int, default=None, help="Maximum number of files to process")
parser.add_argument('--max-n-entries-per-file', required=False, type=int, default=None,
                    help="Maximum number of entries per file")
args = parser.parse_args()

import os
import gc
import pandas
import tensorflow as tf
import numpy as np
from tqdm import tqdm

from common import *
from DataLoader import DataLoader

def Predict(session, graph, X_taus, X_inner, X_outer):
    # for op in graph.get_operations():
    #    print(op.name)
    # raise RuntimeError("stop")

    gr_name_prefix = "deepTau/input_"
    tau_gr = graph.get_tensor_by_name(gr_name_prefix + "tau:0")
    inner_gr = graph.get_tensor_by_name(gr_name_prefix + "inner_cmb:0")
    outer_gr = graph.get_tensor_by_name(gr_name_prefix + "outer_cmb:0")

    y_gr = graph.get_tensor_by_name("deepTau/main_output/Softmax:0")
    N = X_taus.shape[0]
    # if np.any(np.isnan(X_taus)) or np.any(np.isnan(X_cells_pfCand)) or np.any(np.isnan(X_cells_ele)) \
    #     or np.any(np.isnan(X_cells_muon)):
    #     raise RuntimeErrror("Nan in inputs")
    pred = session.run(y_gr, feed_dict={ tau_gr: X_taus, inner_gr: X_inner, outer_gr: X_outer })
    if np.any(np.isnan(pred)):
        raise RuntimeError("NaN in predictions. Total count = {} out of {}".format(np.count_nonzero(np.isnan(pred)), pred.shape))
    if np.any(pred < 0) or np.any(pred > 1):
        raise RuntimeError("Predictions outside [0, 1] range.")
    return pandas.DataFrame(data = {
        'deepId_e': pred[:, e], 'deepId_mu': pred[:, mu], 'deepId_tau': pred[:, tau],
        'deepId_jet': pred[:, jet]
    })

if args.filelist is None:
    if os.path.isdir(args.input):
        file_list = [ f for f in os.listdir(args.input) if f.endswith('.root') or f.endswith('.h5') ]
        prefix = args.input + '/'
    else:
        file_list = [ args.input ]
        prefix = ''
else:
    with open(args.filelist, 'r') as f_list:
        file_list = [ f.strip() for f in f_list if len(f) != 0 ]

if len(file_list) == 0:
    raise RuntimeError("Empty input list")
#if args.max_n_files is not None and args.max_n_files > 0:
#    file_list = file_list[0:args.max_n_files]


graph = load_graph(args.model)
sess = tf.Session(graph=graph)

file_index = 0
for file_name in file_list:
    if args.max_n_files is not None and file_index >= args.max_n_files: break
    full_name = prefix + file_name

    pred_output = args.output + '/' + os.path.splitext(file_name)[0] + '_pred.h5'
    if os.path.isfile(pred_output):
        print('"{}" already present in the output directory.'.format(pred_output))
        continue
        #os.remove(pred_output)
    print("Processing '{}' -> '{}'".format(file_name, os.path.basename(pred_output)))

#    n_entries = GetNumberOfEntries(full_name, args.tree)
#    if args.max_n_entries_per_file is not None:
#        n_entries = min(n_entries, args.max_n_entries_per_file)
#    current_start = 0

    loader = DataLoader(full_name, netConf_full_cmb, args.batch_size, args.chunk_size,
                        max_data_size=args.max_n_entries_per_file, max_queue_size=args.max_queue_size, n_passes = 1)

    with tqdm(total=loader.data_size, unit='taus') as pbar:
        for inputs in loader.generator(return_truth = False, return_weights = False):
            df = Predict(sess, graph, *inputs)
            df.to_hdf(pred_output, args.tree, append=True, complevel=1, complib='zlib')
            pbar.update(df.shape[0])
            del df
            gc.collect()
    file_index += 1

print("All files processed.")
