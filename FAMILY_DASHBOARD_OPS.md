# Family Dashboard — Operations + Handoff

**Live URL:** https://ajays-macbook-pro.tailb3dc79.ts.net
**Repo:** `/Users/ajay/clinet-test/cheetah-market-app`
**Last updated:** 2026-05-08

Personal modules (household-gated) inside the broader Pounce trading app:
- `/morning` — daily trading brief (with stocks-first progressive render)
- `/sepa` — Minervini SEPA scanner (slim by default for fast phone load)
- `/overnight` — pre-market gappers
- `/food` — Hyderabadi/Telangana family meal planner
- `/kids` — Montessori/RIE toddler activity planner
- `/house` — McKinney house sale dashboard

---

## ▶ For the next chat session — read this first

**Who you're helping:** Ajay Kandakatla (and co-owner Vineetha) — Hyderabadi family in McKinney TX. Ajay also runs Pounce / Cheetah trading app; the household modules sit inside that app.

**Communication preferences (the user has explicitly said this multiple times):**
- **Terse > verbose.** Long responses get called out. Cut every paragraph by half before sending.
- **Concrete deliverables > explanations.** Paste-ready text, exact numbers, exact actions.
- **Don't re-prove premises.** Trust facts the user gives ("5 bed 4 bath", "got the meat from Swadeshi Frisco").
- **Plain text when copying** (MLS, agent emails). Skip `**` bold and `#` headers.

