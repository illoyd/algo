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

  def relative_uri(self, uri):
    return requests.compat.urljoin(self.endpoint, uri)

  def get(self, uri, *args):
    uri = self.relative_uri(uri)
    return self.session.get(uri, *args)

  def post(uri, *args):
    uri = self.relative_uri(uri)
    return self.session.post(uri, *args)


class TokenAPI(object):
  def __init__(api, token = None):
    self.api = api
    self.set_token(token)

  self set_token(self, new_token)
    self.token = new_token
    if self.token:
      self.api.session.headers.update('Authorization': 'Token ' + self.token)
    else:
      del self.api.session.headers['Authorization']
    pass

