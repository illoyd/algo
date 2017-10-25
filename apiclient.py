##
# Robinhood namespace

import os
import requests
import logging

class BasicResponse(object):
  def __init__(self, response):
    self.raw_response = response
    self.response = response.json()

  def json(self):
    return self.response

  def __getitem__(self, key):
    return self.response[key]

  def __str__(self):
    return self.response


class PaginatedResponse(BasicResponse):

  def next(self):
    return self.response.get('next')

  def previous(self):
    return self.response.get('previous')

  def results(self):
    return self.response.get('results', self.response)


class BasicClient(object):

  def __init__(self, base_endpoint = None):
    self.base_endpoint = base_endpoint

  def normalize_uri(self, uri):
    # TODO do not add base endpoint if given a fully qualified URI
    if isinstance(uri, list):
      uri = '/'.join(uri)
    return self.base_endpoint + '/' + uri + '/'

  def default_headers(self):
    return { 'Accept': 'application/json' }

  def default_params(self):
    return {}

  def get(self, uri, params = {}, headers = {}, response_class = BasicResponse):
    uri = self.normalize_uri(uri)
    params = { **self.default_params(), **params }
    headers = { **self.default_headers(), **headers }
    response = requests.get(uri, params=params, headers=headers)
    return response_class(response)

  def post(self, uri, params = {}, data = {}, headers = {}, response_class = BasicResponse):
    uri = self.normalize_uri(uri)
    params = { **self.default_params(), **params }
    headers = { **self.default_headers(), **headers }
    response = requests.post(uri, params=params, data=data, headers=headers)
    return response_class(response)

  ##
  # Take the first non-None value from a given list
  def coalesce(self, *args):
    return next((item for item in args if item is not None), None)

class TokenClient(BasicClient):
  def __init__(self, token = None, base_endpoint = None):
    super().__init__(base_endpoint = base_endpoint)
    self.token = token

  def default_headers(self):
    headers = super().default_headers()
    if self.token:
      headers['Authorization'] = 'Token ' + self.token
    return headers
