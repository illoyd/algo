##
# Robinhood namespace

class BasicResponse(object):
  def __init__(self, response):
    self.response = response

class BasicClient(object):

  def __init__(self, base_endpoint = 'https://api.robinhood.com'):
    self.base_endpoint = base_endpoint

  def normalize_uri(self, uri):
    return self.base_endpoint + path

  def default_headers(self):
    return {}

  def default_params(self):
    return {}

  def get(self, path, response_class = BasicResponse, params = {}, headers = {}):
    uri = self.normalize_uri(path)
    params.update(self.default_params())
    headers.update(self.default_headers())
    response = requests.get(uri, params=params, headers=headers)
    return response_class(response)

  def post(self, path, response_class = BasicResponse, params = {}, data = {}, headers = {}):
    uri = self.normalize_uri(path)
    params.update(self.default_params())
    headers.update(self.default_headers())
    response = requests.post(uri, params=params, data=data, headers=headers)
    return response_class(response)
