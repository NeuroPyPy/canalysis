# -*- coding: utf-8 -*-

"""
@author: Dr. Patricia Di Lorenzo Laboratory @ Binghamton University
"""
from matplotlib.collections import LineCollection
import Analysis.Func as func
import Analysis.Plots as plot
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
import pandas as pd
import numpy as np
import os
import warnings
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')
warnings.filterwarnings("ignore", category=np.VisibleDeprecationWarning)

# TODO: Add type hints to functions
# TODO: Remove these calls, redirect to different scripts

doStats = 1  # Perform / output statistics.
outputStats = 0  # Output stats to excel file.
doPCA = 0  # Do PCA Analysis
wholeSession = 0  # Plot "lick" graph for whole session.
zoomGraph = 0  # Graph to zoom in on time window.
stimGraph = 0  # All cells around single stimulus.
singlecells = 0  # Individual cells around a single stimulus.
showPlots = 0  # Show graphs in plots tab as they are drawn.
savePlots = 0  # Save plots to parent dir.
ani = 0

animal_id = 'PGT08'
date = '070121'

datadir = '/Users/flynnoconnell/Documents/Work/Data/'
resultsdir = '/Users/flynnoconnell/Documents/Work/Data/results'


# %% Initialization


colors = {
    'ArtSal': 'blue',
    'Citric': 'yellow',
    'Lick': 'darkgray',
    'MSG': 'orange',
    'NaCl': 'green',
    'Quinine': 'red',
    'Rinse': 'lightsteelblue',
    'Sucrose': 'purple'}


traces, events, session = func.get_dir(
    datadir, animal_id, date)


class Neuron(object):
    cell_data = pd.read_csv(traces, low_memory=False)
    event_data = pd.read_csv(events)

    def __init__(self, cell_data, event_data):
        self.cell_data = cell_data
        self.event_data = event_data
        self.warnings = []

        self.neuron = None
        self.signal = None

    @staticmethod
    def events(self, event_data):
        self.lick = []
        self.timestamps = {}
        self.allstim = []

        # Timestamps
        for stimulus in event_data.columns[1:]:
            self.timestamps[stimulus] = list(
                event_data['Time(s)'].iloc[np.where(
                    event_data[stimulus] == 1)[0]])
            if stimulus != 'Lick':
                self.allstim.extend(self.timestamps[stimulus])

        # Drylicks
        self.drylicks = [
            x for x in self.timestamps['Lick'] if x not in self.allstim]

        # Licktime
        self.licktime = event_data['Time(s)'].iloc[
            np.where(event_data['Lick'] == 1)[0]]
        self.licktime = self.licktime.reset_index(drop=True)

        self.trial_times = {}
        for stim, tslist in self.timestamps.items():
            if stim != 'Lick' and\
                    stim != 'Rinse' and\
                    len(self.timestamps[stim]) > 0:

                # Get list of tastant deliveries
                tslist.sort()
                tslist = np.array(tslist)
                times = [tslist[0]]  # First one is a trial
                # Delete duplicates
                for i in range(0, len(tslist) - 1):
                    if tslist[i] == tslist[i + 1]:
                        nxt = tslist[i + 1]
                        tslist = np.delete(tslist, i + 1)
                        print(f"Deleted timestamp {nxt}")
                # Add each tastant delivery preceded by a drylick (trial start).
                for ts in tslist:
                    last_stimtime = tslist[np.where(
                        tslist == ts)[0] - 1]
                    last_drytime = self.drylicks[np.where(
                        self.drylicks < ts)[0][-1]]
                    if last_drytime > last_stimtime:
                        times.append(ts)
                self.trial_times[stim] = times


