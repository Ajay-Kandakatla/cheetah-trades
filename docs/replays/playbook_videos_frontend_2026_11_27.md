# 📚 Playbook learning / 🎬 Videos — frontend (2026-11-27)

Ajay 2026-11-27 ~02:15 ET, verbatim:

> "I loved the video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with videos"

Inside Gajjala (his teaching charts, shown to the owner). Display only: no rule, gate, threshold, push or trade. A study
film: hand-picked teaching charts, descriptive, UNMEASURED, not a signal.

Backend contract: `playbook_videos_2026_11_27.md`. Publisher: `playbook_videos_publish_2026_11_27.md`.

## Files

| file | what |
|---|---|
| `frontend/src/lib/playbookVideos.ts` | route `PBV_PATH` (== backend `C.PLAYBOOK_API_PATH`), param `PBV_PARAM` (`playbook`), the two mounts `PBV_WHERE`, `PBV_FETCH_FAILED`, payload types, pure guards (`pbvText`, `pbvSrc`, `pbvVariants`, `pbvPick`, `pbvDefaultVariant`, `pbvOptions`, `pbvMarkers`, `pbvFilms`, `pbvRowKey`, `pbvOpen`, `pbvToggleParams`) |
| `frontend/src/components/PlaybookVideos.tsx` | `PlaybookVideos` (the caller proved the owner) and `PlaybookVideosOwner` (`useCurrentUser` gate) |
| `frontend/src/styles/playbookVideos.css` | `pbv-` sheet, both mounts |
| `frontend/src/components/__fixtures__/playbook_videos_2026_11_27.json` | `ready` / `partial` / `empty` / `no_folder` in the §3.4 payload shape (real sizes / lengths of 11-27) |

## The two mounts and why they differ (Rule #5)

| mount | where | default | fetch | title |
|---|---|---|---|---|
| 🎬 Replays | `<PlaybookVideos where="replays" />`, top of the board | closed | ONE GET each time it opens (`?playbook=1`), nothing while closed | 📚 Playbook learning |
| 🚩 📓 Playbook | `<PlaybookVideosOwner where="playbook" />`, under the playbook note | open | ONE GET on mount | 🎬 Videos |

- 🎬 is a busy board (day cards + 🏆): the section is one closed button at the top, found at once, loading nothing until
  tapped. `?playbook=1` opens it, `?playbook=0` closes it, no param = the mount's default; the toggle deletes the param
  when the new state equals the default and keeps every other param (`tab`, `date`, `winners`, `reel`, `sub`).
- 📓 is the reading page for his playbook: the videos sit open under the note, but the mount is QUIET — it renders
  nothing at all (no title) while loading, on a failure, on `empty` / `no_folder`, and when no row is playable.

## Owner gate per mount

