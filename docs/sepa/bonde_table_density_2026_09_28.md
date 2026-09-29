# 📈 Bonde table density — 2026-09-28

## 1. The ask

Ajay, 2026-09-28, with a screenshot: **"Once done can you fix this table too? so much empty space"**

## 2. Which table

The screenshot's section "Explosive · sales +100%" is the **📈 Bonde tab** (`/chart-maps?tab=bonde`, `frontend/src/components/BondeBoard.tsx`), not the 🚀 Explosive Growth page. That page's own `eg-table` shares none of this markup and is untouched. One loop draws all five Bonde sections (⚡ pivot, explosive, strong, steady, 🔎 rejected), so the fix covers every tier.

## 3. Root causes (HEAD a2f6144)

1. **~200px rows.** `.bd-sym { display:flex; flex-direction:column }` put each of the 13 things in the Ticker cell on its own line (flex stretch turned "+ Signals" and every chip into a full-width bar), and `.bd-row { align-items:center }` centred every other cell against that tall column.
2. **Text spill.** The 🪜 chip is a `.cm-badge`, which is `white-space: nowrap` app-wide. Its served sentence runs to 109 characters (~500-660px) inside a Ticker track of ~260px, so it painted over Today and Since report.
3. **Header overlap.** `.bd-row` was declared three times in `styles.css` (5, 6 and 7 tracks; the last won). The metric heads were `min-width: 52px; white-space: nowrap` inside a flex row, so four uppercase heads of ~70px painted over each other — and head and body metrics were separate flex rows, so a head did not sit over its number.
4. **Episodic Pivot took ~170px holding only "—"** (no row on the board has a pivot; the scanners are paused). Nothing collapsed it.
5. **≤900px** the rows became a two-column stack with **every header hidden** (`display:none`).

## 4. The design

- **Ticker cell = three lines.** Line 1: ticker ☆ · company · ✨ NEW · pair badge · tier · **+ Signals** (pushed right). Line 2: 🎯 · 🚀 · 🎪 · 🧨 · ⛔/✅ · 🪜, flowing and wrapping *inside the cell* (the wrap is scoped to `.bd-sym`; the base `.cm-badge` stays nowrap everywhere else). Line 3: his six 📋 chips with "▸ all N" inline. A row with no reads leaves line 2 empty and CSS hides it.
- **One track template** (`.bd-row`, 7 tracks from CSS custom properties on `.bd-rows`); the Ticker is the only flexible track. Rows are top-aligned so each row reads across on its first line.
- **Metrics** are a 4-column grid shared by head and body: heads wrap to two lines instead of overlapping and sit over their numbers.
- **Sideways scroll.** Each section's table sits in its own `.bd-scroll` box (`overflow-x: auto`); the Ticker column is `position: sticky; left: 0` on an opaque `var(--bg)`. html's `overflow-x: hidden` can no longer cut a column. Headers stay visible at every width (the ≤900 stack is gone). Ticker min width 22rem, 16rem ≤900px, 12rem ≤600px.
- **EP collapse (HIS CALL, default ON).** The Episodic Pivot column draws 2.5rem wide as "EP" (full name on hover and `aria-label`) only when **every served row of that section** has no pivot (`pivotColumnEmpty(all)` — served rows, never filtered rows). One pivot keeps it wide. Body cells still print "—".
- `overflow-x: auto` also clips vertically; nothing in a row is an absolutely-positioned popover today (tooltips are native `title`, `<details>` is in-flow). A future in-row popover would be clipped.
- **"▸ all N" inside the cell:** two tracks at every width, entries 3+ pinned to the second track (see C11 below). The old ≤860px-only fold is gone from the Ticker cell.
- Tuning knob 1 applied (row padding 0.35 → 0.25rem): the 1440 explosive max went 123 → 120px.

## 5. Measurements (headless Chrome, every app stylesheet in main.tsx order, `.app > main.main > .cm-page`)

Snapshots are the REAL 2026-09-28 payloads rendered through the real component: `bonde_real_2026_09_28.json` (14 rows holding every served extreme), `-pivot` (the same with one pivot injected into LQDA) and the scratchpad-only full board (all 200 served rows).

### BEFORE (HEAD a2f6144 stylesheets, same probe)