def main():

    # Nested directories for saving plots.
    animal_dir = os.path.join(resultsdir, animal_id)
    session_dir = os.path.join(animal_dir, date)
    stats_dir = os.path.join(session_dir, 'Stats')

    cell_dir = os.path.join(session_dir, 'Individual Cells')
    tastant_dir = os.path.join(session_dir, 'Tastant Trials')

    # Create parent/session path if not already a directory.
    if not os.path.isdir(resultsdir):
        os.mkdir(resultsdir)
    if not os.path.isdir(animal_dir):
        os.mkdir(animal_dir)
    if not os.path.isdir(session_dir):
        os.mkdir(session_dir)

    # Initialize lists.
    allstats, lickstats, statsummary = [], [], []

    tracedata = func.clean(traces)
    timestamps, allstim, drylicks, licktime, trial_times = func.pop_events(
        events)
    time = np.array(tracedata.iloc[:, 0])

    lickevent = []
    for lick in licktime:
        ind = func.get_matched_time(time, lick)
        match = time[ind]
        lickevent.append(match[0])

    # List of cells for chosing single-cells
    cells = tracedata.columns[1:]
    allcells = [x.replace(' ', '') for i, x in enumerate(cells)]

    # Make dictionary, so we can pull an integer to index the cell later
    cell_index = {x: 0 for x in allcells}
    cell_index.update((key, value) for value, key in enumerate(cell_index))
    cell_names = tracedata.columns.values.tolist()
    cell_names.pop(0)

    lickshade = 1  # How much area after each lick (whole session, (s)).
    zoomshade = .2  # How much area after each lick (zoomed, (s)).

    # Fetch some numbers (cells, time np.array, number of licks)
    nplot = tracedata.shape[1] - 1
    binsize = time[2] - time[1]
    numlicks = len(timestamps['Lick'])
    logger.info(F" Number of licks in this session is {numlicks}.")

    # %% Lick analysis

    lickstats = pd.DataFrame(columns=[
        'File', 'Cell', 'Lick type'])

    # Pull lick data
    start_traces, end_traces, bouts_td_time, bout_dff = func.get_bout(
        licktime, tracedata, time, nplot)
    antibouts_dff, antibouts_td_time = func.get_antibouts(
        tracedata, bouts_td_time, time)
    sponts, stdevs = func.get_sponts(licktime, tracedata, time)

    idxs = np.where(np.diff(licktime) > 30)[0]
    spont_intervs = np.column_stack((licktime[idxs], licktime[idxs + 1]))

    # Calculate stats
    cell_id = np.array(tracedata.columns[1:])
    for index, cell in enumerate(cell_id):
        if (bout_dff[index]) > ((sponts[index]) + ((stdevs[index]) * 2.58)):
            licktype = 'BOUT'
        elif (bout_dff[index]) < ((sponts[index]) - ((stdevs[index]) * 2.58)):
            licktype = 'ANTI-LICK'
        else:
            licktype = 'non-lick'

        lick_dict = {
            'File': session,
            'Cell': cell,
            'Lick cell': licktype}
        lickstats = lickstats.append(
            lick_dict, ignore_index=True)
    lickstats.append(lickstats)

