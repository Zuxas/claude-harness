"""fixture_allowlisted.py -- allow-listed, expect 0 findings."""
import json

def update_matrix(deck, result):
    # drift-detect:rmw-ok reason="single writer; nightly harness runs sequentially"
    with open("data/sim_matchup_matrix.json") as f:
        matrix = json.load(f)
    matrix[deck] = result
    with open("data/sim_matchup_matrix.json", "w") as f:
        json.dump(matrix, f)
