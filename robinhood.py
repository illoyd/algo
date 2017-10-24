import sys
import os
import re
import requests
import json
import apiclient

import numpy as np
import pandas as pd
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import datetime
import dateutil

##
# The Robinhood interface, built from the ground up sadly!
class Client(apiclient.TokenClient):
  def __init__(self, username = None, password = None, account_id = None, token = None, base_endpoint = 'https://api.robinhood.com'):
    super().__init__(token = self.coalesce(token, os.environ.get('ROBINHOOD_TOKEN')), base_endpoint = base_endpoint)

    # Coalesce to environment defaults
    username = self.coalesce(username, os.environ.get('ROBINHOOD_USERNAME'))
    password = self.coalesce(password, os.environ.get('ROBINHOOD_PASSWORD'))
    account_id = self.coalesce(account_id, os.environ.get('ROBINHOOD_ACCOUNTID'))

    # Perform login
    if username and password:
      self.login(username, password)

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
    self.post('api-token-logout')
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
  # Get accounts for this user
  def accounts(self):
    accounts = self.get('accounts', response_class = apiclient.PaginatedResponse)

    # Save the first account ID
    self.account_id = accounts.results()[0]['account_number']

    # Return the account record
    return accounts

  ##
  # Get current portfolio
  # @return A
  def portfolio(self):
    # TODO
    portfolio = self.get(['accounts', self.account_id, 'portfolio'])
    return portfolio

  def positions(self):
    positions = self.get(['accounts', self.account_id, 'positions'])
    return positions

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