```
### bonde_before.html
| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1440 | 1360 / 1373 | yes | 1440 | 25/26 | 9 | NO (18) | yes | NO / n/a | 171/171/171 | 212 / 246 | NO (14) | 0 | 0/0 | FAIL |
| 1280 | 1200 / 1213 | yes | 1280 | 28/29 | 12 | NO (15) | yes | NO / n/a | 150/150/150 | 228 / 248 | NO (14) | 0 | 0/0 | FAIL |
| 1024 | 944 / 957 | yes | 1024 | 28/29 | 12 | NO (15) | yes | NO / n/a | 111/111/111 | 248 / 286 | NO (14) | 0 | 0/0 | FAIL |
| 768 | 688 / 688 | no | 768 | 0/0 | 0 | NO (33) | yes | NO / n/a | 0/0/0 | 280 / 314 | NO (14) | 0 | 0/3 | FAIL |
| 390 | 346 / 667 | yes | 390 | 0/0 | 0 | NO (33) | yes | NO / n/a | 0/0/0 | 320 / 365 | NO (14) | 0 | 0/3 | FAIL |
  1440: row h median/max — Explosive · sa 212/246 (n=10) · Strong · sales 189/189 (n=1) · 🔎 Cleared his 207/207 (n=3)
  1280: row h median/max — Explosive · sa 228/248 (n=10) · Strong · sales 210/210 (n=1) · 🔎 Cleared his 207/223 (n=3)
  1024: row h median/max — Explosive · sa 248/286 (n=10) · Strong · sales 210/210 (n=1) · 🔎 Cleared his 228/244 (n=3)
  768: row h median/max — Explosive · sa 280/314 (n=10) · Strong · sales 278/278 (n=1) · 🔎 Cleared his 275/275 (n=3)
  390: row h median/max — Explosive · sa 320/365 (n=10) · Strong · sales 330/330 (n=1) · 🔎 Cleared his 327/327 (n=3)
### bonde_before_full.html
| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1440 | 1360 / 1373 | yes | 1440 | 204/216 | 12 | NO (24) | yes | NO / n/a | 171/171/171/171 | 210 / 246 | NO (200) | 0 | 0/15 | FAIL |
| 1280 | 1200 / 1213 | yes | 1280 | 208/220 | 16 | NO (20) | yes | NO / n/a | 150/150/150/150 | 228 / 248 | NO (200) | 0 | 0/15 | FAIL |
| 1024 | 944 / 957 | yes | 1024 | 208/220 | 16 | NO (20) | yes | NO / n/a | 111/111/111/111 | 248 / 302 | NO (200) | 0 | 0/15 | FAIL |
| 768 | 688 / 688 | no | 768 | 0/0 | 0 | NO (44) | yes | NO / n/a | 0/0/0/0 | 278 / 314 | NO (200) | 0 | 0/74 | FAIL |
| 390 | 346 / 667 | yes | 390 | 0/0 | 0 | NO (44) | yes | NO / n/a | 0/0/0/0 | 330 / 367 | NO (200) | 0 | 0/74 | FAIL |
  1440: row h median/max — Explosive · sa 210/246 (n=60) · Strong · sales 210/246 (n=60) · Steady · sales 210/246 (n=40) · 🔎 Cleared his 207/207 (n=40)
  1280: row h median/max — Explosive · sa 228/248 (n=60) · Strong · sales 228/246 (n=60) · Steady · sales 210/246 (n=40) · 🔎 Cleared his 207/228 (n=40)
  1024: row h median/max — Explosive · sa 248/302 (n=60) · Strong · sales 248/268 (n=60) · Steady · sales 248/268 (n=40) · 🔎 Cleared his 228/248 (n=40)
  768: row h median/max — Explosive · sa 278/314 (n=60) · Strong · sales 278/296 (n=60) · Steady · sales 278/314 (n=40) · 🔎 Cleared his 275/296 (n=40)
  390: row h median/max — Explosive · sa 330/367 (n=60) · Strong · sales 330/347 (n=60) · Steady · sales 330/365 (n=40) · 🔎 Cleared his 327/347 (n=40)
```

### AFTER

