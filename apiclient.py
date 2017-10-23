##
# Robinhood namespace

class BasicResponse(object):
  def __init__(self, response):
    self.response = response.json()


class PaginatedResponse(BasicResponse):

  def next():
    return self.response['next']

  def previous():
    return self.response['previous']


class BasicClient(object):

  def __init__(self, base_endpoint = 'https://api.robinhood.com'):
    self.base_endpoint = base_endpoint

  def normalize_uri(self, *uri):
    # TODO do not add base endpoint if given a fully qualified URI
    return '/'.join([ self.base_endpoint, *uri ])

  def default_headers(self):
    return {}

  def default_params(self):
    return {}

  def get(self, uri, response_class = BasicResponse, params = {}, headers = {}):
    uri = self.normalize_uri(uri)
    params = { **self.default_params(), **params }
    headers = { **self.default_headers(), **headers }
    response = requests.get(uri, params=params, headers=headers)
    return response_class(response)

  def post(self, uri, response_class = BasicResponse, params = {}, data = {}, headers = {}):
    uri = self.normalize_uri(uri)
    params = { **self.default_params(), **params }
    headers = { **self.default_headers(), **headers }
    response = requests.post(uri, params=params, data=data, headers=headers)
    return response_class(response)
