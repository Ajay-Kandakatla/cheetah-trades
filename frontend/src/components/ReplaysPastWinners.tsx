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
 * 2026-11-22 — setup + timing (his words verbatim in lib/replays.ts RpWinnerLabelFields and the ✨). A row of SERVED setup
 * chips with served counts filters the served cards client-side ('All' default, remembered in localStorage); each card
 * prints its served setup / class / ⛔ / timing text. Nothing here reorders and nothing here types a setup or timing word.
 * 2026-11-22 — ONE ROW PER STOCK (his AKAN ask verbatim in lib/replays.ts RpWinnerRow and the ✨) · "CLRO another
 * example add all the videos may be click them together". The server serves `rows` (one per symbol, every single-day AND multi-day
 * reel of it, newest first) in its order; each row is a collapsed header button printing served words (symbol, wins,
 * newest win, best setup, timing of the newest single-day reel). Tapping it lists the row's reels (the card above, still
 * ONE video at a time across the whole section). `?winners=1&sym=AKAN` opens that ONE row expanded. The filter keeps the
 * rows whose served `filter_keys` hold the pick; a remembered pick the server serves with 0 → All.
 * Hand-picked winners: descriptive, UNMEASURED, not a signal. */
import { useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import {
  FETCH_FAILED, RP_SETUP_ALL, RP_WINNERS_PARAM, RP_WINNERS_PATH, RP_WINNERS_TITLE, rpFilterWinnerRows,
  rpPastWinChips, rpPickedFilter, rpReadSetupFilter, rpSetupOptions, rpText, rpWinnerLabelChips, rpWinnerSrc,
  rpWinnersParams, rpWinnersSym, rpWriteSetupFilter,
  type RpSetupOption, type RpWinner, type RpWinnerRow, type RpWinnersPayload,
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
  const past = rpPastWinChips(v);
  const lab = rpWinnerLabelChips(v);
  return (
    <div className="rpw-row" data-testid={`rpw-row-${rpText(v.sub)}-${rpText(v.file)}`}>
      <div className="rpw-head">
        {rpText(v.symbol) ? <TickerLink ticker={v.symbol} showWatchlist={false} /> : null}
        <div className="rpw-chips">
          {lab.setup ? <span className="rpw-chip rpw-setup" data-testid="rpw-setup" data-setup={rpText(v.setup)}>{lab.setup}</span> : null}
          {lab.cls ? <span className="rpw-chip" data-testid="rpw-class">{lab.cls}</span> : null}
          {lab.also.map((c, i) => <span key={`al${i}-${c}`} className="rpw-chip rpw-also" data-testid="rpw-also">{c}</span>)}
          {lab.stopped ? <span className="rpw-chip rpw-stopped" data-testid="rpw-stopped">{lab.stopped}</span> : null}
          {lab.timing ? <span className="rpw-chip rpw-timing" data-testid="rpw-timing" data-timing={rpText(v.timing)}>{lab.timing}</span> : null}
          {before.map((c, i) => <span key={`b${i}-${c}`} className="rpw-chip">{c}</span>)}
          {spike ? <span className="rpw-chip rpw-spike" data-testid="rpw-spike">{spike}</span> : null}
          {after.map((c, i) => <span key={`a${i}-${c}`} className="rpw-chip">{c}</span>)}
          {past.wins.map((c, i) => <span key={`pw${i}-${c}`} className="rpw-chip rp-pastwin" data-testid="rpw-pastwin">{c}</span>)}
          {past.more ? <span className="rpw-chip rp-pastwin" data-testid="rpw-pastwin-more">{past.more}</span> : null}
        </div>
        {src ? (
          <button type="button" className="rpw-play" aria-label="play" aria-pressed={playing} onClick={onPlay}>▶</button>
        ) : null}
      </div>
      {playing && src ? <video className="rp-video" controls preload="metadata" playsInline src={src} /> : null}
    </div>
  );
}

/* 🏆 setup filter (2026-11-22): the SERVED options in served order ('All' first, then 🎾 …); a chip with a 0 count is
 * shown but disabled. Client-side filter on the served row `filter_keys` only — the served order is never changed. */
function SetupFilter({ opts, picked, onPick }: { opts: RpSetupOption[]; picked: string; onPick: (k: string) => void }) {
  if (!opts.length) return null;
  return (
    <div className="rpw-filter" role="group" data-testid="rpw-filter">
      {opts.map((o) => (
        <button
          key={o.key} type="button" className="rpw-fchip" aria-pressed={picked === o.key}
          disabled={o.count === 0 && o.key !== RP_SETUP_ALL} data-testid={`rpw-filter-${o.key}`}
          onClick={() => onPick(o.key)}
        >
          {o.label} <span className="rpw-fcount">{o.count}</span>
        </button>
      ))}
    </div>
  );
}

/* One stock: a header button (served words only) that opens / closes its reels. The served row order and the served
 * reel order inside it are kept. */
function StockRow({ r, open, onToggle, playing, onPlay }: {
  r: RpWinnerRow; open: boolean; onToggle: () => void; playing: string | null; onPlay: (k: string) => void;
}) {
  const sym = rpText(r.symbol);
  const videos = Array.isArray(r.videos) ? r.videos : [];
  const head = [r.wins_text, r.newest_text].map(rpText).filter((x) => x.length > 0);
  const setup = rpText(r.setup_text);
  const timing = rpText(r.timing_text);
  return (
    <section className="rpw-stock" data-testid={`rpw-stock-${sym}`} data-open={open ? '1' : '0'}>
      <button type="button" className="rpw-stock-head" aria-expanded={open} data-testid={`rpw-stock-toggle-${sym}`} onClick={onToggle}>
        <span className="rpw-stock-sym">{sym}</span>
        {head.map((c, i) => <span key={`h${i}-${c}`} className="rpw-chip">{c}</span>)}
        {setup ? <span className="rpw-chip rpw-setup" data-testid="rpw-stock-setup" data-setup={rpText(r.setup)}>{setup}</span> : null}
        {timing ? <span className="rpw-chip rpw-timing" data-testid="rpw-stock-timing" data-timing={rpText(r.timing)}>{timing}</span> : null}
      </button>
      {open ? (
        <div className="rpw-reels" data-testid={`rpw-reels-${sym}`}>
          {videos.map((v, i) => {
            const k = rowKey(v);
            return <Row key={`${k}-${i}`} v={v} playing={playing === k} onPlay={() => onPlay(k)} />;
          })}
        </div>
      ) : null}
    </section>
  );
}

export default function ReplaysPastWinners() {
  const [params, setParams] = useSearchParams();
  const open = params.get(RP_WINNERS_PARAM) === '1';
  const [load, setLoad] = useState<Load>({ phase: 'idle' });
  const [playing, setPlaying] = useState<string | null>(null);
  const [picked, setPicked] = useState<string>(() => rpReadSetupFilter() || RP_SETUP_ALL);
  const pick = (k: string) => { setPicked(k); rpWriteSetupFilter(k); };
  const urlSym = rpWinnersSym(params);
  /* Collapsed by default; the URL's `sym` row opens expanded (that row only). A tap toggles one row locally. */
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const isOpen = (sym: string) => (sym in toggled ? toggled[sym] : sym === urlSym && sym.length > 0);
  const toggle = (sym: string) => setToggled((prev) => ({ ...prev, [sym]: !isOpen(sym) }));

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
    const opts = rpSetupOptions(p.setups);
    const key = rpPickedFilter(opts, picked);          // a remembered key the server no longer serves, or serves with 0 → All
    const rows = p.state === 'ready' ? rpFilterWinnerRows(p.rows, key) : [];
    body = p.state === 'ready' ? (
      <>
        <Line text={p.note} className="rp-line rp-muted" testId="rpw-note" />
        <Line text={p.window_note} className="rp-line rp-muted" testId="rpw-window-note" />
        <Line text={p.summary_text} className="rp-line" testId="rpw-summary" />
        <SetupFilter opts={opts} picked={key} onPick={pick} />
        {rows.map((r, i) => {
          const sym = rpText(r.symbol);
          return (
            <StockRow
              key={`${rpText(r.key) || sym}-${i}`} r={r} open={isOpen(sym)} onToggle={() => toggle(sym)}
              playing={playing} onPlay={(k) => setPlaying(k)}
            />
          );
        })}
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
