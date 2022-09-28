#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# eating_data.py

Module: Classes for food-related data processing.
"""

from __future__ import annotations

from utils import funcs
import logging
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from typing import ClassVar, Optional, Generator, Iterable, Any
from data_utils.file_handler import FileHandler
from containers.trace_data import TraceData
from heatmaps import EatingHeatmap

logger = logging.getLogger(__name__)


@dataclass
class EatingData:
    __filehandler: FileHandler
    __tracedata: TraceData
    color_dict: dict
    adjust: Optional[int] | None = 34
    eatingdata: pd.DataFrame = field(init=False)
    signals: pd.DataFrame = field(init=False)

    def __post_init__(self, ):
        self.raw_eatingdata = self.__filehandler.get_eatingdata().sort_values("TimeStamp")
        # Core attributes
        self.__set_adjust()
        self.__clean()
        self.__match()
        self.eatingdata: pd.DataFrame = self.__set_eating_signals()
        self.signals = self.eatingdata.drop(columns=['event', 'color'])
        self.events: pd.Series = self.eatingdata['event']
        self.colors: pd.Series = self.eatingdata['color']

    def __repr__(self, ):
        return type(self).__name__

    def __hash__(self, ):
        return hash(repr(self))

    def __set_adjust(self, ) -> None:
        for column in self.raw_eatingdata.columns[1:]:
            self.raw_eatingdata[column] = self.raw_eatingdata[column] + self.adjust

    def __clean(self, ) -> None:
        self.raw_eatingdata = self.raw_eatingdata.loc[
            self.raw_eatingdata["Marker Name"].isin(["Entry", "Eating", "Grooming", "Approach", "Interval"])
        ]

    def __match(self, ):
        self.raw_eatingdata['TimeStamp'] = funcs.get_matched_time(
                self.__tracedata.time, self.raw_eatingdata['TimeStamp'])
        self.raw_eatingdata['TimeStamp2'] = funcs.get_matched_time(
                self.__tracedata.time, self.raw_eatingdata['TimeStamp2'])

    def __set_eating_signals(self, ):
        aggregate_eating_signals = pd.DataFrame()
        for signal, _, event in self.generate_signals():
            if event == 'Interval':
                event = 'Doing Nothing'
            signal['event'] = event
            signal['color'] = self.color_dict[event]
            aggregate_eating_signals = pd.concat(
                    [aggregate_eating_signals, signal],
                    axis=0)
        return aggregate_eating_signals.sort_index()

    def get_reorder_cols(self):
        for signal, time, approachstart, entrystart, eatingstart, eatingend in self.generate_entry_eating_signals():
            s = signal.shape[0]
            ss = self.get_largest_interv()
            if signal.shape[0] == self.get_largest_interv():
                newsig = self.reorder(signal, time[time == entrystart].index[0], time[time == eatingend].index[0])
                return list(newsig.columns)

    @staticmethod
    def reorder(signal: pd.DataFrame, start: int, stop: int) -> pd.DataFrame:
        return signal.reindex(signal.loc[[start, stop], :].mean().sort_values(ascending=False).index, axis=1)

    def get_time_index(self, time: int | float, ):
        """Return INDEX where tracedata time matches argument num."""
        return np.where(self.__tracedata.time == time)[0][0]

    def get_signal_zscore(self, start: int | float, stop: int | float, ):
        """Return  where tracedata time matches argument num."""
        return self.__tracedata.zscores.loc[
               self.get_time_index(start):
               self.get_time_index(stop)
               ].drop(columns=['time'])

    def get_signal_time(self, start: int | float, stop: int | float, ):
        """Return  where tracedata time matches argument num."""
        return self.__tracedata.zscores['time'].loc[
               self.get_time_index(start):
               self.get_time_index(stop)]

    def get_signals_from_events(self, events: Any) -> tuple[pd.DataFrame, pd.Series]:
        signal = self.eatingdata[self.eatingdata['event'].isin(events)].drop(columns=['event'])
        color = signal.pop('color')
        return signal, color

    def get_eating_df(self, events: list) -> pd.DataFrame:
        """
        Return a dataframe of eating, grooming and entry events.
        Containes 'events' column.
        """
        df_interval = pd.DataFrame()
        df_grooming = pd.DataFrame()
        for signal, event in self.generate_signals():
            if event == [events]:
                df_grooming = pd.concat([df_grooming, signal], axis=0)
                df_grooming['events'] = 'grooming'
            if event == "Interval":
                df_interval = pd.concat([df_interval, signal], axis=0)
                df_interval['events'] = 'interval'
        return pd.concat([df_interval, df_grooming], axis=0)

    def get_baseline(self) -> np.ndarray:
        data = self.raw_eatingdata.to_numpy()
        baseline = data[np.where(data[:, 0] == 'Interval')[0][0]]
        signal = self.get_signal_zscore(baseline[1], baseline[2])
        return signal

    def get_largest_interv(self) -> int | float:
        tmp = []
        for signal, _, _, _, _, _ in self.generate_entry_eating_signals():
            tmp.append(signal.shape[0])
        return max(tmp)

    def generate_signals(self, ) -> Generator[(pd.DataFrame, str), None, None]:
        """Generator for each eating event signal (Interval(baseline), Eating, Grooming, Entry."""
        return ((
            self.get_signal_zscore(x[1], x[2]),
            self.get_signal_time(x[1], x[2]), x[0])
            for x in self.raw_eatingdata.to_numpy())

    def generate_entry_eating_signals(self, ) -> Generator[Iterable, None, None]:
        """ Generator for eating events, with entry and eating in one interval."""
        data = self.raw_eatingdata.to_numpy()
        for idx, x in (enumerate(data)):
            if idx > (len(data) - 2):
                break
            if x[0] == 'Approach' and data[idx + 1][0] == 'Entry' and data[idx + 2][0] == 'Eating':
                yield (self.get_signal_zscore(x[1], data[idx + 2][2]),  # signal
                       np.round(self.get_signal_time(x[1], data[idx + 2][2]), 1),  # time
                       np.round(x[1], 2),  # approach start
                       np.round(data[idx + 1][1], 2),  # entry start
                       np.round(data[idx + 2][1], 2),  # eating start
                       np.round(data[idx + 2][2], 2))  # eating end

    def generate_eating_heatmap(
        self,
        premask: Optional[bool] = False,
        save_dir: Optional[str] = "",
        interv_size: Optional[str | float] = -np.inf,
        title: Optional[str] = '',
        cols: Optional[bool] = False,
        **figargs
    ) -> Generator[Iterable, None, None]:
        for signal, time, approachstart, entrystart, eatingstart, eatingend in self.generate_entry_eating_signals():
            tsize = (len(signal.T.columns) / 10)
            if tsize > interv_size:
                if cols:
                    reordercols = self.get_reorder_cols()
                    signal = signal[reordercols]
                for cell in signal:
                    signal[cell][signal[cell] < 0] = 0
                signal = signal.T
                signal.columns = np.round(np.arange(0, len(signal.columns) / 10, 0.1), 1)
                newcols = np.round(np.arange(
                        signal.columns[-1] + 0.1,
                        self.get_largest_interv() / 10, 0.1), 1)
                finalsig = pd.concat([signal, pd.DataFrame(columns=newcols, index=signal.index)], axis=1)
                if premask:
                    premask = signal.columns
                    data = finalsig
                else:
                    premask = None
                    data = signal
                heatmap = EatingHeatmap(
                        data,
                        premask=premask,
                        title=title,
                        save_dir=save_dir,
                        **figargs)
                fig = heatmap.default_heatmap(eatingstart, entrystart, eatingend)
                yield fig

    def store_eating_heatmaps(
        self,
        save_dir: Optional[str] = "",
        interv_size: Optional[str | float] = -np.inf,
        title: Optional[str] = '',
        **figargs
    ) -> dict[float: EatingHeatmap]:
        heatmap_holder = {}
        for signal, time, approachstart, entrystart, eatingstart, eatingend in self.generate_entry_eating_signals():
            tsize = (len(signal.T.columns) / 10)
            cols = self.get_reorder_cols()
            if tsize > interv_size:
                signal = signal[cols]
                for cell in signal:
                    signal[cell][signal[cell] < 0] = 0
                signal = signal.T
                signal.columns = np.round(np.arange(0, len(signal.columns) / 10, 0.1), 1)
                large_cols = self.get_largest_interv() / 10
                newcols = np.round(np.arange(signal.columns[-1] + 0.1, large_cols, 0.1), 1)
                missingsig = pd.DataFrame(columns=newcols, index=signal.index)
                finalsig = pd.concat([signal, missingsig], axis=1)
                heatmap = EatingHeatmap(
                        data=finalsig,
                        title=title,
                        save_dir=save_dir,
                        **figargs)
                fig = heatmap.default_heatmap(eatingstart, entrystart, eatingend)
                heatmap_holder[tsize] = fig
        return heatmap_holder
