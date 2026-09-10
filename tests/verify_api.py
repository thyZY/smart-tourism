"""Regression tests against the running local API and the 40-POI dataset."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = 'http://127.0.0.1:8010/api/places'
BBOX = {
    'min_lng': 118.785,
    'min_lat': 32.025,
    'max_lng': 118.800,
    'max_lat': 32.050,
}


def get(path='', **params):
    with urlopen(BASE_URL + path + '?' + urlencode(params), timeout=10) as response:
        assert response.status == 200
        data = json.load(response)
    assert data['type'] == 'FeatureCollection'
    for feature in data['features']:
        assert feature['type'] == 'Feature'
        assert feature['geometry']['type'] == 'Point'
        coordinates = feature['geometry']['coordinates']
        assert len(coordinates) == 2
        assert all(isinstance(value, (int, float)) for value in coordinates)
        assert feature['properties']['name']
        assert feature['properties']['category']
    return data['features']


def assert_in_bbox(features):
    for feature in features:
        lng, lat = feature['geometry']['coordinates']
        assert BBOX['min_lng'] < lng < BBOX['max_lng']
        assert BBOX['min_lat'] < lat < BBOX['max_lat']


all_places = get()
assert len(all_places) == 40

query = get(q='南京')
assert len(query) == 8
assert all('南京' in f['properties']['name'] or '南京' in f['properties']['category'] for f in query)

museums = get(category='博物馆')
assert len(museums) == 6
assert all(f['properties']['category'] == '博物馆' for f in museums)

query_museums = get(q='南京', category='博物馆')
assert len(query_museums) == 4
assert all(f['properties']['category'] == '博物馆' and '南京' in f['properties']['name'] for f in query_museums)

bbox_places = get(**BBOX)
assert len(bbox_places) == 5
assert_in_bbox(bbox_places)

bbox_query = get(q='夫子', **BBOX)
assert [f['properties']['name'] for f in bbox_query] == ['夫子庙']
assert_in_bbox(bbox_query)

bbox_category = get(category='历史文化', **BBOX)
assert len(bbox_category) == 2
assert all(f['properties']['category'] == '历史文化' for f in bbox_category)
assert_in_bbox(bbox_category)

bbox_query_category = get(q='夫子', category='历史文化', **BBOX)
assert [f['properties']['name'] for f in bbox_query_category] == ['夫子庙']
assert_in_bbox(bbox_query_category)

nearby = get('/nearby', lng=118.7921, lat=32.0407, radius=5000)
assert nearby
distances = [f['properties']['distance_km'] for f in nearby]
assert distances == sorted(distances)
assert all(0 <= distance <= 5 for distance in distances)

nearby_museums = get('/nearby', lng=118.7921, lat=32.0407, radius=5000, category='博物馆')
assert len(nearby_museums) <= len(nearby)
assert all(f['properties']['category'] == '博物馆' for f in nearby_museums)
assert all(0 <= f['properties']['distance_km'] <= 5 for f in nearby_museums)

print('PASS: all /places q/category/bbox combinations and nearby category filtering')
