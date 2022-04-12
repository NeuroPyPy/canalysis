#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#data.py

Module: Classes for data processing.
"""
from __future__ import annotations
from typing import Type, Optional, Iterable
from dataclasses import dataclass

import pandas as pd
import numpy as np
import logging

from core.draw_plots import Plot
from utils import funcs as func
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

tastant_colors_dict = {k: colors_dict[k] for k in list(colors_dict)[:6]}


@dataclass
class CalciumData(object):
    
    def __init__(self,
                 animal: str,
                 date: str,
                 data_dir: str,
                 pick: Optional[int] = 0,
                 tr_cells: Optional[Iterable] = ''):

        # Session information
        self.animal = animal
        self.date = date
        self.session = animal + '_' + date
        self.data_dir = data_dir

        # Core
        self.tracedata: Type[pd.DataFrame]
        self.eventdata: Type[pd.DataFrame]
        self.new_eventdata: Type[pd.DataFrame]

        self._get_data(pick)
        self._authenticate_input_data(self)
        
        # Core attributes
        self.signals = self._set_trace_signals()
        self.cells = np.array(self.tracedata.columns[1:])
        self.time = self.tracedata['Time(s)']
        self.binsize = self.time[2] - self.time[1]

        self.datasets = {'main': self.tracedata}
        
        # Event attributes
        self.timestamps = {}
        self.trial_times = {}
        self.allstim = []
        self.drylicks = []
        self.licktime: Iterable = None
        self.numlicks: int | None = None
        
        self._set_event_attrs()
        self._alldata()
        
        self.bouttimes = []
        
        self.tastant_colors_dict = tastant_colors_dict

        ## Taste attributes
        self.taste_data: Type[pd.NDframeT] = None
        self.fill_taste_trials()
        
        self.taste_time = self.taste_data['Time(s)']
        self.taste_colors = self.taste_data['colors']
        self.taste_events = self.taste_data['events']
        self.taste_signals = self.taste_data.drop(columns=['Time(s)', 'colors', 'events'])
        self.tastants = tastant_colors_dict.keys()
        
        
        if tr_cells:
            self.tr_data = self.all_taste_trials.filter(items=tr_cells)
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


    def _get_data(self, pick):
       
        traces, events = func.get_dir(
            self.data_dir, self.animal, self.date, pick)
        
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

    def fill_taste_trials(self,
                         traces=None,
                         nontaste: bool = False,
                         store: str = ''
                         ) -> None:
        
        if traces is None:
            
            data = self.tracedata
            data_input = 0
            
        else: 
            
            assert isinstance(traces, pd.DataFrame)
            data = traces
            data_input = 1
            
        time = data['Time(s)']
            
        # Get timestamps of taste - trials only
        stamps = self.timestamps.copy()
        stamps.pop('Lick')
        stamps.pop('Rinse')
        taste_data = pd.DataFrame(columns=self.signals.columns)

        # Populate df with taste trials only
        for event, timestamp in stamps.items():
            taste_interval = func.interval(timestamp)
            for lst in taste_interval:
                sig_time = func.get_matched_time(time, lst)

                sig = (data.loc[(data['Time(s)'] >= sig_time[0])
                                          & (data['Time(s)'] <= sig_time[1]), 'Time(s)'])

                holder = (data.iloc[sig.index])
                holder['events'] = event
                holder['colors'] = tastant_colors_dict[event]
                taste_data = pd.concat([taste_data, holder])

        taste_data.sort_index(inplace=True)
        self.taste_data = taste_data
        
        if store:
            self.datasets[store] = taste_data
            
        if func.has_duplicates(taste_data['Time(s)']):
            taste_data.drop_duplicates(subset=['Time(s)'], inplace=True)
            if not taste_data['Time(s)'].is_unique:
                e.DataFrameError('Duplicate values found and not caught.')
                
        if data_input ==1: 
            logging.info('Taste signals set for input data.')
        else: 
            logging.info('Taste signals set for default data.')
        

    def _set_event_attrs(self):
        
        for stimulus in self.eventdata.columns[1:]:
            self.timestamps[stimulus] = list(
                self.eventdata['Time(s)'].iloc[np.where(
                    self.eventdata[stimulus] == 1)[0]])
            if stimulus != 'Lick':
                self.allstim.extend(self.timestamps[stimulus])
        drylicks = [x for x in self.timestamps['Lick'] if x not in self.allstim]
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
                    last_drytime = drylicks[np.where(
                        drylicks < ts)[0][-1]]
                    if last_drytime > last_stimtime:
                        times.append(ts)
                self.trial_times[stim] = times
        self.drylicks = func.get_matched_time(self.time, drylicks)
               

    def _set_trace_signals(self) -> pd.DataFrame:

        temp = self.tracedata.copy()
        temp.pop('Time(s)')
        self.signals = temp
        return temp
    
    def _alldata(self) -> pd.DataFrame:
        
        eventdata = self.eventdata.copy()
        tracedata = self.tracedata.copy()
        
        eventdata = eventdata[:].iloc[np.where(eventdata['Lick'] == 1)]
        matched_eventtime = func.get_matched_time(self.time, eventdata['Time(s)'])
        
        
        eventdata.pop('Time(s)')
        eventdata.insert(0, 'Time(s)', matched_eventtime)
        # eventdata['Time(s)'] = eventdata['Time(s)'].round(3).astype(float)
        eventdata.set_index('Time(s)', inplace=True)
        
        # tracedata['Time(s)'] = tracedata['Time(s)'].round(3).astype(float)
        tracedata.set_index('Time(s)', inplace=True)
        
        self.licktime = eventdata.index[np.where(eventdata['Lick'] == 1)]
                
        # Lick Bout       
        bout_intervs = list(func.interval(self.licktime))
        
        boutstart, boutend = [], []
        for x in bout_intervs:
            boutstart.append(x[0])
            boutend.append(x[1])
        
        bouts = list(zip(boutstart, boutend))
        
        bouttimes = []
        for index, bout in enumerate(bouts):
            start = bout[0]
            end = bout[1]
            this_bout = self.time[(self.time>=start)&(self.time<=end)]
            
            bouttimes.extend(this_bout)
            
        bouts = pd.Series(index=bouttimes, name='bouts', dtype=int).fillna(1)
        drylicks = pd.Series(index=self.drylicks, name='drylicks', dtype=int).fillna(1)

        self.tracecheck = tracedata
        self.eventcheck = eventdata
        
        # self.alldata = pd.concat([tracedata, eventdata, drylicks, bouts ], axis=1).fillna(0)
        
        return None
                                      
# bouts, drylicks


    def plot_stim(self, my_stim=None):
        Plot.plot_stim(len(self.cells),
                       self.signals,
                       self.time,
                       self.timestamps,
                       self.trial_times,
                       self.session,
                       colors_dict,
                       my_stim=None
                       )

    def plot_session(self):
        Plot.plot_session(self.cells,
                          self.signals,
                          self.time,
                          self.session,
                          self.numlicks,
                          self.timestamps
                          )
