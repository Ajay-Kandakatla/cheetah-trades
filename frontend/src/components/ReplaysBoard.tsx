/* ReplaysBoard — 🎬 Replays tab on Chart Maps (2026-11-17, replays spec §3.3, WP-FE).
 *
 * Ajay 2026-11-17: "Can you store the videos in to the app please". The nightly replay videos live in his research
 * folder on the Mac; the api reads that folder through a read-only mount and serves ONE session at a time
 * (GET /chart-maps/replays[?date=]) plus the video bytes on an owner-only Range route. Owner only.
 *
 * ONE fetch on mount and on every session change (`?date=`); no polling. States: `no_folder` / `empty` → the served
 * title and text (plus the session select when the server lists dates); `ready` → the served window note → one
 * section per served group (served label, served order) with a card per video → the served 🎾 tracker block (its
 * title, its note — always printed when the block is served — and its table or its served empty text). REFIX
 * 2026-11-17: the server sends `rs` with `empty` too (a session with 🎾 ledger rows but no full-window video), so the
 * tracker block prints under the served text in `empty` whenever `rs` is served; `no_folder` never prints one. A
 * request that fails prints FETCH_FAILED (the ONE FE sentence).
 *
 * The FE composes NO word about a stock: every visible string is a served field. FE-typed: FETCH_FAILED, the select's
 * aria-label and the " · " separator. The `<video>` is `controls preload="metadata" playsInline` — never autoplay,
 * never muted, no poster, no download attribute. A served `src` off the owner video route renders no `<video>`.
 *
 * Written exemptions the contracts read (replays spec §7 #5 / #7):
 *   No house chips on this tab — the cards are videos, not ticker rows (replays spec §7 #7).
 *   ⚡ / 🧨 toggles: the served group order orders this board — nothing here ranks (replays spec §7 #5).
 * 2026-11-18: the 🏆 section (ReplaysPastWinners) mounts AFTER `.rp-board` in every state — it owns its own lazy GET
 * (only when opened), so this board's ONE GET and its `.rp-board` text are unchanged.
 * UNMEASURED — a replay is for his eyes, not a signal. */
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import {
  FETCH_FAILED, RP_DATE_PARAM, RP_PATH, rpDateParams, rpDates, rpList, rpPastWinChips, rpSelectDates, rpText, rpVideoSrc,
  type RpGroup, type RpPayload, type RpPotential, type RpRs, type RpVideo,
} from '../lib/replays';
import { TickerLink } from './TickerLink';
import ReplaysPastWinners from './ReplaysPastWinners';
import '../styles/replays.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: RpPayload };

const STATES = new Set(['no_folder', 'empty', 'ready']);

function Line({ text, className, testId }: { text: unknown; className: string; testId?: string }) {
  const t = rpText(text);
  return t ? <p className={className} data-testid={testId}>{t}</p> : null;
}

/** A served scalar as text: a string as itself, a finite number as its own digits, anything else nothing. */
function cell(x: unknown): string {
  if (typeof x === 'string') return x;
  if (typeof x === 'number' && Number.isFinite(x)) return String(x);
  return '';
}

function PlanLine({ potential }: { potential: RpPotential | null | undefined }) {
  if (!potential || typeof potential !== 'object') return null;
  const parts = [potential.first_stored_et, potential.trigger, potential.stop, potential.page_text, potential.setup_text]
    .map(cell).filter((s) => s.length > 0);
  return parts.length ? <p className="rp-plan" data-testid="rp-plan">{parts.join(' · ')}</p> : null;
}

function Card({ v }: { v: RpVideo }) {
  const src = rpVideoSrc(v);
  const chips = [v.setup_text, v.page_text, v.grade, v.speed_text, v.length_text].map(rpText).filter((s) => s.length > 0);
  const ringDay = v.carried === true ? rpText(v.ring_day) : '';
  const past = rpPastWinChips(v);
  return (
    <article className="rp-card" data-testid={`rp-card-${rpText(v.file)}`}>
      <div className="rp-head">
        {rpText(v.symbol) ? <TickerLink ticker={v.symbol} showWatchlist={false} /> : null}
        <div className="rp-chips">
          {chips.map((c, i) => <span key={`${i}-${c}`} className="rp-chip">{c}</span>)}
          {ringDay ? <span className="rp-chip" data-testid="rp-ring-day">{ringDay}</span> : null}
          {past.wins.map((c, i) => <span key={`pw${i}-${c}`} className="rp-chip rp-pastwin" data-testid="rp-pastwin">{c}</span>)}
          {past.more ? <span className="rp-chip rp-pastwin" data-testid="rp-pastwin-more">{past.more}</span> : null}
        </div>
      </div>
      {src ? <video className="rp-video" controls preload="metadata" playsInline src={src} /> : null}
      {rpList(v.why).map((w, i) => <p key={`${i}-${w}`} className="rp-why">{w}</p>)}
      <Line text={v.story} className="rp-story" />
      <PlanLine potential={v.potential} />
    </article>
  );
}

