#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#data.py

Module: Classes for data processing.
"""
from __future__ import annotations
from typing import Type, Optional, Iterable

import pandas as pd
import numpy as np
import logging

from utils import funcs as func
from utils import draw_plots as plot
from utils import excepts as e

logger = logging.getLogger(__name__)

# %%

colors_dict = {
    'ArtSal': 'dodgerblue',
    'MSG': 'darkorange',
    'NaCl': 'lime',
    'Sucrose': 'magenta',
    'Citric': 'yellow',
    'Quinine': 'red',
    'Rinse': 'lightsteelblue',
    'Lick': 'darkgray'
}

tastant_colors_dict = {k: colors_dict[k] for k in list(colors_dict)[:]}


class Data(object):

    def __init__(self,
                 animal: str,
                 date: str,
                 data_dir: str,
                 tr_cells: Optional[Iterable] = ''):

        # Session information
        self.animal = animal
        self.date = date
        self.session = animal + '_' + date
        self.data_dir = data_dir

        # Core
        self.tracedata: Type[pd.DataFrame]
        self.eventdata: Type[pd.DataFrame]
        self._get_data()
        self._authenticate_input_data(self)

        # Trace attributes
        self.signals = self._set_trace_signals()
        self.cells = np.array(self.tracedata.columns[1:])
        self.time = self.tracedata['Time(s)']
        self.binsize = self.time[2] - self.time[1]

        # Event attributes
        self.timestamps = {}
        self.trial_times = {}
        self.drylicks = []
        self.numlicks: int | None = None
        self._set_event_attrs()

        # Other
        self.tastant_colors_dict = tastant_colors_dict

        ## (Optional) Taste-specific data
        if tr_cells:
            # Getting weird type errors between pd.DataFrame and pd.NDframeT
            # pd.DataFrame is a subclass of NDframeT, so both should be valid, likely just
            # an issue on pandas side. Will raise an issue request.

            self.all_taste_trials: Type[pd.NDframeT]  # All data for taste-trials
            self.tr_colors = None  # Array of which color of tastant was presented
            self._get_taste_trials()

            self.tastants = func.get_unique(  # List of all tastants (not rinse or lick)
                self.all_taste_trials.tastant)
            self.tr_data = self.all_taste_trials.filter(items=tr_cells)  # Data for taste-responsive cells only
            self.tr_cells = self.tr_data.columns
        logging.info('Data instantiated.')

    @staticmethod
    def _authenticate_input_data(self):

        if not isinstance(self.tracedata, pd.DataFrame):
            raise e.DataFrameError('Trace data must be a dataframe')
        if not isinstance(self.eventdata, pd.DataFrame):
            raise e.DataFrameError('Event data must be a dataframe.')
        if not any(x in self.tracedata.columns for x in ['C0', 'C00']):
            raise AttributeError("No cells found in DataFrame")

    def _get_data(self):

        traces, events = func.get_dir(
            self.data_dir, self.animal, self.date)

        self.tracedata = self._clean(traces)
        self.eventdata = events

    @staticmethod
    def _clean(_df) -> pd.DataFrame:

        # When CNMFe is run, we choose cells to "accept", but with manual ROI's every cell is accepted
        # so often that step is skipped. Need some way to check (check_if_accepted)

        def check_if_accepted(_df):
            accepted_col = [col for col in _df.columns if ' accepted' in col]
            return accepted_col
        accept = check_if_accepted(_df)

        if accept:
            accepted = np.where(_df.loc[0, :] == ' accepted')[0]
            _df = _df.iloc[:, np.insert(accepted, 0, 0)]
        _df = _df.drop(0)
        _df = _df.rename(columns={' ': 'Time(s)'})
        _df = _df.astype(float)
        _df = _df.reset_index(drop=True)
        _df.columns = [column.replace(' ', '') for column in _df.columns]
        return _df

    def _get_taste_trials(self) -> None:

        # Get timestamps of taste - trials only
        stamps = self.timestamps.copy()
        stamps.pop('Lick')
        stamps.pop('Rinse')

        taste_signals = pd.DataFrame(columns=self.signals.columns)
        color_signals = pd.DataFrame(columns=self.signals.columns)

        # Populate df with taste trials only
        for event, timestamp in stamps.items():
            taste_interval = func.interval(timestamp)
            for lst in taste_interval:
                sig_time = func.get_matched_time(self.time, *lst)

                sig = (self.tracedata.loc[(self.tracedata['Time(s)'] >= sig_time[0])
                                          & (self.tracedata['Time(s)'] <= sig_time[1]), 'Time(s)'])

                holder = (self.tracedata.iloc[sig.index])
                holder['tastant'] = event
                taste_signals = pd.concat([taste_signals, holder])

                pd.DataFrame(columns=taste_signals.columns)
                hol = (self.tracedata.iloc[sig.index])
                hol['col'] = tastant_colors_dict[event]
                color_signals = pd.concat([color_signals, hol])

        taste_signals.sort_index(inplace=True)
        self.all_taste_trials = taste_signals
        self.tr_colors = color_signals['col']

        if func.has_duplicates(self.all_taste_trials['Time(s)']):
            self.all_taste_trials.drop_duplicates(subset=['Time(s)'], inplace=True)
            if not self.all_taste_trials['Time(s)'].is_unique:
                e.DataFrameError('Duplicate values found and not caught.')

    def _set_event_attrs(self):
        allstim = []
        for stimulus in self.eventdata.columns[1:]:
            self.timestamps[stimulus] = list(
                self.eventdata['Time(s)'].iloc[np.where(
                    self.eventdata[stimulus] == 1)[0]])
            if stimulus != 'Lick':
                allstim.extend(self.timestamps[stimulus])
        self.drylicks = [x for x in self.timestamps['Lick'] if x not in allstim]
        self.numlicks = len(self.timestamps['Lick'])

        for stim, tslist in self.timestamps.items():
            if stim != 'Lick' and stim != 'Rinse' and len(self.timestamps[stim]) > 0:
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

    def _set_trace_signals(self) -> pd.DataFrame:

        temp = self.tracedata.copy()
        temp.pop('Time(s)')
        self.signals = temp
        return temp

    def plot_stim(self):
        plot.plot_stim(len(self.cells),
                       self.signals,
                       self.time,
                       self.timestamps,
                       self.trial_times,
                       self.session,
                       tastant_colors_dict)

    def plot_session(self):
        plot.plot_session(len(self.cells),
                          self.signals,
                          self.time,
                          self.session,
                          self.numlicks,
                          self.eventdata.timestamps)