```
### bonde_after.html
| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1440 | 1360 / 1360 | no | 1440 | 0/0 | 0 | yes | yes | ok / n/a | 40/40/40 | 97 / 107 | yes | 0 | 0/0 | PASS |
| 1280 | 1200 / 1200 | no | 1280 | 0/0 | 0 | yes | yes | ok / n/a | 40/40/40 | 120 / 134 | yes | 0 | 0/0 | PASS |
| 1024 | 944 / 1153 | yes | 1024 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40 | 120 / 153 | yes | 0 | 0/0 | PASS |
| 768 | 688 / 1057 | yes | 768 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40 | 158 / 193 | yes | 0 | 0/0 | PASS |
| 390 | 346 / 993 | yes | 390 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40 | 242 / 260 | yes | 0 | 0/0 | PASS |
  1440: row h median/max — Explosive · sa 97/107 (n=10) · Strong · sales 85/85 (n=1) · 🔎 Cleared his 87/87 (n=3)
  1280: row h median/max — Explosive · sa 120/134 (n=10) · Strong · sales 118/118 (n=1) · 🔎 Cleared his 120/120 (n=3)
  1024: row h median/max — Explosive · sa 120/153 (n=10) · Strong · sales 118/118 (n=1) · 🔎 Cleared his 120/138 (n=3)
  768: row h median/max — Explosive · sa 158/193 (n=10) · Strong · sales 136/136 (n=1) · 🔎 Cleared his 134/187 (n=3)
  390: row h median/max — Explosive · sa 242/260 (n=10) · Strong · sales 205/205 (n=1) · 🔎 Cleared his 222/235 (n=3)
### bonde_after-pivot.html
| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1440 | 1360 / 1360 | no | 1440 | 0/0 | 0 | yes | yes | ok / n/a | 112/40/40 | 107 / 120 | yes | 0 | 0/0 | PASS |
| 1280 | 1200 / 1225 | yes | 1280 | 0/0 | 0 | yes | yes | ok / 0 | 112/40/40 | 120 / 153 | yes | 0 | 0/0 | PASS |
| 1024 | 944 / 1225 | yes | 1024 | 0/0 | 0 | yes | yes | ok / 0 | 112/40/40 | 120 / 153 | yes | 0 | 0/0 | PASS |
| 768 | 688 / 1129 | yes | 768 | 0/0 | 0 | yes | yes | ok / 0 | 112/40/40 | 158 / 193 | yes | 0 | 0/0 | PASS |
| 390 | 346 / 1065 | yes | 390 | 0/0 | 0 | yes | yes | ok / 0 | 112/40/40 | 242 / 260 | yes | 0 | 0/0 | PASS |
  1440: row h median/max — Explosive · sa 107/120 (n=10) · Strong · sales 85/85 (n=1) · 🔎 Cleared his 87/87 (n=3)
  1280: row h median/max — Explosive · sa 120/153 (n=10) · Strong · sales 118/118 (n=1) · 🔎 Cleared his 120/120 (n=3)
  1024: row h median/max — Explosive · sa 120/153 (n=10) · Strong · sales 118/118 (n=1) · 🔎 Cleared his 120/138 (n=3)
  768: row h median/max — Explosive · sa 158/193 (n=10) · Strong · sales 136/136 (n=1) · 🔎 Cleared his 134/187 (n=3)
  390: row h median/max — Explosive · sa 242/260 (n=10) · Strong · sales 205/205 (n=1) · 🔎 Cleared his 222/235 (n=3)
### bonde_after_full.html
| viewport | box / content | scrolls | page | spill (closed/open) | head overlaps | heads over cells | last head reachable | pin bg / sticky Δpx | EP px | row h median / max (explosive) | first line | unpainted | mid-word (closed/open) | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1440 | 1360 / 1360 | no | 1440 | 0/0 | 0 | yes | yes | ok / n/a | 40/40/40/40 | 87 / 120 | yes | 0 | 0/0 | PASS |
| 1280 | 1200 / 1200 | no | 1280 | 0/0 | 0 | yes | yes | ok / n/a | 40/40/40/40 | 120 / 134 | yes | 0 | 0/0 | PASS |
| 1024 | 944 / 1153 | yes | 1024 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40/40 | 120 / 153 | yes | 0 | 0/0 | PASS |
| 768 | 688 / 1057 | yes | 768 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40/40 | 155 / 193 | yes | 0 | 0/0 | PASS |
| 390 | 346 / 993 | yes | 390 | 0/0 | 0 | yes | yes | ok / 0 | 40/40/40/40 | 235 / 292 | yes | 0 | 0/0 | PASS |
  1440: row h median/max — Explosive · sa 87/120 (n=60) · Strong · sales 97/118 (n=60) · Steady · sales 87/118 (n=40) · 🔎 Cleared his 87/99 (n=40)
  1280: row h median/max — Explosive · sa 120/134 (n=60) · Strong · sales 118/120 (n=60) · Steady · sales 118/120 (n=40) · 🔎 Cleared his 118/120 (n=40)
  1024: row h median/max — Explosive · sa 120/153 (n=60) · Strong · sales 120/139 (n=60) · Steady · sales 118/154 (n=40) · 🔎 Cleared his 120/138 (n=40)
  768: row h median/max — Explosive · sa 155/193 (n=60) · Strong · sales 155/187 (n=60) · Steady · sales 155/187 (n=40) · 🔎 Cleared his 153/187 (n=40)
  390: row h median/max — Explosive · sa 235/292 (n=60) · Strong · sales 239/272 (n=60) · Steady · sales 242/272 (n=40) · 🔎 Cleared his 222/272 (n=40)
```

**Phone density** (full board, explosive section, median / max row height): 390px **330 / 367 → 235 / 292**; 768px **278 / 314 → 155 / 193**. At 1440 **210 / 246 → 87 / 120**; at 1280 **228 / 248 → 120 / 134** (the ≤ ~90px target holds at 1440 only — HIS CALL 5).

