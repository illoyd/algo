# Standard library imports
import sys
import numpy as np
import pandas as pd
# import tensorflow as tf
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import datetime
import json
import requests
import dateutil
import re
import logging
import itertools

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
  def __init__(self, client, lookback = 21, min_lookback = 7):
    self.client = client
    self.lookback = lookback
    self.min_lookback = min_lookback

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

    while len(prices.index) >= self.min_lookback:
      weights, sharpe = self._calculate_target_weights_inner(prices)
      weights['(SHARPE)'] = sharpe
      weights.name = len(prices.index)
      collected_weights.append(weights)

      if sharpe >= best_sharpe:
        best_weights, best_sharpe, best_days = weights, sharpe, weights.name
      prices = prices[1:]

    logging.debug(pd.concat(collected_weights, axis=1).round(2))
    logging.info('Best days %i', best_days)

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
  def __init__(self, client, universe, lookback = 21, min_lookback = 9):
    super().__init__(client, lookback, min_lookback)
    self.universe = universe

  def optimise(self):
    u = self.universe
    p = self.prices(u)
    w = self.weights(p)
    return w


##
# Sharpe Algo class - for handling the calculations!
class WatchlistSharpeAlgo(SharpeAlgo):

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

def filename_for(kind, name):
  return "./data/%s/%s.csv" % ( kind, name, )

def source_filename_for(symbol):
  return filename_for('', symbol)

def training_filename_for(symbol):
  return filename_for('training', symbol)

def test_filename_for(symbol):
  return filename_for('test', symbol)

def data_for(kind, name):
  filename = filename_for(kind, name)
  return pd.read_csv(filename, index_col = 0)

def source_data_for(name):
  return data_for('', name)

def training_data_for(name):
  return data_for('training', name)

def test_data_for(name):
  return data_for('test', name)


##
# Machine Learning! oh boy...
# class DNNAlgo(object):
#   BUY  = 1
#   SELL = 0
#
#   LOOKBACK = 30
#   MEASURES   = [ 'O', 'H', 'L', 'C', 'A', 'V' ]
#   LOOKBACKS  = list(range(1, LOOKBACK+1))
#   TRANSFORMS = [ 'SMA', 'MAX', 'MIN', 'STD' ]
#   PERIODS    = [ 3, 5, 7, 10, 12, 15, 30 ]
#
#   FEATURES = [
#     '%s%i_%s%i' % (t, p, m, l) for (t, p, m, l) in itertools.product( TRANSFORMS, PERIODS, MEASURES, LOOKBACKS )
#   ]
#   LABEL    = "action"
#
#   def __init__(self, name = 'TSLA'):
#     self.name = name
#
#   def classify(self, inputs):
#     results = self.classifier.classify(self._input_fn(inputs, num_epochs=1, shuffle=False))
#     logging.info(results)
#     return results
#
#   def train(self, training_set = None, test_set = None):
#
#     # Create a training set, if needed
#     if not training_set:
#       training_set = training_data_for(self.name)
#
#     # Create a testing set, if needed
#     if not test_set:
#       test_set = test_data_for(self.name)
#
#     # Configure classifier
#     feature_cols = [tf.feature_column.numeric_column(k) for k in self.FEATURES]
#     self.classifier = tf.estimator.DNNClassifier(feature_columns=feature_cols,
#       hidden_units=[1024, 512, 258],
#       n_classes=2,
#       model_dir="./tmp/" + self.name)
#
#     # Perform training
#     self.classifier.train(input_fn=self._input_fn(training_set), steps=5000)
#
#     # Evaluate
#     ev = self.classifier.evaluate(input_fn=self._input_fn(test_set, num_epochs=1, shuffle=False))
#
#     # Output
#     print("Loss: {0:f}".format(ev["loss"]))
#     return ev
#
#   def _input_fn(self, inputs, num_epochs=None, shuffle=True):
#     return tf.estimator.inputs.pandas_input_fn(
#       x=pd.DataFrame({k: inputs[k].values for k in self.FEATURES}),
#       y=pd.Series(inputs[self.LABEL].values),
#       num_epochs=num_epochs,
#       shuffle=shuffle)
#
#
# def parse_yahoo(name):
#
#   # Read data from source and convert to percent changes
#   data = source_data_for(name)
#
#   data = data.pct_change()
#
#   # Prepare an empty list to hold the results
#   outputs = []
#
#   # For every lookback window...
#   for lookback in DNNAlgo.LOOKBACKS:
#     # Shift the data for this lookback
#     lookback_data = data.shift(lookback - 1)
#
#     tmp = pd.DataFrame()
#
#     # Add key values
#     tmp['O%i' % (lookback,)] = lookback_data['Open']
#     tmp['H%i' % (lookback,)] = lookback_data['High']
#     tmp['L%i' % (lookback,)] = lookback_data['Low']
#     tmp['C%i' % (lookback,)] = lookback_data['Close']
#     tmp['A%i' % (lookback,)] = lookback_data['Adj Close']
#     tmp['V%i' % (lookback,)] = lookback_data['Volume']
#
#     # Calculate measures over a rolling window
#     columns = list(tmp.columns.values)
#     for period in DNNAlgo.PERIODS:
#       for column in columns:
#         rolling = tmp[column].rolling(window=period)
#         tmp['SMA%i_%s' % (period, column)] = rolling.mean()
#         tmp['MAX%i_%s' % (period, column)] = rolling.max()
#         tmp['MIN%i_%s' % (period, column)] = rolling.min()
#         tmp['STD%i_%s' % (period, column)] = rolling.std()
#
#     outputs.append(tmp)
#
#   outputs = pd.DataFrame().join(outputs, how='outer')
#
#   # Determine action
#   outputs['action'] = (data['Open'].shift(-1) > data['Open']).astype(int)
#
#   # Clean NAs
#   outputs = outputs.dropna()
#
#   # Save!
#   shuffled = outputs.sample(frac=1).round(6)
#   shuffled.index.name = 'Date'
#   count = int(len(shuffled) * 0.8)
#
#   # Training set
#   training_filename = training_filename_for(name)
#   shuffled[:count].to_csv(training_filename)
#
#   # Testing set
#   test_filename = test_filename_for(name)
#   shuffled[count:].to_csv(test_filename)
#
#   return outputs