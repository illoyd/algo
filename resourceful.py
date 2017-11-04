import sys
import os
import re
import requests
import json
import simpleapi

##
# Resource!
class Resource(object):
  def __init__(self, api, base_uri):
    self.api = api
    self.base_uri = base_uri

  def list(self):
    uri = self.base_uri
    return self.api.get(uri).json()

  def find(self, id):
    uri = ('{}{}/', self.base_uri, id)
    return self.api.get(uri).json()