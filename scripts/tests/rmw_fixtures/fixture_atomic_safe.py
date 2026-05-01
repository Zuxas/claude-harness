"""fixture_atomic_safe.py -- uses atomic_rmw_json, expect 0 findings."""
import json
from engine.atomic_json import atomic_rmw_json

def update_matrix(deck, result):
    def mutator(matrix):
        matrix[deck] = result
        return matrix
    atomic_rmw_json("data/sim_matchup_matrix.json", mutator)
