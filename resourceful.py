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
  def __init__(self, api_or_parent, endpoint = None, root = False):
    self.api_or_parent = api_or_parent
    self.endpoint = endpoint or self.ENDPOINT
    if root and not self.endpoint[0] == "/":
      self.endpoint = "/" + self.endpoint

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
  # Delegate DELETE to api or parent
  def delete(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.api_or_parent.delete(uri, *args, **kwargs)

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

  @property
  def endpoint(self):
    return self._endpoint

  @endpoint.setter
  def endpoint(self, value):
    self._endpoint = value

  ##
  # Compile the absolute URI for this object
  def _absolute_uri(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.api_or_parent._absolute_uri(uri, *args, **kwargs)

  ##
  # A repr helper
  def _to_repr(self, **data):
    labels = " ".join([ label + "={" + label + "}" for label in data.keys() ])
    return ("<{class_name} " + labels + ">").format(class_name = type(self).__name__, **data)


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
      items.extend(response.results)

    # Convert items to objects
    instance_class = instance_class or self.INSTANCE_CLASS
    if instance_class:
      items = [ instance_class(self, item) for item in items ]

    return items

  def __repr__(self):
    return self._to_repr(endpoint = self.endpoint)

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

  def __repr__(self):
    return self._to_repr(id = self.id)


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
