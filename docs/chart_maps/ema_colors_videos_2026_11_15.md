# 9 / 21 EMA colours like the replay videos (2026-11-15)

Ajay, verbatim: "I need something in the videos you show different colors yellow for 9 EMA here and its inverted in the app
also can you switch its up in the app please..  Also make the lines a little more thick"

- The videos (eod-audits/replays/replay_gif.py PALETTE) draw the 9 EMA yellow (250,204,21) and the 21 EMA purple
  (190,120,255). The app drew the 9 blue (--cm-vcp) and the 21 amber (--cm-amberlt), so the yellow-ish line was the 21.
- Now `toneColor('ema9')` = `EMA_BOLD.ema9.color` (#FACC15) and `toneColor('ema21')` = `EMA_BOLD.ema21.color` (#BE78FF)
  — every PatternChart (all Chart Maps boards, Gajjala, Luk, Support, Signals…), the 9 EMA checkbox swatch, the
  price-gutter labels, and LiveCandlesChart (scalping) read them.
- Thickness: ordinary charts draw the 9 / 21 at `EMA_LINE_W` = 2 px (was 1.1); the 👀 Watch bold charts 2 → 3 px.
  LiveCandlesChart 1 → 2 px. Other curves (Keltner, 20 / 200 SMA) unchanged.
- Note: the 200 SMA stays gold (#c9a227) — close in hue to the new yellow 9; the 20 SMA stays mint.
- Display only. No scan, gate, sort or alert reads a colour.