**C11 (no mid-word break in the Ticker cell).** A token ends after a hyphen: a break after "-" is a normal browser break point ("2007-03-", "fiscal-"), not a broken word. The BEFORE mid-word counts above (15 at 1440-1024, 74 at 768/390 on the full board) are real letter-level breaks inside the "▸ all N" fold on the old stylesheets. The first build of this fix made them far worse (212 / 845 / 1,852 / 10,088 at 1440 / 1280 / 1024 / 768-390 — critic, 2026-09-28): `overflow-wrap: anywhere` on the Ticker cell reaches the fold, and a five-track fold inside a 12-34rem cell splits each entry into slivers. The fix: `.bd-sym .bd-pick-row` is **two tracks at every width** (`14px minmax(0, 1fr)`) with children 3+ (value, source, date link) pinned to the second track (`> :nth-child(n+3) { grid-column: 2 }`), so each criterion reads glyph · label, then value, source and link stacked under the label. A plain two-track fold without the pin auto-places every other entry into the 14px glyph track, which is what broke "$2.29" and "2007-03-30" letter by letter. AFTER: 0 mid-word breaks at every width on all three snapshots.

### Mutation checks

| Mutation | Result |
|---|---|
| `.bd-sym .cm-badge{white-space:nowrap}` | C3 FAIL at 1440 (3 cells) and every width |
| `.bd-metrics{display:flex}.bd-row.bd-hdr .bd-m{min-width:52px;white-space:nowrap}` | C4 (6 overlaps) + C4b FAIL at every width |
| `.bd-row > .bd-sym{position:static}` | C6b FAIL at 1024 (209px drift), 768, 390 |
| `.bd-row > .bd-sym{background:transparent}` | C6a FAIL at every width |
| `.bd-coname{display:none}` | C10 FAIL (14 unpainted) at every width |
| five-track `.bd-sym .bd-pick-row` (`14px minmax(0,1.3fr) minmax(0,0.6fr) minmax(0,1.4fr) auto`) | C11 [open] FAIL at 1280, 1024, 768, 390 |
| `.bd-sym .bd-pick-row>:nth-child(n+3){grid-column:auto}` | C11 [open] FAIL at every width |
| `.bd-sym .cm-badge` flipped to nowrap in styles.css | contracts (f) FAIL |
| `grid-column: 2` → `auto` in styles.css | contracts (n) FAIL |
| `.bd-sym .bd-pick-row` back to five tracks in styles.css | contracts (n) FAIL (two errors) |
| a five-track `.bd-sym .bd-pick-row` inside an `@media (min-width: 861px)` block | contracts (n) FAIL (NEGATIVE: no 3+ track template in any media block) |
| `bd-coname` div deleted | T5 FAIL |

C10 checks `display:none` / zero-size boxes only; it does not catch `visibility:hidden`, `opacity:0` or text coloured like its background (none is used in a Bonde row).

## 6. Nothing removed

Every row's text, titles, test ids and links deep-equal a golden written on the UNCHANGED component (T5, `bonde_real_2026_09_28.golden.json`). Nothing was removed, re-sorted, filtered or gated.

## 7. HIS CALL (defaults ship)

1. **EP collapse** — ON: narrow "EP" only when every served row of the section has no pivot. Alternatives: always full width, or a two-line "EPISODIC / PIVOT" at 4rem.
2. **Phones / narrow windows** — headers stay visible and the table scrolls sideways with the Ticker pinned (16rem ≤900, 12rem ≤600), replacing the header-less two-column stack. Numbers above. Alternatives: a 10rem pin ≤600, or the old stack on phones only.
3. **Only the pivot column collapses** — Today (an em-dash board-wide off-session) and Since report keep their widths so columns do not shift twice a day.
4. **Scope is the 📈 Bonde tab** — the 🚀 Explosive Growth `eg-table` is untouched.
5. **Row height at 1280** — the explosive median is 87px at 1440 but 120px at 1280 (the Ticker track narrows by ~160px, so line 2 wraps once more). The ≤ ~90px target is asserted at 1440 only. Alternative: tuning knob 3 (`--bd-w-char` 9 → 8rem) and knob 4 to buy width at 1280.

## 8. Re-run

```bash
cd frontend
BD_LAYOUT_SNAPSHOT=/tmp/bonde_after npx vitest run src/components/BondeBoard.layout.test.tsx -t probe
node scripts/bonde-layout-probe.mjs /tmp/bonde_after.html /tmp/bonde_after-pivot.html
npx vitest run src/components/BondeBoard.layout.test.tsx && node scripts/contracts.mjs
```

`BD_LAYOUT_FIXTURE=<full-board json>` writes a snapshot of another fixture of the same shape (no `-pivot` variant). `BD_PROBE_EXTRA_CSS='<rules>'` appends CSS for mutation checks.
