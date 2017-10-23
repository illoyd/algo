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


import apiclient

##
# The Robinhood interface, built from the ground up sadly!
class Robinhood(apiclient.BasicClient):
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

  def post(self, path, params = {}, data = {}, headers = {}):
    # Build path
    path = self.endpoint + path

    # Add default headers
    headers.update(self.default_headers())

    # Request!
    return requests.post(path, data=data, headers=headers)

  ##
  # Perform login to Robinhood, and save the returned token
  # @return Nothing
  def login(self, username, password):
    # Save the username for reference
    self.username = username

    # Sign in
    data = { 'username': self.username, 'password': password }
    response = self.post('/api-token-auth/', data = data)

    # Process response and save
    self.token = response.json()['token']
    pass

  def logout(self):
    self.post('/api-token-logout/')
    self.username, self.token = None, None
    pass

  ##
  # Get quotes
  # @return A pandas dataframe of symbols and prices
  def historical_quotes(self, *symbols_or_ids):

    # If no symbols passed, abort
    if not symbols_or_ids:
      return pd.DataFrame()

    # Query API
    symbol_list = ','.join(symbols_or_ids)
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
  def watchlist(self, name="Default"):
    # Get watchlist
    response = self.get('/watchlists/'+name+'/').json()

    # For every watchlist entry, look up the instrument to get the symbol
    w = [ self.instrument(entry['instrument'])['symbol'] for entry in response['results'] ]
    return w

  ##
  # Get the instrument details
  def instrument(self, symbol_or_id):
    # Extract an ID from a string, if available, and use as the search term
    match = re.match('https://api.robinhood.com/instruments/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?', symbol_or_id)
    if match:
      symbol_or_id = match[1]

    return self.get('/instruments/' + symbol_or_id).json()

  ##
  # Get current portfolio
  # @return A
  def current_portfolio(self):
    # TODO
    portfolio = self.get('/portfolios').json()
    print(portfolio)

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
