import os
import re
import requests
import pandas as pd
import datetime
import dateutil
import logging
from collections import deque

import simpleapi
import resourceful
import helper


##
# Base class for exceptions in this module
class Error(Exception):

    def __init__(self, original: Exception = None, *args: object) -> None:
        super().__init__(*args)
        self.original = original


##
# Base order error class
class OrderError(Error):

    def __init__(self, message: str, *args: object):
        super().__init__(*args)
        self.message = message


##
class TooManySharesError(OrderError):

    def __init__(self, symbol: str, quantity: float, *args: object):
        super().__init__(*args)
        self.symbol = symbol
        self.quantity = float(quantity)


class BuyingTooManySharesError(TooManySharesError):
    pass


##
class SellingTooManySharesError(TooManySharesError):
    pass


##
# The Robinhood interface, built from the ground up sadly!
class Client(object):
    def __init__(self, username=None, password=None, account_id=None, token=None):

        self.username = None

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
            token=token
        )

        # Perform login
        if (not self.is_logged_in()) and username and password:
            self.login(username, password)

        # Add account id
        self.account_id = account_id

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.is_logged_in():
            self.logout()

    ##
    # Perform login to Robinhood, and save the returned token
    # @return Nothing
    def login(self, username, password):
        logging.info('Logging in as %s', username)

        # Save the username for reference
        self.username = username

        # Sign in
        data = {'username': self.username, 'password': password}
        response = self.api.post('/api-token-auth/', data=data)

        # Process response and save
        # self.api.token = response.json()['token']
        pass

    def logout(self):
        self.username, self.api.token = None, None
        pass

    def is_logged_in(self):
        return bool(self.api.token)

    ##
    # Get accounts associated with this user.
    # @returns An Accounts collection.
    @property
    def accounts(self):
        return Accounts(self.api)

    ##
    # Get an identified account, defaulting to the first account if no ID given.
    # @returns An Account resource.
    def account(self, account_id=None):

        # If given an account ID, or if defined on this Client, return an account resource
        if account_id or self.account_id:
            account = self.accounts.account(account_id or self.account_id)

        # Otherwise, look up the default account, save the ID, and return the resource
        else:
            account = self.accounts.default
            self.account_id = account.id

        return account

    @property
    def equity(self) -> float:
        """Get the current total equity, which is cash + held assets

        :return: a float representing the value of cash and held assets
        """
        return float(self.portfolio()['equity'])

    ##
    # Get the current total margin, which is the Robinhood Gold limit
    # @return Float representing total margin
    @property
    def margin(self):
        return float(self.account()['margin_balances']['margin_limit'])

    ##
    # Get quotes
    # @return A pandas dataframe of symbols and prices
    def historical_prices(self, *symbols_or_ids):

        # If no symbols passed, abort
        if not symbols_or_ids:
            return pd.DataFrame()

        # Query API
        symbol_list = ','.join([*symbols_or_ids])
        response = self.api.get('/quotes/historicals/', params={'symbols': symbol_list, 'interval': 'day'}).json()

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
        return Watchlist(self.watchlists, name + '/')

    ##
    # Get the instrument details
    def instrument(self, symbol_or_id):
        # Extract an ID from a string, if available, and use as the search term
        match = helper.id_for(symbol_or_id)
        if match:
            symbol_or_id = match

        # TODO: Turn this into a real cache, but for now...
        if not self.instrument_cache.get(symbol_or_id):
            logging.info('Finding instrument %s', symbol_or_id)
            if helper.id_for(symbol_or_id):
                instrument = self.api.get(('/instruments/{}/', symbol_or_id)).json()
            else:
                instrument = self.api.get('/instruments/', params={'symbol': symbol_or_id}).json()['results'][0]

            self.instrument_cache[instrument['symbol']] = instrument
            self.instrument_cache[instrument['id']] = instrument

        return self.instrument_cache[symbol_or_id]

    ##
    # Get current account portfolio
    # @return A response object of the portfolio
    def portfolio(self):
        return self.account().portfolio

    ##
    # Get all positions; note that this includes closed positions!
    # @return A list of positions as hashes
    def positions(self):
        return self.account().positions

    ##
    # Get all open positions; removes any closed positions from list
    # @return A list of open positions
    def open_positions(self):
        positions = self.positions()
        positions = [position for position in positions if position.quantity > 0.0]
        for position in positions:
            position['symbol'] = self.instrument(position['instrument'])['symbol']
        return pd.Series({p['symbol']: float(p['quantity']) for p in positions})

    def quotes(self, *symbols_or_ids):
        symbol_list = ','.join([*symbols_or_ids])
        response = self.api.get('/quotes/', params={'symbols': symbol_list}).json()
        quotes = [(float(quote['bid_price']) + float(quote['ask_price'])) / 2.0 for quote in response['results']]
        index = [quote['symbol'] for quote in response['results']]
        return pd.Series(quotes, index=index)

    ##
    # Issue a buy order
    # @return Whatever!
    def buy(self, symbol, quantity, price):
        response = self._buy(symbol, quantity, price)

        # If not successful...
        if response.status_code != requests.codes.ok:
            # Check if buying too many shares
            search = re.search('[Yy]ou can only purchase (\d+) shares', response.text)
            if search:
                raise BuyingTooManySharesError(response.text, symbol, search.group(1))

            # Otherwise, raise general error message
            else:
                raise OrderError(response.text)

        return response

    def _buy(self, symbol, quantity, price):
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

    def are_markets_open(self, date=None):
        return self.nyse_market.is_open(date)


