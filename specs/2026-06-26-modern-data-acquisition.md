---
title: Modern Data-Acquisition Spec
status: PROPOSED
created: 2026-06-26
project: mtg-meta-analyzer
---

# Modern Data-Acquisition Spec

**ETHICS ANCHOR:** Sanctioned + polite acquisition only. No proxy/UA rotation, no
CAPTCHA/Cloudflare bypass, no spoofed browser fingerprints, no ban evasion. A host
that blocks us (mtgdecks.net) is **respected and replaced**, never routed around.
Every request carries an honest, descriptive User-Agent with a contact address.

---

## 1. Current reality + root cause of the mtgdecks block

### 1.1 Current pipeline reality

All scrapers live in `scrapers/` with shared rate constants in `scrapers/constants.py`
(`DELAY_DEFAULT = 1.5`, `DELAY_SCRYFALL = 0.1`, `DELAY_MYTHICSPOILER = 1.0`). Every
source writes through `upsert_event` / `upsert_deck` / `insert_deck_cards`
(`db/database.py` lines 19-50) and is tagged by the `events.source` column
(`mtgtop8`, `mtgdecks`, `spicerack`, ...).

| Source | File | Fetch | Throttle | Modern decklists? |
|---|---|---|---|---|
| MTGTop8 recent | `scrapers/mtgtop8.py` | `requests` + `HEADERS_MINIMAL` | 1.5s/req | YES (`FORMATS_MTGTOP8["modern"]="MO"`) |
| MTGTop8 backfill | `scrapers/backfill.py` | reuses `mtgtop8._get` | 1.5s/req | YES (`YEAR_META["modern"]` 2022-2026) |
| MTGO Challenges | `scrapers/challenges.py` | reuses mtgtop8 | 1.5s/req | YES (Modern Challenge 32/64) |
| MTGDecks decklists | `scrapers/mtgdecks.py` | **cloudscraper** + `HEADERS_FULL` | 2.5-5.0s/req | YES (**BLOCKED**) |
| MTGDecks winrates | `scrapers/matchup_scraper.py` | cloudscraper | none | matchup matrix only |
| Spicerack RCQ/paper | `scrapers/spicerack_scraper.py` | urllib → `api.spicerack.gg` + Moxfield | 0.5s | YES (default = Modern) |
| MTGMelee matches | `scrapers/mtgmelee_scraper.py` | **cloudscraper** POST/GET | per-run pages | match W/L, not decklists |
| Scryfall | `scrapers/scryfall.py` | bulk JSON + live API | 0.1s | card enrichment only |
| Untapped | `scrapers/untapped_*.py` | urllib public + premium | M/W/F gate, ~2 r/s | Arena ladder meta, NOT paper/Modern |

### 1.2 Confirmed block status

