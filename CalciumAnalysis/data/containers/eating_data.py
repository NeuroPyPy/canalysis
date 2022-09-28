#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# eating_data.py

Module: Classes for food-related data processing.
"""

from __future__ import annotations

from operator import index

from utils import funcs
import logging
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from typing import Optional, Generator, Iterable, Any
from data_utils.file_handler import FileHandler
from containers.trace_data import TraceData

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

    def __repr__(self):
        return type(self).__name__

    def __hash__(self, ):
        return hash(repr(self))

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

    def __set_eating_signals(self):
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

    def generate_signals(
        self,
    ) -> Generator[(pd.DataFrame, str), None, None]:
        """Generator for each eating event signal (Interval(baseline), Eating, Grooming, Entry."""
        return ((
            self.get_signal_zscore(x[1], x[2]),
            self.get_signal_time(x[1], x[2]), x[0])
            for x in self.raw_eatingdata.to_numpy())

    def generate_entry_eating_signals(
        self,
    ) -> Generator[Iterable, None, None]:
        """ Generator for eating events, with entry and eating in one interval."""
        data = self.raw_eatingdata.to_numpy()
        counter = 0
        for idx, x in (enumerate(data)):
            counter += 1
            nxt = idx + 1
            nxt2 = idx + 2
            if idx > (len(data) - 2):
                break
            if x[0] == 'Approach' and data[nxt][0] == 'Entry' and data[nxt2][0] == 'Eating':
                # yield: signal, time, counter, approach start, entry start, eating start, eating end
                check1 = x[1]
                check2 = data[nxt2][2]
                check3 = np.round(data[nxt2][2], 2)
                yield (self.get_signal_zscore(x[1], data[nxt2][2]),
                       np.round(self.get_signal_time(x[1], data[nxt2][2]), 1),
                       counter,
                       np.round(x[1], 2),
                       np.round(data[nxt][1], 2),
                       np.round(data[nxt2][1], 2),
                       np.round(data[nxt2][2], 2)
                       )

    def get_eating_df(
        self,
        events: list
    ) -> pd.DataFrame:
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

    def baseline(self):
        data = self.raw_eatingdata.to_numpy()
        baseline = data[np.where(data[:, 0] == 'Interval')[0][0]]
        signal = self.get_signal_zscore(baseline[1], baseline[2])
        return signal

    @staticmethod
    def reorder(signal: pd.DataFrame, start: int, stop: int) -> pd.DataFrame:
        return signal.reindex(signal.loc[[start, stop], :].mean().sort_values(ascending=False).index, axis=1)

    def eating_heatmap(
        self,
        save_dir: Optional[str] = "",
        show: Optional[bool] = False,
        **kwargs
    ) -> Generator[Iterable, None, None]:
        from heatmaps import EatingHeatmap
        for signal, time, counter, approachstart, entrystart, eatingstart, eatingend in \
                self.generate_entry_eating_signals():
            signal = self.reorder(signal, time[time == entrystart].index[0], time[time == eatingend].index[0])
            for cell in signal:
                signal[cell][signal[cell] < 0] = 0
            heatmap = EatingHeatmap(
                    signal.T,
                    title="Approach, Entry and Eating Interval",
                    save_dir=save_dir,
                    **kwargs)

            heatmap.interval_heatmap(eatingstart, entrystart, eatingend)
            yield heatmap.show()

    def get_signals_from_events(self, events: Any) -> tuple[pd.DataFrame, pd.Series]:
        signal = self.eatingdata[self.eatingdata['event'].isin(events)].drop(columns=['event'])
        color = signal.pop('color')
        return signal, color
