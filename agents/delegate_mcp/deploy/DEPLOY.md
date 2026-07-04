# Delegate MCP — deployment snapshot (out-of-repo files)

The delegate MCP's CODE lives in this repo (`harness/agents/delegate_mcp/`,
`harness/agents/routing.yaml`, `harness/agents/ollama_client.py`). But four
touchpoints must live at the **workspace root** (`E:\vscode ai project\`), which
is NOT a git repo — so they are snapshotted here for version control + backup.
The LIVE copies at those paths are what Claude Code actually loads.

## The four out-of-repo touchpoints

1. **`.claude/skills/delegate/SKILL.md`** (workspace root)
   Live copy of `deploy/delegate.SKILL.md`. Claude Code auto-discovers skills
   under `.claude/skills/`. To restore: copy `delegate.SKILL.md` there.

2. **`.mcp.json`** (workspace root)
   Live copy of `deploy/mcp.json`. Registers the `delegate` MCP server
   (`python -m delegate_mcp.server`, cwd + PYTHONPATH = `harness/agents`).
   Loads at Claude Code startup (one-time approval prompt). To restore: copy
   `mcp.json` to the workspace root as `.mcp.json`.

3. **`CLAUDE.md` (workspace root) — routing-rules block**
   A "## LOCAL-LLM DELEGATION (delegate MCP)" section: route mechanical
   high-output work to `mcp__delegate__run`; keep reasoning on Claude; always
   verify delegated output; routing is user-owned in `agents/routing.yaml`.
   (Edit to the shared root CLAUDE.md — not snapshotted whole to avoid drift.)

4. **`.claude/skills/council/SKILL.md` — codex line fix**
   The cross-vendor seat must call `codex exec --skip-git-repo-check "..."`
   (this workspace is not a git repo; bare `codex exec` aborts). Edit to the
   shared council skill — not snapshotted whole to avoid drift.

## Restore-from-scratch (fresh clone / dead machine)
```
# from workspace root, with this repo checked out at harness/
mkdir -p .claude/skills/delegate
cp harness/agents/delegate_mcp/deploy/delegate.SKILL.md .claude/skills/delegate/SKILL.md
cp harness/agents/delegate_mcp/deploy/mcp.json .mcp.json
# then re-apply touchpoints 3 & 4 to CLAUDE.md and .claude/skills/council/SKILL.md
# (content documented above); install PyYAML into the python the MCP runs under;
# llama.cpp -> E:\tools\llama.cpp, GGUF -> E:\models (see the spec).
```

## Keeping the snapshot fresh
If you edit the live `.claude/skills/delegate/SKILL.md` or `.mcp.json`, re-copy
them here and commit. These are point-in-time backups, not symlinks — they can
drift. (A future workspace reorg may move the live files into a repo and retire
this snapshot.)
