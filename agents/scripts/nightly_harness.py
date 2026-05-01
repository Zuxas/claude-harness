"""
nightly_harness.py — Automated nightly harness job

Runs after the meta-analyzer 5 PM scraper completes.
Scheduled via Windows Task Scheduler at 5:30 PM daily.

WHAT IT DOES:
  1. Detect meta shifts via meta_change.compare_periods()
  2. Re-run APL tuner on decks whose meta% shifted >2%
  3. Parse new MTGA game logs if any exist
  4. Compile a nightly summary knowledge block
  5. Update MEMORY.md with what ran

USAGE:
  python nightly_harness.py                   # full run
  python nightly_harness.py --dry-run         # show what would happen
  python nightly_harness.py --format modern   # specific format
  python nightly_harness.py --skip-mtga       # skip MTGA parsing
"""

import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Paths
HARNESS_ROOT = Path("E:/vscode ai project/harness")
META_ANALYZER = Path("E:/vscode ai project/mtg-meta-analyzer")
SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
LOG_DIR = HARNESS_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Add meta-analyzer to path for imports
sys.path.insert(0, str(META_ANALYZER))
sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(HARNESS_ROOT / "agents" / "scripts"))

from agent_hardening import (
    IdempotencyGuard, AgentLogger, write_dashboard, check_ollama_health
)

TODAY = datetime.now().strftime("%Y-%m-%d")
TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M")
SHIFT_THRESHOLD = 0.02  # 2% meta share change triggers re-analysis

# Idempotency guard to prevent duplicate runs
guard = IdempotencyGuard()

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    log_file = LOG_DIR / f"nightly-{TODAY}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Step 1: Detect Meta Shifts
# ---------------------------------------------------------------------------

def detect_meta_shifts(format_name="modern", dry_run=False):
    """Check for significant meta changes since last analysis."""
    log(f"Checking meta shifts for {format_name}...")
    
    try:
        from analysis.meta_change import compare_periods
        result = compare_periods(format_name, weeks_current=1, weeks_prior=2)
    except Exception as e:
        log(f"Meta change detection failed: {e}", "ERROR")
        return {"shifted": [], "summary": {}, "error": str(e)}
    
    shifted = []
    for arch in result["archetypes"]:
        delta = abs(arch["share_delta"])
        if delta >= SHIFT_THRESHOLD:
            shifted.append({
                "archetype": arch["archetype"],
                "status": arch["status"],
                "delta": arch["share_delta"],
                "current_share": arch["current_share"],
                "prior_share": arch["prior_share"],
            })
            log(f"  SHIFT: {arch['archetype']} "
                f"{arch['status']} ({arch['share_delta']:+.1%}) "
                f"[{arch['prior_share']:.1%} -> {arch['current_share']:.1%}]")
    
    if not shifted:
        log(f"  No significant shifts detected (threshold: {SHIFT_THRESHOLD:.0%})")
    else:
        log(f"  {len(shifted)} archetype(s) shifted >{ SHIFT_THRESHOLD:.0%}")
    
    return {"shifted": shifted, "summary": result["summary"], "format": format_name}


# ---------------------------------------------------------------------------
# Step 2: Re-run APL Tuner on Shifted Archetypes
# ---------------------------------------------------------------------------

