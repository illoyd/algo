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
  # Return a completed, relative URI
  def relative_uri(self, uri):
    if isinstance(uri, tuple):
      base, inputs = uri[0], uri[1:]
      uri = base.format(*inputs)
    return requests.compat.urljoin(self.endpoint, uri)

  def build_full_uri(self, uri, *args, **kwargs):
    return self._absolute_uri(uri, *args, **kwargs)

  def _absolute_uri(self, uri = None, *args, **kwargs):
    return requests.Request('GET', self.relative_uri(uri), *args, **kwargs).prepare().url

  def get(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    response = self.session.get(uri, *args, **kwargs)
    logging.debug(response.text)
    return response

  def post(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    response = self.session.post(uri, *args, **kwargs)
    logging.debug(response.text)
    return response

  def delete(self, uri, *args, **kwargs):
    uri = self.relative_uri(uri)
    response = self.session.delete(uri, *args, **kwargs)
    logging.debug(response.text)
    return response


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
      self.api.session.headers.update({'Authorization': 'Bearer ' + val})
    else:
      self.api.session.headers.pop('Authorization', None)

  def assign_token_if_exists(self, response):
    if response.status_code == requests.codes.ok and response.content:
      token = response.json().get('access_token', None)
      if token:
        logging.debug('Assigning token %s', token)
        self.token = token
    pass

##
# Memory Cache API
class MemoryCacheAPI(APIProxy):
  def __init__(self, api):
    super().__init__(api)
    self.reset()

  def get(self, uri, *args, **kwargs):
    full_uri = self.build_full_uri(uri, *args, **kwargs)
    if not self._cache.get(full_uri, None):
      self._cache[full_uri] = self.api.get(uri, *args, **kwargs)
    return self._cache[full_uri]

  def reset(self):
    self._cache = {}
