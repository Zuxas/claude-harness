# Execution Chain — 2026-05-16 (Saturday)

**Authored:** 2026-05-15 end-of-day
**Days to RC DC:** 13
**Total estimate:** 6-9h focused
**Pre-resolved decisions** (no debate at runtime):
- Overlay mode = **companion window** (not transparent click-through)
- Window flags = `Qt.WindowStaysOnTopHint | Qt.Tool`
- Toggle hotkey = **Ctrl+Shift+M**
- Crash log dir = `logs/gui_crash_YYYY-MM-DD.log`
- Maps URL pattern = `https://www.google.com/maps/search/?api=1&query=<urlencoded venue>`

---

## Execution order

Run sections **strictly in this order** -- each section unblocks the next.

```
1.5a Crash logger        (30min) -- MUST be first so we capture bugs in §1
1   MTGA log QA          (1-2h)  -- walk surfaces; crash logger captures anything that fires
1.5b Thread audit        (30min) -- informed by §1 observations
1.5c Responsiveness      (45-60m) -- informed by §1 observations
4   Google Maps deeplink (30-45m) -- quick win mid-day
2   Matchup overlay      (3-4h)  -- biggest feature, last
```

---

## Section 0 — Session start (15min)

1. Read `harness/state/latest-snapshot.md`.
2. Read `harness/inbox/drift-pr--2026-05-16.md` if present.
3. Read `harness/MEMORY.md` -- 2026-05-14 / 2026-05-15 entries.
4. Check `harness/IMPERFECTIONS.md`.
5. `git pull` on mtg-meta-analyzer + harness (in case anything landed overnight).
6. Surface DAILY RHYTHM CHECK options (skip if user already wants the chain as-is).

---

## Section 1.5a — Crash instrumentation (30min, FIRST)

**Goal:** install sys.excepthook + Qt message handler so any crash during today's work writes a forensic log to disk.

### Tasks

- [ ] Create `gui/crash_handler.py`:
```python
"""Install global exception + Qt message handlers so crashes leave a
forensic trail in logs/gui_crash_YYYY-MM-DD.log instead of silently
killing the process."""
import sys
import traceback
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from PyQt6.QtWidgets import QMessageBox

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def install_handlers() -> None:
    """Call once from run_gui.py BEFORE creating QApplication."""
    sys.excepthook = _exception_hook
    qInstallMessageHandler(_qt_message_handler)


def _exception_hook(exc_type, exc_value, tb):
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOG_DIR / f"gui_crash_{datetime.now().strftime('%Y-%m-%d')}.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now().isoformat()} ===\n")
        traceback.print_exception(exc_type, exc_value, tb, file=f)
    try:
        body = "".join(traceback.format_exception(exc_type, exc_value, tb))
        QMessageBox.critical(None, "Unhandled exception", body[-2000:])
    except Exception:
        pass


def _qt_message_handler(msg_type, context, message):
    if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg,
                    QtMsgType.QtWarningMsg):
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _LOG_DIR / f"qt_msgs_{datetime.now().strftime('%Y-%m-%d')}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} [{msg_type}] {message}\n")
```

- [ ] In `run_gui.py`, add at the very top of main entry (before `QApplication`):
```python
from gui.crash_handler import install_handlers
install_handlers()
```

- [ ] Smoke test: deliberately raise an exception in a button handler (or
      via Ctrl+K palette + a bogus command), confirm log file gets written
      and modal appears.

- [ ] Commit: `feat(gui): crash + Qt message handlers logging to disk`.

---

## Section 1 — MTGA log tool QA (1-2h)

**Goal:** walk every surface from the last 2 days' work, fix bugs on the spot. Crash logger from 1.5a captures anything that explodes.

### 1.1 Launch + auto-sync

- [ ] Close any open GUI. From repo root: `python run_gui.py`.
- [ ] Verify console prints `[auto-sync] N new MTGA matches imported on launch` within ~3s (N=0 if nothing to import).
- [ ] Verify Dashboard rank label shows current rank (Platinum 2 29-29 as of 5/15 evening; will have shifted by Saturday).
- [ ] Verify label is underlined + cursor changes on hover.

### 1.2 Live tail

- [ ] In MTGA, play one ranked Bo3 match (Traditional_Ladder).
- [ ] Within 30s of match completion, statusbar should flash `MTGA watcher: 1 new match imported`.
- [ ] If active tab is Match Log or My Decks → Match History, it should auto-refresh.
- [ ] Verify new row in match_log via the GUI.

### 1.3 Match Log tab — Sync buttons

