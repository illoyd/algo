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
import logging

##
# Sharpe Algo class - for handling the calculations!
class SharpeAlgo(object):

  def optimise(self, prices):
    pass