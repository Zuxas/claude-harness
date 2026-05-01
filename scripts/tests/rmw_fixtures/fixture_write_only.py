"""fixture_write_only.py -- write-only (no read), expect 0 findings."""
import json

def save_results(data):
    with open("data/results.json", "w") as f:
        json.dump(data, f)
