# Playbook videos — the host publisher (2026-11-27)

Ajay 2026-11-27 ~02:15 ET:

> "I loved the video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with videos"

This page covers the host step: getting finished film files from the film folder into the folder the app already serves. The listing and the two screens have their own docs (`playbook_videos_2026_11_27.md`, `playbook_videos_frontend_2026_11_27.md`).

## What the script does

`eod-audits/research/2026-11-27_gg_film/engine/publish.py` (stdlib only, Python 3.9, outside the repo — `eod-audits` is not a git repo; the backend `ast` pin and the end-to-end test hold the contract):

- reads `chapters/*.json` and `out/*.mp4` of a film folder;
- copies each FINISHED file into `eod-audits/replays/videos/playbook/<slug>/` and writes one sidecar `<stem>.json` next to it;
- writes nothing anywhere else: never deletes, never touches the film folder (no cache, no lock), never creates `videos/` itself. A published file that has left `out/` stays and is printed as `left in place: <name>`.

The api already binds `eod-audits/replays/videos` read-only, so the new rows appear with no deploy and no compose change.

Re-run any time; it only adds or refreshes.

## Commands

```bash
cd /Users/ajay/clinet-test/eod-audits/research/2026-11-27_gg_film && /usr/bin/python3 engine/publish.py --dry-run
```

```bash
cd /Users/ajay/clinet-test/eod-audits/research/2026-11-27_gg_film && /usr/bin/python3 engine/publish.py
```

Options: `--film-root DIR` (default: the folder above `engine/`), `--videos-root DIR` (default `$PLAYBOOK_VIDEOS_ROOT`, else `eod-audits/replays/videos`), `--slug S` (default: the film folder's name), `--title T` / `--description D` (default: the lowest-`nn` chapter's title / subtitle), `--ffprobe PATH` (default `$FFPROBE`, else `/opt/homebrew/bin/ffprobe`, else `ffprobe` on PATH), `--dry-run`, `--until-full`, `--max-minutes N`.

Output: one line per file (`published` / `sidecar` / `unchanged` / `skipped: <reason>` / `refused: <reason>`), then `published N · sidecar N · unchanged N · skipped N` (with `· refused N` added only when a file was refused).

## Which files, in this order

1. a name containing `.part` → `skipped: in flight`;
2. the name must fullmatch `^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.mp4$` (a trailing newline fails), be a regular file (no symlink), size > 0;
3. a stem ending `_phone` → tried as the phone copy of the stem without it first, then as a desktop file;
4. `NN_<id>` with `chapters/<id>.json` present and the same `nn` → a chapter;
5. a stem ending `_full` → the full film;
6. anything else → skipped with the reason.

Per file: same size and the same `source {name, size, mtime_ns}` in the existing sidecar → no copy and no ffprobe. Otherwise ffprobe (duration must be finite > 0), copy to `<name>.<pid>.part`, fsync, stat the source again (changed → the temp file is removed, `skipped: source changed while copying`), atomic rename; then the sidecar the same way (`.json.<pid>.part` → rename). The mp4 lands before its sidecar; the server hides a pair whose `bytes` disagree, so a half-updated pair is never listed.

Text checks (refuse that file, exit 1, the others still publish): film title / chapter title ≤ 120, subtitle ≤ 200, description ≤ 300 characters, printable characters only, and no banned word (the b-word: the house word is "reversal").

## Wait mode — `--until-full`

Keeps publishing until the full film has landed; bounded.

```bash
cd /Users/ajay/clinet-test/eod-audits/research/2026-11-27_gg_film && nohup /usr/bin/python3 engine/publish.py --until-full --max-minutes 240 > /private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/playbookvid/publish_wait.log 2>&1 &
```

One pass, then the stop rule. Done only when ALL four hold:

1. no name in `out/` contains `.part`;
2. every chapter in `chapters/` has at least one file published / refreshed / unchanged this pass;
3. a desktop full film is in `out/`, published this pass, and its mtime is at or after every chapter file's (a stale full film from an earlier concat does not end the wait);
4. no file this pass was refused or changed while copying.

