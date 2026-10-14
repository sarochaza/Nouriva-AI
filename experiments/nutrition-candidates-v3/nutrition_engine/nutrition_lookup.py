"""Read one reference row using its stable, source-scoped food ID."""
def lookup(matcher, food_id):
    row=matcher.by_id.get(food_id)
    if row is None:raise KeyError(food_id)
    return dict(row)
