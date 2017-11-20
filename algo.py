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

import helper


##
# Algo base, for working with signals and other items
class Algo(object):

  def optimise(self):
    return None


##
# Client Algo, which uses a robinhood.Client object
class ClientAlgo(Algo):

  ##
  # Initialise with a client object
  # @client A robinhood.Client object
  def __init__(self, client):
    self.client = client


##
# Client Algo, which uses a robinhood.Client object
class SharpeAlgo(Algo):

  ##
  # Initialise with a client object
  # @client A robinhood.Client object
  def __init__(self, client):
    self.client = client

  ##
  # Get all prices for the given universe
  # @returns A pandas dataframe of prices; vertical axis are dates and horizontal axis are symbols
  def prices(self, universe):
    prices = self.client.historical_prices(*universe).iloc[-self.lookback:]
    logging.info('Found prices %s - %s for %s', prices.index[0], prices.index[-1], ", ".join(list(prices.columns)))
    logging.debug(prices)
    return prices

  def weights(self, prices):
    target_weights = self._calculate_target_weights(prices)
    logging.info('Target weights: %s', ', '.join([ '{}: {:0.1f}%'.format(s, w * 100.0) for s, w in target_weights.iteritems() ]))
    logging.debug(target_weights.round(2))
    return target_weights

  ##
  # Calculate the optimal Sharpe portfolio
  def _calculate_target_weights(self, prices):
    prices = prices.astype(float)
    best_weights, best_sharpe, best_days = None, 0.0, 0

    collected_weights = []

    while len(prices.index) >= 3:
      weights, sharpe = self._calculate_target_weights_inner(prices)
      weights['(SHARPE)'] = sharpe
      weights.name = len(prices.index)
      collected_weights.append(weights)

      if sharpe >= best_sharpe:
        best_weights, best_sharpe, best_days = weights, sharpe, weights.name
      prices = prices[1:]

    logging.debug(pd.concat(collected_weights, axis=1).round(2))
    logging.debug('Best days %i', best_days)

    return best_weights.drop('(SHARPE)')

  def _calculate_target_weights_inner(self, prices):
    # Perform general calculations
    expected_returns = (prices.iloc[-1] / prices.iloc[0]) - 1
    returns = prices.pct_change()
    covariance = returns.cov()

    # Run the tangency optimiser; on failure, return an empty series and a 0 sharpe.
    try:
        w = helper.tangency_portfolio(covariance, expected_returns)
        return (w, helper.annualized_sharpe(returns, covariance, w))

    except ValueError as e:
        logging.error(e)
        return (pd.Series(), 0.0)


##
# Defined-Universe algo - for calculating a Sharpe portfolio for a pre-defined universe.
class UniverseSharpeAlgo(SharpeAlgo):

  ##
  # Create a new defined-universe Sharpe algo
  # @universe An iterable list of symbols representing the universe
  def __init__(self, client, universe, lookback=21):
    super().__init__(client)
    self.universe = universe
    self.lookback = lookback

  def optimise(self):
    u = self.universe
    p = self.prices(u)
    w = self.weights(p)
    return w


##
# Sharpe Algo class - for handling the calculations!
class WatchlistSharpeAlgo(SharpeAlgo):

  ##
  # Initialise with additional parameters for a Sharpe algo
  def __init__(self, client, lookback = 21):
    super().__init__(client)
    self.lookback = lookback

  ##
  # Optimise
  def optimise(self):
    u = self.universe()
    p = self.prices(u)
    w = self.weights(p)
    return w

  ##
  # Get the universe of stocks from the Robinhood Watchlist
  # @returns A list of symbols
  def universe(self):
    universe = self.client.watchlist().symbols()
    logging.info('Found %s', ', '.join(universe))
    return universe


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
