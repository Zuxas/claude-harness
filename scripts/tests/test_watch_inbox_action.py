"""Pins the watch-inbox.ps1 FileSystemWatcher fix (#14).

CI has no pwsh, so this is a source-scan guard. The behavioural proof lives in
the PR: a real pwsh 7.4.6 run compiled a dropped `mtg--rcq-notes.txt`, wrote the
log line, skipped a `drift-pr--` file, and produced no "$using:" error.

The bug: the Register-ObjectEvent -Action block used `$using:LogFile` and
`& $using:ProcessScript`, which throw "A Using variable cannot be retrieved..."
in an event action, and the first Add-Content sat outside the try/catch, so the
action died before ever invoking process-inbox.ps1.

Comments are stripped before scanning so the explanatory NOTE (which names the
very tokens being banned) does not trip the checks.
"""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "watch-inbox.ps1"
RAW = SCRIPT.read_text(encoding="utf-8")
# Drop each line's inline/full comment (no `#` appears inside a string in this file).
CODE = "\n".join(line.split("#", 1)[0] for line in RAW.splitlines())


def test_no_using_variables_remain():
    assert "$using:" not in CODE, "$using: does not work in a Register-ObjectEvent action"


def test_paths_passed_via_messagedata():
    assert CODE.count("-MessageData") == 2, "both Created and Changed handlers pass -MessageData"
    assert "$Event.MessageData" in CODE, "action must read paths from $Event.MessageData"


def test_action_body_is_guarded():
    # The whole action is wrapped so a failure is logged, not swallowed by the
    # event job's error stream: the try precedes the first Add-Content.
    action = CODE[CODE.index("$action = {"):]
    assert action.index("try {") < action.index("Add-Content"), "action body must be inside try/catch"


def test_drift_pr_files_are_skipped():
    assert "drift-pr--" in CODE, "the daily drift-pr-- files must be ignored, not counted as failures"
