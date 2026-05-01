"""Fixture: same as partial_key but with allow-list comment. Expected: 0 findings."""
import json


def write_match_result(deck, opp, result):
    # drift-detect:cache-key-ok reason="opp-only path is intentional; deck context implicit via subprocess working dir"
    path = f"data/cache/{opp}.json"
    with open(path, "w") as f:
        json.dump(result, f)
