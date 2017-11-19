import sys
import os
import re
import requests
import json

import simpleapi
import resourceful

import numpy as np
import pandas as pd
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import datetime
import dateutil
import logging

import helper

##
# The Robinhood interface, built from the ground up sadly!
class Client(object):
  def __init__(self, username = None, password = None, account_id = None, token = None):

    # Coalesce to environment defaults
    username = helper.coalesce(username, os.environ.get('ROBINHOOD_USERNAME'))
    password = helper.coalesce(password, os.environ.get('ROBINHOOD_PASSWORD'))
    account_id = helper.coalesce(account_id, os.environ.get('ROBINHOOD_ACCOUNTID'))
    token = helper.coalesce(token, os.environ.get('ROBINHOOD_TOKEN'))

    # Set up the instrument cache
    self.instrument_cache = {}

    # Activate the client
    self.api = simpleapi.TokenAPI(
      simpleapi.MemoryCacheAPI(
        simpleapi.API('https://api.robinhood.com/')
      ),
      token = token
    )

    # Perform login
    if (not self.api.token) and username and password:
      self.login(username, password)

    # Add account id
    self.account_id = account_id

  ##
  # Perform login to Robinhood, and save the returned token
  # @return Nothing
  def login(self, username, password):
    logging.info('Logging in as %s', username)

    # Save the username for reference
    self.username = username

    # Sign in
    data = { 'username': self.username, 'password': password }
    response = self.api.post('/api-token-auth/', data = data)

    # Process response and save
    #self.api.token = response.json()['token']
    pass

  def logout(self):
    response = self.api.post('/api-token-logout/')
    self.username, self.api.token = None, None
    pass

  ##
  # Get quotes
  # @return A pandas dataframe of symbols and prices
  def historical_prices(self, *symbols_or_ids):

    # If no symbols passed, abort
    if not symbols_or_ids:
      return pd.DataFrame()

    # Query API
    symbol_list = ','.join([*symbols_or_ids])
    response = self.api.get('/quotes/historicals/', params={ 'symbols': symbol_list, 'interval': 'day' }).json()

    # Process response
    quotes = []
    for entry in response.get('results', []):
      symbol = entry['symbol']
      prices = list(map(lambda e: float(e['close_price']), entry['historicals']))
      dates = list(map(lambda e: dateutil.parser.parse(e['begins_at']).date(), entry['historicals']))
      s = pd.Series(prices, index=dates, name=symbol)
      quotes.append(s)

    return pd.concat(quotes, axis=1)

  @property
  def watchlists(self):
    return Watchlists(self.api)

  ##
  # Get watchlist
  # @return An array of symbols included in this watchlist
  def watchlist(self, name="Default"):

    return Watchlist(self.watchlists, name)

    # Get watchlist
    response = self.api.get(('/watchlists/{}/', name)).json()

    # For every watchlist entry, look up the instrument to get the symbol
    w = [ self.instrument(entry['instrument'])['symbol'] for entry in response['results'] ]
    return w

  def add_to_watchlist(self, name, *symbols_or_ids):
    symbol_list = ','.join([*symbols_or_ids])
    return self.api.post(('/watchlists/{}/bulk_add/', name), data={ 'symbols': symbol_list }).json()

  ##
  # Get the instrument details
  def instrument(self, symbol_or_id):
    # Extract an ID from a string, if available, and use as the search term
    match = re.match('https://api.robinhood.com/instruments/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?', symbol_or_id)
    if match:
      symbol_or_id = match[1]

    # TODO: Turn this into a real cache, but for now...
    if not self.instrument_cache.get(symbol_or_id):
      logging.info('Finding instrument %s', symbol_or_id)
      instrument = self.api.get(('/instruments/{}/', symbol_or_id)).json()
      self.instrument_cache[instrument['symbol']] = instrument
      self.instrument_cache[instrument['id']] = instrument

    return self.instrument_cache[symbol_or_id]

  ##
  # Get accounts for this user
  def accounts(self):
    accounts = Accounts(self.api).list() #self.api.get('accounts')

    # Save the first account ID
    self.account_id = accounts[0]['account_number']

    # Return the accounts list
    return accounts

  ##
  # Get the primary (first?) account
  def account(self):

    # If no account ID, look it up
    if not self.account_id:
      account = Accounts(self.api).list()[0]
      self.account_id = account.id
    else:
      account = Account(Accounts(self.api), self.account_id)
    return account



  ##
  # Get current account portfolio
  # @return A response object of the portfolio
  def portfolio(self):
    return self.api.get(('/accounts/{}/portfolio/', self.account_id)).json()

  ##
  # Get all positions; note that this includes closed positions!
  # @return A list of positions as hashes
  def positions(self):
    return Positions(self.account()).list()

  ##
  # Get all open positions; removes any closed positions from list
  # @return A list of open positions
  def open_positions(self):
    positions = self.positions()
    positions = [ position for position in positions if position.quantity > 0.0 ]
    for position in positions:
      position['symbol'] = self.instrument(position['instrument'])['symbol']
    return pd.Series({ p['symbol']: float(p['quantity']) for p in positions })

  ##
  # Get the current total equity, which is cash + held assets
  # @return Float representing total equity
  # TODO Convert to decimal!
  def equity(self):
    return float(self.portfolio()['equity'])

  ##
  # Get the current total margin, which is the Robinhood Gold limit
  # @return Float representing total margin
  # TODO Convert to decimal!
  # TODO Get from the account object!
  def margin(self):
    return float(6000.0)

  def quotes(self, *symbols_or_ids):
    symbol_list = ','.join([*symbols_or_ids])
    response = self.api.get('/quotes/', params = { 'symbols': symbol_list }).json()
    quotes = [ (float(quote['bid_price']) + float(quote['ask_price'])) / 2.0 for quote in response['results'] ]
    index = [ quote['symbol'] for quote in response['results'] ]
    return pd.Series(quotes, index=index)

  ##
  # Issue a buy order
  # @return Whatever!
  def buy(self, symbol, quantity, price):
    data = {
      'account': self.account_uri(),
      'instrument': self.instrument(symbol)['url'],
      'symbol': symbol,
      'type': 'limit',
      'price': price,
      'time_in_force': 'gfd',
      'trigger': 'immediate',
      'quantity': abs(quantity),
      'side': 'buy'
    }
    return self.api.post('/orders/', data=data)

  ##
  # Issue a sell order
  # @return Whatever!
  def sell(self, symbol, quantity):
    data = {
      'account': self.account_uri(),
      'instrument': self.instrument(symbol)['url'],
      'symbol': symbol,
      'type': 'market',
      'time_in_force': 'gfd',
      'trigger': 'immediate',
      'quantity': abs(quantity),
      'side': 'sell'
    }
    return self.api.post('/orders/', data=data)

  def account_uri(self):
    # TODO FIx this!
    return 'https://api.robinhood.com/accounts/' + self.account_id + '/'

  @property
  def orders(self):
    return Orders(self.api)

  @property
  def markets(self):
    return Markets(self.api)

  @property
  def nyse_market(self):
    return Market(self.markets, 'XNYS')

  def are_markets_open(self, date = None):
    return self.nyse_market.is_open(date)


