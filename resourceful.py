import sys
import os
import re
import requests
import json
import logging

import simpleapi

##
# Resource!
class Resource(object):
  def __init__(self, api_or_parent, endpoint):
    self.api_or_parent = api_or_parent
    self.endpoint = endpoint

  ##
  # Delegate GET to api or parent
  def get(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.api_or_parent.get(uri, *args, **kwargs)

  ##
  # Delegate POST to api or parent
  def post(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.api_or_parent.post(uri, *args, **kwargs)

  ##
  # Return a completed URI
  def relative_uri(self, uri):
    if isinstance(uri, tuple):
      base, inputs = uri[0], uri[1:]
      uri = base.format(*inputs)
    return requests.compat.urljoin(self.endpoint, uri)

  ##
  # Get the index, or general, URI
  def list(self):
    uri = self.endpoint
    response = PaginatedResponse(self.get(uri))
    items = response.results()

    while response.next():
      response = PaginatedResponse(self.get(uri))
      items.concat(response.results())

    return items

  ##
  # Find a specific item
  def find(self, id):
    uri = ('{}{}/', self.endpoint, id)
    return PaginatedResponse(self.get(uri))


##
# A collection
class Collection(Resource):
  pass


##
# An instance
class Instance(Resource):
  def __init__(self, api_or_parent, id_or_data = None, id_field = 'id'):
    self._id_field = id

    if isinstance(id_or_data, dict):
      self.data = id_or_data
      id = data[self._id_field]
    else:
      id = id_or_data

    super().__init__(api_or_parent, str(id) + '/')

  @property
  def id(self):
    return self[self._id_field]

  def __getitem__(self, key):
    if self.data is None:
      self.data = Response(self.get(None)).results()
    return self.data[key]

  def __setitem__(self, key, value):
    self.data[key] = value


class Response(object):
  def __init__(self, response):
    self.response = response
    self.content = response.json()

  def json(self):
    return self.content

  @property
  def results(self):
    return self.content.get('results', self.content)

  def __getitem__(self, key):
    return self.content[key]

  def __str__(self):
    return self.content


class PaginatedResponse(Response):

  @property
  def next(self):
    return self.content.get('next', None)

  @property
  def previous(self):
    return self.content.get('previous', None)
