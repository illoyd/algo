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
import time

import robinhood
import algo

# Activate logging!
logging.basicConfig(level=logging.INFO)

perform_orders = True

##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args = {}):

  # Sign into Robinhood
  client = robinhood.Client()

  # Get universe of symbols
  logging.info('STEP 1: WATCHLIST')
  universe = client.watchlist()
  logging.info('Found %s', ', '.join(universe))

  # Get historical data for universe (only last X days)
  logging.info('STEP 2: PRICES')
  prices = client.historical_prices(*universe).iloc[-20:]
  logging.info('Found prices %s - %s for %s', prices.index[0], prices.index[-1], ", ".join(list(prices.columns)))
  logging.debug(prices)

  # Calculate the target portfolio weights based on Sharpe
  logging.info('STEP 3: TARGET WEIGHTS')
  target_portfolio_weights = calculate_target_portfolio_weights(prices)
  logging.info('Target weights: %s', ', '.join([ '{}: {:0.1f}%'.format(s, w * 100.0) for s, w in target_portfolio_weights.iteritems() ]))
  logging.debug(target_portfolio_weights.round(2))

  # Short circuit if no target portfolio is found!
  if len(target_portfolio_weights) == 0:
    universe = [ 'TLT', 'HYG', 'SPY' ]

    # Get historical data for universe (only last X days)
    logging.info('STEP 2a: RETRY PRICES')
    prices = client.historical_prices(*universe).iloc[-20:-1]
    logging.info('Found prices %s - %s for %s', prices.index[0], prices.index[-1], ", ".join(list(prices.columns)))
    logging.debug(prices)

    # Calculate the target portfolio weights based on Sharpe
    logging.info('STEP 3a: RETRY TARGET WEIGHTS')
    target_portfolio_weights = calculate_target_portfolio_weights(prices)
    logging.info('Target weights: %s', ', '.join([ '{}: {:0.1f}%'.format(s, w * 100.0) for s, w in target_portfolio_weights.iteritems() ]))
    logging.debug(target_portfolio_weights.round(2))

  # Short circuit if no target portfolio is found!
  if len(target_portfolio_weights) == 0:
    return { 'error': 'No optimal portfolio found.' }

  # Determine available captial to play with
  logging.info('STEP 4: CAPITAL')
  capital = (client.equity() * 0.98) + client.margin()
  logging.info('Capital: %s', capital)

  # Get mid quotes
  logging.info('STEP 5: QUOTES')
  mid_quotes = client.quotes(*universe)
  logging.info('Found quotes: %s', ', '.join([ '{}@{:0.4f}'.format(s, q) for s, q in mid_quotes.iteritems() ]))
  logging.debug(mid_quotes)

  # Convert the target weights into target positions
  logging.info('STEP 6: TARGET HOLDINGS')
  target_portfolio = calculate_target_portfolio(target_portfolio_weights, mid_quotes, capital)
  logging.info('Target holdings: %s', portfolio_stringify(target_portfolio))
  logging.debug(target_portfolio)

  # Get the current portfolio
  logging.info('STEP 7: CURRENT HOLDINGS')
  current_portfolio = client.open_positions()
  logging.info('Current holdings: %s', portfolio_stringify(current_portfolio))
  logging.debug(current_portfolio)

  # Calculate the necessary movements
  logging.info('STEP 8: DETERMINE MOVEMENTS')
  portfolio_delta = target_portfolio.subtract(current_portfolio, fill_value = 0.0).sort_values()
  logging.info('Delta: %s', portfolio_stringify(portfolio_delta))
  logging.debug(portfolio_delta)

  # Perform sells
  logging.info('STEP 9: SELL')
  for symbol, delta in portfolio_delta[portfolio_delta < 0].iteritems():
    logging.info('  Selling %s: %s @ %s', symbol, abs(delta), 'market')
    if perform_orders:
      client.sell(symbol, abs(delta))

  # Sleep a bit...
  logging.info('TAKE A BREATH...')
  time.sleep(5)

  # Perform buys
  logging.info('STEP 10: BUY')
  for symbol, delta in portfolio_delta[portfolio_delta > 0].iteritems():
    limit = round( mid_quotes[symbol] * 1.02, 2 )
    logging.info('  Buying %s: %s @ %s', symbol, abs(delta), limit)
    if perform_orders:
      client.buy(symbol, abs(delta), limit)

  # Boring stuff!
  return {
    'current_portfolio': dict(current_portfolio),
    'target_portfolio': dict(target_portfolio),
    'delta': dict(portfolio_delta)
   }


