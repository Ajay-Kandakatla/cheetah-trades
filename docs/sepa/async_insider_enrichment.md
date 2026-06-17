# Async insider enrichment + EDGAR rate-limit fix

**Requested:** Ajay, 2026-06-17 — the scan was hammering SEC EDGAR with a wall of
`HTTP 429 Too Many Requests`, stuck on the `insider_sweep` phase. *"Make this an
async update and let me use the app while the backend figures it out — maybe
Server-Sent-Event or WebSocket driven."*

Two problems, two fixes:

---

## 1. The 429 storm — root cause + fix

**Root cause (confirmed):** nested *unbounded* EDGAR concurrency with no
per-request pacing and no 429 backoff. The broad insider sweep in
`scanner.py` ran `Semaphore(4)` across ~280 candidates; each candidate's
`insider_activity()` fired **3 full-text searches + up to 3 Form-4 XML fetches**
in parallel (`sepa/insider.py`), so ~24 EDGAR GETs landed in the same
millisecond — far over EDGAR's ~10 req/s. The only "retry" was a linear sleep on
*exception*, which re-fired the whole burst and synchronized the next 429 wave.

**Fix — a single global chokepoint** (`sepa/insider.py`):

- **`_edgar_get(url, ...)`** — every EDGAR GET (the FTS search, the Form-4 XML
  fetch, the ticker→CIK map) now goes through this one function.
- **`_edgar_pace()`** — a token-bucket-of-1 (a loop-bound `asyncio.Lock` +
  monotonic next-slot clock) spaces every GET ≥ `1 / EDGAR_MAX_RPS` apart, so no
  matter how many coroutines race, **starts are paced under the limit**. Verified
  in `test_insider_throttle.py`: 5 concurrent calls take ≥ 4 intervals.
- **429 / 5xx backoff** — honours `Retry-After`, else exponential (capped 8s);
  bounded by `SEC_MAX_RETRIES`. On exhaustion it returns the last response (never
  raises, never loops) → the caller degrades to "no insider data" gracefully.

Tunables (env): `SEC_MAX_RPS` (default **7**, headroom under 10), `SEC_MAX_RETRIES`
(default 4), `SEC_USER_AGENT` (set a real contact email in prod). This chokepoint
protects **both** the scan sweep AND the per-card `/sepa/card-enrichment` path.

---

## 2. Async decoupling — the scan no longer blocks on insider

The broad insider sweep is **deferred out of the blocking scan** into a detached
post-scan background task, and results push to the UI over the existing global
SSE bus (`backend/events`, the same channel `quote.update` uses) — so the scan
returns fast and the cards' 🟢 Cluster / Insider chips fill in **live** while the
app stays fully usable.

**Flow:**

1. `scan_universe(..., defer_insider_sweep=True)` (passed by `/sepa/scan` +
   `/sepa/scan/stream`) keeps the small top-20 enrichment inline but **skips the
   broad sweep**, returning the remaining candidate symbols in
   `payload["deferred_insider_symbols"]`. The scan emits `done` immediately.
2. The endpoint hands that list to **`_kick_background_insider_sweep()`**
   (`main.py`) — a `asyncio.create_task` held in a module set so it's **detached**
   from the scan request: it survives the SSE scan-stream closing and the user
   navigating away.
3. `_run_background_insider_sweep()` fetches each symbol's insider data via
   **`card_enrichment.refresh_insider()`** (globally rate-limited by `_edgar_get`),
   warms the 24h card-enrichment cache, and **`publish("insider.update", {symbol,
   insider})`** per name. A final `insider.sweep_done` marks completion.
4. **Frontend** — `useCardEnrichment` subscribes to `insider.update` on the
   global `/events` stream and **merges the pushed insider slice** into the card's
   chip data (no refetch, no reload). Cards that haven't been JIT-fetched yet seed
   from the event; valuation/headline still come from the JIT viewport fetch.

The daily **cron** scan keeps the inline sweep (`defer_insider_sweep` defaults
False) — unattended, so blocking is fine, and it warms the insider cache for the
day (now reliably, thanks to the throttle).

## What this is NOT

- Not a methodology change — no book formula, gate, or score touched. Pure
  plumbing: rate-limit + scheduling + a display push.
- Not WebSocket — SSE (the app's existing one-directional push) is the right fit;
  the global bus already fans out to every tab.
- Not single-process-safe across replicas — the in-memory bus is per-process,
  which matches the single-process deployment (note for future scaling: Redis
  pub/sub).

## Tests

- `backend/tests/test_insider_throttle.py` — pacing under concurrency, 429/5xx
  backoff, bounded give-up (never raises/loops), error→None, `refresh_insider`.
- `frontend/src/hooks/useCardEnrichment.test.tsx` — live merge of its own symbol,
  case-insensitive match, ignores other symbols, only touches the insider slice.