def retune_shifted_decks(shifted_archetypes, format_name="modern", dry_run=False):
    """Run APL tuner on rising/new decks that have matching APLs."""
    if not shifted_archetypes:
        log("No decks to retune.")
        return []
    
    # Only retune rising or new decks (not gone/falling — they're leaving the meta)
    actionable = [a for a in shifted_archetypes if a["status"] in ("rising", "new")]
    if not actionable:
        log("No rising/new decks to retune.")
        return []
    
    # Check which decks have APLs or deck files
    apl_dir = SIM_ROOT / "apl"
    deck_dir = SIM_ROOT / "decks"
    available_apls = {f.stem.lower() for f in apl_dir.glob("*.py")}
    available_decks = {f.stem.lower() for f in deck_dir.glob("*.txt")}
    
    results = []
    tuner_script = HARNESS_ROOT / "agents" / "scripts" / "apl_tuner.py"
    
    for arch in actionable:
        safe_name = arch["archetype"].lower().replace(" ", "_").replace("-", "_")
        has_apl = any(safe_name in a for a in available_apls)
        has_deck = any(safe_name in d for d in available_decks)
        if not has_apl and not has_deck:
            log(f"  SKIP: {arch['archetype']} — no APL or deck file found")
            continue
        deck_name = arch["archetype"]
        log(f"Retuning: {deck_name} ({arch['status']}, {arch['delta']:+.1%})")
        
        if dry_run:
            log(f"  [DRY RUN] Would run: apl_tuner.py \"{deck_name}\" --mode analyze")
            results.append({"deck": deck_name, "status": "dry_run"})
            continue
        
        try:
            proc = subprocess.run(
                [sys.executable, str(tuner_script), deck_name,
                 "--mode", "analyze", "--format", format_name, "--games", "500"],
                capture_output=True, text=True, timeout=300,
                cwd=str(HARNESS_ROOT.parent)
            )
            if proc.returncode == 0:
                log(f"  Tuner completed for {deck_name}")
                results.append({"deck": deck_name, "status": "completed"})
            else:
                log(f"  Tuner failed for {deck_name}: {proc.stderr[:200]}", "ERROR")
                results.append({"deck": deck_name, "status": "failed",
                               "error": proc.stderr[:200]})
        except subprocess.TimeoutExpired:
            log(f"  Tuner timed out for {deck_name}", "ERROR")
            results.append({"deck": deck_name, "status": "timeout"})
        except Exception as e:
            log(f"  Tuner error for {deck_name}: {e}", "ERROR")
            results.append({"deck": deck_name, "status": "error", "error": str(e)})
    
    return results


# ---------------------------------------------------------------------------
# Step 3: Parse MTGA Logs
# ---------------------------------------------------------------------------

def parse_mtga_logs(dry_run=False):
    """Check for new MTGA game logs and parse them."""
    log("Checking for new MTGA game logs...")
    
    parser_script = HARNESS_ROOT / "scripts" / "parse-mtga.ps1"
    
    if dry_run:
        log("  [DRY RUN] Would run: parse-mtga.ps1 -KnowledgeBlock")
        return {"status": "dry_run", "matches": 0}
    
    try:
        proc = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File",
             str(parser_script), "-KnowledgeBlock"],
            capture_output=True, text=True, timeout=120,
        )
        # Count matches from output
        output = proc.stdout
        match_count = output.count("Match saved") + output.count("match_log")
        
        if "No new matches" in output or match_count == 0:
            log("  No new MTGA matches found.")
            return {"status": "no_new_matches", "matches": 0}
        else:
            log(f"  Parsed {match_count} new match(es)")
            return {"status": "completed", "matches": match_count}
    except subprocess.TimeoutExpired:
        log("  MTGA parser timed out", "ERROR")
        return {"status": "timeout", "matches": 0}
    except Exception as e:
        log(f"  MTGA parser error: {e}", "ERROR")
        return {"status": "error", "matches": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Step 3.5: Calibration
# ---------------------------------------------------------------------------

def run_calibration_step(dry_run=False):
    """Run sim calibration if match_log has data."""
    calibrate_script = HARNESS_ROOT / "agents" / "scripts" / "calibrate.py"
    
    if dry_run:
        log("  [DRY RUN] Would run calibration")
        return {"status": "dry_run", "divergent": 0}
    
    try:
        proc = subprocess.run(
            [sys.executable, str(calibrate_script), "--min-matches", "1", "--games", "300"],
            capture_output=True, text=True, timeout=300,
            cwd=str(HARNESS_ROOT.parent)
        )
        # Parse divergent count from output
        output = proc.stdout
        divergent = output.count("divergent") + output.count("wrong")
        if "No matches found" in output:
            log("  No match data available for calibration.")
            return {"status": "no_data", "divergent": 0}
        log(f"  Calibration complete. Divergent matchups: {divergent}")
        return {"status": "completed", "divergent": divergent}
    except subprocess.TimeoutExpired:
        log("  Calibration timed out", "ERROR")
        return {"status": "timeout", "divergent": 0}
    except Exception as e:
        log(f"  Calibration error: {e}", "ERROR")
        return {"status": "error", "divergent": 0}


# ---------------------------------------------------------------------------
# Step 4: Process Inbox (any files dropped during the day)
# ---------------------------------------------------------------------------

def process_inbox(dry_run=False):
    """Process any files sitting in the inbox."""
    inbox_dir = HARNESS_ROOT / "inbox"
    files = [f for f in inbox_dir.iterdir() if f.is_file()]
    
    if not files:
        log("Inbox empty.")
        return {"status": "empty", "files": 0}
    
    log(f"Found {len(files)} file(s) in inbox.")
    
    if dry_run:
        for f in files:
            log(f"  [DRY RUN] Would compile: {f.name}")
        return {"status": "dry_run", "files": len(files)}
    
    try:
        proc = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File",
             str(HARNESS_ROOT / "scripts" / "process-inbox.ps1")],
            capture_output=True, text=True, timeout=600,
        )
        log(f"  Inbox processing complete.")
        return {"status": "completed", "files": len(files)}
    except Exception as e:
        log(f"  Inbox processing error: {e}", "ERROR")
        return {"status": "error", "files": len(files), "error": str(e)}


