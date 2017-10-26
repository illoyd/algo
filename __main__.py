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

import robinhood
import algo

# Activate logging!
logging.basicConfig(level=logging.DEBUG)

##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args = {}):

  # Sign into Robinhood
  client = robinhood.Client()

  # Get watchlist
  watchlist = client.watchlist()

  # Get historical data for watchlist (only last 15)
  prices = client.historical_prices(*watchlist).iloc[-15:]

  # Calculate the target portfolio weights based on Sharpe
  target_portfolio_weights = calculate_target_portfolio_weights(prices)

  # Convert the target weights into target positions
  capital = (client.equity() * 0.97) + client.margin()
  mid_quotes = client.quotes(*watchlist)
  target_portfolio = calculate_target_portfolio(target_portfolio_weights, mid_quotes, capital)

  # Get the current portfolio
  current_portfolio = client.open_positions()

  # Calculate the necessary movements
  portfolio_delta = target_portfolio.subtract(current_portfolio, fill_value = 0.0).sort_values()
  # TODO: Sort

  # Perform sells

  # Perform buys

  # Boring stuff!
  return portfolio_delta


##
# Calculate the optimal Sharpe portfolio
def calculate_target_portfolio_weights(prices):
  prices = prices.astype(float)
  best_weights, best_sharpe, best_days = None, 0.0, 0
  while len(prices.index) >= 2:
    weights, sharpe = calculate_target_portfolio_weights_inner(prices)
    if sharpe >= best_sharpe:
      best_weights, best_sharpe, best_days = weights, sharpe, len(prices.index)
    prices = prices[1:]

  logging.info('Best days %i', best_days)
  return best_weights

def calculate_target_portfolio_weights_inner(prices):
  # Perform general calculations
  expected_returns = (prices.iloc[-1] / prices.iloc[0]) - 1
  returns = prices.pct_change()
  covariance = returns.cov()

  # Run the tangency optimiser; on failure, return an empty series and a 0 sharpe.
  try:
      w = tangency_portfolio(covariance, expected_returns)
      for asset, weight in w.iteritems():
          w[asset] = round(weight, 2)
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
  shares = capital_weights / mid_quotes

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