function Group({ g }: { g: RpGroup }) {
  const videos = Array.isArray(g.videos) ? g.videos : [];
  return (
    <section className="rp-group" data-testid={`rp-group-${rpText(g.key)}`}>
      <h2 className="rp-h">{rpText(g.label)}</h2>
      <div className="cm-grid rp-grid">
        {videos.map((v, i) => <Card key={`${rpText(v.file)}-${i}`} v={v} />)}
      </div>
    </section>
  );
}

function RsBlock({ rs }: { rs: RpRs }) {
  const columns = Array.isArray(rs.columns) ? rs.columns : [];
  const rows = Array.isArray(rs.rows) ? rs.rows : [];
  return (
    <section className="rp-rs" data-testid="rp-rs">
      <h2 className="rp-h">{rpText(rs.title)}</h2>
      <Line text={rs.note} className="rp-line rp-muted" testId="rp-rs-note" />
      {rows.length ? (
        <div className="rp-rs-wrap">
          <table className="rp-rs-table" data-testid="rp-rs-table">
            <thead><tr>{columns.map((c) => <th key={rpText(c.key)}>{rpText(c.label)}</th>)}</tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {columns.map((c) => <td key={rpText(c.key)}>{rpText(r && r.cells ? r.cells[c.key] : '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Line text={rs.text} className="rp-line" testId="rp-rs-text" />}
    </section>
  );
}

export default function ReplaysBoard() {
  const [params, setParams] = useSearchParams();
  const date = params.get(RP_DATE_PARAM);
  const [load, setLoad] = useState<Load>({ phase: 'loading' });

  /* ONE GET on mount and on every session change; no polling (the folder grows once a night). */
  useEffect(() => {
    let alive = true;
    setLoad({ phase: 'loading' });
    fetch(`${API}${RP_PATH}${date ? `?${RP_DATE_PARAM}=${encodeURIComponent(date)}` : ''}`,
      { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => {
        if (!alive) return;
        const ok = j && typeof j === 'object' && typeof j.state === 'string' && STATES.has(j.state);
        setLoad(ok ? { phase: 'loaded', p: j as RpPayload } : { phase: 'failed' });
      })
      .catch(() => { if (alive) setLoad({ phase: 'failed' }); });
    return () => { alive = false; };
  }, [date]);

  if (load.phase === 'loading') return <><div className="rp-board" data-state="loading" /><ReplaysPastWinners /></>;
  if (load.phase === 'failed') {
    return (
      <>
        <div className="rp-board" data-state="failed"><p className="rp-line" data-testid="rp-failed">{FETCH_FAILED}</p></div>
        <ReplaysPastWinners />
      </>
    );
  }
  const p = load.p;
  const dates = rpDates(p.dates);
  const served = rpText(p.date) || null;
  const options = rpSelectDates(dates, served);
  const groups = p.state === 'ready' && Array.isArray(p.groups) ? p.groups : [];
  const rs = (p.state === 'ready' || p.state === 'empty') && p.rs && typeof p.rs === 'object' ? p.rs : null;

  return (
    <>
    <div className="rp-board" data-state={p.state}>
      <Line text={p.title} className="rp-title" testId="rp-title" />
      {options.length ? (
        <select
          className="rp-select" aria-label="session" value={served ?? ''}
          onChange={(e) => {
            const v = e.target.value;
            setParams((prev) => rpDateParams(prev, v), { replace: true });
          }}
        >
          {options.map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.value}</option>)}
        </select>
      ) : null}
      {p.state === 'ready' ? (
        <>
          <Line text={p.window_note} className="rp-line rp-muted" testId="rp-window-note" />
          {groups.map((g, i) => <Group key={`${rpText(g.key)}-${i}`} g={g} />)}
          {rs ? <RsBlock rs={rs} /> : null}
        </>
      ) : (
        <>
          <Line text={p.text} className="rp-line" testId="rp-text" />
          {rs ? <RsBlock rs={rs} /> : null}
        </>
      )}
    </div>
    <ReplaysPastWinners />
    </>
  );
}
