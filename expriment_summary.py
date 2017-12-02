import torch
import numpy as np
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
from compress_training import DATASETS
from glob import glob

# These attribute are for retro compatibility with
# Experiments that did not have them
DEFAULT_EXTRA_PARAMS = ['compression']

def reject_outliers(sr, iq_range=0.5):
    pcnt = (1 - iq_range) / 2
    qlow, median, qhigh = sr.dropna().quantile([pcnt, 0.50, 1-pcnt])
    iqr = qhigh - qlow
    return sr[ (sr - median).abs() <= iqr]

def summarize_experiment(experiment, extra_params):
    val_acc = experiment[experiment.measure == 'val_acc']
    best_val = val_acc.sort_values(by='value', ascending=False).iloc[0]
    epoch = best_val.epoch
    summary = experiment[experiment.epoch==epoch].groupby('measure').mean()
    keys = list(summary.index) + ['time', 'epoch', 'lambda_start', 'lambda_decay', 'layers', 'iteration', 'algorithm']

    values = list(summary.value) + [float(best_val.time), int(epoch)] + list(extra_params)
    missing_values = len(keys) - len(values) # Computing the number of missin paramters
    # Adding default values for the missing parmaeters
    if missing_values > 0:
        values += DEFAULT_EXTRA_PARAMS[-missing_values:]
    result = pd.DataFrame([values], columns=keys)
    if 'lambda' not in result.columns:
        return None
    return result

def merge_all_experiments(experiments):
    return pd.concat(experiments).fillna(0)

def get_experiments(experiment_name):
    files = glob('./experiments/%s/*.experiment' % experiment_name)
    experiments = [torch.load(x, 'rb') for x in files]
    ids = [x.split('/')[-1].replace('.experiment', '') for x in files]
    return ids, experiments

def get_summary(experiments):
    summarized = [summarize_experiment(x[1], x[0]) for x in experiments]
    summary = merge_all_experiments([x for x in summarized if x is not None])
    # summary['lambda_start'] = np.log10(summary['lambda_start'])
    summary.reset_index(drop=True, inplace=True)
    return summary

def best_experiment(summary, experiments, mode):
    s = summary.sort_values(by='val_acc')
    best = s.iloc[-1]
    return [x for x in experiments if x[1][x[1].measure == 'val_acc'].value.max() == best.val_acc][0]

def plot_experiment(experiment, prefix, mode):
    infos, x = experiment
    capacities = x[x.measure == 'capacity']
    train_acc = x[x.measure == 'mean_train_acc']
    test_acc = x[x.measure == 'test_acc']
    val_acc = x[x.measure == 'val_acc']
    best_val_acc_idx = val_acc.value.argmax()
    best_batch = val_acc.loc[best_val_acc_idx].batch
    best_val_acc = val_acc[val_acc.batch == best_batch].iloc[0].value
    best_test_acc = test_acc[test_acc.batch == best_batch].iloc[0].value
    best_capacity = capacities[capacities.batch == best_batch].iloc[0].value
    fig = plt.figure(figsize=(10, 5))
    a = fig.gca()
    a.grid()
    a.set_xlabel('Time (s)')
    b = a.twinx()
    b.set_yscale('log')
    b.set_ylabel('Capacity in neurons')
    b.plot(capacities.time, capacities.value, label='Total Capacity')
    if mode == 'classification':
        a.set_ylabel('Accuracy (%)')
        a.plot(train_acc.time, train_acc.value * 100, label='Train accuracy')
        a.plot(val_acc.time, val_acc.value * 100, label='Validation accuracy')
        a.plot(test_acc.time, test_acc.value * 100, label='Test accuracy')
        a.yaxis.set_minor_locator(MultipleLocator(0.1))
        a.yaxis.set_major_locator(MultipleLocator(1))
        a.legend(loc='lower left')
    else:
        a.set_ylabel('MSE')
        a.plot(train_acc.time, -train_acc.value, label='Train Error')
        a.plot(val_acc.time, -val_acc.value, label='Validation Error')
        a.plot(test_acc.time, -test_acc.value, label='Test Error')
        a.set_yscale('log')
        a.legend(loc='upper right')
    a.yaxis.grid(b=True, which='major', linestyle='-')
    a.yaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    a.xaxis.grid(b=True, which='major', linestyle='-')
    a.xaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    plt.title('%s - Best Model (%s layer(s), %s neurons, v=%s, t=%s)' % (prefix, infos[2], int(best_capacity), -best_val_acc, -best_test_acc))
    plt.savefig('./plots/%s_compressor_accuracies_size.png' % prefix)
    plt.close()

