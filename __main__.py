# Standard library imports
import sys
import numpy as np
import pandas as pd
import math
import cvxopt as opt
import cvxopt.solvers as optsolvers
import datetime

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
  name = args.get('name', 'stranger')
  return { 'message': f"Hello {name}!" }


##
# The Robinhood interface, built from the ground up sadly!
class Robinhood(object):
  def __init__(self, username = None, password = None):
    self.token = None
    if username:
      self.login(username, password)

  ##
  # Perform login to Robinhood, and save the returned token
  # @return Nothing
  def login(self, username, password):
    # Get token
    self.token = None
    pass

  ##
  # Get quotes
  # @return A pandas dataframe of symbols and prices
  def quotes(self, symbols):
    # TODO
    q = pandas.Dataframe()
    return q

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
  def portfolio(self):
    # TODO
    p = pandas.Dataframe()
    return p

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


if __name__ == "__main__":
    print( main({ 'name': 'Bob' }) )