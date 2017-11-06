import sys
import os
import re
import requests
import json
import logging

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
  def __init__(self, api_or_parent, endpoint = None):
    self.api_or_parent = api_or_parent
    self.endpoint = endpoint or self.ENDPOINT

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
  # Find a specific item
  def find(self, id):
    uri = ('{}{}/', self.endpoint, id)
    return PaginatedResponse(self.get(uri))


##
# A collection
class Collection(Resource):

  ##
  # Get the index, or general, URI
  def list(self, instance_class = None):
    # Get first pass of data
    response = PaginatedResponse(self.get(None))
    items = response.results

    # While there is a next link, follow
    while response.next:
      response = PaginatedResponse(self.get(response.next))
      items.concat(response.results)

    # Convert items to objects
    instance_class = instance_class or self.INSTANCE_CLASS
    if instance_class:
      items = [ instance_class(self, item) for item in items ]

    return items


##
# An instance
class Instance(Resource):
  def __init__(self, api_or_parent, id_or_data = None):

    if isinstance(id_or_data, dict):
      self.data = id_or_data
      id = self.data.get(self.ID_FIELD, None)
    else:
      self.data = None
      id = id_or_data

    super().__init__(api_or_parent, str(id) + '/')

  @property
  def id(self):
    return self[self.ID_FIELD]

  def __getitem__(self, key):
    if self.data is None:
      self.reload()
    return self.data[key]

  def __setitem__(self, key, value):
    self.data[key] = value

  def reload(self):
    self.data = Response(self.get(None)).results
    pass


class Response(object):
  def __init__(self, response):
    self.response = response

    if response.status_code == requests.codes.ok and response.content:
      self.content = response.json()
    else:
      self.content = response.content

  def json(self):
    return self.content

  @property
  def results(self):
    return self.content.get('results', self.content)

  def __getitem__(self, key):
    return self.results[key]

  def __str__(self):
    return self.content


class PaginatedResponse(Response):

  @property
  def next(self):
    return self.content.get('next', None)

  @property
  def previous(self):
    return self.content.get('previous', None)
