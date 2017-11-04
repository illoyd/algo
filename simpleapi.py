##
# Simple API
import requests
import logging

##
# Simple restful api
class API(object):
  def __init__(self, endpoint, session = None):
    self.session = session if session else requests.Session()
    self.endpoint = endpoint

    self.session.headers.update({ 'Accept': 'application/json' })

  ##
  # Return a completed URI
  def relative_uri(self, uri):
    if isinstance(uri, tuple):
      base, inputs = uri[0], uri[1:]
      uri = base.format(*inputs)
      logging.warn(uri)
    return requests.compat.urljoin(self.endpoint, uri)

  def get(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.session.get(uri, *args, **kwargs)

  def post(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    return self.session.post(uri, *args, **kwargs)


##
# Passthrough proxy for APIs
class APIProxy(object):
  def __init__(self, api):
    self.api = api

  def __getattr__(self, name):
        return getattr(self.api, name)

##
# Include Token detection for APIs
class TokenAPI(APIProxy):
  def __init__(self, api, token = None):
    super().__init__(api)
    self.token = token

  def get(self, *args, **kwargs):
    response = self.api.get(*args, **kwargs)
    self.assign_token_if_exists(response)
    return response

  def post(self, *args, **kwargs):
    response = self.api.post(*args, **kwargs)
    self.assign_token_if_exists(response)
    return response

  @property
  def token(self):
    return self._token

  @token.setter
  def token(self, val):
    self._token = val
    if val:
      self.api.session.headers.update({'Authorization': 'Token ' + val})
    else:
      self.api.session.headers.pop('Authorization', None)

  def assign_token_if_exists(self, response):
    token = response.json().get('token', None)
    if token:
      logging.debug('Assigning token %s', token)
      self.token = token
    pass
