"""fixture_different_paths.py -- reads from a.json, writes to b.json, expect 0 findings."""
import json

def transform(key, value):
    with open("data/a.json") as f:
        data = json.load(f)
    data[key] = value
    with open("data/b.json", "w") as f:
        json.dump(data, f)