**Owner-gated modules** (`/food`, `/kids`, `/house`):
- Backend: `auth.require_household_member` — returns **stealth 404** to anyone outside the allowlist
- Frontend: NavBar hides links from non-owners
- Allowlist in `backend/.env` → `HOUSE_OWNER_EMAILS=ajaykandakatla@gmail.com,gandurivineetha@gmail.com`
- All three modules **share the same partition key** (Ajay's email) so both spouses see/edit the same data

**Out of scope unless explicitly asked:**
- The trading dashboard codebase (separate concern)
- Architectural changes to existing modules
- New auth/email gates (already correct)

**Suggested first move when chat opens:**
Ask if anything is broken or missing. Default to *small, focused, paste-ready* changes. Don't refactor unprompted.

---

## 1. Module map

| Module | Owner-gated | Mongo collections | Frontend cache key | Daily cron |
|---|---|---|---|---|
| `/food` | ✅ | `food_menus`, `food_preferences`, `food_pantry`, `food_video_cache` | `food.today.full`, `food.today.quick`, `food.history.14`, `food.grocery` | `4:00 ET` |
| `/kids` | ✅ | `kids_activity_log`, `kids_video_cache` | `kids.today`, `kids.influencers` | `4:30 ET` |
| `/house` | ✅ | `house_config`, `house_snapshots`, `house_comps`, `house_events` | (none — manual entry) | `8:00 ET` (Redfin scrape) |
| `/sepa` | shared | `scan_runs`, `candidate_snapshots`, `sepa_research_cache` | `sepa.scan` (slim) | `16:30 ET` weekday |
| `/overnight` | shared | `overnight_cache` | `overnight.movers.0.5.true` | `5:15 ET` |
| `/supply-demand` | shared | `supply_demand_cache` (24h TTL, 7d stale-allowed) | (no FE SWR — backend cache enough) | `5:00 ET`, `6:00 ET` |

---

## 2. The Gemma + YouTube + oEmbed video factory

**Used by:** `/food` and `/kids` (each has its own resolver module).

### Pipeline (per recipe / activity)

```
1. Gemma crafts query  (LM Studio · gemma-4-26b-a4b-it-mlx · localhost:1234)
2. YouTube search scrape  (parses ytInitialData JSON for video IDs)
3. oEmbed validate     (200 = live + embeddable; 401/404 = dead)
4. Gemma picks best    (reads titles + channels, returns choice_index + reason)
5. Cache to Mongo      ({video_id, video_url, title, author_name, thumbnail,
                         search_query, llm_reason, validated_at})
```

### Continuous-factory cron (runs daily 4:00 / 4:30 ET)

```bash
python -m food.video_resolver factory 21
python -m kids.video_resolver factory 21
```

**Each factory run does 3 phases:**
1. `revalidate_cache()` — drop dead videos (oEmbed check)
2. `refresh_stale(21)` — drop entries > 21 days old (forces newer-content discovery)
3. `resolve_all()` — fill in everything missing (newly-added recipes/activities + replacements)

**Key invariant:** the request path NEVER hits Gemma. All LLM work is offline cron. Phone reads from Mongo cache.

### Manual commands cheat sheet

```bash
# === Daily factory run (what cron does) ===
docker compose exec api python -m food.video_resolver factory       # default 21d
docker compose exec api python -m food.video_resolver factory 7     # tighter staleness
docker compose exec api python -m kids.video_resolver factory

# === Granular controls ===
docker compose exec api python -m food.video_resolver run                 # resolve missing only
docker compose exec api python -m food.video_resolver run --force         # re-resolve EVERYTHING
docker compose exec api python -m food.video_resolver run hyderabadi_mutton_curry  # one item
docker compose exec api python -m food.video_resolver revalidate          # drop dead, no resolve
docker compose exec api python -m food.video_resolver refresh-stale 21    # drop stale, no resolve
docker compose exec api python -m food.video_resolver list                # show all cached

# === Same commands work for kids ===
docker compose exec api python -m kids.video_resolver factory
docker compose exec api python -m kids.video_resolver run lentil_scoop_pour
```

### Adding new recipes / activities

**Recipe** (food):
1. Add a dict to `RECIPES` list in `backend/food/recipes.py`
2. Required keys: `id`, `name`, `type`, `protein`, `tags`, `prep_min`, `cuisine`, `kid_friendly`, `lunch_next_day`, `iron_rich`, `probiotic`, `citrus`, `weekend`, `quick`, `ingredients`
3. Wait for next 4:00 ET cron — video auto-resolved
4. Or run manually: `docker compose exec api python -m food.video_resolver run <new_id>`

**Activity** (kids):
1. Add a dict to `ACTIVITIES` list in `backend/kids/activities.py`
2. Required keys: `id`, `name`, `framework`, `age_min`, `age_max`, `duration_min`, `materials`, `skill`, `mess_level`, `setup_min`, `reset_min`, `notes`, `source`, `search_query`
3. Wait for next 4:30 ET cron — video auto-resolved
4. Or run manually: `docker compose exec api python -m kids.video_resolver run <new_id>`

The factory is **fully automated** — adding to the static list is the only manual step, and the cron handles the rest.

---

## 3. Cron schedule (current state)

Edit `backend/crontab`. Container TZ is `America/New_York`. After editing, container reloads automatically (supercronic watches the file via volume mount).

```
# Video factory (daily, runs 3-phase pipeline: revalidate + refresh stale + fill missing)
0      4     *    *    *    python -m food.video_resolver factory 21
30     4     *    *    *    python -m kids.video_resolver factory 21

# Backend cache pre-warmers (run before user wakes)
0      5     *    *    *    python -m supply_demand.tracker --force
5      5     *    *    *    python -c "from food import planner as p; p.suggest_today('ajaykandakatla@gmail.com')"
10     5     *    *    *    python -c "from kids import activities as a; print('kids warm:', len(a.ACTIVITIES))"
15     5     *    *    *    python -c "from overnight import movers as m; m.scan_movers(min_gap_pct=0.5)"
0      6     *    *    *    python -m supply_demand.tracker --force

# House — daily Redfin/Zillow scrape (best-effort)
0      8     *    *    *    python -c "..."  # see crontab for full command
```

---

## 4. Frontend caching strategy

Every household-page hook follows the **SWR localStorage** pattern:

```ts
// 1. Initial state from cache (synchronous, instant render)
const [data, setData] = useState(() => readCache(KEY)?.data ?? null);

// 2. Network call in useEffect → setData(fresh) + writeCache(KEY, fresh)
```

Cache keys live in `frontend/src/lib/swrCache.ts` (already there from earlier work — versioned envelope, 8 MB cap, slim-fallback).

**Hooks now using SWR:**
- `useFoodToday`, `useFoodHistory`, `useGrocery`
- `useKidsToday`, `useKidsInfluencers`
- `useOvernightMovers`
- `useSepaScan` (also uses backend `?slim=true` for 83% smaller payload)

---

## 5. Backend caching strategy

**Mongo cache with TTL + serve-stale pattern:**

```python
# Example from supply_demand/tracker.py
_CACHE_TTL_SEC = 24 * 60 * 60        # fresh threshold
_CACHE_STALE_SEC = 7 * 24 * 60 * 60  # serve-stale-and-refresh threshold

def _cache_get(key, allow_stale=True):
    age = now - cached_at
    max_age = _CACHE_TTL_SEC if not allow_stale else _CACHE_STALE_SEC
    if age <= max_age:
        return cached  # serves up to 7d stale rather than blocking on LLM
```

This means: **the request path NEVER blocks on Gemma**, even if the daily cron failed for a week. Cache always serves something.

---

## 6. Phone optimization summary

**What was done in this session:**

| Change | Before | After |
|---|---|---|
| Route code-splitting | 194 KB single bundle | 60 KB shell + 4-15 KB per route |
| `/sepa/scan` payload | 4.3 MB | 742 KB slim (full lazy-loaded) |
| Morning Brief blocking | waits for `/morning/brief` + all panels | progressive render, stocks first |
| Food/Kids/Overnight FE cache | network on every visit | localStorage SWR (instant on revisit) |
| Supply/Demand TTL | 6h (cache miss = 15× LLM blast) | 24h fresh, 7d serve-stale |
| Video resolution | request-path (slow) | offline cron (cached, fast) |

---

## 7. Source-of-truth files

When this doc and code disagree, code wins.

```
backend/
  llm/__init__.py                 ← Gemma client (chat, health, JSON parse)
  auth.py                         ← require_household_member, HOUSE_OWNER_EMAILS
  food/
    recipes.py                    ← static recipe DB (~80 entries)
    planner.py                    ← suggest_today() with quick/iron/cuisine bias
    video_resolver.py             ← Gemma + oEmbed video factory
    eat_out.py                    ← weekend DFW restaurant picks
    grocery.py                    ← weekly roll-up
    api.py                        ← all /food/* endpoints
    store.py                      ← Mongo CRUD
  kids/
    activities.py                 ← 24 household-item activities + 8 influencers
    video_resolver.py             ← same factory pattern as food
    api.py                        ← /kids/* endpoints
    store.py                      ← Mongo CRUD
  house/
    api.py, store.py, scraper.py, playbook.py
  supply_demand/
    tracker.py                    ← _CACHE_TTL_SEC=24h, _CACHE_STALE_SEC=7d
  crontab                         ← single source of truth for cron schedule

frontend/src/
  App.tsx                         ← lazy-loaded route imports
  components/NavBar.tsx           ← PRIMARY = Morning/SEPA/Overnight/Food/Kids
  hooks/
    useFood.ts, useKidsToday, useOvernightMovers — all SWR localStorage
    useSepa.ts                    ← uses ?slim=true by default
  lib/swrCache.ts                 ← localStorage envelope (8 MB cap)
  pages/
    MorningBrief.tsx              ← progressive render, stocks first
    Food.tsx, Kids.tsx, House.tsx, Sepa.tsx, Overnight.tsx
```

---

## 8. Where to look when something breaks

| Symptom | First place to look |
|---|---|
| Phone slow on `/food` first paint | Backend cron didn't run; check `docker compose logs cron --tail 100` |
| Video links broken | `python -m <food|kids>.video_resolver revalidate` then `factory` |
| Gemma hits on request path | `supply_demand/tracker.py:_CACHE_TTL_SEC` and `_CACHE_STALE_SEC` |
| `/food` or `/kids` returns 404 to a household member | `HOUSE_OWNER_EMAILS` env in `backend/.env` |
| New recipe doesn't show video | Wait for next 4am cron OR `python -m food.video_resolver run <id>` |
| SEPA list slow | Should use `?slim=true` automatically — check `frontend/src/hooks/useSepa.ts` |
| Morning Brief blank for >2 sec | `useMorningBrief` blocking — check progressive-render code in `pages/MorningBrief.tsx` |
| All cards missing thumbnails on phone | YouTube CDN block? Try the `i.ytimg.com/<id>/mqdefault.jpg` URL directly |
| Cron skipped a day | `docker compose logs cron` will show supercronic events |

---

## 9. Owner email allowlist (current)

```
backend/oauth2-emails.txt:
  ajaykandakatla@gmail.com   ← household + admin
  gandurivineetha@gmail.com  ← household
  deepankarsai27@gmail.com   ← trading-only
  chiranjeevikarkolla@gmail.com  ← trading-only
  Korvi.Nareshkumar@gmail.com    ← trading-only
  kathakoo1991@gmail.com         ← trading-only (test email)
  aravindreddy481@gmail.com      ← trading-only

backend/.env:
  HOUSE_OWNER_EMAILS=ajaykandakatla@gmail.com,gandurivineetha@gmail.com
```

After editing `oauth2-emails.txt`: `docker compose restart oauth2-proxy` (or just edit — file is hot-reloaded).
After editing `HOUSE_OWNER_EMAILS`: `docker compose up -d --force-recreate api`.

---

## 10. Deploy procedures (the only things you actually need to remember)

```bash
# Backend code change (most common)
docker compose build api
docker compose up -d --force-recreate api cron

# Frontend code change
docker compose build frontend
docker compose up -d --force-recreate frontend

# Both
docker compose build api frontend
docker compose up -d --force-recreate api cron frontend

# Just env var change (no code rebuild)
docker compose up -d --force-recreate api

# Verify health
curl -s http://localhost:8000/llm/health | python3 -m json.tool
docker compose ps
docker compose logs cron --tail 50
```

**Critical:** `cron` container must be recreated whenever `api` is — they share the same image. Without `--force-recreate cron`, the cron runs old code.

---

## 11. The "this is fully automated" promise

Once this doc is in place + cron is running, the system self-maintains:

1. **New recipes/activities** added to static lists → next 4am cron resolves videos
2. **Dead YouTube videos** → next 4am cron drops them, finds replacements
3. **Stale pinned videos** (>21 days old) → next 4am cron refreshes for newer content
4. **Supply/Demand sector data** → daily 5am refresh, 24h TTL, 7d stale fallback
5. **Phone first-paint** → SWR localStorage means instant render on every revisit
6. **No request-path Gemma calls** → backend Mongo cache serves even mid-rebuild

The only manual intervention required:
- Adding new recipes/activities to the static lists
- Editing `oauth2-emails.txt` to add/remove sign-in users
- Bumping `HOUSE_OWNER_EMAILS` to add/remove household members
- Editing `crontab` to change schedules (rare)

Everything else is the cron's job.

---

## 12. Quick verification checklist

Run these to confirm the system is healthy:

```bash
# Containers up
docker compose ps                             # 5 should be running

# Gemma reachable
curl -s http://localhost:8000/llm/health | python3 -c "import sys, json; d=json.load(sys.stdin); print('Gemma OK' if d.get('ok') else 'BROKEN', d)"

# Video cache populated
docker compose exec api python -c "from food.video_resolver import all_cached as f; from kids.video_resolver import all_cached as k; print(f'food: {len(f())} videos · kids: {len(k())} activities')"

# Today's menu serves cache (not Gemma)
time curl -s -H "X-User-Email: ajaykandakatla@gmail.com" -o /dev/null -w 'time: %{time_total}s\n' http://localhost:8000/food/today
# expect: < 0.2s. If > 1s, something's hitting Gemma synchronously.

# Cron container fresh code
docker compose logs cron --tail 5
```

---

*This document is the operational handoff for the family-dashboard work. Update timestamp + relevant sections as things ship. Keep section headers stable so deep-links (e.g. "see § 7 source-of-truth files") survive edits.*
