from ..query import page


def install(s):
    s.route('GET', r'/api/search', lambda store, ids, payload, query: page(store, query))
