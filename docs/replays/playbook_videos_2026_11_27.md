# 📚 Playbook learning — backend (2026-11-27)

Ajay 2026-11-27 ~02:15 ET, verbatim:

> "I loved the video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with videos"

Inside Gajjala: his teaching charts, shown to the owner. Display only — no rule, gate, threshold, push or trade. Hand-picked teaching charts: descriptive, UNMEASURED, not a signal.

Related: [publisher](playbook_videos_publish_2026_11_27.md) · [frontend](playbook_videos_frontend_2026_11_27.md).

## Folder layout

```
eod-audits/replays/videos/playbook/<film-slug>/<name>.mp4
eod-audits/replays/videos/playbook/<film-slug>/<name>.json     one sidecar per mp4, same stem
```

`videos/` is already bind-mounted read-only at `/data/replays/videos` (`docker-compose.yml`), so `videos/playbook/` needs no compose change. `<film-slug>` fullmatches `C.PLAYBOOK_SLUG_RE` (`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$` — no dot, no slash, no trailing newline). The publisher writes the mp4 first and the sidecar second, both via a `.part` temp name and an atomic rename.

## Sidecar contract (schema 1)

| key | rule on the server |
|---|---|
| `kind` | `== C.PLAYBOOK_KIND` (`"playbook"`) |
| `schema` | int `== C.PLAYBOOK_SCHEMA` (1); a bool is refused |
| `window` | MUST NOT be present (a nightly sidecar is never a film) |
| `file` | fullmatches `C.FILE_RE`, equals the json's stem + `.mp4`, present in the same scan, a regular file by `os.lstat` (no symlink) |
| `bytes` | int > 0, equal to that file's size (a half-updated pair stays hidden until the second rename) |
| `film` | dict: `slug` == the folder name; `title` clean, non-empty, ≤ 120; `description` clean ≤ 300 or null; `chapters_total` int ≥ 1 or null |
| `role` / `variant` | `chapter` or `full` / `phone` or `desktop` |
| `chapter` (role `chapter`) | `nn` int 0..99 (bool refused), `id` fullmatches `C.PLAYBOOK_CHAPTER_ID_RE`, `title` clean ≤ 120, `subtitle` clean ≤ 200 or null |
| `markers` (role `full`) | list; an entry is kept only with finite `0 <= start_s < duration_s` and a clean non-empty `title`; a non-list → `[]` |
| `duration_s` | finite > 0, not a bool |
| `height` | int > 0 or null |

"Clean" = a `str`, every character printable (`str.isprintable()`), non-blank where required. Every other key the publisher writes (`width`, `soft_subtitles`, `voice`, `description`, `created_at`, `published_at`, `source`) is carried on disk and not served. Any failure → that file counts `skipped_bad`; each card is built inside `except C.CARD_ERRORS`, so one bad sidecar never breaks the listing. Two sidecars claiming the same (role, nn, id, variant) → the first by file name wins. The film's title / description come from the FIRST ACCEPTED sidecar by file name; `chapters_total` is the largest served.

## Routes (owner only)

Both live in `backend/chart_maps/replays/playbook_api.py`, included from `replays/api.py` with `router.include_router(playbook_router)` (so `api.py` keeps its four own routes and its pins).

| route | answer |
|---|---|
| `GET /chart-maps/replays/playbook` | the listing (`playbook.payload`), `Cache-Control: no-store`, NaN-scrubbed |
| `GET\|HEAD /chart-maps/replays/playbook/video/{film}/{name}` | the bytes of a LISTED file through Starlette `FileResponse` (Range → 206 / 416 / 400, HEAD) with `C.VIDEO_HEADERS`: `Content-Encoding: identity` (the GZipMiddleware trap), `Cache-Control: private, no-transform`, `Accept-Ranges: bytes` |

The gate is `ollama_chat.api.require_primary_admin`, a dependency: anyone else gets the stealth 404 before the path is looked at; no header → 401. Why owner only: the film is Gajjala's third-party teaching screenshots, a personal study film (widening it is HIS CALL 1).

`resolve_video` returns a path only when: the film is a slug AND is listed by `film_slugs` (which refuses a `videos/playbook` that is not a REAL directory by `os.lstat` + `stat.S_ISDIR`, and a film folder that is a symlink); the name fullmatches `C.FILE_RE` and is in the film's accepted set; and its realpath starts with `realpath(videos root) + "/playbook/<film>/"` — the base is built from the REAL videos root plus the two literal names, so a symlinked `playbook` or film folder fails even if the first guard were gone.

## Listing payload

