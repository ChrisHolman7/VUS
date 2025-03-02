import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib import cm
import pandas as pd
from tqdm import tqdm as tqdm
import time
from sklearn.preprocessing import MinMaxScaler
from multiprocessing import Pool
import pickle

import os
import sys
module_path = os.path.abspath(os.path.join('../..'))
if module_path not in sys.path:
    sys.path.append(module_path)

from src.utils.slidingWindows import find_length
from src.utils.metrics import metricor

from src.models.distance import Fourier
from src.models.feature import Window
from src.models.cnn import cnn
from src.models.AE_mlp2 import AE_MLP2
from src.models.lstm import lstm
from src.models.ocsvm import OCSVM
from src.models.poly import POLY
from src.models.pca import PCA
from src.models.norma import NORMA
from src.models.matrix_profile import MatrixProfile
from src.models.lof import LOF
from src.models.iforest import IForest

from src.analysis.score_computation import generate_data,compute_score
from src.analysis.robustness_eval import compute_anomaly_acc_pairwise,normalize_dict_exp,group_dict,box_plot,generate_curve





def normalize_dict_exp_pair(methods_acc_lag,methods_keys):
	key_metrics = [
		'VUS_ROC',
		'VUS_PR',
		'R_AUC_ROC',
		'R_AUC_PR',
		'AUC_ROC',
		'AUC_PR',
		'Rprecision',
		'Rrecall',
		'RF',
		'Precision',
		'Recall',
		'F',
		'Precision@k'
	][::-1]
	
	norm_methods_acc_lag = {}
	for key in methods_keys:
		norm_methods_acc_lag[key] = {}
		for key_metric in key_metrics:
			ts = list(methods_acc_lag[key][key_metric])
			new_ts = list(np.array(ts))
			norm_methods_acc_lag[key][key_metric] = new_ts
	return norm_methods_acc_lag




def box_plot(data, edge_color, fill_color):
	bp = ax.boxplot(data, patch_artist=True)
	
	for element in ['boxes', 'whiskers', 'fliers', 'means', 'medians', 'caps']:
		plt.setp(bp[element], color=edge_color)

	for patch in bp['boxes']:
		patch.set(facecolor=fill_color)       
		
	return bp



def generate_box_plot_pair(group_methods_acc_random_pair_norma_CNN,names,show_labels=False):

	colors = ['green','red']
	for i,key in enumerate(group_methods_acc_random_pair_norma_CNN.keys()):
		#plt.subplot(1,2,1+i)    
		if i == 1:
			pos = 0.40
		else:
			pos = -0.40
		labels, data = [*zip(*group_methods_acc_random_pair_norma_CNN[key].items())]  # 'transpose' items to parallel key, value lists
		position = [val*2+pos for val in list(range(1,len(labels)+1))]
		bp = plt.boxplot(data,showfliers=False,positions=position,patch_artist=True, widths=0.8)
		for element in ['boxes', 'whiskers', 'fliers', 'means', 'medians', 'caps']:
			plt.setp(bp[element], color='black')
		for patch in bp['boxes']:
			patch.set(facecolor=colors[i])
		for vl in np.array(list(range(1, len(labels) + 1)))*2:
			plt.axvline(vl - 1,0,1,linestyle='dotted',color='black')
	plt.xlim(1,(np.array(list(range(1, len(labels) + 1)))*2)[-1]+1)
	plt.ylim(0,1.01)
	plt.ylabel('Metric')
	if show_labels:
		plt.xticks(np.array(list(range(1, len(labels) + 1)))*2, labels, rotation=90)
	else:
		plt.xticks([])
	plt.title('in green: {} (accurate detection) \n vs in red: {} (inaccurate detection)'.format(names[0],names[1]))

def compute_z_test(group_methods_acc_random_pair_norma_CNN,method_name):
	Z_tests = {}
	for key in group_methods_acc_random_pair_norma_CNN[method_name[0]].keys():
		method_1_mean = np.mean(group_methods_acc_random_pair_norma_CNN[method_name[0]][key])
		method_1_std = np.std(group_methods_acc_random_pair_norma_CNN[method_name[0]][key])

		method_2_mean = np.mean(group_methods_acc_random_pair_norma_CNN[method_name[1]][key])
		method_2_std = np.std(group_methods_acc_random_pair_norma_CNN[method_name[1]][key])
		Z_tests[key] = (method_1_mean - method_2_mean)/np.sqrt(method_1_std**2 + method_2_std**2)
	return Z_tests

