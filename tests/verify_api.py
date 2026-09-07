"""Smoke tests against the running local API and the three demo POIs."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen


def get(path, **params):
    with urlopen('http://127.0.0.1:8010/api/places' + path + '?' + urlencode(params), timeout=10) as r:
        assert r.status == 200
        data = json.load(r)
    assert data['type'] == 'FeatureCollection'
    return data['features']


assert len(get('')) == 3
assert [f['properties']['name'] for f in get('', q='博物')] == ['南京博物院']
assert get('', q='不存在') == []
nearby = get('/nearby', lng=118.7921, lat=32.0407, radius=5000)
assert [f['properties']['name'] for f in nearby] == ['南京博物院', '夫子庙']
assert nearby[0]['properties']['distance_km'] == 0
assert abs(nearby[1]['properties']['distance_km'] - 1.57) < 0.02
assert get('/nearby', lng=0, lat=0, radius=5000) == []
print('PASS: all/search/empty/nearby API; nearby distances 0.00 and 1.57 km')
