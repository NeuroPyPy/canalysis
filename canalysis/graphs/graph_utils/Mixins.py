#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#_plots.py

Module (graph): .Mixin functions to inherit, plotting functions that use instance attributes from Calcium Data
 class and nothing else.
"""
from __future__ import annotations

import logging
from typing import Optional, Iterable, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from canalysis.graphs.graph_utils import ax_helpers
import seaborn as sns

logger = logging.getLogger(__name__)


class CalPlots:
    tracedata: Any
    doevents: Any
    doeating: Any
    eventdata: Optional[Any]
    eatingdata: Optional[Any]
    signals: pd.DataFrame | pd.Series | np.ndarray | Iterable
    time: np.ndarray | Iterable | int | float | bool
    cells: np.ndarray | pd.Series | Iterable | int | float | bool
    session: str
    trial_times: dict
    timestamps: dict
    color_dict: dict

    def plot_stim(self, save_dir: str = None) -> None:
        if save_dir:
            save_dir = save_dir
        nplot = len(self.signals.columns)
        for stim, times in self.trial_times.items():
            trialno = 0
            for trial in times:
                trialno += 1
                # get only the data within the analysis window
                data_ind = np.where((self.time > trial - 2) & (self.time < trial + 5))[0]
                # index to analysis data
                this_time = self.time[data_ind]

                fig, ax = plt.subplots(nplot, 1, sharex=True)
                for i in range(0, nplot):
                    # Get calcium trace for this analysis window
                    signal = list(self.signals.iloc[data_ind, i])
                    # plot signal
                    ax[i].plot(this_time, signal, "k", linewidth=1)
                    ax[i].get_xaxis().set_visible(False)
                    ax[i].spines["top"].set_visible(False)
                    ax[i].spines["bottom"].set_visible(False)
                    ax[i].spines["right"].set_visible(False)
                    ax[i].set_yticks([])
                    ax[i].set_ylabel(
                        self.signals.columns[i],
                        rotation="horizontal",
                        labelpad=15,
                        y=0.1,
                    )
                    # Add shading.
                    for stimmy in ["Lick", "Rinse", stim]:
                        done = 0
                        timey = self.timestamps[stimmy]
                        for ts in timey:
                            if trial - 1 < ts < trial + 3:
                                if done == 0:
                                    label = stimmy
                                    done = 1
                                else:
                                    label = "_"
                                ax[i].axvspan(
                                    ts,
                                    ts + 0.15,
                                    color=self.color_dict[stimmy],
                                    label=label,
                                    lw=0,
                                )

                # Make the plots act like they know each other.
                fig.subplots_adjust(hspace=0)
                plt.xlabel("Time (s)")
                ax[-1].get_xaxis().set_visible(True)
                ax[-1].spines["bottom"].set_visible(True)
                fig.set_figwidth(4)
                if save_dir:
                    fig.savefig(
                        save_dir + f"/{stim}_{trial}.png",
                        bbox_inches="tight",
                        dpi=600,
                        facecolor="white",
                    )
        return None

    def plot_session(self, lickshade: int = 1, save: bool = False, eatingdata=None) -> None:
        # Set Seaborn style
        sns.set(style="darkgrid")

        # Create a series of plots with a shared x-axis
        fig, ax = plt.subplots(len(self.tracedata.cells), 1, sharex=True)

        for i in range(len(self.tracedata.cells)):
            # Get calcium trace (y axis data)
            signal = list(self.tracedata.signals.iloc[:, i])

            # Plot signal with a contrasting color
            sns.lineplot(x=self.tracedata.time, y=signal, ax=ax[i], color="lime", linewidth=0.5)

            # Set axis and label colors
            ax[i].tick_params(colors="white")
            ax[i].xaxis.label.set_color("white")
            ax[i].yaxis.label.set_color("white")

            # Remove borders
            ax[i].spines["top"].set_visible(False)
            ax[i].spines["bottom"].set_visible(False)
            ax[i].spines["right"].set_visible(False)

            ax[i].set_yticks([])  # No Y ticks
            ax[i].grid(False, which="both", axis="both")

            # Add the cell name as a label for this graph's y-axis
            ax[i].set_ylabel(
                self.tracedata.signals.columns[i],
                rotation="horizontal",
                labelpad=15,
                y=0.1,
                fontweight="bold",
                color="white",
            )

            # Shade in licks
            if self.doevents:
                for lick in self.eventdata.timestamps["Lick"]:
                    label = "_yarp"
                    if lick == self.eventdata.timestamps["Lick"][0]:
                        label = "Licking"
                    ax[i].axvspan(lick, lick + lickshade, color="lightgray", lw=0, label=label)

            if self.doeating:
                for interv in self.eatingdata.raw_eatingdata.reset_index(drop=True).to_numpy():
                    if interv[0] == "Grooming":
                        ax[i].axvspan(interv[1], interv[2], color="cyan", lw=0, label=interv[0])
                    if interv[0] == "EATING":
                        ax[i].axvspan(interv[1], interv[2], color="blue", lw=0, label=interv[0])

            ax[i].yaxis.label.set_fontsize(10)

        fig.subplots_adjust(hspace=0)

        ax[-1].xaxis.label.set_color("white")
        ax[-1].tick_params(colors="white")
        ax[-1].spines["bottom"].set_color("white")

        plt.show()

        if save:
            fig.savefig(
                f"/Users/flynnoconnell/Dropbox/Lab/{self.session}_session.png",
                bbox_inches="tight",
                dpi=1000,
                facecolor="none",
                transparent=True,
            )

        return None

    def plot_zoom(
        self,
        zoomshade: float = 0.4,
        cells="all",
        save: Optional[bool] = True,
        zoombounding=None,
        savename=None,
    ) -> None:
        # Set Seaborn style
        sns.set(style="darkgrid")
        if cells == "all":
            cells_to_plot = self.tracedata.signals.columns.tolist()
        else:
            cells_to_plot = [cell for cell in cells if cell in self.tracedata.signals.columns]

        fig, ax = plt.subplots(len(cells_to_plot), 1, sharex=True, facecolor="black")
        if len(cells_to_plot) == 1:
            ax = [ax]

        if not zoombounding:
            zoombounding = [0, 40]

        for i, cell in enumerate(cells_to_plot):
            signal = self.tracedata.signals[cell]
            # Seaborn lineplot
            sns.lineplot(x=self.tracedata.time, y=signal, ax=ax[i], color="lime", linewidth=0.5)

            # Styling adjustments
            ax[i].tick_params(colors="white")
            ax[i].grid(False, which="both", axis="both")
            ax[i].xaxis.label.set_color("white")
            ax[i].yaxis.label.set_color("white")
            ax[i].spines["top"].set_visible(False)
            ax[i].spines["bottom"].set_visible(False)
            ax[i].spines["right"].set_visible(False)

            ax[i].set_yticks([])
            ax[i].set_ylabel(
                self.tracedata.signals.columns[i],
                rotation="horizontal",
                labelpad=15,
                y=0.1,
                fontweight="bold",
                color="white",
            )

            # Shade in timestamps
            if self.doevents:
                for stim, times in self.eventdata.timestamps.items():
                    if stim != "Rinse":
                        for ts in times:
                            label = "_"  # Keeps label from showing.
                            if ts == times[0]:
                                label = stim
                            ax[i].axvspan(ts, ts + zoomshade, color=self.color_dict[stim], label=label, lw=0)

        fig.subplots_adjust(hspace=0)
        plt.xlabel("Time (s)", color="white")
        ax[-1].xaxis.label.set_color("white")
        ax[-1].tick_params(colors="white")
        ax[-1].spines["bottom"].set_color("white")

        plt.setp(ax, xlim=zoombounding)
        plt.show()

        if save:
            fig.savefig(
                savename,
                bbox_inches="tight",
                dpi=1200,
                facecolor="none",
                transparent=True,
            )
        return None

    def plot_cells(self, save_dir: Optional[bool] = True) -> None:
        cells = self.cells
        if cells is None:
            cells = self.cells

        for cell in cells:
            # Create int used to index a column in tracedata.
            cell_index = {x: 0 for x in cells}
            cell_index.update((key, value) for value, key in enumerate(cell_index))
            currcell = cell_index[cell]
            for stim, times in self.trial_times.items():
                ntrial = len(times)
                minmax = []
                # Max/mins to standardize plots
                for it, tri in enumerate(times):
                    temp_data_ind = np.where((self.time > tri - 2) & (self.time < tri + 5))[0]
                    temp_signal = self.tracedata.iloc[temp_data_ind, currcell + 1]
                    norm_min = min(temp_signal)
                    norm_max = max(temp_signal)
                    minmax.append(norm_min)
                    minmax.append(norm_max)
                stim_min = min(minmax)
                stim_max = max(minmax)
                fig, xaxs = plt.subplots(ntrial, 1, sharex=False, squeeze=False)
                if ntrial < 2:
                    xaxs.flatten()
                for iteration, trial in enumerate(times):
                    i = int(iteration)
                    data_ind = np.where((self.time > trial - 2) & (self.time < trial + 4))[0]
                    this_time = self.time[data_ind]
                    signal = list(self.tracedata.iloc[data_ind, currcell + 1])
                    signal[:] = [number - stim_min for number in signal]
                    l_bound = min(signal)
                    u_bound = max(signal)
                    center = 0
                    xaxs[i, 0].plot(this_time, signal, "k", linewidth=0.8)
                    xaxs[i, 0].tick_params(axis="both", which="minor", labelsize=6)
                    xaxs[i, 0].get_xaxis().set_visible(False)
                    xaxs[i, 0].spines["top"].set_visible(False)
                    xaxs[i, 0].spines["bottom"].set_visible(False)
                    xaxs[i, 0].spines["right"].set_visible(False)
                    xaxs[i, 0].spines["left"].set_bounds((l_bound, stim_max))
                    xaxs[i, 0].set_yticks((0, center, u_bound))
                    xaxs[i, 0].set_ylabel(
                        " Trial {}     ".format(i + 1),
                        rotation="horizontal",
                        labelpad=15,
                        y=0.3,
                    )
                    xaxs[i, 0].set_ylim(bottom=0, top=max(signal))
                    xaxs[i, 0].axhspan(0, 0, color="k", ls=":")
                    # Add shading for licks, rinses  tastant delivery
                    for stimmy in ["Lick", "Rinse", stim]:
                        done = 0
                        timey = self.timestamps[stimmy]
                        for ts in timey:
                            if trial - 1.5 < ts < trial + 5:
                                if done == 0:
                                    label = stimmy
                                    done = 1
                                else:
                                    label = "_"
                                xaxs[i, 0].axvspan(
                                    ts,
                                    ts + 0.15,
                                    color=self.color_dict[stimmy],
                                    label=label,
                                    lw=0,
                                )
                plt.xlabel("Time (s)")
                fig.suptitle("Calcium Traces: {}\n{}: {}".format(cell, self.session, stim), y=1.0)
                fig.set_figwidth(6)
                fig.text(
                    0,
                    -0.03,
                    "Note: Each trace has" "been normalized over the graph window",
                    fontstyle="italic",
                    fontsize="small",
                )
                xaxs[-1, 0].spines["bottom"].set_bounds(False)
                plt.legend(loc=(1.02, 3))
        if save_dir:
            plt.savefig(str(save_dir) + ".png", bbox_inches="tight", dpi=600)
        return None