WebFetch of `https://mtgdecks.net/robots.txt` returned **HTTP 403 on 2026-06-26** — we
cannot even read robots.txt. This is an IP/Cloudflare-level deny, not a JS challenge or
path rule. It corroborates `harness/MEMORY.md:498-500` (2026-05-15: "MTGDecks 403
hard-block — vanilla curl + cloudscraper + Scrapling all 403... No scraper bypass
possible from this IP"). Last mtgdecks row in `mtg_meta.db` is dated 2026-05-05. Because
robots.txt itself 403s, there is no readable ToS/Crawl-delay to define a "polite resume,"
so drop+replace is the only sanctioned route.

### 1.3 Root cause (not the delay — the volume + cadence + no abort)

The per-request delay (2.5-5.0s, `scrapers/mtgdecks.py:36-37,74`) was actually polite.
The ban came from four compounding drivers:

- **Driver A — fan-out volume.** `fill_database.step_mtgdecks()` (lines 159-187) hardcodes
  `MTGDECKS_PAGES = 5`, `min_players=32` (below the module default 50, widening the net),
  and `HIGH_SIGNAL_KEYWORDS` force-include events regardless of size. `_process_event`
  (`scrapers/mtgdecks.py:432-448`) issues **one HTTP request per deck**. Cost ≈
  `formats × 5 pages × events/page × (1 + decks/event)`. A single Challenge 64 = 65
  requests; a full 3-format rebuild ≈ **7,500-11,000 sequential cloudscraper hits in one run.**
- **Driver B — automated cadence (the actual trip-wire).** That volume formerly ran on a
  Task-Scheduler M/W/F gate (`scripts/run_fill_from_prefs.py:61-66`), unattended, from one
  IP via the same cloudscraper fingerprint. Sustained automated pattern → protection tripped.
  Hard-disabled 2026-06-04.
- **Driver C — no circuit breaker.** `_get` (`scrapers/mtgdecks.py:65-87`) retries each URL
  3× on 403 with a 5-10s sleep, then `_process_event` moves to the next URL and tries again.
  No global "N consecutive 403s → abort," so once Cloudflare started blocking, the scraper
  kept hammering every remaining URL, **reinforcing** the block.
- **Driver D — uncapped backfill.** `backfill_missing_cards` (lines 487-530) loops over every
  deck with missing cards, capped only if `--limit` is passed.

---

## 2. RANKED source plan

### Card data (complementary, no new scraping — see §6)
- **Scryfall** (`scrapers/scryfall.py`) — canonical card/oracle layer. Already integrated.
- **MTGJSON** — optional bulk card/set alternative.

### Tournament decklists / results / meta share

| Rank | Source | Access method | Auth | Documented limits | Modern coverage | Sanctioned vs scrape |
|---|---|---|---|---|---|---|
| **1 (PRIMARY)** | **MTGO official decklists** `https://www.mtgo.com/decklists` | HTML page w/ embedded JSON blob (`window.MTGO.decklists.data`); per-event URL `/decklist/<event>-<date>-<id>`. **NEW** scraper. | none (public) | no published API limits; `robots.txt` → 404 (no restrictions). Treat as polite-scrape: descriptive UA + ≥1.5s delay. | **YES — the true primary.** Publishes the exact weekly Challenges mtgdecks re-published ("Modern Challenge 64", verified Jun 25-26 2026) + Leagues/Showcase. | **First-party (WotC/Daybreak).** Sanctioned, robots-clean. Caveat: site restructured ~2024-06; standings/results degraded for some events, decklists+dates survive. |
| **2 (PRIMARY, premier)** | **magic.gg decklists** `https://magic.gg/decklists` | HTML scrape. **NEW** scraper. | none | polite-scrape; descriptive UA + ≥1.5s. | **YES — premier only.** Regional Championships, MTGO Champions Showcase (Modern, Jun 7 2026), Spotlight, Arena Championship. NOT weekly Challenges. | **First-party (WotC).** Sanctioned. |
| **3 (SECONDARY aggregator/anchor)** | **MTGTop8** `https://www.mtgtop8.com` | `requests` scrape. Already integrated (`mtgtop8.py`, `challenges.py`, `backfill.py`). | none | `robots.txt` → 404 (no restrictions, no Crawl-delay). Keep polite at 1.5s (consider raising). | YES — best free Modern *volume*, but shallow (~8.8 decks/event top-8 slices, not full dumps). 4,344 Modern decks / 493 events in DB. | **Tolerated scrape** (no API, no robots). Keep rate polite + honest UA. Cross-source dedup anchor via `events.event_fingerprint` / `event_fingerprint_cs`. |
| **4 (SECONDARY, sanctioned API — BENCHMARK)** | **Topdeck.gg API** `https://topdeck.gg/api/v2/...` | REST: `POST /v2/tournaments`, `GET /v2/tournaments/{TID}`, `/standings`, `/rounds`. **NEW** client. | **Free API key** from `/account`; `Authorization: <key>` header. | Documented: **100 req/min**, `429` + `Retry-After`; **attribution required** (visible credit + link). | Filters `game="Magic: The Gathering"` + `format="Modern"` + date. Decklists+standings+rounds+dates. **UNVERIFIED:** Modern event depth (user base skews Commander/cEDH). One free-key test query resolves it. | **First-party, sanctioned, free.** Cleanest legitimacy/effort ratio; gated only by a benchmark of depth. |
| **5 (SECONDARY, paper — DEFERRED/org-gated)** | **melee.gg OFFICIAL API** `/swagger/ui` | REST, client ID+secret. | **Org-gated:** email `contact@melee.gg`; owner confirmation; likely tiered/paid. Closed to non-organizers. | none published. | Best-in-class paper Modern (full decklists, standings, rounds). | **Sanctioned only via delegated TO grant** (pursue through a Team Resolve-affiliated TO). Existing `mtgmelee_scraper.py` (cloudscraper + spoofed UA on undocumented endpoints) is a **liability, NOT an asset** — 0 events/0 decks in DB, never populated; do NOT scale it. |
| **6 (COMPLEMENTARY, meta-share only)** | **MTGGoldfish** `/metagame/modern` | scrape. | none | `robots.txt` retrieved: `Allow: /` BUT `Disallow: /deck/download*`, `/deck/registration*`, `/embed/decklist`; AI bots (`ClaudeBot`/`GPTBot`/`CCBot`) fully disallowed; ToS 403/UNVERIFIED. | Meta-share context only — **decklist download is off-limits per robots.** | Scrape-only, restricted. Low priority. |
| **dismiss** | 17Lands | — | — | — | Limited-only, no Constructed. | Not relevant. |

**PRIMARY recommendation:** Make **MTGO official decklists (mtgo.com)** the first-party
primary for weekly-Challenge Modern volume — the literal source mtgdecks was re-publishing —
with **magic.gg** as the first-party premier feed and **MTGTop8** as the cross-source
aggregator/dedup anchor. This trio (all robots-clean, first-party or tolerated) fully covers
Modern tournament decklists without any Cloudflare-protected HTML. Layer **Topdeck.gg API**
(sanctioned, free) once a depth benchmark confirms Modern volume. Pursue **melee API** only
via a delegated organizer grant.

### Matchup matrix (the real loss from dropping mtgdecks)
mtgdecks `/{Format}/winrates` was the only aggregated paper head-to-head WR%×match-count grid.
No source reproduces it 1:1. Formalize the **source of record** as: real **melee.gg match
results** (`mtgmelee_scraper.py`, where reachable) + **Untapped Bo3 ladder matrix**
(`untapped_matchup_scraper.py` / `untapped_premium_scraper.py`) + the placement proxy in
`analysis/win_rates.py`. Paper-specific matchup granularity degrades but does not disappear.

---

## 3. Shared POLITE-FETCH client design

New module: **`scrapers/polite_client.py`**. Full design spec at
`mtg-meta-analyzer/docs/superpowers/specs/2026-06-26-polite-fetch-client-design.md`.

### 3.1 Module surface
```python
def get(url, *, host_rate=None, cache_ttl=None, conditional=True, params=None,
        headers=None, timeout=20.0, respect_robots=True, max_retries=4,
        force_refresh=False) -> requests.Response: ...
def post(url, *, json=None, data=None, **kw) -> requests.Response: ...   # cache off by default
def get_json(url, **kw) -> dict: ...
def host_state(host) -> dict: ...   # diagnostics
class PoliteClientError(Exception): ...
class RobotsDisallowed(PoliteClientError): ...
class HostCircuitOpen(PoliteClientError): ...   # surfaced, NOT retried
```

### 3.2 Per-host config registry (keeps call sites tiny)
```python
DEFAULT_UA = "mtg-meta-analyzer/1.0 (+https://github.com/Zuxas/mtg-meta-analyzer; contact: jermeywallace1@gmail.com)"
HOST_CONFIG = {
  "api.scryfall.com":     dict(rate=10.0, search_rate=2.0, min_interval=0.1, cache_ttl=86400,
                               accept="application/json;q=0.9,*/*;q=0.8"),
  "www.mtgtop8.com":      dict(rate=0.67, min_interval=1.5, cache_ttl=21600),
  "www.mtgo.com":         dict(rate=0.67, min_interval=1.5, cache_ttl=21600),  # NEW primary
  "magic.gg":             dict(rate=0.67, min_interval=1.5, cache_ttl=86400),  # NEW premier
  "api.mtga.untapped.gg": dict(rate=2.0,  min_interval=0.5, cache_ttl=3600),
  "mtgajson.untapped.gg": dict(rate=1.0,  cache_ttl=604800),
  "melee.gg":             dict(rate=0.67, min_interval=1.5, cache_ttl=0, needs_cloudscraper=True),
  "mtgdecks.net":         dict(rate=0.0, blocked=True, needs_cloudscraper=True),  # breaker OPEN forever
}
```

### 3.3 Request lifecycle (`get()`)
1. Load host config → 2. robots gate `can_fetch` else `RobotsDisallowed` → 3. breaker check;
OPEN → `HostCircuitOpen` (**no network**) → 4. per-host rate gate sleeps to honor
`max(min_interval, crawl_delay)` → 5. issue via host session (`CachedSession` or
`cloudscraper`); cache may short-circuit fresh-200 or revalidate 304 → 6. 200/304 record
success; 429/503 honor `Retry-After` then exp-backoff+jitter retry; **403 → record failure →
trip breaker (NOT retried)**; other 4xx raise → 7. return Response.

- **Rate (4a):** per-host `threading.Lock` gate; fixed min-interval or token-bucket
  (capacity=`rate`) for Scryfall bursts. Per-host so unrelated hosts don't block each other.
- **Cache (4b):** `requests_cache.CachedSession(backend="sqlite")` at `data/http_cache/`
  (gitignored); `expire_after`=host ttl, `urls_expire_after` per path, `cache_control=True`,
  `allowable_codes=(200,)` so a 429/503/Cloudflare-block page never poisons the cache.
- **Conditional (4c):** free with requests-cache — ETag→`If-None-Match`,
  Last-Modified→`If-Modified-Since`, 304 reuses stored body. Biggest win on mtgtop8/mtgo.com
  event pages + Scryfall bulk index.
- **Backoff (4d):** tenacity `@retry` with a **custom Retry-After-aware `wait=` callable**
  (header → body "available in N" hint → exp+jitter, +1s cushion, 60s cap); only 429/503
  retryable; 403 never retried. Generalizes the good logic already in `untapped_replay_fetcher`.
- **Circuit breaker (4e):** per-host `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=900)`
  (or hand-rolled ~15 lines). N consecutive 403/429-exhausted → OPEN → immediate
  `HostCircuitOpen` during cooldown → half-open probe. `blocked=True` hosts start **OPEN
  forever** (mtgdecks ethics). Orchestrator catches and prints `SKIPPED (circuit open)`.
- **robots (4f):** one cached `RobotFileParser` per host (~24h TTL); `can_fetch` before each
  fetch; `crawl_delay` feeds the rate floor; robots fetch itself bypasses the gate (chicken/egg).

### 3.4 Incremental migration (the integration crux)
A `CachedSession` cannot transparently absorb `urllib`/`cloudscraper` callers, so the client
owns a **pluggable session per host** via `_session_for(host)`: default `CachedSession`;
Cloudflare hosts get a `cloudscraper` scraper wrapped so the SAME rate/breaker/backoff apply
(caching off by default). `constants.py` UA/headers/delays move into `HOST_CONFIG` as one
source of truth — and the **fake Chrome UA is replaced with the honest descriptive UA.**

| Scraper | Change | Effort |
|---|---|---|
| `mtgtop8.py`, `matchup_scraper.py` | swap body of `_get()` for `polite_client.get(url)`; delete manual retry/sleep | tiny |
| `scryfall.py` | `_api_lookup` → `get_json(NAMED_URL, params=..., host_rate=2.0)`; keep streamed oracle bulk on raw requests | small |
| `untapped_*` (7 files) | replace `urllib` urlopen blocks with `get_json(url)`; central 429/Retry-After deletes the bespoke loop | medium (largest delta) |
| `mtgmelee_scraper.py` | `polite_client.post(..., needs_cloudscraper host)` | small |
| `mtgdecks.py` | leave disabled (blocked-host breaker) | none |

Migrate one scraper at a time; the client is additive, so unmigrated scrapers keep working.

---

## 4. DROP-MTGDECKS migration

### 4.1 Remove / disable
1. Hard-disable `scrapers/mtgdecks.py` from the active pipeline: remove the
   `fill_database.step_mtgdecks()` call path (lines 159-187) and the M/W/F invocation in
   `scripts/run_fill_from_prefs.py` (lines 57-79). The 2026-06-04 disable stays.
2. Register `mtgdecks.net` in `HOST_CONFIG` with `blocked=True` so its circuit breaker
   **starts OPEN forever** — any future call raises `HostCircuitOpen` with zero network I/O.
   No proxy/UA/CAPTCHA circumvention, ever.
3. **Keep all historical rows.** The 9,450 existing Modern decks (and 30,353 total) in
   `mtg_meta.db` remain queryable forever — nothing is deleted. Dropping mtgdecks loses only
   *future inflow* from that aggregator.

### 4.2 Replace coverage
- **Decklists:** mtgo.com (weekly Challenges — the 1:1 replacement for mtgdecks' bulk depth)
  + magic.gg (premier) + MTGTop8 (aggregate/dedup via `events.event_fingerprint`). Cross-source
  dedup prevents double-counting the same MTGO Challenge from mtgo.com and mtgtop8.
- **Matchup matrix:** melee real matches + Untapped Bo3 + placement proxy (§2).
- Note the depth reframe: mtgdecks supplied ~68% of Modern deck *volume* at ~28 decks/event
  (full dumps). mtgo.com restores that depth because it is the same primary feed; bumping
  mtgtop8 paging alone would NOT (it stores shallow top-8 slices).

### 4.3 Block circuit breaker (so no source can be hammered into a block again)
The per-host breaker in `polite_client` is the structural guarantee: **N consecutive
403/429-exhausted responses → breaker OPEN → all further calls to that host raise
`HostCircuitOpen` with no network traffic** until the reset timeout, then a single half-open
probe. This directly fixes Driver C (no abort-on-block). Add an optional
`POLITE_MAX_REQUESTS_PER_RUN` per-host soft cap to kill runaway nested loops (fixes Driver A/D),
and jitter `random.uniform(0, 0.3*min_interval)` so requests are not on a regular clock
(mitigates Driver B). The orchestrator governs *whether* a source runs; the client governs
politeness and the breaker — no source can self-reinforce a block.

---

## 5. Phased implementation

### SAFE-NOW (no new auth, lowest risk, do first)
| Step | What | File | Size |
|---|---|---|---|
| **S1 (FIRST)** | Build `polite_client.py` — surface §3.1, `HOST_CONFIG` §3.2, lifecycle §3.3, breaker §3.4. Minimum-dep variant: add only `requests-cache`, hand-roll backoff + breaker. | `scrapers/polite_client.py` (new) | M |
| S2 | Route the **lowest-risk scraper first** through it — Scryfall (well-documented limits, sanctioned, already gentle). Swap `_api_lookup` → `get_json(..., host_rate=2.0)`. | `scrapers/scryfall.py` | S |
| S3 | Add the block-circuit-breaker behavior + register `mtgdecks.net` `blocked=True` (OPEN forever) and `melee.gg` as contained. | `scrapers/polite_client.py` | S (part of S1) |
| S4 | Drop mtgdecks: remove `step_mtgdecks` call path + M/W/F invocation; keep historical rows. | `fill_database.py` (159-187), `scripts/run_fill_from_prefs.py` (57-79) | S |
| S5 | Replace fake Chrome UA with descriptive UA + contact (ethics + Scryfall correctness fix). | `scrapers/constants.py` | XS |
| S6 | Migrate `mtgtop8.py` + `matchup_scraper.py` `_get()` to `polite_client.get`. | `scrapers/mtgtop8.py`, `scrapers/matchup_scraper.py` | S |
| S7 | Build mtgo.com decklists scraper (polite_client.get, descriptive UA, ≥1.5s). | `scrapers/mtgo.py` (new) | M |
| S8 | Build magic.gg premier scraper. | `scrapers/magic_gg.py` (new) | M |

### NEEDS-KEY / BENCHMARK (gated on external auth or a test)
| Step | What | File | Size |
|---|---|---|---|
| B1 | Topdeck.gg: get free API key from `/account`; one test query for Modern event **depth** (the benchmark). If depth is adequate, build client. | `scrapers/topdeck.py` (new) | M |
| B2 | melee.gg OFFICIAL API: pursue delegated organizer grant via a Team Resolve-affiliated TO (client ID+secret, likely paid). Do NOT scale the cloudscraper path. | `scrapers/mtgmelee_scraper.py` (replace) | L (blocked on grant) |
| B3 | Migrate `untapped_*` (7 files) to `get_json` — largest internal delta; central 429/Retry-After deletes bespoke loops. | `scrapers/untapped_*.py` | M-L |

### Code-hygiene fixes that fall out (do in SAFE-NOW)
1. `constants.py` `USER_AGENT` fake Chrome string → `MTGMetaAnalyzer/1.0 (+contact: jermeywallace1@gmail.com)` (S5). Scryfall now *requires* descriptive UA + `Accept`, so this is correctness too.
2. Treat `mtgmelee_scraper.py` cloudscraper path as deprecated/contained, not a growth area.

---

## 6. Use what we already have (no new scraping)

### Card data — needs no scraping
- **Scryfall** (`scrapers/scryfall.py`): canonical card/oracle enrichment. Bulk JSON cached
  locally, weekly refresh. Keep as the card layer; not a tournament source. (Honor: descriptive
  UA + `Accept` header now required; ≤10 r/s; 429 → 30s lockout.)
- **MTGJSON**: optional bulk card/set alternative (`mtgjson.com/api/v5/`, daily rebuild,
  downloadable JSON/CSV/SQLite). Not a tournament source.

### Local tournament rows — already queryable, nothing deleted
- `mtg_meta.db`: **9,450 Modern decks** already from mtgdecks + **4,344** from mtgtop8 (493
  events) remain queryable forever. These are the only local Modern decklists we hold.

### Untapped — substantial but NOT Modern (premise correction)
- Untapped data is **MTG Arena only** and contributes **ZERO Modern** — Arena has no Modern
  format. `untapped_meta_snapshots` (95), `untapped_meta_archetypes` (12,231),
  `untapped_entries` (1,791), `untapped_decklists` (341), `untapped_replay_decks` (982);
  coverage 2026-05-10 → 2026-06-24. Local Untapped is free to query (no upstream scrape).
- **Use it for Standard / Timeless / Explorer / Historic / Alchemy ladder meta — never as a
  Modern tournament-decklist source.** It cannot backfill the mtgdecks gap.

---

## Changelog
- 2026-06-26: Initial PROPOSED spec synthesized from four research reports (mtgdecks
  over-scrape audit, sanctioned-source survey, polite-fetch client design, drop+replace +
  local-data report).
