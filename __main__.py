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

import robinhood

##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args = {}):

  # Sign into Robinhood
  robinhood = robinhood.Client()

  # Get watchlist
  watchlist = robinhood.watchlist()

  # Get historical data for watchlist
  prices = robinhood.historical_quotes(watchlist)

  # Calculate the target portfolio weights based on Sharpe
  target_portfolio_weights = calculate_target_portfolio_weights(prices)

  # Convert the target weights into target positions
  current_capital = robinhood.current_capital()
  target_portfolio = calculate_target_portfolio(target_portfolio_weights, prices, current_capital)

  # Get the current portfolio
  current_portfolio = robinhood.current_portfolio()

  # Calculate the necessary movements
  portfolio_delta = target_portfolio - current_portfolio
  # TODO: Sort

  # Perform sells

  # Perform buys

  # Boring stuff!
  return portfolio_delta


##
# Calculate the optimal Sharpe portfolio
def calculate_target_portfolio_weights(prices):
  return pd.DataFrame()


##
# Calculate the target portfolio units
def calculate_target_portfolio(weights, prices, capital):
  return pd.DataFrame()

