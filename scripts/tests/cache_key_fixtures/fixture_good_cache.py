"""Fixture: function takes (deck, opp), writes path that includes both. Expected: 0 findings."""
import json


def write_match_result(deck, opp, result):
    path = f"data/cache/{deck}__{opp}.json"
    with open(path, "w") as f:
        json.dump(result, f)
