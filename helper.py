# Standard library imports
import sys
import numpy as np
import pandas as pd
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import re

##
# A symbol look-up table. Not used yet.
symbol_table = {}

##
# Take the first non-None value from a given list
# @args A list of items to compare
# @return The first non-None item in the list, or None otherwise
def coalesce(*args):
  return next((item for item in args if item is not None), None)

def id_for(sz):
  match = re.findall('([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', sz)
  if match:
    return match[-1]
  else:
    return None

##
# Calcalate the annualised Sharpe value for a given set of returns, covariances, and portfolio weights.
# @returns A pandas.Series of expected or actual returns, with the index the symbol
# @covariance A pandas.DataFrame of expected or actual covariance, with the indices being symbols
# @weights A pandas.Series representing the relative weight or fractional holding of the symbol in the portfolio
# @return A float representing the calculated annualized Sharpe value
def annualized_sharpe(returns, covariance, weights):
  portfolio_return = np.sum(returns.mean() * weights) * 252
  portfolio_stddev = np.sqrt( np.dot( weights.T, np.dot(covariance, weights) ) * np.sqrt(252) )
  return portfolio_return / portfolio_stddev

##
# Calculate a tangency portfolio
# TODO See if we can replace with simple matrix algebra
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
