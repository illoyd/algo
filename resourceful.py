import sys
import os
import re
import requests
import json
import simpleapi


##
# Collection!
class Collection(object):
  def __init__(self, api, base_uri):
    self.api = api
    self.base_uri = base_uri

  def list(self):
    if self._list is None:
      self._list = self.get_list()
    return self._list

  def get_list(self):
    return self.api.get(self.base_uri)



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