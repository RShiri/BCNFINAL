import json, sys
sys.path.insert(0, '.')
from build_website import _event_stats

d = json.load(open('assets/data/match_1914086_cache.json', encoding='utf-8'))
h, a = _event_stats(d)
print('Home (Barcelona):', h)
print('Away (Real Oviedo):', a)
