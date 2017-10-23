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

##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args = {}):

  # Sign into Robinhood
  robinhood = Robinhood()

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


##
# The Robinhood interface, built from the ground up sadly!
class Robinhood(object):
  def __init__(self, username = None, password = None, endpoint = 'https://api.robinhood.com'):
    self.token = None
    self.endpoint = endpoint
    if username:
      self.login(username, password)

  def default_headers(self):
    headers = { 'Accept': 'application/json' }
    if self.token:
      headers['Authorization'] = 'Token ' + self.token
    return headers

  def get(self, path, params = {}, headers = {}):
    # Build path
    path = self.endpoint + path

    # Add default headers
    headers.update(self.default_headers())

    # Request!
    return requests.get(path, params=params, headers=headers)

  def post(self, path, params = {}, headers = {}):
    # Build path
    path = self.endpoint + path

    # Add default headers
    headers.update(self.default_headers())

    # Request!
    return requests.get(path, params=params, headers=headers)

  ##
  # Perform login to Robinhood, and save the returned token
  # @return Nothing
  def login(self, username, password):
    # Prepare sign in
    self.token = None
    pass

  ##
  # Get quotes
  # @return A pandas dataframe of symbols and prices
  def historical_quotes(self, symbols):

    # If no symbols passed, abort
    if not symbols:
      return pd.DataFrame()

    # Query API
    symbol_list = ','.join(symbols)
    response = self.get('/quotes/historicals/', { 'symbols': symbol_list, 'interval': 'day' }).json()

    # Process response
    quotes = []
    for entry in response.get('results', []):
      symbol = entry['symbol']
      prices = list(map(lambda e: float(e['close_price']), entry['historicals']))
      dates = list(map(lambda e: dateutil.parser.parse(e['begins_at']).date(), entry['historicals']))
      s = pd.Series(prices, index=dates, name=symbol)
      quotes.append(s)

    return pd.concat(quotes, axis=1)

  ##
  # Get watchlist
  # @return An array of symbols included in this watchlist
  def watchlist(self, list="Default"):
    # TODO
    w = []
    return w

  ##
  # Get current portfolio
  # @return A
  def current_portfolio(self):
    # TODO
    p = pd.DataFrame()
    return p

  ##
  # Get the current total portfolio size (all assets)
  # @return The dollar value of the asset
  def current_capital(self):
    # TODO
    capital = 0.0
    return capital

  ##
  # Issue a buy order
  # @return Whatever!
  def buy(self, symbol, units):
    # TODO
    r = None
    return r

  ##
  # Issue a sell order
  # @return Whatever!
  def sell(self, symbol, units):
    # TODO
    r = None
    return r
