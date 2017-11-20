# Standard library imports
import sys
import numpy as np
import pandas as pd
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