Not done → sleep `POLL_SECONDS` (60) and pass again. A pass in which nothing changed prints ONE line `waiting: <reason>`. Once `--max-minutes` (default 360) has passed: one last pass, then `gave up waiting: <reason>` and exit 3. Reasons: `in flight: <name>` · `chapters missing: <ids>` · `no full film yet` · `full film older than <name>` · `source changed while copying: <name>` · `refused: <name>`.

The LAST line of the log is always `done: <N> chapters + the full film` or `gave up waiting: <reason>` — read that line to know how a detached run ended. Check it is running with `pgrep -fl "publish.py --until-full"` (a host process, never a container). Two publishers at once are safe: the temp names carry the pid and both renames are atomic.

## Exit codes

| code | meaning |
|---|---|
| 0 | ran (in-flight skips are not errors); with `--until-full`: done |
| 1 | at least one file refused (bad text, ffprobe failure, read-back mismatch) |
| 2 | refused before any write: bad slug, videos root missing / not a folder, `playbook` or `<slug>` is a symlink or not a folder, destination not inside `<videos-root>/playbook/<slug>/` by realpath, no `chapters/` or `out/`, ffprobe not found, `--until-full` with `--dry-run`, `--max-minutes` < 1 |
| 3 | `--until-full` reached its bound before the full film landed; everything finished IS published |

## The sidecar (`<stem>.json`, one per mp4)

| key | value |
|---|---|
| `kind` | `"playbook"` |
| `schema` | `1` |
| `file` | the mp4's name |
| `film` | `{slug, title, description, chapters_total}` — `chapters_total` = the number of valid `chapters/*.json` |
| `role` | `"chapter"` or `"full"` |
| `variant` | `"phone"` or `"desktop"` |
| `chapter` | `{nn, id, title, subtitle}`; `null` for the full film |
| `markers` | full film: `[{start_s, title}]` from `ffprobe -show_chapters`, in time order (may be `[]`); chapter: `null` |
| `duration_s` | ffprobe duration, 3 decimals |
| `bytes` | the published file's size |
| `width`, `height` | first video stream |
| `soft_subtitles` | a subtitle stream is present (subtitles are also burned in) |
| `voice` | `"<backend> <name>"` from `build/<id>/timing.json`; full film: the single shared voice, else `null` |
| `description` | chapter: `<film title> · NN <title> — <subtitle>`; full film: `<film title> · full film — <film description>` |
| `created_at` | the source file's mtime, ISO-8601, America/New_York |
| `published_at` | now, same format |
| `source` | `{name, size, mtime_ns}` of the `out/` file — the "same already?" key |

Never a `window` key (so it can never enter a nightly day list) and never an absolute path.

## Traps of the render (film.sh)

- The in-flight names END in `.mp4` (`01_bull_flag_phone.mp4.part.mp4`, `GG_setups_full.part.mp4`): a bare `out/*.mp4` glob would publish a half-written file. The `.part` skip and the stat-before / stat-after guard against it.
- `build/.render.lock` is held only around the frame render, not during mux / the phone two-pass / the concat, so it cannot mean "done"; the wait mode keys on the file set instead.
- Inside a chapter the desktop file lands first and the phone copy 4-7 minutes later: between the two a pass lists the chapter desktop-only.
- The render loop goes on past a failed chapter and the concat skips a chapter with no out file, so the full film lands LAST and can hold fewer chapters. Then the waiter ends at its bound with `gave up waiting: chapters missing: <id>` (exit 3) and the finished files are listed.

## A future film

Same script, its own folder: `--film-root` points at the film folder (with `chapters/` and `out/`), the slug defaults to that folder's name.

```bash
/usr/bin/python3 /Users/ajay/clinet-test/eod-audits/research/2026-11-27_gg_film/engine/publish.py --film-root /Users/ajay/clinet-test/eod-audits/research/NEXT_FILM --dry-run
```

Nothing runs it automatically for a future film (his call).

## Tests

`engine/test_publish_host.py` (50 tests; fake ffprobe, everything under `tmp_path`; one real-folder `--dry-run` smoke that must leave `eod-audits/replays/videos` unchanged):

```bash
cd /Users/ajay/clinet-test/eod-audits/research/2026-11-27_gg_film && PYTHONDONTWRITEBYTECODE=1 /Users/ajay/clinet-test/cheetah-market-app/backend/.venv/bin/python -m pytest -q -p no:cacheprovider engine/test_publish_host.py
```
