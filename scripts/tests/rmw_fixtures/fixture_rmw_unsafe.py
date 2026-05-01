"""fixture_rmw_unsafe.py -- expect 1 INFO finding."""
import json

def update_matrix(deck, result):
    with open("data/sim_matchup_matrix.json") as f:
        matrix = json.load(f)
    matrix[deck] = result
    with open("data/sim_matchup_matrix.json", "w") as f:
        json.dump(matrix, f)
