"""_ollama_model_available must match the exact name:tag (#4).

The old check used startswith(family), so asking for gemma4:26b matched an
installed gemma4:latest -- the preference chain never fell back and the later
generate call failed. These tests mock /api/tags.

Run: python agents/scripts/test_ollama_model_available.py
"""
import json
import os
import sys
import urllib.request
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_pipeline


@contextmanager
def _tags(*names):
    """Mock /api/tags to report exactly these installed model names."""
    payload = json.dumps({"models": [{"name": n} for n in names]}).encode()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return payload

    with mock.patch.object(urllib.request, "urlopen", lambda *a, **k: _Resp()):
        yield


def test_sibling_tag_is_not_a_match():
    # The bug: only gemma4:latest installed, asking for gemma4:26b.
    with _tags("gemma4:latest", "qwen2.5-coder:7b"):
        assert auto_pipeline._ollama_model_available("gemma4:26b") is False
        assert auto_pipeline._ollama_model_available("qwen2.5-coder:14b") is False


def test_exact_tag_matches():
    with _tags("gemma4:26b", "gemma4:latest"):
        assert auto_pipeline._ollama_model_available("gemma4:26b") is True
        assert auto_pipeline._ollama_model_available("gemma4:latest") is True


def test_bare_name_means_latest():
    with _tags("gemma4:latest"):
        assert auto_pipeline._ollama_model_available("gemma4") is True
    with _tags("gemma4:26b"):
        # bare "gemma4" -> gemma4:latest, which is NOT installed here
        assert auto_pipeline._ollama_model_available("gemma4") is False


def test_network_error_is_false():
    def _boom(*a, **k):
        raise OSError("connection refused")
    with mock.patch.object(urllib.request, "urlopen", _boom):
        assert auto_pipeline._ollama_model_available("gemma4:latest") is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_ollama_model_available: OK")