def plot_algorithm_comparison(summaries, dataset_name, mode='classification', metric='val_acc', first='compression', other='static'):
    cmap_first = 'Greens'
    cmap_second = 'Reds'
    outlier_limit = np.inf
    if dataset_name == 'Add10':
        outlier_limit = 1.3
    elif dataset_name == 'Airfoil':
        outlier_limit = 25
    first_summaries = summaries[np.bitwise_and(summaries.algorithm == first, np.abs(summaries.test_acc) < outlier_limit)]
    second_summaries = summaries[np.bitwise_and(summaries.algorithm == other, np.abs(summaries.test_acc) < outlier_limit)]
    plt.figure()
    if mode == 'classification':
        factor1 = 100
        factor2 = 100
    else:
        factor1 = -1
        factor2 = -1
    if metric != 'val_acc':
        factor1 = 1

    sns.kdeplot(factor1 * first_summaries[metric], factor2 * first_summaries.test_acc, cmap=cmap_first, shade_lowest=False,shade=True, alpha=0.8, label=False)
    sns.kdeplot(factor1 * second_summaries[metric], factor2 * second_summaries.test_acc, cmap=cmap_second, shade_lowest=False,shade=True, alpha=0.5, label=False)
    plt.scatter(factor1 * first_summaries[metric], factor2 * first_summaries.test_acc, alpha=1, color=sns.color_palette(cmap_first)[1], edgecolors='0.3', label=None)
    plt.scatter(factor1 * second_summaries[metric], factor2 * second_summaries.test_acc, alpha=0.5, color=sns.color_palette(cmap_second)[1], edgecolors='0.3', label=None)
    a = plt.gca()
    if mode == 'classification':
        plt.ylabel('Testing accuracy (%)')
        if metric == 'val_acc':
            plt.xlabel('Validation accuracy (%)')
            a.yaxis.set_minor_locator(MultipleLocator(0.1))
            a.yaxis.set_major_locator(MultipleLocator(1))
            a.xaxis.set_minor_locator(MultipleLocator(0.1))
            a.xaxis.set_major_locator(MultipleLocator(1))
        elif metric == 'capacity':
            plt.xlabel('Capacity in neurons')
    else:
        a.yaxis.set_minor_locator(AutoMinorLocator())
        a.xaxis.set_minor_locator(AutoMinorLocator())
        plt.ylabel('Testing MSE')
        if metric == 'val_acc':
            plt.xlabel('Validation MSE')
        elif metric == 'capacity':
            plt.xlabel('Capacity in neurons')

    a.yaxis.grid(b=True, which='major', linestyle='-')
    a.yaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    a.xaxis.grid(b=True, which='major', linestyle='-')
    a.xaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    a.set_axisbelow(True)
    if 'reference' in DATASETS[dataset_name]:
        plt.axhline(abs(factor2) *DATASETS[dataset_name]['reference'], label='Best result for this architecture')
        handles, labels = [list(x) for x in a.get_legend_handles_labels()]
    else:
        handles = []
        labels = []

    first_rectangle = plt.Rectangle((0, 0), 1, 1, color=sns.color_palette(cmap_first)[-3])
    second_rectangle = plt.Rectangle((0, 0), 1, 1, color=sns.color_palette(cmap_second)[-3])
    plt.legend([first_rectangle, second_rectangle] + handles, ['Deterministic Compression Training', 'Classic Training'] + labels)
    plt.gcf().set_size_inches((10, 10))
    if metric == 'val_acc':
        plt.axes().set_aspect('equal', 'datalim')
        plt.title('%s - Algorithm comparision for testing and validation accuracies' % dataset_name)
    else:
        plt.title('%s - Algorithm comparision for testing and capacity' % dataset_name)
    plt.savefig('./plots/%s_test_%s_compression_static_comparison.png' % (dataset_name, metric))
    plt.close()

def plot_dataset(dataset_name, mode='classification'):
    ids, experiments = get_experiments(dataset_name)
    summaries = get_summary(experiments)
    best = best_experiment(summaries, experiments, mode=mode)
    pairs = find_closest_experiments(summaries)
    plot_experiment(best, dataset_name, mode)
    plot_algorithm_comparison(summaries, dataset_name, mode, metric='val_acc')
    plot_algorithm_comparison(summaries, dataset_name, mode, metric='capacity')
    plot_compression_improvements(pairs, dataset_name, mode)

def find_closest_experiments(summaries, first='compression', second='static'):
    first_summaries = summaries[summaries.algorithm == first].sort_values('val_acc', ascending=False).drop_duplicates(['capacity'])
    second_summaries = summaries[summaries.algorithm == second].sort_values('val_acc', ascending=False).drop_duplicates(['capacity'])
    first_cap = first_summaries.capacity
    second_cap = second_summaries.capacity

    result = []
    for i, x in enumerate(first_cap):
        index = np.argmin(np.abs(second_cap.values - x))
        a = first_summaries.iloc[i]
        b = second_summaries.iloc[index]
        result.append((a, b))
    return result

def plot_compression_improvements(pairs, dataset_name, mode='classification'):
    plt.figure(figsize=(10, 5))
    if mode == 'classification':
        factor = 100
    else:
        factor = 1
    plt.scatter([x[0].capacity for x in pairs], [(x[0].test_acc - x[1].test_acc) * factor for x in pairs],
        color='C1', linewidth=1, marker='o', s=100, edgecolor='black')
    a = plt.gca()
    plt.xscale('log')
    plt.title('%s - Improvement in testing accuracy for compress training at fixed capacity' % dataset_name)
    plt.axhline(y=0, color='black', linewidth=3)
    plt.xlabel('Model capacity (neurons)')
    if mode == 'classification':
        plt.ylabel('Absolute MSE delta')
    a.yaxis.set_minor_locator(AutoMinorLocator())
    a.yaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    a.xaxis.grid(b=True, which='minor', alpha=0.4, linestyle='--')
    a.yaxis.grid(b=True, which='major', linestyle='-')
    a.xaxis.grid(b=True, which='major', linestyle='-')
    plt.show()
    plt.savefig('./plots/%s_compression_training_improvements.png' % dataset_name)
    plt.close()


if __name__ == '__main__':
    plot_dataset('MNIST')
    plot_dataset('FashionMNIST')
    plot_dataset('Add10', mode='regression')
    plot_dataset('Airfoil', mode='regression')
    pass