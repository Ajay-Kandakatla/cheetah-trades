# Cheetah Market App Constitution

The non-negotiable principles every feature, refactor, and PR in this repo
must respect. SPECS.md describes *what* the system does; this file describes
*how* we build it. When the two disagree, this file wins.

## Core Principles

### I. Free-tier first
Every feature must work end-to-end on free data sources by default. Paid
upgrades (Massive Developer, Twilio, Reddit OAuth, Finnhub paid) are
opt-in and must degrade gracefully when keys are missing. Never gate a
feature behind a paid key without a documented fallback path. The user
running this app on a Mac mini at home should never hit a hard wall.

### II. Cache-aware data layers
Every external data hit goes through a layered cache: in-process →
Mongo → parquet/disk → provider. New modules must declare their cache
collection name, TTL, and invalidation strategy in the module docstring.
Mongo is the source of truth across the api + cron services; never
introduce process-local-only state for anything that survives a request.

### III. Two-tier scan architecture
Per-symbol analysis splits into **research** (slow-changing, weekly:
VCP, Power Play, CANSLIM, base count, liquidity, ADR baseline, IPO age,
company name) and **hot** (price-derived, daily: trend template, stage,
volume, entry-setup match). New SEPA features must declare which tier
they belong to. If a computation costs more than ~500ms per symbol and
its output is stable across days, it goes in the research tier.

### IV. Graceful degradation
Every external dependency failure must produce a usable response, not a
500. Missing API key → `{"available": false, "reason": "..."}`. Provider
timeout → fallback to next layer. Mongo unreachable → in-memory dict
with a warning log. The UI must render empty/skeleton states rather
than blow up the page.

### V. SPECS.md is the source of truth
Every new endpoint, module, Mongo collection, env var, or scheduled job
gets a row/section in SPECS.md in the same PR. The file is canonical
documentation — if it disagrees with code, the code is wrong.

## Operational Constraints

- **Container TZ**: `America/New_York`. All cron schedules and
  market-hour logic use ET, not UTC.
- **Cron via supercronic** under `init: true` (Apple Silicon Docker VM
  requirement — supercronic-as-PID-1 fails to re-exec as a subreaper
  child).
- **Absolute paths in crontabs**: bare `python` fails under supercronic,
  always use `/usr/local/bin/python`.
- **Frontend**: React + Vite + TypeScript + plain CSS (no UI framework
  beyond what's already in use). Routing via react-router-dom.
- **Backend**: FastAPI + httpx + pymongo + pandas + yfinance. All HTTP
  clients use `timeout=` arguments — no infinite waits.
- **Universe modes** (curated / sp500 / russell1000 / expanded) are
  configured via `SEPA_UNIVERSE_MODE` env var. Production default
  documented in SPECS.md § 6.

## Development Workflow

- **One feature, one commit**. Co-authored commits include the
  `Co-Authored-By:` trailer.
- **TypeScript first**: every new frontend module ships with proper
  types. Run `npx tsc --noEmit` before committing — zero errors.
- **AST-validate Python** before committing when a clean local env
  (with pandas / yfinance / pymongo) isn't available. Module-level
  syntax errors must never reach `main`.
- **Mongo collections** must have an explicit `create_index([...])`
  on the lookup key. Document collection names in SPECS.md.
- **Sensitive secrets** (Twilio auth tokens, API keys) must never be
  committed. `.env` is gitignored; `.env.example` is the reference.
- **Spec-driven changes** for non-trivial features: use `/specify`,
  `/plan`, `/tasks`, `/implement` slash commands. Specs land in
  `specs/<feature-name>/` directories.

## Governance

- This constitution supersedes ad-hoc preferences. Amendments require
  a commit explicitly bumping the version below and a one-line entry
  in the SPECS.md changelog explaining what changed and why.
- Pull requests must verify constitution compliance — at minimum, the
  cache strategy, free-tier path, and SPECS.md update.
- When a principle blocks pragmatic delivery, prefer amending the
  constitution over silently violating it.

**Version**: 1.0.0 | **Ratified**: 2026-04-26 | **Last Amended**: 2026-04-26
