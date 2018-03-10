# Standard library imports
import sys
import os
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
import functools
import concurrent.futures

import robinhood
import algo

# Activate logging!
logging.basicConfig(level=logging.INFO)

MAX_IN_ONE = 1.0 / 12.0
EQUITY_UTILISATION = 0.98
BUY_LIMIT = 1.0 + ( (1.0 - EQUITY_UTILISATION) / 2.0 )

SECONDARY_MAX_IN_ONE = 5.0 / 6.0


##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args = {}):

  # Extract values from arguments
  username = args.get('username', os.environ.get('ROBINHOOD_USERNAME'))
  password = args.get('password', os.environ.get('ROBINHOOD_PASSWORD'))
  account_id = args.get('account', os.environ.get('ROBINHOOD_ACCOUNTID'))
  market_check = ( args.get('market_check', 'yes') == 'yes' )
  execute = ( args.get('execute', 'no') == 'yes' )

  # Preamble!
  logging.info('Beginning algo with options:')
  logging.info('  username:  %s', username)
  logging.info('  password:  %s', ('SET' if password else 'NONE'))
  logging.info('  account:   %s', account_id)
  logging.info('  market_check: %s', market_check)
  logging.info('  execute:   %s', execute)

  # Activate a Robinhood client
  with robinhood.Client(username = username, password = password, account_id = account_id) as client:

    # Assemble algos
    PRIMARY = [
      algo.UniverseAlgo([ 'TSLA', 'NFLX', 'SBUX', 'FB', 'TWTR', 'NVDA' ], 0.30)
    ]
    SECONDARY = [
      algo.WatchlistSharpeAlgo(client, lookback = 21)
    ]

    # Check if markets are open
    if market_check:
      logging.info('PRE: MARKETS OPEN?')
      if not client.are_markets_open():
        logging.warn('Markets are closed! Cancelling')
        client.logout()
        return {
          "status": "not run",
          "reason": "markets closed",
          "success": False
        }

    # Multithreading goodness
    with concurrent.futures.ThreadPoolExecutor() as executor:
      # Execute primaries and secondaries
      primary_weights = [ executor.submit(algo.optimise) for algo in PRIMARY ]
      secondary_weights = [ executor.submit(algo.optimise) for algo in SECONDARY ]

      # Calculate secondaries
      # a. Unwrap weights
      # b. Add all weights together
      # c. Re-scale to 1.0
      # d. Limit individual entries to no more than SECONDARY MAX (currently 5/6ths)
      if secondary_weights:
        secondary_weights = [ future.result() for future in secondary_weights ]
        secondary_weights = functools.reduce( (lambda a, b: a.add(b, fill_value=0.0)), secondary_weights )
        secondary_weights /= secondary_weights.sum()
        secondary_weights[secondary_weights > SECONDARY_MAX_IN_ONE] = SECONDARY_MAX_IN_ONE
      else:
        secondary_weights = pd.Series()

      # Calculate primaries
      # a. Unwrap weights
      # b. Add all weights together
      # c. Limit to 1/12 of portfolio
      # c. Re-scale to 1.0 if > 1.0
      if primary_weights:
        primary_weights = [ future.result() for future in primary_weights ]
        primary_weights = functools.reduce( (lambda a, b: a.add(b, fill_value=0.0)), primary_weights )
        primary_weights[primary_weights > MAX_IN_ONE] = MAX_IN_ONE
        if primary_weights.sum() > 1.0:
          primary_weights /= primary_weights.sum()
      else:
        primary_weights = pd.Series()

      # Merge primary and secondary
      # a. Calculate Primary's unused portion of portfolio
      # b. Scale Secondary to fit unused portfolio
      # c. Add weights together
      if primary_weights.any():
        secondary_weights *= (1.0 - primary_weights.sum())
      target_portfolio_weights = primary_weights.add(secondary_weights, fill_value=0.0)

    # Short circuit if no target portfolio is found!
    if target_portfolio_weights.empty:
      target_portfolio_weights = algo.UniverseSharpeAlgo(client, [ 'TLT', 'HYG', 'SPY' ]).optimise()

    # Short circuit if no target portfolio is found!
    if target_portfolio_weights.empty:
      return { 'status': 'error', 'reason': 'No optimal portfolio found.' }

    logging.info('Target weights: %s', ', '.join([ '{}: {:0.1f}%'.format(s, w * 100.0) for s, w in target_portfolio_weights.iteritems() ]))
    logging.debug(target_portfolio_weights.round(2))

    # Determine available captial to play with
    logging.info('STEP 4: CAPITAL')
    capital = (client.equity * EQUITY_UTILISATION) + client.margin
    logging.info('Capital: %s (equity: %s, margin: %s)', capital, client.equity, client.margin)

    # Get mid quotes
    logging.info('STEP 5: QUOTES')
    mid_quotes = client.quotes(*target_portfolio_weights.index)
    logging.info('Found quotes: %s', ', '.join([ '{}@{:0.4f}'.format(s, q) for s, q in mid_quotes.iteritems() ]))
    logging.debug(mid_quotes)

    # Convert the target weights into target positions
    logging.info('STEP 6: TARGET HOLDINGS')
    target_portfolio = calculate_target_portfolio(target_portfolio_weights, mid_quotes, capital)
    logging.info('Target holdings: %s', portfolio_stringify(target_portfolio))
    logging.debug(target_portfolio)

    # Calculate total portfolio value...
    capital_used = (target_portfolio * mid_quotes).sum()
    capital_utilisation = capital_used / capital
    logging.info('TOTAL PORTFOLIO VALUE: %s (%s)', capital_used, capital_utilisation)

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
      if execute:
        response = client.sell(symbol, abs(delta))
        if response.status_code == requests.codes.ok:
          logging.info('    Ok! Order is %s', response.json()['state'])
        else:
          logging.warn(response.text)

    # Sleep a bit...
    if execute:
      logging.info('TAKE A BREATH...')
      time.sleep(5)

    # Perform buys
    logging.info('STEP 10: BUY')
    for symbol, delta in portfolio_delta[portfolio_delta > 0].iteritems():
      limit = round( mid_quotes[symbol] * BUY_LIMIT, 2 )
      logging.info('  Buying %s: %s @ %s', symbol, abs(delta), limit)
      if execute:
        response = client.buy(symbol, abs(delta), limit)
        if response.status_code == requests.codes.ok:
          logging.info('    Ok! Order is %s', response.json()['state'])
        else:
          # Parse error message; if cap'ed, re-run a buy
          search = re.search('[Yy]ou can only purchase (\d+) shares', response.text)
          if m.group(0):
            logging.info('    Limited! Can purchase %s', m.group(0))
            delta = m.group(0)
            response = client.buy(symbol, abs(delta), limit)
            if response.status_code == requests.codes.ok:
              logging.info('    Ok! Order is %s', response.json()['state'])
            else:
              logging.warn(response.text)
          else:
            logging.warn(response.text)


  # Boring stuff!
  return {
    'current_portfolio': dict(current_portfolio),
    'target_portfolio': dict(target_portfolio),
    'delta': dict(portfolio_delta)
   }


def portfolio_stringify(portfolio):
  return ', '.join([ '{}: {:0.0f}'.format(symbol, quantity) for symbol, quantity in portfolio.iteritems() ])

##
# Calculate the target portfolio units
def calculate_target_portfolio(weights, mid_quotes, capital):
  # Determine portion assigned to each asset
  capital_weights = weights * float(capital)

  # Divide the capital weight of each asset by its mid-quote
  shares = capital_weights.divide(mid_quotes, fill_value = 0.0)

  # Round the share (no fractional shares here)
  shares = np.around(shares, 0)

  return shares


def train():
  pass


##
# Run pre-set-ups
if __name__ == "__main__":
  client = robinhood.Client()
#   tsla = algo.DNNAlgo('TSLA')