def portfolio_stringify(portfolio):
  return ', '.join([ '{}: {:0.0f}'.format(symbol, quantity) for symbol, quantity in portfolio.iteritems() ])


##
# Calculate the optimal Sharpe portfolio
def calculate_target_portfolio_weights(prices):
  prices = prices.astype(float)
  best_weights, best_sharpe, best_days = None, 0.0, 0

  collected_weights = []

  while len(prices.index) >= 3:
    weights, sharpe = calculate_target_portfolio_weights_inner(prices)
    weights['(SHARPE)'] = sharpe
    weights.name = len(prices.index)
    collected_weights.append(weights)

    if sharpe >= best_sharpe:
      best_weights, best_sharpe, best_days = weights, sharpe, weights.name
    prices = prices[1:]

  logging.debug(pd.concat(collected_weights, axis=1).round(2))
  logging.debug('Best days %i', best_days)

  return best_weights.drop('(SHARPE)')

def calculate_target_portfolio_weights_inner(prices):
  # Perform general calculations
  expected_returns = (prices.iloc[-1] / prices.iloc[0]) - 1
  returns = prices.pct_change()
  covariance = returns.cov()

  # Run the tangency optimiser; on failure, return an empty series and a 0 sharpe.
  try:
      w = tangency_portfolio(covariance, expected_returns)
      return (w, annualized_sharpe(returns, covariance, w))

  except ValueError as e:
      logging.error(e)
      return (pd.Series(), 0.0)

##
# Calcalate the annualised sharpe
def annualized_sharpe(returns, covariance, weights):
  portfolio_return = np.sum(returns.mean() * weights) * 252
  portfolio_stddev = np.sqrt( np.dot( weights.T, np.dot(covariance, weights) ) * np.sqrt(252) )
  return portfolio_return / portfolio_stddev

##
# Calculate the target portfolio units
def calculate_target_portfolio(weights, mid_quotes, capital):
  # Determine portion assigned to each asset
  capital_weights = weights * float(capital)

  # Divide the capital weight of each asset by its mid-quote
  shares = capital_weights.divide(mid_quotes, fill_value = 0.0)

  # Floor the share (no fractional shares here)
  shares = np.floor(shares)

  return shares

##
# Calculate a tangency portfolio
# TODO See if we can replace with simple matrix math
def tangency_portfolio(cov_mat, exp_rets, allow_short=False):
  """
  Computes a tangency portfolio, i.e. a maximum Sharpe ratio portfolio.

  Note: As the Sharpe ratio is not invariant with respect
  to leverage, it is not possible to construct non-trivial
  market neutral tangency portfolios. This is because for
  a positive initial Sharpe ratio the sharpe grows unbound
  with increasing leverage.

  Parameters
  ----------
  cov_mat: pandas.DataFrame
      Covariance matrix of asset returns.
  exp_rets: pandas.Series
      Expected asset returns (often historical returns).
  allow_short: bool, optional
      If 'False' construct a long-only portfolio.
      If 'True' allow shorting, i.e. negative weights.
  Returns
  -------
  weights: pandas.Series
      Optimal asset weights.
  """
  if not isinstance(cov_mat, pd.DataFrame):
      raise ValueError("Covariance matrix is not a DataFrame")

  if not isinstance(exp_rets, pd.Series):
      raise ValueError("Expected returns is not a Series")

  if not cov_mat.index.equals(exp_rets.index):
      raise ValueError("Indices do not match")

  n = len(cov_mat)

  P = opt.matrix(cov_mat.values)
  q = opt.matrix(0.0, (n, 1))

  # Constraints Gx <= h
  if not allow_short:
      # exp_rets*x >= 1 and x >= 0
      G = opt.matrix(np.vstack((-exp_rets.values,
                                -np.identity(n))))
      h = opt.matrix(np.vstack((-1.0,
                                np.zeros((n, 1)))))
  else:
      # exp_rets*x >= 1
      G = opt.matrix(-exp_rets.values).T
      h = opt.matrix(-1.0)

  # Solve
  optsolvers.options['show_progress'] = False
  sol = optsolvers.qp(P, q, G, h)

  # Put weights into a labeled series
  weights = pd.Series(sol['x'], index=cov_mat.index)

  # Log warning on convergence issue
  if sol['status'] != 'optimal':
      logging.warn(weights)
      raise ValueError("Convergence problem")

  # Rescale weights, so that sum(weights) = 1
  weights /= weights.sum()
  return weights

