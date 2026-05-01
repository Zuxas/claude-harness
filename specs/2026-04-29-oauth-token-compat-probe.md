# Spec: OAuth-token-vs-raw-v1/messages compatibility probe

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code OR user (interactive Python session)
**Estimated effort:** 5-10 minutes (60s probe + 5 min documentation)
**Risk level:** MINIMAL — single low-cost API call (1 token completion); cost cap ~$0.0001 even on console-billed path
**Dependencies:** None
**Resolves:** 1 OPEN imperfection (`oauth-vs-raw-v1-messages-compat-unverified`)

## Goal

Settle the question that's been sitting open since S3.9 T.0: does a Claude Code OAuth token (`sk-ant-o...` from `~/.claude/.credentials.json`) work when sent to `https://api.anthropic.com/v1/messages` directly, or does Anthropic require a separate console-issued API key (`sk-ant-api03-...`) for raw API calls?

The answer determines the auto-pipeline cost model:
- **If OAuth tokens work:** auto-pipeline Claude path is free under your Claude Max subscription (no separate API key needed). Friday-night PT-watch can use Claude generation without console billing.
- **If OAuth tokens don't work:** Need a separate console API key for the Claude path. Cost becomes real (~$0.05/deck × N decks). Default-Gemma stays the right choice; Claude path requires explicit console-key setup.

This is a 60-second test that resolves a question blocking strategic decisions about the auto-pipeline.

## Pre-flight reads

1. `harness/IMPERFECTIONS.md` — entry `oauth-vs-raw-v1-messages-compat-unverified`
2. `mtg-sim/apl/auto_apl.py:_get_api_token` — current token resolution logic (confirms `sk-ant-o...` prefix gets returned)

## Scope

### In scope
- One probe call to `https://api.anthropic.com/v1/messages` using the OAuth token
- Observe: success (200 with completion), or auth failure (401/403)
- Document outcome in IMPERFECTIONS resolution + auto_apl.py docstring

### Explicitly out of scope
- Refactoring auto_pipeline to use one path or the other based on outcome — separate spec depending on result
- Cost-model analysis past the binary "works/doesn't" question

## Steps

### T.0 — Resolve token (~30 sec)

```python
import sys, os
sys.path.insert(0, "E:/vscode ai project/mtg-sim")
from apl.auto_apl import _get_api_token
token = _get_api_token()
print(f"Token resolved: prefix={token[:10]}..., length={len(token)}")
```

Confirm: prefix is `sk-ant-o...` (OAuth) not `sk-ant-api03-...` (console).

### T.1 — Single probe call (~30 sec)

```python
import urllib.request, json

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    method="POST",
    headers={
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    data=json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode("utf-8"),
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
        print(f"SUCCESS: status={resp.status}, model={body.get('model')}, content={body.get('content')}")
        result = "OAUTH_WORKS"
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8", errors="replace")
    print(f"HTTP {e.code}: {err_body}")
    result = f"OAUTH_FAILS_{e.code}"
except Exception as e:
    print(f"OTHER: {type(e).__name__}: {e}")
    result = f"OAUTH_FAILS_OTHER"

print(f"\n=== RESULT: {result} ===")
```

Use Haiku (cheapest) and `max_tokens=5` (minimal cost). Even if billed, total cost ~$0.0001.

### T.2 — Document outcome (~5 min)

Update three places:

1. `harness/IMPERFECTIONS.md` — move entry to RESOLVED with one of:
   - "OAuth path works (probe returned 200, completion received). Claude path absorbs into Claude Max."
   - "OAuth path fails with HTTP 401/403. Claude path requires separate console API key."
2. `mtg-sim/apl/auto_apl.py` — update the docstring on `_get_api_token` with a note documenting probe outcome and date
3. `harness/HARNESS_STATUS.md` — Layer 5 section's "Auth-path topology" paragraph: replace "OAuth-token-for-raw-v1/messages compatibility unverified" with the verified outcome

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — token resolves | T.0 prints `sk-ant-o...` prefix | token resolution fails (different problem; out of scope) |
| 2 — probe completes | T.1 returns either SUCCESS or definitive failure (not timeout/network error) | timeout — retry once, then stop and surface |
| 3 — outcome documented | All three docs updated | any doc not updated |

## Stop conditions

- **Network timeout / connection error:** STOP. Retry once. If second attempt also fails, surface as separate "network reachability" issue, not the auth question.
- **Probe returns 429 (rate limit):** STOP. Wait 60 seconds, retry. If persistent, this is also a separate finding.
- **Probe succeeds but with unexpected response shape:** STOP. Document the response, escalate — could indicate API version change.

## Reporting expectations

1. Token prefix confirmation (T.0 output)
2. Probe HTTP status + response body summary
3. Resolved vs failed binary
4. All 3 docs updated
5. Cost actually incurred (should be ~$0 or ~$0.0001 depending on path)

## Future work this enables (NOT in scope)

- **If OAuth works:** auto-pipeline Claude path defaults can change (`--auto-pipeline-use-claude` becomes safe-by-default, since cost goes to Max not console). Spec change to re-evaluate the two-flag-opt-in rule.
- **If OAuth fails:** auto-pipeline Claude path documentation should add explicit "set ANTHROPIC_API_KEY first" instruction. Possibly add a startup check that errors if Claude path requested without console key.
- **Either way:** if `gemma-apl-quality-lift` (separate spec) doesn't lift pass rate enough, this probe outcome decides whether to pivot to Claude path or stay on Gemma + iterate.

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Smallest unblocking spec on the OPEN list. Recommended ordering: do this BEFORE `gemma-apl-quality-lift` if Claude path is the desired escape hatch from low Gemma pass rate.
