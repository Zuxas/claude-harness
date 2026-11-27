"""harness_auth: credential lookup order + the removeprefix header fix (#5).

Run: python agents/scripts/test_harness_auth.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness_auth


def _write(path, text):
    Path(path).write_text(text, encoding="utf-8")


# ---- auth_header: the removeprefix fix -----------------------------------

def test_oauth_token_uses_bearer():
    assert harness_auth.auth_header("sk-ant-oat-ABC") == {"Authorization": "Bearer sk-ant-oat-ABC"}


def test_bearer_prefix_is_stripped_exactly():
    # A literal 'Bearer ' prefix is removed; the token is left intact.
    assert harness_auth.auth_header("Bearer sk-ant-oat-ABC") == {"Authorization": "Bearer sk-ant-oat-ABC"}


def test_api_key_uses_x_api_key():
    assert harness_auth.auth_header("sk-ant-api03-XYZ") == {"x-api-key": "sk-ant-api03-XYZ"}


def test_removeprefix_does_not_eat_token_characters():
    # The whole point of #5: str.lstrip('Bearer ') strips any leading char in
    # {B,e,a,r,space}, corrupting a token whose body starts with one of them.
    tok = "Bearer arctic-key"
    assert tok.removeprefix("Bearer ") == "arctic-key"
    assert tok.lstrip("Bearer ") == "ctic-key"          # the old bug, for contrast
    # auth_header must preserve the full token, not the lstrip-corrupted one.
    assert harness_auth.auth_header(tok) == {"x-api-key": "arctic-key"}


# ---- get_claude_token: lookup order --------------------------------------

def test_env_key_wins():
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-ENV"}, clear=False):
        assert harness_auth.get_claude_token() == "sk-ant-api03-ENV"


def test_oauth_used_when_fresh_and_no_env():
    with tempfile.TemporaryDirectory() as d:
        creds = Path(d) / ".credentials.json"
        _write(creds, json.dumps({"claudeAiOauth": {
            "accessToken": "sk-ant-oat-FRESH",
            "expiresAt": int(time.time() * 1000) + 3_600_000}}))
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(harness_auth, "_CREDS_PATH", creds):
            assert harness_auth.get_claude_token() == "sk-ant-oat-FRESH"


def test_expired_oauth_falls_through_to_env_file():
    with tempfile.TemporaryDirectory() as d:
        creds = Path(d) / ".credentials.json"
        _write(creds, json.dumps({"claudeAiOauth": {
            "accessToken": "sk-ant-oat-STALE",
            "expiresAt": int(time.time() * 1000) - 1000}}))      # already expired
        env_file = Path(d) / ".env"
        _write(env_file, 'ANTHROPIC_API_KEY="sk-ant-api03-FROMENVFILE"\n')
        clean = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, clean, clear=True), \
             mock.patch.object(harness_auth, "_CREDS_PATH", creds):
            assert harness_auth.get_claude_token(env_file=env_file) == "sk-ant-api03-FROMENVFILE"


def test_none_when_nothing_available():
    with tempfile.TemporaryDirectory() as d:
        missing = Path(d) / "nope.json"
        clean = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, clean, clear=True), \
             mock.patch.object(harness_auth, "_CREDS_PATH", missing):
            assert harness_auth.get_claude_token() is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_harness_auth: OK")
