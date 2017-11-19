# Standard library imports
import sys
import numpy as np
import pandas as pd
import tensorflow as tf
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import datetime
import json
import requests
import dateutil
import re
import logging

##
# Sharpe Algo class - for handling the calculations!
class SharpeAlgo(object):

  def optimise(self, prices):
    pass


##
# Machine Learning! oh boy...
class DNNAlgo(object):
  BUY  = 1
  SELL = 0

  PERIODS = [ 3, 5, 7, 10, 12, 15, 30 ]
  FEATURES = [
    "O0", "O1", "H1", "L1", "C1", "V1",
    *[ 'SMA_O0_' + str(n) for n in PERIODS ],
    *[ 'MAX_O0_' + str(n) for n in PERIODS ],
    *[ 'MIN_O0_' + str(n) for n in PERIODS ],
    *[ 'STD_O0_' + str(n) for n in PERIODS ],
    *[ 'SMA_V1_' + str(n) for n in PERIODS ],
    *[ 'MAX_V1_' + str(n) for n in PERIODS ],
    *[ 'MIN_V1_' + str(n) for n in PERIODS ],
    *[ 'STD_V1_' + str(n) for n in PERIODS ],
  ]
  LABEL    = "action"

  def __init__(self, name):
    self.name = name

  def classify(self, inputs):
    results = self.classifier.classify(self._input_fn(inputs, num_epochs=1, shuffle=False))
    logging.info(results)
    return results

  def parse_yahoo(self):
    data = pd.read_csv("./data/" + self.name + ".csv")

    # Re-assign the existing values
    data['O1'] = data['Open'].pct_change()
    data['H1'] = data['High'].pct_change()
    data['L1'] = data['Low'].pct_change()
    data['C1'] = data['Adj Close'].pct_change()
    data['V1'] = data['Volume'].pct_change()

    # Add a T0, which is the opening price of the next forward period
    data['O0'] = data['O1'].shift(-1)

    # Add SMAs
    for n in self.PERIODS:
      rolling = data['O0'].rolling(window=n)
      data['SMA_O0_' + str(n)] = rolling.mean()
      data['MAX_O0_' + str(n)] = rolling.max()
      data['MIN_O0_' + str(n)] = rolling.min()
      data['STD_O0_' + str(n)] = rolling.std()

      rolling = data['V1'].rolling(window=n)
      data['SMA_V1_' + str(n)] = rolling.mean()
      data['MAX_V1_' + str(n)] = rolling.max()
      data['MIN_V1_' + str(n)] = rolling.min()
      data['STD_V1_' + str(n)] = rolling.std()

    # Add action (buy/sell)
    data['action'] = (data['O0'].shift(-1) > data['O0']).astype(int)

    # Save!
    shuffled = data.dropna().sample(frac=1)
    shuffled.index.name = 'Observation'
    count = int(len(shuffled) * 0.8)

    # Training set
    training_filename = "./data/" + self.name + "_train.csv"
    shuffled[:count].to_csv(training_filename)

    # Testing set
    test_filename = "./data/" + self.name + "_test.csv"
    shuffled[count:].to_csv(test_filename)

    return data


  def train(self, training_set = None, test_set = None):

    # Create a training set, if needed
    if not training_set:
      training_set = pd.read_csv("./data/" + self.name + "_train.csv")

    # Create a testing set, if needed
    if not test_set:
      test_set = pd.read_csv("./data/" + self.name + "_test.csv")

    # Configure classifier
    feature_cols = [tf.feature_column.numeric_column(k) for k in self.FEATURES]
    self.classifier = tf.estimator.DNNClassifier(feature_columns=feature_cols,
      hidden_units=[10, 20, 20, 10],
      n_classes=2,
      model_dir="./tmp/" + self.name)

    # Perform training
    self.classifier.train(input_fn=self._input_fn(training_set), steps=5000)

    # Evaluate
    ev = self.classifier.evaluate(input_fn=self._input_fn(test_set, num_epochs=1, shuffle=False))

    # Output
    print("Loss: {0:f}".format(ev["loss"]))
    return ev

  def _input_fn(self, inputs, num_epochs=None, shuffle=True):
    return tf.estimator.inputs.pandas_input_fn(
      x=pd.DataFrame({k: inputs[k].values for k in self.FEATURES}),
      y=pd.Series(inputs[self.LABEL].values),
      num_epochs=num_epochs,
      shuffle=shuffle)
