#!/usr/bin/env bash
# zuxas-lint-hook-start
# pre-commit hook -- run lint-mtg-sim.py on commits that touch lint-relevant files.
#
# Catches the class of bugs that drift-detect.ps1 catches AFTER the fact, but
# at commit time instead, when the introducer has full mental context of what
# they just did. Concrete prevention for:
#   - canonical-deck-mismatch (registry pointing at missing stub or .txt)
#   - orphan stubs in stub_decks._DB_DECKS with no APL_REGISTRY reference
#   - orphan deck files in decks/ with no APL_REGISTRY reference
#   - handler-deck mismatches (SPECIAL_MECHANICS handler for card not in deck)
#
# Bypass: git commit --no-verify  (only when you know what you're doing)
#
# Install:    cp this file to .git/hooks/pre-commit && chmod +x
#   OR run:   powershell -File harness/scripts/install-pre-commit-hook.ps1
# Uninstall:  rm .git/hooks/pre-commit
#   OR run:   powershell -File harness/scripts/install-pre-commit-hook.ps1 -Remove
#
# Source of truth: harness/scripts/templates/mtg-sim-pre-commit.sh
# (.git/hooks/ is not under version control; keep this template in sync)
#
# zuxas-lint-hook-end-marker (used for safe in-place updates)

set -u

# ── Path resolution ────────────────────────────────────────────────
# git pre-commit runs from repo root by default; double-check.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "[pre-commit] ERROR: not in a git repo, skipping lint" >&2
    exit 0
fi

LINT_SCRIPT="E:/vscode ai project/harness/scripts/lint-mtg-sim.py"
if [ ! -f "$LINT_SCRIPT" ]; then
    # Lint script not available -- don't block commit, just warn quietly.
    # This keeps the hook from breaking on machines where harness/ isn't checked out.
    echo "[pre-commit] WARN: lint-mtg-sim.py not found at $LINT_SCRIPT, skipping" >&2
    exit 0
fi

# ── Scope: only run when staged files touch lint-relevant paths ────
# lint-mtg-sim.py checks: apl/__init__.py, data/stub_decks.py, apl/*.py, decks/*.txt
# If none of the staged changes touch these areas, skip lint entirely (fast path).

STAGED="$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null)"
if [ -z "$STAGED" ]; then
    # No staged files (probably an empty commit or a merge); let git handle it
    exit 0
fi

# Match lint-relevant paths. Anchored matches to avoid false hits on substrings.
RELEVANT="$(echo "$STAGED" | grep -E '^(apl/[^/]+\.py|data/stub_decks\.py|decks/[^/]+\.txt)$' || true)"
if [ -z "$RELEVANT" ]; then
    # Doc-only or unrelated commit -- skip lint, pass through silently
    exit 0
fi

# ── Run lint ──────────────────────────────────────────────────────
# Use a tempfile so concurrent git operations don't interfere.
TMP_OUT="$(mktemp -t mtg-sim-lint.XXXXXX 2>/dev/null || echo "/tmp/mtg-sim-lint.$$")"
trap 'rm -f "$TMP_OUT"' EXIT

# Resolve python -- prefer python3 then fall back to python.
# On Windows git-bash, python is usually the right one.
PYTHON_BIN="python"
if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
        PYTHON_BIN="python3"
    fi
fi

# Capture both stdout and stderr; lint emits findings to stdout
"$PYTHON_BIN" "$LINT_SCRIPT" >"$TMP_OUT" 2>&1
LINT_EXIT=$?

# ── Interpret exit code ────────────────────────────────────────────
# 0 = clean
# 1 = warnings only
# 2 = errors found -- block commit
# anything else = unexpected; surface it but don't block (degrade gracefully)

case "$LINT_EXIT" in
    0)
        # Clean. Don't print anything -- silence is the success signal.
        exit 0
        ;;
    1)
        # Warnings -- print but don't block.
        echo ""
        echo "[pre-commit] lint-mtg-sim.py reports warnings (commit proceeding):"
        echo ""
        cat "$TMP_OUT"
        echo ""
        exit 0
        ;;
    2)
        # Errors -- block.
        echo ""
        echo "═══════════════════════════════════════════════════════════════"
        echo " Commit BLOCKED: lint-mtg-sim.py found errors"
        echo "═══════════════════════════════════════════════════════════════"
        echo ""
        cat "$TMP_OUT"
        echo ""
        echo "═══════════════════════════════════════════════════════════════"
        echo " Options:"
        echo "   1. Fix the errors above and re-stage + re-commit"
        echo "   2. Verify it's intentional and bypass with: git commit --no-verify"
        echo ""
        echo " Lint script: $LINT_SCRIPT"
        echo " Run manually: python \"\$LINT_SCRIPT\" --check all"
        echo "═══════════════════════════════════════════════════════════════"
        exit 1
        ;;
    *)
        # Unexpected exit code -- print and let commit proceed.
        # Don't block on tooling failures; that's worse than a missed lint.
        echo "" >&2
        echo "[pre-commit] WARN: lint-mtg-sim.py exited unexpectedly ($LINT_EXIT)" >&2
        echo "[pre-commit] Output:" >&2
        cat "$TMP_OUT" >&2
        echo "[pre-commit] Allowing commit to proceed; investigate the lint script" >&2
        exit 0
        ;;
esac
