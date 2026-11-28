"""Shared Claude credential handling for harness scripts (#5).

One place decides which Claude credential to use, so apl_optimizer and
auto_pipeline stop each doing their own ad-hoc lookup. The value is never
logged.

Lookup order:
  1. ANTHROPIC_API_KEY in the environment (an explicit API key wins).
  2. A Claude Code OAuth accessToken from ~/.claude/.credentials.json, used
     only if it is not within 5 minutes of expiry.
  3. An ANTHROPIC_API_KEY= line in a given .env file.

auth_header() builds the correct header for a RAW Anthropic HTTP call:
Authorization: Bearer for an OAuth token, x-api-key for a plain API key. It
uses str.removeprefix('Bearer '), because the old str.lstrip('Bearer ') strips
any leading character in the set {B,e,a,r,space} -- so a token beginning with
one of those letters was silently corrupted.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

_CREDS_PATH = Path.home() / ".claude" / ".credentials.json"
_EXPIRY_SKEW_MS = 300_000  # treat a token expiring within 5 min as unusable


def get_claude_token(env_file: Optional[Path] = None) -> Optional[str]:
    """Return a usable Claude credential, or None. Never logs the value."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    try:
        creds = json.loads(_CREDS_PATH.read_text(encoding="utf-8"))
        oauth = creds.get("claudeAiOauth", {})
        token = oauth.get("accessToken", "")
        expires = oauth.get("expiresAt", 0)
        if token and expires > (time.time() * 1000 + _EXPIRY_SKEW_MS):
            return token
    except Exception:
        pass

    if env_file is not None:
        try:
            for line in Path(env_file).read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"')
                    if value:
                        return value
        except Exception:
            pass

    return None


def auth_header(token: str) -> dict:
    """Header for a raw Anthropic HTTP request. OAuth accessTokens (which begin
    'sk-ant-oat', optionally sent with a literal 'Bearer ' prefix) authenticate
    with Authorization: Bearer; a plain API key uses x-api-key."""
    tok = token.removeprefix("Bearer ").strip()
    if tok.startswith("sk-ant-oat"):
        return {"Authorization": f"Bearer {tok}"}
    return {"x-api-key": tok}


def credential_kind(token: str) -> str:
    """'oauth' for an sk-ant-oat accessToken, else 'api_key'. For logging which
    credential TYPE was used -- never the value."""
    return "oauth" if token.removeprefix("Bearer ").strip().startswith("sk-ant-oat") else "api_key"


def sdk_auth_kwargs(token: str) -> dict:
    """Anthropic() kwargs for the SDK path, matching auth_header's raw-HTTP
    classification so both paths agree (#30). An OAuth token goes through
    auth_token= (SDK sends Authorization: Bearer); a plain API key goes through
    api_key=. This is correct on both the pre-2026-10 SDK (api_key -> x-api-key,
    auth_token -> Bearer) and the post-migration 2.x SDK (both -> Bearer): an
    OAuth token must never ride the x-api-key path the old SDK builds for
    api_key=."""
    tok = token.removeprefix("Bearer ").strip()
    if tok.startswith("sk-ant-oat"):
        return {"auth_token": tok}
    return {"api_key": tok}
