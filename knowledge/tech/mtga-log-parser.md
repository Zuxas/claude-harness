---
title: "MTGA Log Parser"
domain: "tech"
last_updated: "2026-04-15"
confidence: "high"
sources: ["live-testing", "mtga-log-analysis"]
---

## Summary
Python module that parses MTGA Player.log files to extract match results,
opponent names, play/draw, mulligan counts, and full decklists. Saves to
the Meta Analyzer's `match_log` SQLite table with dedup via `arena_match_id`.

## Architecture
- **Core**: `mtg-meta-analyzer/scrapers/mtga_log_parser.py`
- **Wrapper**: `harness/scripts/parse-mtga.ps1`
- **Card cache**: `mtg-meta-analyzer/data/arena_card_cache.json` (23,709 entries)

## Data Extraction
| Field | Source Event | Notes |
|-------|-------------|-------|
| Match result | `MatchGameRoomStateChangedEvent` (MatchCompleted) | `finalMatchResult.resultList` |
| Per-game W/L | `resultList` entries with `scope: MatchScope_Game` | `winningTeamId` vs your teamId |
| Opponent name | `reservedPlayers[].playerName` | From match start event |
| Play/draw | `GREMessageType_DieRollResultsResp` | Highest roll = play |
| Mulligan count | `GameStateMessage.players[].mulliganCount` | Per-game tracking |
| Deck (card IDs) | `GREMessageType_ConnectResp.deckMessage` | Arena GRP IDs |
| Event type | `reservedPlayers[].eventId` | e.g. "DirectGameTournamentMode" |
| Bo1 vs Bo3 | `matchWinCondition` in GameStateMessage | "MatchWinCondition_Best2of3" |

## Card ID Resolution
Arena uses internal GRP IDs (not Scryfall arena_id). Resolution chain:
1. Local JSON cache (`data/arena_card_cache.json`)
2. MTGA's own SQLite card database (`F:\SteamLibrary\...\Raw_CardDatabase_*.mtga`)
   - `Cards.GrpId` JOIN `Localizations_enUS` on `TitleId = LocId`
3. Scryfall API fallback (`/cards/arena/{id}`)

The MTGA database is authoritative — 23,709 entries, 100% resolution.
Scryfall only covers ~16,434 arena_ids and misses newer sets.

## Identity
- User ID: `GCIUQPR6DRC4XL7L2ZTNU2OMNI`
- Player name: `Zaxos`
- Team ID varies per match (check reservedPlayers)

## Log Locations
- Current: `%LOCALAPPDATA%\..\LocalLow\Wizards Of The Coast\MTGA\Player.log`
- Previous: `...Player-prev.log`
- MTGA rotates logs — Player.log is current session, Player-prev.log is prior

## DB Integration
- Writes to `match_log` table via `db.match_log.save_match()`
- Added `arena_match_id TEXT` column + unique index for dedup
- Tags: format (default "standard"), deck name (user-specified)

## Usage
```bash
# CLI
python -m scrapers.mtga_log_parser --all --resolve-cards --summary --deck "Dimir Tempo"

# Harness wrapper
powershell -ExecutionPolicy Bypass -File harness/scripts/parse-mtga.ps1 -All -Deck "Dimir Tempo"
```

## Known Limitations
- Format detection: logs say "Constructed" not "Standard" — user must specify
- Opponent deck: only your deck is visible in logs, not opponent's
- Play/draw: die roll occasionally missing in continued sessions
- Round numbers: Arena doesn't expose round numbers for events

## Related
- [[meta-analyzer]] — parent project
- [[harness-architecture]] — harness system
- Layer 4 roadmap: MTGA log parser feeds real match data into sim calibration

## Changelog
- 2026-04-15: Created — full parser with card resolution from MTGA database