# TODO: Split below functions into separate modules
# # %% Generate graph for entire session
# def wholeSession():
#     fig = plot.line_session(
#         nplot, tracedata, time, timestamps, lickshade, session, numlicks)
#     if savePlots == 1:
#         fig.savefig(session_dir + '/{}_session.png'.format(session),
#                     bbox_inches='tight', dpi=300)
#     if showPlots == 1:
#         plt.show()
#     else:
#         plt.close()
#
#
# # %% Generate graph zoomed to a specific area
# if zoomGraph == 1:
#
#     zoomfig = plot.line_zoom(
#         nplot, tracedata, time, timestamps, session, zoomshade, colors)
#     if savePlots == 1:
#         zoomfig.savefig(
#             session_dir + '/{}_zoomed.png'.format(session),
#             bbox_inches='tight',
#             dpi=300)
#     if showPlots == 1:
#         plt.show()
#     else:
#         plt.close()
#
# # %% Generate graph centered around each stimulus delivery
# if stimGraph == 1:
#
#     fig, stim, trialno = plot.line_stim(
#         nplot, tracedata, time, timestamps, trial_times, session, colors)
#     if savePlots == 1:
#         if not os.path.isdir(tastant_dir):
#             os.mkdir(tastant_dir)
#         fig.savefig(tastant_dir + '/{}_{}_trial{}.png'.format(
#             session, stim, trialno),
#                     bbox_inches='tight',
#                     dpi=300)
#     if showPlots == 1:
#         plt.show()
#     else:
#         plt.close()
#
# # %% Setting cell for individual graphs
# if singlecells == 1:
#     plotcells = plot.plot_cell(allcells, singlecells)
#
# # %% Generate (& output) statistics
# if doStats == 1:
#
#     raw_df = pd.DataFrame(data=None, columns=tracedata.columns)
#     trialStats, summary = func.get_stats(
#         tracedata, trial_times, time, session, raw_df)
#     allstats.append(trialStats)
#     statsummary.append(summary)
#
#     if outputStats == 1:
#         func.output(
#             session, session_date, stats_dir,
#             allstats, statsummary, lickstats, raw_df)
#
# # %% PCA Analysis
# # TODO: Check PCA_explained_var value for each pca_df
# # TODO: Check cell_names for both pca_c and pca_t
#
# if doPCA == 1:
#
#     colors_fill = [
#         'b', 'g', 'r', 'c', 'm', 'y',
#         'k', 'lime', 'darkorange', 'purple',
#         'magenta', 'crimson', 'cyan', 'peru']
#
#     # Initialize input vars and instances
#     pca_c = PCA()
#     pca_t = PCA()
#     pca_df = tracedata.drop('Time(s)', axis=1)
#
#     # Calculate PCA for cell components
#     pca_df_c, labels = plot.get_pca(pca_df, pca_c)
#     pca_df_t = plot.get_pca(pca_df.T, pca_t)
#
#     # PCA transformations / explained varience
#     per_var_c = np.round(
#         pca_c.explained_variance_ratio_ * 100, decimals=1)
#     pca_df_c, per_var, labels_c = plot.pca_cells(
#         pca_df_c, cell_names, per_var_c)
#
#     per_var_t = np.round(
#         pca_t.explained_variance_ratio_ * 100, decimals=1)
#     pca_df_t, perT_var, labels_t = plot.pca_time(
#         pca_df_t, time, cell_names)
#
#     # PCA - Cells as components
#     pca_df_c['colors'] = plot.get_colors(colors_fill, allcells)
#     pca_df_c['Bout'] = bout_dff
#     pca_df_c['Antibout'] = antibouts_dff
#
#     licknolick = []
#     for t in time:
#         tmp = []
#         for bout in bouts_td_time:
#             if bout[0] < t < bout[1]:
#                 licknolick.append(1)
#                 tmp.append(t)
#             else:
#                 continue
#         if not tmp:
#             licknolick.append(0)
#
#     pca_df_t['Licks'] = licknolick
#
#     # Bar Skree------------------
#     plt.figure()
#     plt.bar(x=range(1, len(per_var) + 1), height=per_var, tick_label=labels)
#     plt.ylabel('Variance explained (%)')
#     plt.xlabel('Principal Component')
#     plt.title('{}'.format(session) + '-' + 'Scree plot (Bar)')
#     plt.xticks(range(1, len(per_var) + 1))
#     plt.show()
#
#     # Line Skree------------------
#     plt.figure()
#     plt.plot(labels, per_var, 'o-', linewidth=2, color='blue')
#     plt.title('{}'.format(session) + '-' + 'Scree plot (Line)')
#     plt.ylabel('Variance explained (%)')
#     plt.xlabel('Principal Component')
#     plt.xticks(range(1, len(per_var) + 1))
#     plt.show()
#
#     # 2d scatter------------------
#     plt.figure()
#     plt.scatter(pca_df_c.PC1, pca_df_c.PC2)
#     plt.title('{}'.format(session) + '-' + 'PCA 1 and 2')
#     plt.xlabel('PC1 - {0}%'.format(per_var[0]))
#     plt.ylabel('PC2 - {0}%'.format(per_var[1]))
#     for sample in pca_df_c.index:
#         plt.annotate(
#             sample,
#             (pca_df_c.PC1.loc[sample],
#              pca_df_c.PC2.loc[sample]))
#     plt.show()
#
#     # 3d scatters--------------------
#     fig_pca = plot.scatter(
#         pca_df_c.PC1, pca_df_c.PC2, pca_df_c.PC3,
#         'PC1 - {0}%'.format(per_var[0]),
#         'PC2 - {0}%'.format(per_var[1]),
#         'PC3 - {0}%'.format(per_var[2]))
#
#     fig_bout = plot.scatter(
#         pca_df_c.PC1, pca_df_c.Bout, pca_df_c.Antibout,
#         'PC1 - {0}%'.format(per_var[0]),
#         'Avg. dF/F (Bout)',
#         'Avg. dF/F (Antibout)')
#
#     if ani == 1:
#         fig = plot.scatter_ani(
#             pca_df_c.PC1, pca_df_c.Bout, pca_df_c.Antibout,
#             'PC1 - {0}%'.format(per_var[0]),
#             'Avg. dF/F (Bout)',
#             'Avg. dF/F (Antibout)', pca_df_c)
#
#     pca_df_t['Time'] = time
#     pca_df_t.reset_index(drop=True, inplace=True)
#     x = pca_df_t['PC1'].iloc[0:1202]
#     y = pca_df_t['PC2'].iloc[0:1202]
#     z = pca_df_t['PC3'].iloc[0:1202]
#
#     lines = [((x0, y0), (x1, y1))
#              for x0, y0, x1, y1
#              in zip(x[:-1], y[:-1], x[1:], y[1:])]
#
#     fig = plot.scatter_t(
#         x, y, z,
#         'PC1 - {0}%'.format(per_var[0]),
#         'PC2 - {0}%'.format(per_var[1]),
#         'PC3 - {0}%'.format(per_var[2]))
#
#     fig = plot.scatter_ani(
#         x, y, z,
#         'PC1 - {0}%'.format(per_var[0]),
#         'PC2 - {0}%'.format(per_var[1]),
#         'PC3 - {0}%'.format(per_var[2]))
#
#     # set up colors
#     c = ['r' if a > 0 else 'k' for a in licknolick]
#
#     # convert time series to line segments
#     lines = [((x0, y0), (x1, y1)) for x0, y0, x1, y1 in zip(x[:-1], y[:-1], x[1:], y[1:])]
#     colored_lines = LineCollection(lines, colors=c, linewidths=(.5,))
#     # plt.legend(handles=handles, labels=list(pca_df.index.values),
#     #        loc='best', prop={'size':6}, bbox_to_anchor=(1,1),ncol=1, numpoints=1)
#
#     fig, ax = plt.subplots(1)
#     ax.add_collection(colored_lines)
#     ax.autoscale_view()
#     plt.show()

if __name__ == "__main__":
    main()
