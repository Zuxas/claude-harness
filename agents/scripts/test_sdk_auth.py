"""Tests for #30: the SDK auth path routes OAuth vs API-key credentials the same
way the raw-HTTP path does, so an sk-ant-oat token never rides x-api-key.

Run: python -I agents/scripts/test_sdk_auth.py   (from repo root)

The classification tests are pure (no SDK). The header test runs against the
installed anthropic SDK via a mocked transport when importable, and prints a skip
line otherwise -- so it proves Bearer here without requiring anthropic in CI.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_auth as ha


def test_sdk_kwargs_routes_oauth_to_auth_token():
    assert ha.sdk_auth_kwargs("sk-ant-oat-ABC") == {"auth_token": "sk-ant-oat-ABC"}
    # a literal 'Bearer ' prefix is stripped before classification
    assert ha.sdk_auth_kwargs("Bearer sk-ant-oat-ABC") == {"auth_token": "sk-ant-oat-ABC"}


def test_sdk_kwargs_routes_api_key_to_api_key():
    assert ha.sdk_auth_kwargs("sk-ant-api03-XYZ") == {"api_key": "sk-ant-api03-XYZ"}


def test_credential_kind():
    assert ha.credential_kind("sk-ant-oat-ABC") == "oauth"
    assert ha.credential_kind("Bearer sk-ant-oat-ABC") == "oauth"
    assert ha.credential_kind("sk-ant-api03-XYZ") == "api_key"


def test_sdk_and_raw_agree_on_bearer_vs_key():
    # For every credential type the two paths must agree: a token that goes
    # Bearer on raw HTTP goes auth_token on the SDK; an x-api-key token goes
    # api_key.
    for tok, bearer in [("sk-ant-oat-1", True), ("sk-ant-api03-2", False)]:
        raw = ha.auth_header(tok)
        sdk = ha.sdk_auth_kwargs(tok)
        raw_bearer = "Authorization" in raw
        sdk_bearer = "auth_token" in sdk
        assert raw_bearer == bearer == sdk_bearer, (tok, raw, sdk)


def test_oauth_kwargs_produce_bearer_header_live():
    # Version-independent assertion: auth_token= always yields Authorization:
    # Bearer. Verified against the installed SDK via a mocked transport; skipped
    # where the SDK (or its http lib) isn't importable.
    try:
        import anthropic
        try:
            import httpx2 as hx  # anthropic >= 2.x
        except ImportError:
            import httpx as hx   # anthropic 0.x/1.x
    except ImportError:
        print("  skip test_oauth_kwargs_produce_bearer_header_live (anthropic not installed)")
        return

    captured = {}

    def handler(request):
        captured.update(dict(request.headers))
        return hx.Response(200, json={
            "id": "m", "type": "message", "role": "assistant", "model": "c",
            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1}})

    client = anthropic.Anthropic(
        http_client=hx.Client(transport=hx.MockTransport(handler)),
        **ha.sdk_auth_kwargs("sk-ant-oat-FAKE"))
    try:
        client.messages.create(model="c", max_tokens=1,
                               messages=[{"role": "user", "content": "hi"}])
    except Exception:
        pass  # network layer is mocked; we only need the captured headers
    assert captured.get("authorization") == "Bearer sk-ant-oat-FAKE", captured
    assert "x-api-key" not in captured, "OAuth token leaked onto x-api-key"
    print("  (live header check: Authorization: Bearer confirmed)")


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_sdk_auth: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