`state`: `no_folder` (no `videos/`, `text = C.NO_FOLDER_TEXT`) · `empty` (`text = C.PLAYBOOK_EMPTY_TEXT`, `films: []`) · `ready`.
Top keys: `title`, `tab`, `state`, `text`, `note` (`C.PLAYBOOK_NOTE`), `variant_options`, `counts`, `films`.

- `counts`: `films`, `chapters`, `videos`, `skipped_bad`, `no_sidecar` (an mp4 with no `.json` of the same stem).
- film: `slug`, `title`, `description`, `summary_text`, `chapters`, `full`. Films by slug DESC; a film with no accepted file is omitted (its skips still count).
- chapter: `key` (`NN_id`), `nn`, `nn_text`, `id`, `title`, `subtitle`, `variants`; chapters by `(nn, id)`.
- variant: `key`, `label`, `file`, `src`, `duration_s`, `length_text` (`m:ss`, `h:mm:ss` from one hour), `bytes`, `size_text` (`29 MB`, `1.4 GB` from 1e9), `height`, `quality_text` (`720p` or null); in `C.PLAYBOOK_VARIANT_KEYS` order (phone, desktop).
- `full`: `key: "full"`, `title: C.PLAYBOOK_FULL_TITLE`, `subtitle` = `"1 chapter"` / `"N chapters back to back"` by the marker count (null with no marker), `variants`, `markers` (`start_s`, `text` = `"m:ss title"`), sorted by `start_s`.
- `summary_text`: `"n of total chapters · m min so far"` while `n < total`, else `"1 chapter · m min"` / `"n chapters · m min"`; `m` = the rounded sum of each chapter's first-variant duration in minutes.
- `variant_options`: the variant keys present anywhere, constant order, with their switch labels.

## Why a playbook file can never appear under a date (three independent reasons)

1. The nightly listing only scans folders whose name is a date (`store.dates`, `store.read_day`); `playbook` is not one.
2. The files sit one level deeper (`videos/playbook/<slug>/`); the 🏆 lists read `videos/winners` and `videos/multiday` non-recursively.
3. A playbook sidecar never carries `window`; the nightly and 🏆 accept rules require one (`window == FULL_DAY_WINDOW`). The other way round, a nightly sidecar (it has `window`) placed in a film folder is refused here.

All three are pinned by the ISOLATION tests.

## Tests

`backend/tests/test_replays_playbook_2026_11_27.py` — 135 tests: listing words and order, new-chapter pickup with no code change, the full film (markers, subtitle singular / plural / none), which sidecar names the film, every refused sidecar (parametrized), symlinks (mp4 outside and inside the film, film folder, `videos/playbook` itself, `videos/playbook` a file), fullmatch only (trailing newline), routes (strict JSON, headers, Range 206 / 416 / 400, HEAD), non-owner 404 with the engine never called, no header 401, traversal (`..%2F`, `../../`, `%2e%2e`, `//etc/passwd`, `a.b`, a nightly date, `.json`, case change, unlisted, encoded slash, `%0A` on either segment), isolation both ways, source pins, guarded host-path helpers (skip, never `IndexError`), the publisher's constants by `ast`, an end-to-end run of the real `publish.py` with a fake ffprobe, the frontend fixture's key sets.

Mutations proved RED then reverted (caches purged each run): (a) drop the `kind` check · (b) drop the gate from the video route · (c) `os.lstat` → `os.stat` on the mp4 · (d) `is_slug` with `.match`.

## How to verify

```bash
cd /Users/ajay/clinet-test/.wt-playbookvid/backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} + ; .venv/bin/python -m pytest tests/test_replays_playbook_2026_11_27.py -q -p no:cacheprovider
```

```bash
cd /Users/ajay/clinet-test/.wt-playbookvid/backend && REPLAYS_DIR=/Users/ajay/clinet-test/eod-audits/replays .venv/bin/python -c "import json; from chart_maps.replays import playbook as PB; print(json.dumps(PB.payload()))"
```

Expect `state: ready`, `skipped_bad: 0` and the published chapters once the publisher has run. After the deploy: the owner gets 200 on the list; a co-owner gets 404 on the list and on a video URL; a `Range: bytes=0-1023` on a video answers 206 with `content-encoding: identity` and `cache-control: private, no-transform`.

## Not built

- The soft `mov_text` subtitle track is not surfaced (subtitles are burned in; turning the track on in Safari doubles the line).
- No phone copy of the full film (HIS CALL 4); the server lists `*_full_phone.mp4` with no code change if one is published.
- No automatic publish for a future film (HIS CALL 8): `publish.py` is run by hand.