- 🎬: no `/auth/me` here (it would add a fetch on the tab's mount and break the ONE-fetch pins). The board mounts the
  section only after its own GET returned a 200 with a known `state` — only the primary owner gets one.
- 📓: `PlaybookVideosOwner` reads `useCurrentUser()`; `if (loading || !user?.is_primary_admin) return null;` — a
  co-owner, a loading `/auth/me`, or no user → empty DOM and zero fetch.
- Both: the list route is owner-gated at the server; an HTTP 404 → the section returns null (title included) and stays
  gone for the mount (no second GET).

## The 🎬 slot (C1, C2)

The board puts the SAME slot expression `{pbSlot}` as the first child of ALL THREE of its returns (loading / failed /
loaded), filled behind a sticky `ownerSeen` flag set by the board's own 200. So:

- 🏆 Past winners keeps its child position in every return → its `<video>` node and its one GET survive a session pick
  (C1; pins `ReplaysPastWinJump.test.tsx:206` "ONE 🏆 GET" and `:428` the same playing 🏆 node).
- The 📚 section, once mounted, survives every session pick, 🏆 chip jump, Back and a later failed load (C2). Its open
  state is the URL param; the tapped row, the wanted size and the `<video>` are its own state; its fetch effect reads
  `open` alone, so a `date` / `winners` / `reel` / `card` / `sub` change fires no second GET and keeps the playing node.

(The board lines are WP fe-mount; this component is what makes them safe: no request while closed, none to `/auth/me`.)

## The phone default (C3)

- The house breakpoint: `useIsMobile` = `(max-width: 768px)` (`MOBILE_MAX_WIDTH`), so 768 itself counts as a phone.
- Read ONCE on the section's first render: `useState(() => pbvDefaultVariant(isMobile))`. After that only a tap on the
  📱 phone / 🖥 desktop switch changes it. Turning the phone (a viewport `change`) never swaps the playing file, its
  position or the switch.
- A phone already sideways when the tab loads (932 px) starts on the 1080p copy (HIS CALL 6). The chips always show the
  length, quality and size of the file that WILL play (`pbvPick`: the wanted size, else the first playable), before any
  tap; `preload="metadata"` pulls no media until he plays.
- A tap on the switch while a video is mounted keeps the position: the time is stored, restored on `loadedmetadata`,
  paused. A switch that does not change the playing file (the desktop-only full film) arms no restore.

## The player

- Rows are text: served `nn_text`, `title`, `subtitle`, chips; ▶ (`aria-pressed`) mounts ONE `<video>` in the whole
  section, under the tapped row; the same ▶ removes it, another ▶ moves it; closing removes it.
- `<video className="pbv-video" controls preload="metadata" playsInline src=…>` — never `autoPlay`, `muted`, `poster`,
  `download`; the app never calls `.play()`.
- The full film, while playing, shows its served markers as buttons; a tap sets `currentTime` to the served second.
- `pbvSrc` = API + the served `src` only when it starts with `${PBV_PATH}/video/`; anything else → no ▶ for that
  variant and never a `<video>` of it.
- No `<a>` anywhere (pin `GajjalaBoard.movers_links.test.tsx:206-215`), no `TickerLink`.
- Phone layout: every container `min-width: 0; max-width: 100%`, rows and chip rows wrap, texts and chips wrap
  (`white-space: normal; overflow-wrap: anywhere`), the video `width: 100%`, 16:9; the player capped at 60rem above 768 px.

## FE-typed vs served

FE types: the two titles (📚 Playbook learning == backend `C.PLAYBOOK_TITLE`; 🎬 Videos), `PBV_FETCH_FAILED` ("Could not
load the playbook videos."), the ▶ glyph, three aria-labels (`play`, `video size`, `chapters`). Everything else is
served: the note, the empty / no-folder text, the film title + summary + description, chapter number / title /
subtitle, the length / quality / size chips, the switch labels, the full film's title / subtitle, the marker texts.

## Tests

- `frontend/src/lib/playbookVideos.test.ts` (21): every helper, with NEGATIVES (off-route / absolute / `javascript:` src,
  junk keys, bad markers, zero playable rows, a COPY on toggle, the param deleted at the default).
- `frontend/src/components/PlaybookVideos.test.tsx` (42): closed + zero fetch; `?playbook=1` / a tap → ONE GET with
  `credentials: 'include'`, `cache: 'no-store'`; served order and words; one `<video>` (attrs, move, remove, close);
  phone / desktop default; the switch + position restore; the latch (turn BEFORE ▶ → still phone; NEGATIVE: turn while
  playing → the same node, src, `currentTime`, switch; the mirror); partial on a phone → desktop file + desktop chips;
  a third chapter with no code change; markers; the owner mount (ONE GET, open, 🎬 Videos); NEGATIVES: co-owner /
  loading / no user → empty DOM + zero fetch; 404 → nothing in both mounts and no second GET; reject / 500 / unknown
  state / junk JSON → `PBV_FETCH_FAILED` only; `empty` / `no_folder` → served text only; quiet mount empty on loading /
  failed / empty / no_folder / zero playable; off-route src; junk fields (no `NaN` / `undefined`); no autoplay / muted /
  poster / download; no `<a>`; stay mounted across a date change and a 🏆 jump (ONE GET, same node, `currentTime`
  kept); source guards (no admin email, no `04:00-20:00`, no b-word; the video attrs; the owner gate; the latch literal
  once).
- `frontend/src/components/PlaybookVideos.phone.test.tsx` (6): CSS source guards, each with a pre-fix NEGATIVE.
- Mutations proved RED then reverted: (1) the size follows the viewport (`pbvDefaultVariant(useIsMobile())` unless
  tapped) → the latch tests + the source guard red (6); (2) the fetch effect also depends on the URL params → the
  stay-mounted test and the owner one-GET test red (2).
