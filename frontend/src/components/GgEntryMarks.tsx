/* 🟢 Gajjala sub-tab entry marks + ✨ 30-minute blinker (2026-11-12, spec §3.5). Ajay 2026-11-12 ~15:22 ET: "Can you show
 * me green on these tabs some indicators to show be which ones have best potential entries right now ... an Indicator or
 * new tickers with in last 30 mins like blinkers or something would be nice".
 *
 * Two pieces, both drawing ONLY what the server sent (backend chart_maps/gajjala/entry_marks.py):
 *  - GgSubMarksView — inside a sub chip: the 🟢 badge (the served label is drawn by CSS from `data-label`, so the chip's
 *    textContent stays byte-identical) and the ✨ pulsing dot while the served `until` is ahead. Both absolutely placed in
 *    the chip's top padding band (ggEntryMarks.css) — the chip's width never changes.
 *  - GgNewMark — at the end of a card's chip row: the pulsing dot + the served `text`, gone at the served `until`.
 * The component types no word and no number; an older API (no block) or an invalid block draws nothing. Display only —
 * UNMEASURED. */
import { useEffect, useState } from 'react';
import { markLive, msUntil, validGreen, validMark, validNew, type GgSubMarks } from '../lib/ggEntryMarks';
import '../styles/ggEntryMarks.css';

/** True while the served `until` is ahead; re-renders itself once at `until` (one timer, cleared on unmount / change). */
function useLiveUntil(until: unknown): boolean {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const ms = msUntil(until, Date.now());
    if (ms === null) return undefined;
    const id = setTimeout(() => setTick((n) => n + 1), ms + 1);
    return () => clearTimeout(id);
  }, [until, tick]);
  return markLive(until, Date.now());
}

/** 🟢 + ✨ for one sub chip — the served block for `subKey`, or nothing. */
export function GgSubMarksView({ subKey, block }: { subKey: string; block?: GgSubMarks | null }) {
  const green = validGreen(block?.green) ? block?.green : null;
  const fresh = validNew(block?.new) ? block?.new : null;
  const lit = useLiveUntil(fresh?.until);
  return (
    <>
      {green ? (
        <span className="gg-sub-green" data-testid={`gg-sub-green-${subKey}`} data-label={green.label}
              role="img" aria-label={green.title} title={green.title} />
      ) : null}
      {fresh && lit ? (
        <span className="gg-sub-new" data-testid={`gg-sub-new-${subKey}`}
              role="img" aria-label={fresh.title} title={fresh.title} />
      ) : null}
    </>
  );
}

/** ✨ the served card mark (tile.new_mark) — the dot + the served text while the served `until` is ahead. */
export function GgNewMark({ mark, sym }: { mark?: unknown; sym: string }) {
  const m = validMark(mark) ? mark : null;
  const lit = useLiveUntil(m?.until);
  if (!m || !lit) return null;
  return (
    <span className="gg-new-mark" data-testid={`gg-new-${sym}`} title={m.title}>
      <span className="gg-new-dot" aria-hidden="true" />{m.text}
    </span>
  );
}
