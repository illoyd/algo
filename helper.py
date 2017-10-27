##
# Take the first non-None value from a given list
# @args A list of items to compare
# @return The first non-None item in the list, or None otherwise
def coalesce(*args):
  return next((item for item in args if item is not None), None)
