#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
# models.py

Module (models): Classes/functions for NeuralNetwork module training.
"""

from __future__ import division

from typing import Optional, Iterable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
import pandas as pd
import logging

from sklearn import preprocessing
from sklearn.svm import (
    SVC,
    LinearSVC)

from sklearn.model_selection import (
    StratifiedShuffleSplit,
    ShuffleSplit,
    GridSearchCV,
    train_test_split
)

from sklearn.metrics import (
    accuracy_score,
    recall_score,
    f1_score,
    classification_report
    )

from graphs import draw_plots
from models.tracking import ModelTracker, Stage
logger = logging.getLogger(__name__)


# %%

class Stage(Enum):
    TRAIN = auto()
    TEST = auto()
    EVAL = auto()


    
class DataHandler(object):
    """
    Class to check that features and targets have the same length, with a getter for each sample that also
    includes the target for that sample.
    
    Give instance of DataHandler() to GridSearchCV. 
    """
    
    def __init(self, data, target):
        self.data = data.reset_index(drop=True)
        self.target = target.reset_index(drop=True)
        assert self.data.shape[0] == self.target.shape

    def __getitem__(self, x):
        return self.data[x], self.target[x]


class SVM(ModelTracker):
    def __init__(self):
        self.encoder = preprocessing.OrdinalEncoder()
        self.state = ModelTracker.encoder(self, 'unfit')
        self.model = None
        self.grid = None
        
    def validate_shape(self, x, y):
        assert x.shape[0] == y.shape[0]
        
        

class Train(SVM):
    
    def __init__(self, data: Iterable[float], targets: Iterable[str], **params):
        
        self.encoder = super().encoder
            
        self.data = data.reset_index(drop=True) 
        self.targets = targets  
        super().validate_shape(data, targets)
        

    @staticmethod
    def split(X: np.ndarray,
              y: np.ndarray,
              train_size: float = 0.9,
              test_size: float = None,
              n_splits=1,
              stratify=True,
              **splitparams
          ):

        if stratify:
            stratify = y

        shuffle_split = StratifiedShuffleSplit(
            n_splits=n_splits,
            train_size=train_size,
            **splitparams
        )
        logging.info('train_test_split completed')

        train_index, test_index = next(shuffle_split.split(X, y))
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y[train_index], y[test_index]

        return X_train, X_test, y_train, y_test

class EvalSVM(object):
    
    def __init__(self, X: Iterable[Any], Y: Iterable[Any], **params):

        self.scaler = preprocessing.StandardScaler()
        self.encoder = preprocessing.LabelEncoder()

        ## Training Data ---------------------------

        self.X: np.ndarray = X.reset_index(drop=True) # samples / features, 1darray
        self.Y = Y  

        # Encode/Decode y
        self.encoder.fit(self.Yt)
        self.Y = self.encoder.transform(self.Yt)
        self.Y = self.encoder.transform(self.ye)

        ## Helpers ---------------------------------

        self.grid = None


    def train(self,
               train_size: float = 0.9,
               test_size: float = None,
               random_state: int = None,
               stratify=None,
               **cv_params,
               ):

        X = self.X
        y = self.y

        if train_size:
            assert train_size > 0.6
        if test_size:
            assert test_size < 0.5
        if train_size and test_size:
            assert train_size + test_size == 1
        if stratify:
            stratify = y

        if not self.cv:
            self.cv = StratifiedShuffleSplit(train_size=train_size, test_size=test_size, random_state=random_state)
            logging.info('train_test_split completed with sklearn.train_test_split')
        else:
            cv = self.cv(**cv_params)

        # Scale everything to only the training data's fit
        self.scaler.fit(self.X_train)
        self.scaler.transform(self.X_train)
        self.scaler.transform(self.X_test)
        self.scaler.transform(self.X2)

    def _get_classifier(self,
                        cv=None,
                        kernel=None,
                        c_range=None,
                        gamma_range=None,
                        **params):
        """
        Return SVM classifier built from training data.
    
        Args:
            train_x (Iterable) : Features.
            train_y (Iterable) : Targets
            kernel (str): Function type for computing SVM().
                -'linear' (Default)
                -'rbf'
            c_range (list): Values of C parameter to run GridSearchCV.
            gamme_range (list):  Values of gamma parameter to run GridSearchCV.
            params (str): Instance of data for different session.

        Returns:
            SCV classifier.

        """
        from sklearn.pipeline import Pipeline
        scalar = preprocessing.StandardScaler()
        svc = SVC()
        pipe = Pipeline([('scalar', scalar), ('svc', svc)])

        if not params:
            param_grid = {
                'kernel': ('linear', 'rbf','poly'),
                'svc__C': [0.1, 1, 10, 100, 150, 200, 500, 1000, 2000, 5000, 10000],
                'svc__gamma': ['scale', 'auto'],
                'svc__kernel': ['linear', 'rbf', 'poly'],
                'epsilon':[0.1,0.2,0.5,0.3]
            }

        if 'cv':
            cv = cv
        else:
            cv = StratifiedShuffleSplit(n_splits=2, test_size=0.2, random_state=42)

        X_train, _, y_train, _ = self._split(self.X, self.y)

        self.grid = GridSearchCV(pipe, param_grid=param_grid, cv=cv, verbose=True)
        self.grid.fit(X_train, y_train)

        # Store training results 
        self.summary['param_grid'] = param_grid
        self.summary['Best score - Train'] = self.grid.best_score_
        # self.summary['kernel'] = self.grid.best_params_['kernel']
        self.summary['C'] = self.grid.best_params_['svc__C']
        self.summary['gamma'] = self.grid.best_params_['svc__gamma']
        self.summary['kernel'] = self.grid.best_params_['svc__kernel']

        print('**', '-' * 20, '*', '-' * 20, '**')
        print(f"Best params: {self.grid.best_params_}")
        print(f"Score: {self.grid.best_score_}")
        kernel = self.grid.best_params_['svc__kernel']
        c_best = self.grid.best_params_['svc__C']
        gamma_best = self.grid.best_params_['svc__gamma']

        clf = SVC(C=c_best, kernel=kernel, gamma=gamma_best, verbose=False)

        return clf

    def fit(self,
            params: Optional[str] = '',
            learning_curve: bool = False,
            **kwargs
            ) -> object:

        if 'mat' in kwargs:
            mat = kwargs['mat']
        else:
            mat = True

        x_train = self.X_train
        y_train = self.y_train

        #### Get / Fit Model ####

        self.model = self._get_classifier(self, x_train, y_train)
        self.model.fit(self.X_train, self.y_train)

        y_pred = self.model.predict(self.X_test)

        self.train_scores = Scoring(y_pred, self.y_test, self.classes,
                                    descriptor='train', mat=mat, metrics=True)

        self.summary['train_scores'] = self.train_scores
        self.summary['train_acc'] = self.train_scores.accuracy

        return None

    def validate(self, **kwargs):

        y_pred = self.model.predict(self.X2)
        if 'mat' in kwargs:
            mat = kwargs['mat']
        else:
            mat = True

        self.eval_scores = Scoring(y_pred, self.y2, self.classes, descriptor='eval', mat=mat, metrics=True)

        self.summary['eval_scores'] = self.eval_scores
        self.summary['Best score - test'] = self.eval_scores.accuracy

        return None


    def get_learning_curves(self,
                            estimator,
                            cv=None,
                            title: str = ''):

        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(3, 2, figsize=(10, 15))

        X = self.X
        y = self.y

        # Cross validation with 50 iterations to get smoother mean test and train
        # score curves, each time with 20% data randomly selected as a validation set.
        title = "Learning Curves (LinearSVC"
        estimator = estimator

        
        Plot.plot_learning_curve(
            title, X, y, axes=axes[:, 0], ylim=(0, 1.01), cv=cv
        )

        kern = self.grid.best_params_['svc__kernel']
        gam = self.grid.best_params_['svc__gamma']
        C = self.grid.best_params_['svc__C']

        title = (f'SVC - kernel = {kern}, gamma = {gam}, C = {C}')
        if cv:
            cv = cv
        else:
            # SVC is more expensive so decrease number of CV iterations:
            cv = ShuffleSplit(n_splits=50, test_size=0.2, random_state=0)

        estimator = estimator
        plot_learning_curve(
            title, X, y, axes=axes[:, 1], ylim=(0, 1.01), cv=cv
        )

        plt.show()


@dataclass
class Scoring(object):

    def __init__(self,
                 pred,
                 true,
                 classes,
                 descriptor: Optional[str] = '',
                 mat: bool = False,
                 metrics: bool = False
                 ):

        # Input variables
        self.results = {}

        self.predicted = pred
        self.true = true
        self.classes = classes
        self.results['descriptor'] = descriptor

        # Report variables
        self.clf_report = self.get_report()

        if mat:
            self.mat = self.get_confusion_matrix()

        if metrics:
            self.get_metrics()

        if descriptor is None:
            logging.info('No descriptor')
            pass

    def get_report(self) -> pd.DataFrame:

        if self.descriptor:
            assert self.descriptor in ['train', 'test', 'eval']

        report = classification_report(
            self.true,
            self.predicted,
            target_names=self.classes,
            output_dict=True
        )
        report = pd.DataFrame(data=report).transpose()

        return report

    def get_metrics(self):

        self.results['accuracy'] = accuracy_score(self.true, self.predicted)
        self.results['recall'] = recall_score(self.true, self.predicted, average='micro')
        self.results['f1'] = f1_score(self.true, self.predicted, average='micro')

    def get_confusion_matrix(self, caption: Optional[str] = '') -> object:

        mat = draw_plots.Plot.confusion_matrix(
            self.true,
            self.predicted,
            labels=self.classes,
            caption=caption)

        return mat


if __name__ == "__main__":
    pass