def compute_mean_dict_test(list_dict):
	new_dict = {}
	for key in list_dict[0].keys():
		list_val = []
		for dict_s in list_dict:
			list_val.append(dict_s[key])
		new_dict[key] = np.mean(list_val)
	return new_dict

def multi_run_wrapper(args):
   return compute_anomaly_acc_pairwise(*args)

def main():

	filepaths = [
		'../../data/MBA_ECG805_data.out',
		'../../data/MBA_ECG820_data.out',
	]

	methods = [
		'NormA',
		'POLY',
		'IForest',
		'AE',
		'OCSVM',
		'MatrixProfile',
		'LOF',
		'LSTM',
		'CNN',
	]

	filepath = filepaths[0]
	max_length = 10000


	all_glob_list_z_test = []

	for filepath in filepaths:
		_,slidingWindow,data,X_data,data_train,data_test,X_train,X_test,label = generate_data(filepath,0,max_length)
		methods_scores =  compute_score(methods,slidingWindow,data,X_data,data_train,data_test,X_train,X_test)
		
		list_params = [
			(methods_scores,label,slidingWindow,"NormA","CNN"),
			(methods_scores,label,slidingWindow,"NormA","LSTM"),
			(methods_scores,label,slidingWindow,"IForest","CNN"),
			(methods_scores,label,slidingWindow,"IForest","LSTM"),
			(methods_scores,label,slidingWindow,"NormA","MatrixProfile"),
			(methods_scores,label,slidingWindow,"NormA","LOF"),
			(methods_scores,label,slidingWindow,"AE","CNN"),
			(methods_scores,label,slidingWindow,"AE","LSTM"),
			(methods_scores,label,slidingWindow,"OCSVM","CNN"),
			(methods_scores,label,slidingWindow,"OCSVM","LSTM"),
			(methods_scores,label,slidingWindow,"AE","MatrixProfile"),
			(methods_scores,label,slidingWindow,"AE","LOF"),
		]


		with Pool(processes=8) as pool:
			results = pool.map(multi_run_wrapper,list_params)

		methods_acc_random_pair_norma_CNN 	= results[0]
		methods_acc_random_pair_norma_LSTM 	= results[1]
		methods_acc_random_pair_IF_CNN 		= results[2]
		methods_acc_random_pair_IF_LSTM 	= results[3]
		methods_acc_random_pair_norma_MP 	= results[4]
		methods_acc_random_pair_norma_LOF 	= results[5]
		methods_acc_random_pair_AE_CNN 		= results[6]
		methods_acc_random_pair_AE_LSTM 	= results[7]
		methods_acc_random_pair_OCSVM_CNN 	= results[8]
		methods_acc_random_pair_OCSVM_LSTM 	= results[9]
		methods_acc_random_pair_AE_MP 		= results[10]
		methods_acc_random_pair_AE_LOF 		= results[11]
		

	
		group_methods_acc_random_pair_norma_CNN 	= normalize_dict_exp_pair(methods_acc_random_pair_norma_CNN,methods_keys=["NormA","CNN"])
		group_methods_acc_random_pair_norma_LSTM 	= normalize_dict_exp_pair(methods_acc_random_pair_norma_LSTM,methods_keys=["NormA","LSTM"])
		group_methods_acc_random_pair_norma_MP 		= normalize_dict_exp_pair(methods_acc_random_pair_norma_MP,methods_keys=["NormA","MatrixProfile"])
		group_methods_acc_random_pair_norma_LOF 	= normalize_dict_exp_pair(methods_acc_random_pair_norma_LOF,methods_keys=["NormA","LOF"])

		group_methods_acc_random_pair_IF_CNN 		= normalize_dict_exp_pair(methods_acc_random_pair_IF_CNN,methods_keys=["IForest","CNN"])
		group_methods_acc_random_pair_IF_LSTM 		= normalize_dict_exp_pair(methods_acc_random_pair_IF_LSTM,methods_keys=["IForest","LSTM"])

		group_methods_acc_random_pair_AE_CNN 		= normalize_dict_exp_pair(methods_acc_random_pair_AE_CNN,methods_keys=["AE","CNN"])
		group_methods_acc_random_pair_AE_LSTM 		= normalize_dict_exp_pair(methods_acc_random_pair_AE_LSTM,methods_keys=["AE","LSTM"])
		group_methods_acc_random_pair_AE_MP 		= normalize_dict_exp_pair(methods_acc_random_pair_AE_MP,methods_keys=["AE","MatrixProfile"])
		group_methods_acc_random_pair_AE_LOF 		= normalize_dict_exp_pair(methods_acc_random_pair_AE_LOF,methods_keys=["AE","LOF"])

		group_methods_acc_random_pair_OCSVM_CNN 	= normalize_dict_exp_pair(methods_acc_random_pair_OCSVM_CNN,methods_keys=["OCSVM","CNN"])
		group_methods_acc_random_pair_OCSVM_LSTM 	= normalize_dict_exp_pair(methods_acc_random_pair_OCSVM_LSTM,methods_keys=["OCSVM","LSTM"])


	


		all_res = [
			(group_methods_acc_random_pair_norma_CNN,["NormA","CNN"]),
			(group_methods_acc_random_pair_norma_LSTM,["NormA","LSTM"]),
			(group_methods_acc_random_pair_norma_MP,["NormA","MatrixProfile"]),
			(group_methods_acc_random_pair_norma_LOF,["NormA","LOF"]),
			(group_methods_acc_random_pair_IF_CNN,["IForest","CNN"]),
			(group_methods_acc_random_pair_IF_LSTM,["IForest","LSTM"]),
			(group_methods_acc_random_pair_AE_CNN,["AE","CNN"]),
			(group_methods_acc_random_pair_AE_LSTM,["AE","LSTM"]),
			(group_methods_acc_random_pair_AE_MP,["AE","MatrixProfile"]),
			(group_methods_acc_random_pair_AE_LOF,["AE","LOF"]),
			(group_methods_acc_random_pair_OCSVM_CNN,["OCSVM","CNN"]),
			(group_methods_acc_random_pair_OCSVM_LSTM,["OCSVM","LSTM"]),
		]

		list_z_test = []
		
		for dict_res,method_name in all_res:
			list_z_test.append(compute_z_test(dict_res,method_name=method_name))

		all_glob_list_z_test += list_z_test
		z_test_total = compute_mean_dict_test(list_z_test)

		with open('../../results/separability_results/{}_z_test.pickle'.format(filepath.split('/')[-1]), 'wb') as fp:
			pickle.dump(z_test_total, fp)
		

		plt.rcParams.update({'font.size': 22})

		
		methods_to_plot = [
			('NormA','darkgreen'),
			('IForest','darkgreen'),
			('AE','darkgreen'),
			('OCSVM','darkgreen'),
			('MatrixProfile','darkred'),
			('LOF','darkred'),
			('LSTM','darkred'),
			('CNN','darkred'),
		]

		nb_sub_row = len(methods_to_plot)+1
		plt.figure(figsize=(10,30))
		plt.subplot(nb_sub_row,1,1)
		plt.title(filepath.split('/')[-1].strip('.out'))
		plt.plot(data,color='darkblue')
		plotted = False
		for index_pos,lb in enumerate(label):
			if lb == 1:
				if not plotted:
					plotted = True
					plt.plot([int(index_pos+sub_index) for sub_index in range(slidingWindow)],data[int(index_pos):int(index_pos)+int(slidingWindow)],color='darkred')
			else:
				if plotted:
					plotted = False
		plt.xlim(0,max_length)

		for id_key,key_method in enumerate(methods_to_plot):
			plt.subplot(nb_sub_row,1,2+id_key)
			plt.title(key_method[0])
			plt.plot(methods_scores[key_method[0]],color=key_method[1])
			plt.xlim(0,max_length)
		plt.tight_layout()
		plt.savefig('results_figures/{}_anomalyscore_ts.png'.format(filepath.split('/')[-1]),format='png')
		plt.close()

		plt.figure(figsize=(30,5))
		plt.grid()
		plt.bar(z_test_total.keys(), z_test_total.values(), width=0.5, color='grey',edgecolor='black',alpha=1)
		plt.title('Z-test averaged on 12 pair of good vs bad methods')
		plt.ylabel('Z-test')
		plt.ylim(0,max(z_test_total.values()) + 0.2*max(z_test_total.values()))
		xlocs, xlabs = plt.xticks()
		for i, v in enumerate(z_test_total.values()):
			plt.text(xlocs[i] - 0.125, v + 1, "{:.2f}".format(v))
		plt.xticks(rotation=0)
		
		plt.tight_layout()
		plt.savefig('results_figures/{}_aggregated.pdf'.format(filepath.split('/')[-1]),format='pdf')
		plt.close()


		nb_sub_row = 6
		plt.figure(figsize=(20,30))
		plt.subplot(nb_sub_row,2,1)
		generate_box_plot_pair(group_methods_acc_random_pair_norma_CNN,names=['NormA','CNN'])
		plt.subplot(nb_sub_row,2,3)
		generate_box_plot_pair(group_methods_acc_random_pair_norma_LSTM,names=['NormA','LSTM'])
		plt.subplot(nb_sub_row,2,5)
		generate_box_plot_pair(group_methods_acc_random_pair_IF_CNN,names=['IForest','CNN'])
		plt.subplot(nb_sub_row,2,7)
		generate_box_plot_pair(group_methods_acc_random_pair_IF_LSTM,names=['IForest','LSTM'])
		
		plt.subplot(nb_sub_row,2,9)
		generate_box_plot_pair(group_methods_acc_random_pair_norma_MP,names=['NormA','MatrixProfile'])
		plt.subplot(nb_sub_row,2,11)
		generate_box_plot_pair(group_methods_acc_random_pair_norma_LOF,names=['NormA','LOF'])
		


		plt.subplot(nb_sub_row,2,2)
		generate_box_plot_pair(group_methods_acc_random_pair_AE_CNN,names=['AE','CNN'])
		plt.subplot(nb_sub_row,2,4)
		generate_box_plot_pair(group_methods_acc_random_pair_AE_LSTM,names=['AE','LSTM'])
		plt.subplot(nb_sub_row,2,6)
		generate_box_plot_pair(group_methods_acc_random_pair_OCSVM_CNN,names=['OCSVM','CNN'])
		plt.subplot(nb_sub_row,2,8)
		generate_box_plot_pair(group_methods_acc_random_pair_OCSVM_LSTM,names=['OCSVM','LSTM'])

		plt.subplot(nb_sub_row,2,10)
		generate_box_plot_pair(group_methods_acc_random_pair_AE_MP,names=['AE','MatrixProfile'])
		plt.subplot(nb_sub_row,2,12)
		generate_box_plot_pair(group_methods_acc_random_pair_AE_LOF,names=['AE','LOF'])
		

		plt.tight_layout()

		plt.savefig('results_figures/{}.pdf'.format(filepath.split('/')[-1]),format='pdf')
		plt.close()

	
	z_test_total = compute_mean_dict_test(all_glob_list_z_test)
	plt.rcParams.update({'font.size': 32})
	plt.figure(figsize=(60,7))
	plt.grid()
	plt.bar(z_test_total.keys(), z_test_total.values(), width=0.5, color='grey',edgecolor='black',alpha=1)
	plt.title('Z-test averaged on 36 pair of good vs bad methods over 3 datasets')
	plt.ylabel('Z-test')
	plt.ylim(0,max(z_test_total.values()) + 0.2*max(z_test_total.values()))
	xlocs, xlabs = plt.xticks()
	for i, v in enumerate(z_test_total.values()):
		plt.text(xlocs[i] - 0.125, v + 1, "{:.2f}".format(v))
	plt.xticks(rotation=0)
	plt.tight_layout()
	plt.savefig('results_figures/{}_aggregated_total_MBA.pdf'.format(filepath.split('/')[-1]),format='pdf')
	plt.close()

if __name__ == '__main__':
	main()