##
# Generic Order
class Order(object):
    def __init__(self, symbol, quantity, limit=None, stop=None):
        self.symbol = symbol
        self.quantity = quantity
        self.limit = limit
        self.stop = stop


##
# A buy order
class BuyOrder(Order):
    pass


##
# A sell order
class SellOrder(Order):
    pass


##
# The Order Manager class, for managing the buying and selling orders of an account.
class OrderManager(object):

    def __init__(self, client):
        self.client = client
        self.orders = deque()

    def add(self, order):
        self.orders.append(order)

    def buy(self, symbol, quantity, limit=None):
        self.add(BuyOrder(symbol, quantity, limit=limit))

    def sell(self, symbol, quantity, stop=None):
        self.add(SellOrder(symbol, quantity, stop=stop))

    def execute(self):
        while self.orders:
            order = self.orders.popleft()
            self._execute_order(order)

    def _execute_order(self, order):
        logging.info('  %s %s: %s @ %s', self._humanize_order(order), order.symbol, abs(order.quantity),
                     (order.limit or order.stop or 'market'))
        try:
            if isinstance(order, BuyOrder):
                response = self.client.buy(order.symbol, order.quantity, order.limit)
            elif isinstance(order, SellOrder):
                response = self.client.sell(order.symbol, order.quantity)

        except BuyingTooManySharesError as error:
            logging.warning('    May only buy %s shares of %s', error.quantity, error.symbol)
            self.buy(order.symbol, error.quantity, order.limit)

        except SellingTooManySharesError as error:
            logging.warning('    May only sell %s shares of %s', error.quantity, error.symbol)
            self.sell(order.symbol, error.quantity, order.stop)

        except OrderError as error:
            logging.error('Unexpected order error: %s', error.message)

        else:
            logging.info('    Ok! Order is %s', response.json()['state'])

    def _humanize_order(self, order):
        if isinstance(order, BuyOrder):
            return "Buying"
        elif isinstance(order, SellOrder):
            return "Selling"
        return str(order)


class Account(resourceful.Instance):
    ID_FIELD = 'account_number'

    @property
    def positions(self):
        return Positions(self)

    @property
    def portfolio(self):
        return Portfolio(self, 'portfolio')


##
# Account collections
class Accounts(resourceful.Collection):
    ENDPOINT = 'accounts/'
    INSTANCE_CLASS = Account

    def account(self, account_id):
        return Account(self, account_id)

    @property
    def default(self):
        return self[0]


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
        return self._to_repr(id=self.id, symbol=self.symbol)


class Instruments(resourceful.Collection):
    ENDPOINT = 'instruments/'
    INSTANCE_CLASS = Instrument


class Market(resourceful.Instance):
    ID_FIELD = 'mic'

    def hours(self, date=None):
        date = date or datetime.datetime.now()
        year, month, day = date.year, date.month, date.day
        uri = ('hours/{}-{}-{}/', year, month, day)
        return resourceful.Response(self.get(uri))

    def is_open(self, date=None):
        return self.hours(date)['is_open']


class Markets(resourceful.Collection):
    ENDPOINT = 'markets/'
    INSTANCE_CLASS = Market


class Portfolio(resourceful.Instance):
    ID_FIELD = 'url'

    @property
    def equity(self):
        return float(self['equity'])


##
# Watchlist Instrument class, for use with a Watchlist.
class WatchlistInstrument(resourceful.Instance):
    ID_FIELD = 'url'

    @resourceful.Instance.endpoint.setter
    def endpoint(self, value):
        self._endpoint = helper.id_for(value)

    @property
    def id(self):
        return helper.id_for(self[self.ID_FIELD])

    @property
    def instrument(self):
        return Instrument(Instruments(self.api_or_parent, root=True), self.id)


class Watchlist(resourceful.Collection):
    INSTANCE_CLASS = WatchlistInstrument

    def instruments(self):
        return [ii.instrument for ii in self.list()]

    def symbols(self):
        return [ii.symbol for ii in self.instruments()]

    def add_all(self, *id_or_symbols):
        return [self.add(id_or_symbol) for id_or_symbol in id_or_symbols]

    def remove_all(self, *id_or_symbols):
        return [self.remove(id_or_symbol) for id_or_symbol in id_or_symbols]

    def add(self, id_or_symbol):
        if hasattr(id_or_symbol, 'id'):
            return self.add_instrument(id_or_symbol.id)
        elif helper.id_for(id_or_symbol):
            return self.add_instrument(helper.id_for(id_or_symbol))
        else:
            return self.add_symbols(id_or_symbol)

    def remove(self, id_or_symbol):
        if hasattr(id_or_symbol, 'id'):
            return self.remove_instrument(id_or_symbol.id)
        elif helper.id_for(id_or_symbol):
            return self.remove_instrument(helper.id_for(id_or_symbol))
        else:
            return self.remove_symbol(id_or_symbol)

    def add_symbols(self, *symbols):
        symbol_list = ','.join([*symbols])
        return self.post('bulk_add/', data={'symbols': symbol_list})

    def remove_symbol(self, symbol):
        # For every symbol, find its instrument ID and delete
        instrument_id = helper.symbol_table.get(symbol)
        if not instrument_id:
            instrument_id = Instruments(self, root=True).find_by(symbol=symbol).id
        return self.remove_instrument(instrument_id)

    def add_instrument(self, instrument_id):
        return self.post(instrument_id)

    def remove_instrument(self, instrument_id):
        return self.delete(instrument_id)


class Watchlists(resourceful.Collection):
    ENDPOINT = 'watchlists/'
    INSTANCE_CLASS = Watchlist

    def create(self, name):
        return self.post(None, data={'name': name})
