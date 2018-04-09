# Standard library imports
import concurrent.futures
import functools
import logging
import os
import time

import numpy as np
import pandas as pd

import algo
import helper
import robinhood

# Activate logging!
logging.basicConfig(level=logging.INFO)

MAX_IN_ONE = 1.0 / 12.0
EQUITY_UTILISATION = 0.99
MARGIN_UTILISATION = 0.0
BUY_LIMIT = 1.0 + ((1.0 - EQUITY_UTILISATION) / 2.0)

SECONDARY_MAX_IN_ONE = 5.0 / 6.0


##
# Main entry point for this cloud function
# @args A single JSON (or dictionary) object
# @return A JSON (or dictionary) object
def main(args={}):
    # Extract values from arguments
    username = args.get('username', os.environ.get('ROBINHOOD_USERNAME'))
    password = args.get('password', os.environ.get('ROBINHOOD_PASSWORD'))
    account_id = args.get('account', os.environ.get('ROBINHOOD_ACCOUNTID'))
    market_check = helper.truthy(args.get('market_check', True))
    execute = helper.truthy(args.get('execute', False))

    # Preamble!
    logging.info('Beginning algo with options:')
    logging.info('  username:  %s', username)
    logging.info('  password:  %s', ('SET' if password else 'NONE'))
    logging.info('  account:   %s', account_id)
    logging.info('  market_check: %s', market_check)
    logging.info('  execute:   %s', execute)

    # Activate a Robinhood client
    with robinhood.Client(username=username, password=password, account_id=account_id) as client:
        order_manager = robinhood.OrderManager(client)

        # Assemble algos
        primary_algos = [
            algo.WatchlistAlgo(client, 0.50)
        ]
        secondary_algos = [
            algo.UniverseSharpeAlgo(client, ['SPY', 'TLT', 'HYG'], lookback=21)
        ]

        # Check if markets are open
        if market_check:
            logging.info('PRE: MARKETS OPEN?')
            if not client.are_markets_open():
                logging.warning('Markets are closed! Cancelling')
                client.logout()
                return {
                    "status": "not run",
                    "reason": "markets closed",
                    "success": False
                }

        # Multithreading goodness
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Execute primaries and secondaries
            primary_weights = [executor.submit(aa.optimise) for aa in primary_algos]
            secondary_weights = [executor.submit(aa.optimise) for aa in secondary_algos]

            # Calculate secondaries
            # a. Unwrap weights
            # b. Add all weights together
            # c. Re-scale to 1.0
            # d. Limit individual entries to no more than SECONDARY MAX (currently 5/6ths)
            if secondary_weights:
                secondary_weights = [future.result() for future in secondary_weights]
                secondary_weights = functools.reduce((lambda a, b: a.add(b, fill_value=0.0)), secondary_weights)
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
                primary_weights = [future.result() for future in primary_weights]
                primary_weights = functools.reduce((lambda a, b: a.add(b, fill_value=0.0)), primary_weights)
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
            target_portfolio_weights = algo.UniverseSharpeAlgo(client, ['TLT', 'HYG', 'SPY']).optimise()

        # Short circuit if no target portfolio is found!
        if target_portfolio_weights.empty:
            return {'status': 'error', 'reason': 'No optimal portfolio found.', 'success': False}

        logging.info('Target weights: %s',
                     ', '.join(['{}: {:0.1f}%'.format(s, w * 100.0) for s, w in target_portfolio_weights.iteritems()]))
        logging.debug(target_portfolio_weights.round(2))

        # Determine available captial to play with
        logging.info('STEP 4: CAPITAL')
        capital = (client.equity * EQUITY_UTILISATION) + (client.margin * MARGIN_UTILISATION)
        logging.info('Capital: %s (equity: %s, margin: %s)', capital, client.equity, client.margin)

        # Get mid quotes
        logging.info('STEP 5: QUOTES')
        mid_quotes = client.quotes(*target_portfolio_weights.index)
        logging.info('Found quotes: %s', ', '.join(['{}@{:0.4f}'.format(s, q) for s, q in mid_quotes.iteritems()]))
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
        portfolio_delta = target_portfolio.subtract(current_portfolio, fill_value=0.0).sort_values()
        logging.info('Delta: %s', portfolio_stringify(portfolio_delta))
        logging.debug(portfolio_delta)

        # Perform sells
        logging.info('STEP 9: SELL')
        for symbol, delta in portfolio_delta[portfolio_delta < 0].iteritems():
            order_manager.sell(symbol, abs(delta))
        order_manager.execute()

        # Sleep a bit...
        if execute:
            logging.info('TAKE A BREATH...')
            time.sleep(5)

        # Perform buys
        logging.info('STEP 10: BUY')
        for symbol, delta in portfolio_delta[portfolio_delta > 0].iteritems():
            limit = round(mid_quotes[symbol] * BUY_LIMIT, 2)
            order_manager.buy(symbol, abs(delta), limit=limit)
        order_manager.execute()

    # Boring stuff!
    return {
        'current_portfolio': dict(current_portfolio),
        'target_portfolio': dict(target_portfolio),
        'delta': dict(portfolio_delta)
    }


def portfolio_stringify(portfolio):
    return ', '.join(['{}: {:0.0f}'.format(symbol, quantity) for symbol, quantity in portfolio.iteritems()])


##
# Calculate the target portfolio units
def calculate_target_portfolio(weights, mid_quotes, capital):
    # Determine portion assigned to each asset
    capital_weights = weights * float(capital)

    # Divide the capital weight of each asset by its mid-quote
    shares = capital_weights.divide(mid_quotes, fill_value=0.0)

    # Round the share (no fractional shares here)
    shares = np.around(shares, 0)

    return shares


def train():
    pass


##
# Run pre-set-ups
if __name__ == "__main__":
    c = robinhood.Client()
    om = robinhood.OrderManager(c)

#   tsla = algo.DNNAlgo('TSLA')
