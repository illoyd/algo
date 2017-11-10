##
# Take the first non-None value from a given list
# @args A list of items to compare
# @return The first non-None item in the list, or None otherwise
def coalesce(*args):
  return next((item for item in args if item is not None), None)

def parse_instrument_id(sz):
  match = re.match('https://api.robinhood.com/instruments/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?', sz)
  if match:
    return match[1]
  else:
    return None

symbol_table = {}