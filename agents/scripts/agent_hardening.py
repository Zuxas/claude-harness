"""
agent_hardening.py — Production hardening utilities for harness agents.

Provides: circuit breakers, idempotency guards, loop control,
structured logging, and Ollama health checks.

Based on: Agentic AI for Engineers (Nagasubramanian 2026)
- Circuit breakers for external service failures
- Idempotency keys for non-repeatable operations
- Loop control with max-step and no-progress cutoffs
- Tool contracts with input/output validation
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, date
from functools import wraps
import urllib.request

HARNESS_ROOT = Path("E:/vscode ai project/harness")
STATE_DIR = HARNESS_ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Circuit breaker for external services (Ollama, APIs).

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery)

    After `failure_threshold` consecutive failures, circuit opens.
    After `recovery_timeout` seconds, allows one test request (half-open).
    If test succeeds, circuit closes. If it fails, circuit reopens.
    """

    def __init__(self, name, failure_threshold=3, recovery_timeout=60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def can_execute(self):
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"

    def __repr__(self):
        return f"CircuitBreaker({self.name}, state={self.state}, failures={self.failures})"


# Global circuit breakers
ollama_breaker = CircuitBreaker("ollama", failure_threshold=3, recovery_timeout=120)
sim_breaker = CircuitBreaker("mtg-sim", failure_threshold=2, recovery_timeout=60)


def check_ollama_health(timeout=5):
    """Quick health check for Ollama. Returns True if responsive."""
    if not ollama_breaker.can_execute():
        return False
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                ollama_breaker.record_success()
                return True
    except Exception:
        ollama_breaker.record_failure()
    return False


def require_ollama(func):
    """Decorator that checks Ollama health before executing."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_ollama_health():
            state = ollama_breaker.state
            if state == "OPEN":
                print(f"[CIRCUIT BREAKER] Ollama circuit OPEN — skipping {func.__name__} "
                      f"(will retry after {ollama_breaker.recovery_timeout}s)")
            else:
                print(f"[CIRCUIT BREAKER] Ollama unreachable — skipping {func.__name__}")
            return {"status": "ollama_unavailable", "circuit": state}
        return func(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Idempotency Guard
# ---------------------------------------------------------------------------

class IdempotencyGuard:
    """Prevents duplicate execution of nightly/scheduled jobs.

    Uses a JSON state file to track what ran today.
    """

    def __init__(self, state_file="run_state.json"):
        self.state_path = STATE_DIR / state_file
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"runs": {}}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    def has_run_today(self, job_name, format_name=""):
        """Check if a job already ran successfully today."""
        key = f"{job_name}:{format_name}" if format_name else job_name
        today = date.today().isoformat()
        entry = self.state["runs"].get(key, {})
        return entry.get("date") == today and entry.get("status") == "completed"

    def mark_started(self, job_name, format_name=""):
        key = f"{job_name}:{format_name}" if format_name else job_name
        self.state["runs"][key] = {
            "date": date.today().isoformat(),
            "started": datetime.now().isoformat(),
            "status": "running",
        }
        self._save()

    def mark_completed(self, job_name, format_name="", summary=None):
        key = f"{job_name}:{format_name}" if format_name else job_name
        entry = self.state["runs"].get(key, {})
        entry.update({
            "date": date.today().isoformat(),
            "completed": datetime.now().isoformat(),
            "status": "completed",
        })
        if summary:
            entry["summary"] = summary
        self.state["runs"][key] = entry
        self._save()

    def mark_failed(self, job_name, format_name="", error=""):
        key = f"{job_name}:{format_name}" if format_name else job_name
        entry = self.state["runs"].get(key, {})
        entry.update({
            "date": date.today().isoformat(),
            "failed": datetime.now().isoformat(),
            "status": "failed",
            "error": str(error)[:500],
        })
        self.state["runs"][key] = entry
        self._save()

    def get_status(self):
        """Get a summary of today's runs for dashboard display."""
        today = date.today().isoformat()
        today_runs = {k: v for k, v in self.state["runs"].items()
                      if v.get("date") == today}
        return today_runs


# ---------------------------------------------------------------------------
# Loop Control
# ---------------------------------------------------------------------------

class LoopController:
    """Prevents runaway loops with max iterations, time budgets,
    and no-progress detection.

    Usage:
        ctrl = LoopController(max_steps=20, time_budget=600, stall_limit=3)
        for i in range(100):
            if not ctrl.can_continue():
                print(ctrl.stop_reason)
                break
            result = do_work()
            ctrl.step(progress=result.improved)
    """

    def __init__(self, max_steps=50, time_budget=600, stall_limit=5):
        self.max_steps = max_steps
        self.time_budget = time_budget  # seconds
        self.stall_limit = stall_limit  # consecutive no-progress steps
        self.steps = 0
        self.stalls = 0
        self.start_time = time.time()
        self.stop_reason = ""

    def can_continue(self):
        elapsed = time.time() - self.start_time

        if self.steps >= self.max_steps:
            self.stop_reason = f"Max steps reached ({self.max_steps})"
            return False
        if elapsed > self.time_budget:
            self.stop_reason = f"Time budget exceeded ({elapsed:.0f}s > {self.time_budget}s)"
            return False
        if self.stalls >= self.stall_limit:
            self.stop_reason = f"No progress for {self.stall_limit} consecutive steps"
            return False
        return True

    def step(self, progress=True):
        self.steps += 1
        if progress:
            self.stalls = 0
        else:
            self.stalls += 1

    def summary(self):
        elapsed = time.time() - self.start_time
        return {
            "steps": self.steps,
            "elapsed": round(elapsed, 1),
            "stalls": self.stalls,
            "stop_reason": self.stop_reason or "completed",
        }


# ---------------------------------------------------------------------------
# Structured Logger
# ---------------------------------------------------------------------------

class AgentLogger:
    """Structured logger that writes to both console and persistent log file.

    All agent scripts should use this instead of bare print().
    """

    def __init__(self, agent_name, log_dir=None):
        self.agent_name = agent_name
        self.log_dir = Path(log_dir) if log_dir else HARNESS_ROOT / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.today = date.today().isoformat()
        self.log_path = self.log_dir / f"{agent_name}-{self.today}.log"
        self.entries = []

    def _write(self, level, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] [{self.agent_name}] {msg}"
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.entries.append({"time": ts, "level": level, "msg": msg})

    def info(self, msg):
        self._write("INFO", msg)

    def warn(self, msg):
        self._write("WARN", msg)

    def error(self, msg):
        self._write("ERROR", msg)

    def success(self, msg):
        self._write("OK", msg)

    def section(self, title):
        self._write("----", f"--- {title} ---")

    def get_errors(self):
        return [e for e in self.entries if e["level"] == "ERROR"]

    def get_summary(self):
        errors = len(self.get_errors())
        total = len(self.entries)
        return f"{self.agent_name}: {total} entries, {errors} errors"


# ---------------------------------------------------------------------------
# Nightly Dashboard
# ---------------------------------------------------------------------------

def write_dashboard(guard=None):
    """Write a single-page dashboard showing today's system status.

    Reads from: IdempotencyGuard state, log files, nightly reports.
    Writes to: harness/dashboard.md
    """
    today = date.today().isoformat()

    if guard is None:
        guard = IdempotencyGuard()

    runs = guard.get_status()

    lines = [
        f"# Harness Dashboard - {today}",
        f"_Auto-generated. Do not edit._",
        f"",
        f"## Job Status",
        f"| Job | Status | Time |",
        f"|-----|--------|------|",
    ]

    for job, info in sorted(runs.items()):
        status = info.get("status", "unknown")
        icon = {"completed": "[OK]", "failed": "[FAIL]", "running": "[...]"}.get(status, "[?]")
        time_str = info.get("completed", info.get("failed", info.get("started", "")))
        if time_str:
            time_str = time_str.split("T")[1][:8] if "T" in time_str else time_str
        lines.append(f"| {job} | {icon} {status} | {time_str} |")

    if not runs:
        lines.append(f"| _(no jobs today)_ | | |")

    # Check for errors in today's logs
    log_dir = HARNESS_ROOT / "logs"
    error_lines = []
    for log_file in log_dir.glob(f"*-{today}.log"):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if "[ERROR]" in line:
                    error_lines.append(f"- `{log_file.name}`: {line.strip()}")

    if error_lines:
        lines.extend(["", "## Errors", *error_lines[:20]])
    else:
        lines.extend(["", "## Errors", "None today."])

    # Check nightly report
    nightly = HARNESS_ROOT / "knowledge" / "mtg" / f"nightly-{today}.md"
    if nightly.exists():
        lines.extend(["", f"## Nightly Report", f"See: [nightly-{today}.md](knowledge/mtg/nightly-{today}.md)"])

    lines.extend(["", f"_Generated: {datetime.now().strftime('%H:%M:%S')}_"])

    dashboard_path = HARNESS_ROOT / "dashboard.md"
    dashboard_path.write_text("\n".join(lines), encoding="utf-8")
    return str(dashboard_path)
