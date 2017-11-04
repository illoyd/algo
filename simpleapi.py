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

  def relative_uri(self, uri):
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
    self.api = api
    self.token = token

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