- [ ] Open Tournament → Match Log.
- [ ] Click **↻ Sync Untapped** → expect "Sync complete: N new rows".
- [ ] Click **↻ Sync MTGA** → expect "MTGA sync complete: N new matches imported".
- [ ] Orphan banner appears IF any my_deck_id IS NULL rows exist.
- [ ] Click "Resolve..." → OrphanResolverDialog walks orphans (existing feature, just smoke).

### 1.4 My Decks → Match History sub-tab

For Tokyo Prowess (id=17):
- [ ] Filter dropdown defaults to "Ranked (any)".
- [ ] Summary header shows ranked-only W-L + per-category breakdown.
- [ ] Matchup table populates with ranked-only data.
- [ ] **Mulligan analysis** section shows ranked-only buckets (this is the fix from yesterday — verify it's actually filtering).
- [ ] Switch filter to "All matches" → counts increase (includes Bo3 casual / Sealed).
- [ ] Recent Matches table on the LEFT of the splitter; Match Detail panel on the RIGHT.
- [ ] Click a Bo3 row → Match Detail populates with:
  - Per-game W/L + class (close / blowout / normal)
  - T# / mull-to / life endpoints
  - SB plan with **target on counter casts** ("You cast Annul → targets: High Noon")
  - Canonical-vs-actual diff IF matchup exists in saved_sb_plans
- [ ] Click **▶ Watch replay** → popup opens.
- [ ] Verify transcript shows:
  - Opening hand at top of each game
  - Mulligan KEEP/MULL decisions
  - Cards drawn ("You draw X", "Kajar draws a card")
  - Lands played, spells cast, resolves
  - Counterspells with target attribution
  - Scry top/bottom with card names
  - Declare attackers / blockers
  - Damage, tokens, +1/+1 counters
  - Life changes color-coded red/green

### 1.5 Ladder sub-tab (Mythic decklist ingestion)

- [ ] Meta → Ladder.
- [ ] **↻ Cache local** button works → "Decklists: N written, ..."
- [ ] Click a Mythic leaderboard row → decklist panel below populates with main + SB.
- [ ] Right-click row → "Save to My Decks" → confirm dialog.
- [ ] **↻ Pull current top 30** triggers an actual network pull (rate-limited, ~15-30s).

### 1.6 Dashboard

- [ ] Click rank label → progression chart popup opens.
- [ ] Format dropdown switches Constructed / Limited (data may be sparse for Limited).
- [ ] Win Rate Over Time chart is the DEFAULT (not Meta Share).
- [ ] Format dropdown "all" option works (cross-format query).
- [ ] Refresh button updates rank label.

### 1.7 Known issues to look for

- Any cut-off text / wrong widths in tables
- Date sort issues
- Per-game stats panel empty for old matches (acceptable — pre-feature import)
- 5c Lute matches still labeled "Deck" by opp classifier (real gap; defer to seed-archetype work later)

### 1.8 Bug fix sweep

For every bug found above:
- [ ] Quick fix on the spot if <15min
- [ ] If >15min, add to IMPERFECTIONS.md + move on (don't derail QA)
- [ ] Commit each fix separately with `fix(gui): <description>`

---

## Section 1.5b — Thread lifecycle audit (30min)

**Goal:** the "GUI closes randomly" complaint may be a thread joining/cleanup issue. Audit + fix any obvious gaps.

### Tasks

- [ ] Grep `gui/tabs/` for `DataLoadWorker(`:
  ```
  rtk grep "DataLoadWorker(" gui/tabs/
  ```
  For each tab, verify the worker is either:
  - Held in a `self._*_worker = w` reference (cleanup possible)
  - Cancelled in tab's `cleanup()` method (if present)

- [ ] Add a `cleanup()` method to any tab that holds workers but doesn't:
```python
def cleanup(self):
    for attr in ("_panel_worker", "_chart_worker", "_mtga_sync_worker", "_fetch_worker"):
        w = getattr(self, attr, None)
        if w is not None:
            try:
                w.cancel()
                w.wait(2000)  # 2s join
            except Exception:
                pass
            setattr(self, attr, None)
```

- [ ] Verify `gui/main_window.py:closeEvent` calls `cleanup()` on all tabs before super().closeEvent.

- [ ] Verify `MtgaLogWatcher.stop()` is called in closeEvent (already is per 5/14 ship).

- [ ] Test: open GUI, click around tabs, close — check no zombie processes in Task Manager. Check gui_crash log for any messages.

- [ ] Commit: `fix(gui): clean worker lifecycle on tab + window close`.

---

## Section 1.5c — Responsiveness profiling (45-60min)

**Goal:** identify and fix the top 2-3 UI-thread hot spots. Don't refactor everything.

### Tasks

- [ ] **Hot spot 1: `_refresh_orphan_banner` synchronous COUNT(*).** Match Log tab calls `_ensure_table()` + `SELECT COUNT(*)` on every tab show. Cache the count; only re-query after sync or on explicit refresh.
  - File: `gui/tabs/match_log.py`
  - Pattern: add `self._orphan_count_cache = None`; check + use cache in `_refresh_orphan_banner`; invalidate in `_on_sync_*` methods.

- [ ] **Hot spot 2: Watch Replay first-build is sync.** First click on a match's Watch Replay can take 1-2s parsing Player.log; UI freezes during that time. Move to worker.
  - File: `gui/widgets/replay_transcript_dialog.py`
  - Pattern: in `_load`, the `build_transcript` call should be in a DataLoadWorker, with the QTextEdit showing "Parsing log..." during the wait.

- [ ] **Hot spot 3: QTableWidget repaint flicker.** Match History recent-matches table flickers on filter change because we don't gate updates.
  - Files: `gui/widgets/deck_match_history.py`, `gui/tabs/match_log.py`
  - Pattern: in `_render_recent` / `_load_matches`, wrap:
    ```python
    table.setUpdatesEnabled(False)
    table.setSortingEnabled(False)
    # ... populate ...
    table.setSortingEnabled(True)
    table.setUpdatesEnabled(True)
    ```

- [ ] Test each fix in isolation by clicking around the GUI.

- [ ] Commit each as `perf(gui): <description>`.

---

## Section 4 — My Events Google Maps deeplink (30-45min)

**Goal:** right-click an event in My Events → open Google Maps to the venue.

### Tasks

- [ ] Identify the "My Events" tab. Most likely candidates:
  - Tournament Prep → Event Finder (`gui/tabs/event_finder_tab.py`)
  - Tournament Prep → Event Hub (`gui/tabs/event_hub_tab.py`)
  - Decks tab → ? (depends on label match)
  Ask the user if ambiguous.

- [ ] Find the event-row context-menu handler in that tab.

- [ ] Add a new action: `📍 Open venue in Google Maps`.

- [ ] Build URL:
```python
import urllib.parse
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

def open_event_in_maps(event_name: str, city: str = "", state: str = ""):
    parts = [p for p in (event_name, city, state) if p]
    query = " ".join(parts)
    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/maps/search/?api=1&query={encoded}"
    QDesktopServices.openUrl(QUrl(url))
```

- [ ] Handle the no-venue case: if event_name starts with "MTGO" or contains "Online", grey out / skip the action.

- [ ] Test with 3 real entries — verify Google Maps opens to the right place.

- [ ] Commit: `feat(events): right-click 'Open venue in Google Maps'`.

---

## Section 2 — Matchup notes overlay (3-4h)

**Goal:** companion window that shows the canonical SB plan + notes for the currently-active matchup. Updates as new matches land.

### 2.1 New widget: `gui/widgets/matchup_overlay.py` (~1.5h)

- [ ] Skeleton:
```python
"""Always-on-top companion window with SB plan + matchup notes for
the currently-active MTGA match.

Reads latest match_log row with source='mtga_log' to determine
(my_deck_id, opp_archetype). Pulls canonical plan from saved_sb_plans
via analysis.sb_plan_diff._find_canonical_plan. Pulls free-text
notes from matchup_notes (deck-keyed) if any. Auto-refreshes when
MtgaLogWatcher.matches_imported fires.
"""
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

import gui.theme as theme


class MatchupOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(
            f"background: {theme.BG}; color: {theme.TEXT}; "
            f"border: 2px solid {theme.ACCENT};"
        )
        self.setMinimumSize(360, 460)
        self._drag_pos = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        self._header = QLabel("<b>Matchup overlay</b>")
        self._header.setStyleSheet(f"color: {theme.ACCENT};")
        v.addWidget(self._header)
        self._content = QLabel("Loading...")
        self._content.setTextFormat(Qt.TextFormat.RichText)
        self._content.setWordWrap(True)
        self._content.setAlignment(Qt.AlignmentFlag.AlignTop)
        v.addWidget(self._content, 1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.hide)
        v.addWidget(close_btn)

    # Frameless windows need manual drag handling
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def refresh(self):
        """Re-query latest match + canonical plan, render."""
        from db.database import get_connection
        from analysis.sb_plan_diff import _find_canonical_plan
        from db.saved_decks import get_decks
        with get_connection() as c:
            row = c.execute(
                "SELECT my_deck_id, opp_deck, opp_name FROM match_log "
                "WHERE source='mtga_log' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                self._content.setText("<i>No MTGA matches yet.</i>")
                return
            my_deck_id = row["my_deck_id"]
            opp = row["opp_deck"] or "?"
            opp_name = row["opp_name"] or "?"
            deck = next((d for d in get_decks() if d["id"] == my_deck_id), None)
            deck_name = deck["name"] if deck else "?"
            plan = _find_canonical_plan(c, my_deck_id, opp) if my_deck_id else None
            # Also pull matchup_notes if table has rows for this pair
            note_row = c.execute(
                "SELECT notes FROM matchup_notes "
                "WHERE my_deck = ? AND opp_deck = ? LIMIT 1",
                (deck_name if deck else "", opp),
            ).fetchone() if my_deck_id else None
            notes = (note_row["notes"] if note_row else "") or ""

        parts = [
            f"<b style='font-size:13px;'>{deck_name}</b>",
            f"<span style='color:{theme.TEXT_DIM};font-size:11px;'>"
            f"vs {opp_name} ({opp})</span>",
            "<hr/>",
        ]
        if plan:
            import json
            in_cards = json.loads(plan["play_in"] or "[]")
            out_cards = json.loads(plan["play_out"] or "[]")
            from collections import Counter
            in_c = Counter(in_cards)
            out_c = Counter(out_cards)
            parts.append(f"<b>Canonical plan ({plan['difficulty']}):</b>")
            parts.append("<b style='color:#80c890;'>IN:</b>")
            for nm, q in in_c.most_common():
                parts.append(f"&nbsp;&nbsp;+{q} {nm}")
            parts.append("<br/><b style='color:#d88060;'>OUT:</b>")
            for nm, q in out_c.most_common():
                parts.append(f"&nbsp;&nbsp;-{q} {nm}")
        else:
            parts.append(
                f"<i style='color:{theme.TEXT_DIM};'>No canonical SB plan "
                f"stored for {opp} -- add one via My Decks → SB Plans tab.</i>"
            )
        if notes:
            parts.append("<hr/><b>Notes:</b>")
            parts.append(notes.replace("\n", "<br/>"))
        self._content.setText("<br/>".join(parts))
```

### 2.2 Wire into MainWindow (~30min)

- [ ] In `gui/main_window.py.__init__`, after the watcher init:
```python
from gui.widgets.matchup_overlay import MatchupOverlay
self._matchup_overlay = MatchupOverlay()
# Auto-refresh on new match
self._mtga_watcher.matches_imported.connect(
    lambda _n: self._matchup_overlay.refresh()
)
```

- [ ] Add toggle hotkey (Ctrl+Shift+M):
```python
from PyQt6.QtGui import QKeySequence, QShortcut
self._overlay_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
self._overlay_shortcut.activated.connect(self._toggle_matchup_overlay)
```

- [ ] Add toggle method:
```python
def _toggle_matchup_overlay(self):
    if self._matchup_overlay.isVisible():
        self._matchup_overlay.hide()
    else:
        self._matchup_overlay.refresh()
        self._matchup_overlay.show()
```

- [ ] Add palette command (optional but nice): "> Toggle matchup overlay" in `gui/widgets/_palette_actions.py`.

### 2.3 Persist position (~15min)

- [ ] Save geometry to `ui_state.overlay_geometry` on hide/close.
- [ ] Restore on show.

### 2.4 Smoke test (~30min)

- [ ] Open overlay (Ctrl+Shift+M).
- [ ] Verify it shows the latest match's matchup with plan if available.
- [ ] Drag to reposition.
- [ ] Hide / show — position persists.
- [ ] Play a new MTGA match → within 30s, overlay refreshes automatically.
- [ ] Test "no canonical plan" path with a fresh opp archetype.

- [ ] Commit: `feat(gui): matchup notes overlay (Ctrl+Shift+M)`.

---

## Section 3 — End of day (15min)

- [ ] Author `harness/plan-2026-05-17-execution-chain.md`.
- [ ] Update `mtg-meta-analyzer/CLAUDE.md` + `NEXT_STEPS.md`.
- [ ] Commit + push all repos.

---

## Backlog (defer if time runs short)

- 5c Lute archetype seed (~20-30min)
- Tokyo Prowess canonical SB plans for missing matchups (~45-60min)
- EV vs Field projection refresh + baseline check (~30min)
- Damage breakdown per source (~45min)
- Cards-played-on-curve analysis (~45-60min)
- Rank progression: trigger snapshot on every new ranked match (not just every 30s tick) (~15min)
- Visual board replay viewer v0.7 (6-10h, post-RC)

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If pivoting away from mtg-meta-analyzer at morning DAILY RHYTHM CHECK:
- mtg-sim — Phase 3.5 Stages D-K
- harness — skill-system spec (15d stale)
- APLs — Pioneer L1 backlog
- website — Latent
- calibration — Stable

---

## Standing-by note

Per Rule 7: after each completed section, surface options (continue /
pivot / break / drift-detect). User decides. Don't nudge.

13 days to RC DC.
