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


class TokenAPI(object):
  def __init__(self, api, token = None):
    self.api = api
    self.set_token(token)

  def get(self, *args, **kwargs):
    return self.api.get(*args, **kwargs)

  def post(self, *args, **kwargs):
    return self.api.post(*args, **kwargs)

  def set_token(self, new_token):
    self.token = new_token
    if self.token:
      self.api.session.headers.update({'Authorization': 'Token ' + self.token})
    else:
      self.api.session.headers.pop('Authorization', None)
    pass

