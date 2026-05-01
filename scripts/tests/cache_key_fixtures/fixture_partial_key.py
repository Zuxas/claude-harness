"""Fixture: function takes (deck, opp), writes path with only opp. Expected: 1 INFO finding."""
import json


def write_match_result(deck, opp, result):
    # BUG: deck not in path; concurrent writers from different decks collide
    path = f"data/cache/{opp}.json"
    with open(path, "w") as f:
        json.dump(result, f)