class Account(resourceful.Instance):
  ID_FIELD = 'account_number'

  def positions(self):
    return Positions(self)


class Accounts(resourceful.Collection):
  ENDPOINT = 'accounts/'
  INSTANCE_CLASS = Account

  def list(self):
    return super().list(Account)

  def account(self, id):
    return Account(self, id)


class Position(resourceful.Instance):
  ID_FIELD = 'id'

  @property
  def quantity(self):
    return float(self['quantity'])

  @property
  def is_open(self):
    return self.quantity > 0.0


class Positions(resourceful.Collection):
  ENDPOINT = 'positions/'
  INSTANCE_CLASS = Position


class Order(resourceful.Instance):
  ID_FIELD = 'id'


class Orders(resourceful.Collection):
  ENDPOINT = 'orders/'
  INSTANCE_CLASS = Order


class Instrument(resourceful.Instance):
  ID_FIELD = 'id'

  @property
  def symbol(self):
    return self['symbol']

  def __repr__(self):
    return self._to_repr(id = self.id, symbol = self.symbol)


class Instruments(resourceful.Collection):
  ENDPOINT = 'instruments/'
  INSTANCE_CLASS = Instrument


class Market(resourceful.Instance):
  ID_FIELD = 'mic'

  def hours(self, date = None):
    date = date or datetime.datetime.now()
    year, month, day = date.year, date.month, date.day
    uri = ('hours/{}-{}-{}/', year, month, day)
    return resourceful.Response(self.get(uri))

  def is_open(self, date = None):
    return self.hours(date)['is_open']


class Markets(resourceful.Collection):
  ENDPOINT = 'markets/'
  INSTANCE_CLASS = Market


class WatchlistInstrument(resourceful.Instance):
  ID_FIELD = 'instrument'


class Watchlist(resourceful.Collection):
  INSTANCE_CLASS = WatchlistInstrument

  def add(self, id_or_symbol):
    id = helper.parse_instrument_id(id_or_symbol)
    if id:
      return add_instrument(id)
    else:
      return add_symbols(id_or_symbol)

  def remove(self, id_or_symbol):
    id = helper.parse_instrument_id(id_or_symbol)
    if id:
      return remove_instrument(id)
    else:
      return remove_symbol(id_or_symbol)

  def add_symbols(self, *symbols):
    symbol_list = ','.join([*symbols])
    return self.post('bulk_add/', data={ 'symbols': symbol_list })

  def remove_symbol(self, symbol):
    # For every symbol, find its instrument ID and delete
    instrument_id = helper.symbol_table.get(symbol)
    if not instrument_id:
      instrument_id = Instrument(self.get('/instrument', params = { 'symbol': symbol } )).id
    return remove_instrument(instrument_id)

  def add_instrument(self, instrument_id):
    return self.post(instrument_id)

  def remove_instrument(self, instrument_id):
    return self.delete(instrument_id)


class Watchlists(resourceful.Collection):
  ENDPOINT = 'watchlists/'
  INSTANCE_CLASS = Watchlist
