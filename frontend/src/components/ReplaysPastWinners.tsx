/* ReplaysPastWinners — the 🏆 Past winners section at the bottom of 🎬 Replays (2026-11-18, pastwinners spec §3.6).
 *
 * Ajay 2026-11-18 ~21:45 ET, verbatim: "can you work on todays videos and also..  Winners in general from the past".
 * Market-wide single-day winner reels (videos/winners/) + the multi-day runner reels (videos/multiday/), served by
 * GET /chart-maps/replays/winners (owner only) and played through the owner-only 🏆 video route.
 *
 * Placement (Rule #5, one line): ~500 rows is long, so the section sits at the bottom, collapsed, rows are text until
 * tapped, one video at a time.
 *
 * Collapsed by default. The header button toggles `?winners=1` through the functional setParams (every other param —
 * `tab`, `date` — survives). ONE GET only while open; nothing is fetched on the tab's mount. States: loading → nothing;
 * failed → FETCH_FAILED (reused, the ONE FE sentence); no_folder / empty → the served text; ready → the served note,
 * window note and summary, then per served group its served label and one compact text row per card (ticker + served
 * chips + a ▶ button). Exactly ONE video element is mounted, under the tapped row; tapping another row moves it. A served
 * `src` off the 🏆 video route → no video element. FE-typed: the section title (collapsed before any fetch), the ▶ glyph and
 * its aria-label. The spike chip prints only when `spike_print === true`.
 *
 * Written exemptions the contracts read (copied from the board):
 *   No house chips on this tab — the rows are videos, not ticker rows (replays spec §7 #7).
 *   ⚡ / 🧨 toggles: the served group order orders this board — nothing here ranks (replays spec §7 #5).
 * Hand-picked winners: descriptive, UNMEASURED, not a signal. */
import { useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import {
  FETCH_FAILED, RP_WINNERS_PARAM, RP_WINNERS_PATH, RP_WINNERS_TITLE, rpText, rpWinnerSrc, rpWinnersParams,
  type RpWinner, type RpWinnerGroup, type RpWinnersPayload,
} from '../lib/replays';
import { TickerLink } from './TickerLink';
import '../styles/replays.css';

type Load = { phase: 'idle' } | { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: RpWinnersPayload };

const STATES = new Set(['no_folder', 'empty', 'ready']);

function Line({ text, className, testId }: { text: unknown; className: string; testId?: string }) {
  const t = rpText(text);
  return t ? <p className={className} data-testid={testId}>{t}</p> : null;
}

const rowKey = (v: RpWinner): string => `${rpText(v.sub)}/${rpText(v.file)}`;

function Row({ v, playing, onPlay }: { v: RpWinner; playing: boolean; onPlay: () => void }) {
  const src = rpWinnerSrc(v);
  const before = [v.kind_text, v.gain_text, v.high_text].map(rpText).filter((s) => s.length > 0);
  const after = [v.pick_text, v.days_text, v.speed_text, v.length_text].map(rpText).filter((s) => s.length > 0);
  const spike = v.spike_print === true ? rpText(v.spike_text) : '';
  return (
    <div className="rpw-row" data-testid={`rpw-row-${rpText(v.sub)}-${rpText(v.file)}`}>
      <div className="rpw-head">
        {rpText(v.symbol) ? <TickerLink ticker={v.symbol} showWatchlist={false} /> : null}
        <div className="rpw-chips">
          {before.map((c, i) => <span key={`b${i}-${c}`} className="rpw-chip">{c}</span>)}
          {spike ? <span className="rpw-chip rpw-spike" data-testid="rpw-spike">{spike}</span> : null}
          {after.map((c, i) => <span key={`a${i}-${c}`} className="rpw-chip">{c}</span>)}
        </div>
        {src ? (
          <button type="button" className="rpw-play" aria-label="play" aria-pressed={playing} onClick={onPlay}>▶</button>
        ) : null}
      </div>
      {playing && src ? <video className="rp-video" controls preload="metadata" playsInline src={src} /> : null}
    </div>
  );
}

function Group({ g, playing, onPlay }: { g: RpWinnerGroup; playing: string | null; onPlay: (k: string) => void }) {
  const videos = Array.isArray(g.videos) ? g.videos : [];
  return (
    <section className="rpw-group" data-testid={`rpw-group-${rpText(g.date)}`}>
      <h3 className="rpw-h">{rpText(g.label)}</h3>
      {videos.map((v, i) => {
        const k = rowKey(v);
        return <Row key={`${k}-${i}`} v={v} playing={playing === k} onPlay={() => onPlay(k)} />;
      })}
    </section>
  );
}

export default function ReplaysPastWinners() {
  const [params, setParams] = useSearchParams();
  const open = params.get(RP_WINNERS_PARAM) === '1';
  const [load, setLoad] = useState<Load>({ phase: 'idle' });
  const [playing, setPlaying] = useState<string | null>(null);

  /* ONE GET each time the section opens; nothing while it is closed; no polling. */
  useEffect(() => {
    if (!open) { setLoad({ phase: 'idle' }); setPlaying(null); return; }
    let alive = true;
    setLoad({ phase: 'loading' });
    fetch(`${API}${RP_WINNERS_PATH}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => {
        if (!alive) return;
        const ok = j && typeof j === 'object' && typeof j.state === 'string' && STATES.has(j.state);
        setLoad(ok ? { phase: 'loaded', p: j as RpWinnersPayload } : { phase: 'failed' });
      })
      .catch(() => { if (alive) setLoad({ phase: 'failed' }); });
    return () => { alive = false; };
  }, [open]);

  let body: ReactNode = null;
  if (open && load.phase === 'failed') {
    body = <p className="rp-line" data-testid="rpw-failed">{FETCH_FAILED}</p>;
  } else if (open && load.phase === 'loaded') {
    const p = load.p;
    const groups = p.state === 'ready' && Array.isArray(p.groups) ? p.groups : [];
    body = p.state === 'ready' ? (
      <>
        <Line text={p.note} className="rp-line rp-muted" testId="rpw-note" />
        <Line text={p.window_note} className="rp-line rp-muted" testId="rpw-window-note" />
        <Line text={p.summary_text} className="rp-line" testId="rpw-summary" />
        {groups.map((g, i) => (
          <Group key={`${rpText(g.date)}-${i}`} g={g} playing={playing} onPlay={(k) => setPlaying(k)} />
        ))}
      </>
    ) : <Line text={p.text} className="rp-line" testId="rpw-text" />;
  }

  return (
    <section className="rpw-section" data-testid="rpw-section" data-state={open ? load.phase : 'closed'}>
      <button
        type="button" className="rpw-toggle" aria-expanded={open}
        onClick={() => setParams((prev) => rpWinnersParams(prev, !open), { replace: true })}
      >
        {RP_WINNERS_TITLE}
      </button>
      {body}
    </section>
  );
}