# ---------------------------------------------------------------------------
# Step 5: Write Nightly Summary
# ---------------------------------------------------------------------------

def write_nightly_summary(meta_result, tune_results, mtga_result, inbox_result):
    """Write a summary knowledge block and update MEMORY.md."""
    
    # Build summary block
    shifted_list = meta_result.get("shifted", [])
    tuned_count = sum(1 for r in tune_results if r["status"] == "completed")
    
    summary_lines = [
        f"---",
        f'title: "Nightly Report: {TODAY}"',
        f'domain: "mtg"',
        f'last_updated: "{TODAY}"',
        f'confidence: "high"',
        f'sources: ["nightly-harness-agent"]',
        f"---",
        f"",
        f"## Nightly Harness Report — {TODAY}",
        f"",
        f"### Meta Shifts",
    ]
    
    if shifted_list:
        for s in shifted_list:
            summary_lines.append(
                f"- **{s['archetype']}**: {s['status']} "
                f"({s['delta']:+.1%}) "
                f"[{s['prior_share']:.1%} -> {s['current_share']:.1%}]"
            )
    else:
        summary_lines.append("- No significant shifts detected.")
    
    summary_lines.extend([
        f"",
        f"### APL Tuning",
        f"- Decks retuned: {tuned_count}/{len(tune_results)}",
    ])
    for r in tune_results:
        summary_lines.append(f"  - {r['deck']}: {r['status']}")
    
    summary_lines.extend([
        f"",
        f"### MTGA Logs",
        f"- Status: {mtga_result['status']}",
        f"- New matches: {mtga_result.get('matches', 0)}",
        f"",
        f"### Inbox",
        f"- Status: {inbox_result['status']}",
        f"- Files processed: {inbox_result.get('files', 0)}",
        f"",
        f"## Changelog",
        f"- {TODAY}: Generated by nightly_harness.py",
    ])
    
    # Write nightly report block
    report_path = HARNESS_ROOT / "knowledge" / "mtg" / f"nightly-{TODAY}.md"
    report_path.write_text("\n".join(summary_lines), encoding="utf-8")
    log(f"Nightly report: {report_path}")
    
    # Update MEMORY.md
    memory_path = HARNESS_ROOT / "MEMORY.md"
    memory_entry = (
        f"\n- {TIMESTAMP}: NIGHTLY AUTO — "
        f"meta shifts: {len(shifted_list)}, "
        f"decks retuned: {tuned_count}, "
        f"MTGA matches: {mtga_result.get('matches', 0)}, "
        f"inbox files: {inbox_result.get('files', 0)}"
    )
    
    with open(memory_path, "a", encoding="utf-8") as f:
        f.write(memory_entry)
    log("MEMORY.md updated.")


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_nightly(format_name="modern", dry_run=False, skip_mtga=False,
                enable_auto_pipeline=False, auto_pipeline_use_claude=False):
    """Run the full nightly harness pipeline.

    Stage 1.5 / 2026-04-28: --enable-auto-pipeline opts into Layer 5
    auto_pipeline.py invocation between meta detection and retune. Default
    OFF so Friday's scheduled task stays in safe configuration until the
    user manually flips the flag. Default Gemma per HARNESS_STATUS.md
    design principle 2; --auto-pipeline-use-claude opts into Claude API
    (requires the second flag to bill Anthropic console; two opt-ins =
    no accidental cost).

    Spec: harness/specs/2026-04-28-auto-pipeline-nightly-integration.md
    """
    # Idempotency check: skip if already ran successfully today
    if not dry_run and guard.has_run_today("nightly", format_name):
        log(f"[IDEMPOTENT] Nightly already completed for {format_name} today. Skipping.")
        return

    if not dry_run:
        guard.mark_started("nightly", format_name)

    log(f"")
    log(f"{'='*60}")
    log(f"  NIGHTLY HARNESS JOB — {TIMESTAMP}")
    log(f"  Format: {format_name} | Dry run: {dry_run}")
    log(f"{'='*60}")
    log(f"")

    start = time.time()
    
    # Step 1: Detect meta shifts
    log("[STEP 1/4] Detecting meta shifts...")
    meta_result = detect_meta_shifts(format_name, dry_run)

    # Step 1.5: Auto-pipeline (feature-flagged, default OFF for Friday safety)
    log("")
    if enable_auto_pipeline:
        log("[STEP 1.5/N] Auto-pipeline: generating APLs for new archetypes...")
        # Default Gemma per HARNESS_STATUS design principle 2 + spec safety:
        # nightly should never bill Anthropic console accidentally. User must
        # pass BOTH --enable-auto-pipeline AND --auto-pipeline-use-claude.
        try:
            from auto_pipeline import run_pipeline as auto_run
            auto_run(
                format_name=format_name,
                use_claude=auto_pipeline_use_claude,
                dry_run=dry_run,
            )
        except Exception as e:
            log(f"  Auto-pipeline failed: {e}", level="WARN")
            log("  Continuing nightly; auto-pipeline failure does not block other steps.", level="WARN")
    else:
        log("[STEP 1.5/N] Auto-pipeline: SKIPPED (use --enable-auto-pipeline to wire)")

    # Step 2: Retune shifted decks
    log("")
    log("[STEP 2/4] Retuning shifted decks...")
    tune_results = retune_shifted_decks(
        meta_result.get("shifted", []), format_name, dry_run
    )
    
    # Step 3: Parse MTGA logs
    log("")
    log("[STEP 3/5] Parsing MTGA logs...")
    if skip_mtga:
        log("  Skipped (--skip-mtga)")
        mtga_result = {"status": "skipped", "matches": 0}
    else:
        mtga_result = parse_mtga_logs(dry_run)
    
    # Step 3.5: Calibrate sim vs real matches
    log("")
    log("[STEP 4/7] Running sim calibration...")
    calibration_result = run_calibration_step(dry_run)

    # Step 4: Run matchup gauntlet (weekly on Sundays, or if meta shifted significantly)
    log("")
    gauntlet_result = {"status": "skipped", "matchups": 0}
    significant_shifts = len([s for s in meta_result.get("shifted", []) if abs(s.get("delta", 0)) >= 0.05])
    is_sunday = datetime.now().weekday() == 6
    if is_sunday or significant_shifts >= 3:
        log(f"[STEP 5/7] Running matchup gauntlet ({'Sunday refresh' if is_sunday else f'{significant_shifts} major shifts'})...")
        gauntlet_script = HARNESS_ROOT / "agents" / "scripts" / "matchup_gauntlet.py"
        if dry_run:
            log(f"  [DRY RUN] Would run: matchup_gauntlet.py --format {format_name} --top 8 --games 500")
            gauntlet_result = {"status": "dry_run", "matchups": 0}
        else:
            try:
                proc = subprocess.run(
                    [sys.executable, str(gauntlet_script),
                     "--format", format_name, "--top", "8", "--games", "500"],
                    capture_output=True, text=True, timeout=1800,
                    cwd=str(HARNESS_ROOT.parent)
                )
                if proc.returncode == 0:
                    log(f"  Gauntlet completed for {format_name}")
                    gauntlet_result = {"status": "completed", "matchups": 28}
                else:
                    log(f"  Gauntlet failed: {proc.stderr[:200]}", "ERROR")
                    gauntlet_result = {"status": "failed", "matchups": 0}
            except subprocess.TimeoutExpired:
                log("  Gauntlet timed out (30min limit)", "ERROR")
                gauntlet_result = {"status": "timeout", "matchups": 0}
            except Exception as e:
                log(f"  Gauntlet error: {e}", "ERROR")
                gauntlet_result = {"status": "error", "matchups": 0}
    else:
        log("[STEP 5/7] Skipping gauntlet (not Sunday, no major shifts)")

    # Step 5: Generate playbooks (after gauntlet, if gauntlet ran)
    log("")
    playbook_result = {"status": "skipped", "generated": 0}
    if gauntlet_result.get("status") == "completed":
        log("[STEP 6/7] Generating playbooks from fresh gauntlet data...")
        playbook_script = HARNESS_ROOT / "agents" / "scripts" / "playbook_generator.py"
        if dry_run:
            log(f"  [DRY RUN] Would run: playbook_generator.py --format {format_name} --all")
            playbook_result = {"status": "dry_run", "generated": 0}
        else:
            try:
                proc = subprocess.run(
                    [sys.executable, str(playbook_script),
                     "--format", format_name, "--all"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(HARNESS_ROOT.parent)
                )
                if proc.returncode == 0:
                    log("  Playbooks generated")
                    playbook_result = {"status": "completed", "generated": 1}
                else:
                    log(f"  Playbook generation failed: {proc.stderr[:200]}", "ERROR")
                    playbook_result = {"status": "failed", "generated": 0}
            except Exception as e:
                log(f"  Playbook error: {e}", "ERROR")
                playbook_result = {"status": "error", "generated": 0}
    else:
        log("[STEP 6/7] Skipping playbook generation (no fresh gauntlet data)")

    # Step 6: Process inbox
    log("")
    log("[STEP 7/7] Processing inbox...")
    inbox_result = process_inbox(dry_run)
    
    # Step 5: Write summary
    log("")
    log("[SUMMARY] Writing nightly report...")
    if not dry_run:
        write_nightly_summary(meta_result, tune_results, mtga_result, inbox_result)
    
    elapsed = time.time() - start

    # Mark job completed + write dashboard
    if not dry_run:
        summary = {
            "shifts": len(meta_result.get("shifted", [])),
            "retuned": sum(1 for r in tune_results if r.get("status") == "completed"),
            "mtga_matches": mtga_result.get("matches", 0),
            "inbox_files": inbox_result.get("files", 0),
            "elapsed": round(elapsed, 1),
        }
        guard.mark_completed("nightly", format_name, summary=summary)
        write_dashboard(guard)

    log(f"")
    log(f"{'='*60}")
    log(f"  NIGHTLY COMPLETE — {elapsed:.1f}s | Cost: $0.00")
    log(f"  Meta shifts: {len(meta_result.get('shifted', []))}")
    log(f"  Decks retuned: {sum(1 for r in tune_results if r.get('status')=='completed')}")
    log(f"  MTGA matches: {mtga_result.get('matches', 0)}")
    log(f"  Inbox files: {inbox_result.get('files', 0)}")
    log(f"  Log: harness/logs/nightly-{TODAY}.log")
    log(f"  Report: harness/knowledge/mtg/nightly-{TODAY}.md")
    log(f"  Dashboard: harness/dashboard.md")
    log(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly Harness Job")
    parser.add_argument("--format", default="modern", help="Format to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--skip-mtga", action="store_true", help="Skip MTGA log parsing")
    parser.add_argument("--enable-auto-pipeline", action="store_true",
                        help="Enable Layer 5 auto_pipeline.py step (default: off; opt-in)")
    parser.add_argument("--auto-pipeline-use-claude", action="store_true",
                        help="When auto-pipeline is enabled, use Claude API instead of Gemma "
                             "(default: Gemma; both flags required to bill Anthropic)")
    args = parser.parse_args()
    
    run_nightly(args.format, args.dry_run, args.skip_mtga,
                enable_auto_pipeline=args.enable_auto_pipeline,
                auto_pipeline_use_claude=args.auto_pipeline_use_claude)
