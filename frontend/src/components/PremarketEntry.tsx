/* PremarketEntry — the "ready to enter" section of the ⚡ Signals tab.
 *
 * Ajay 2026-09-09: "I would like to see you ready to enter premarket category
 * for me from In demand and Deep demands with crons firing in the morning to
 * scan at 7 CT and another one regular market session but I need an entry
 * signal with mood considered and demand zone and other criterate we
 * discussed I wanna see this category in the signals page with a section
 * for it."
 *
 * Backend: GET /supply-demand/premarket-entry (supply_demand/premarket_entry.py).
 * Every number on screen comes from that payload — this file computes none of
 * the trading logic, it only groups and labels. Three grades:
 *
 *   READY   clears both standing gates, no measured drag
 *   WATCH   clears both gates but reclaiming from below (66% floor-stop rate)
 *           or a -3..-8% day (22% closed above the print)
 *   BLOCKED fails a gate — still listed, with the reason, because boards list
 *           everything and gates decide only what is tradable
 *
 * Mood prints on every row and breaks ties inside a grade. It can never
 * promote or block one; that separation is enforced in the backend and pinned
 * by a test there. The mood watcher was deleted on 2026-09-08 — this is the
 * context-only form he asked to keep.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

export type Drag = { key: string; text: string };
export type PeRow = {
  symbol: string; name?: string | null; grade: string;
  price?: number | null; change_pct?: number | null; above_band_pct?: number | null;
  session?: string | null;
  band?: { lo: number; hi: number } | null;
  room_txt?: string | null; approach_txt?: string | null; mood_txt?: string | null;
  plan?: string | null; drags?: Drag[]; blockers?: string[];
  confirm?: { state: string; move_pct: number; text: string } | null;
  sources?: string[];
};
export type PePayload = {
  warming?: boolean; pass?: string; universe?: string; as_of?: string | null;
  counts?: Record<string, number> | null; n?: number | null; rows?: PeRow[];
  zone_store_day?: string | null; market_closed?: string | null;
  rules?: string[]; cached?: boolean;
};

export const GRADES = ['READY', 'WATCH', 'BLOCKED'] as const;
export const EMPTY_TEXT = 'No name on either demand board is at its level right now.';
export const WARMING_TEXT = 'Scanning the demand boards for names at their level…';
export const BLOCKED_LABEL = 'Not tradable yet';
const POLL_MS = 90_000;

/** "+1.2%" / "−0.4%" / "—". Never NaN. */
export function pct(v: number | null | undefined, digits = 1): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

export function money(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `$${v >= 1000 ? v.toFixed(0) : v.toFixed(2)}`;
}

/** Where the print sits relative to the band, in words. */
export function bandText(r: PeRow): string {
  const a = r.above_band_pct;
  if (typeof a !== 'number' || !Number.isFinite(a)) return 'at the band';
  if (a < -0.05) return `${Math.abs(a).toFixed(2)}% inside the band`;
  if (a <= 0.05) return 'on the band top';
  return `${a.toFixed(2)}% above the band`;
}

/** Group rows by grade, preserving the backend's order within each group. */
export function byGrade(rows: PeRow[] | undefined): Record<string, PeRow[]> {
  const out: Record<string, PeRow[]> = { READY: [], WATCH: [], BLOCKED: [] };
  for (const r of rows || []) (out[r.grade] ||= []).push(r);
  return out;
}

/** The one-line summary above the section. */
export function headline(d: PePayload | null): string {
  if (!d) return '';
  if (d.warming) return WARMING_TEXT;
  const c = d.counts || {};
  const ready = c.READY || 0, watch = c.WATCH || 0, blocked = c.BLOCKED || 0;
  const when = d.pass === 'premarket' ? 'pre-market' : 'this session';
  const parts = [`${ready} ready`, `${watch} watching`];
  if (blocked) parts.push(`${blocked} blocked`);
  return `${parts.join(' · ')} — ${when}`;
}

function GradePill({ grade }: { grade: string }) {
  const cls = grade === 'READY' ? 'is-ready' : grade === 'WATCH' ? 'is-watch' : 'is-blocked';
  return <span className={`pe-pill ${cls}`}>{grade}</span>;
}

function Row({ r }: { r: PeRow }) {
  return (
    <li className="pe-row" data-testid="pe-row">
      <div className="pe-row__head">
        <a className="pe-row__sym" href={`/chart-maps?tab=support&symbol=${encodeURIComponent(r.symbol)}`}>
          {r.symbol}
        </a>
        <GradePill grade={r.grade} />
        <span className="pe-row__px">{money(r.price)}</span>
        <span className={`pe-row__chg ${(r.change_pct ?? 0) < 0 ? 'is-dn' : 'is-up'}`}>
          {pct(r.change_pct)}
        </span>
        <span className="pe-row__band">{bandText(r)}</span>
        {r.session && r.session !== 'rth' && <span className="pe-row__sess">{r.session}</span>}
      </div>
      {r.approach_txt && <div className="pe-row__line pe-row__approach">{r.approach_txt}</div>}
      {r.plan && <div className="pe-row__line pe-row__plan">{r.plan}</div>}
      {r.confirm && <div className="pe-row__line pe-row__confirm">{r.confirm.text}</div>}
      {(r.drags || []).map((d) => (
        <div className="pe-row__line pe-row__drag" key={d.key} data-testid="pe-drag">⚠ {d.text}</div>
      ))}
      {(r.blockers || []).map((b) => (
        <div className="pe-row__line pe-row__blocked" key={b} data-testid="pe-blocker">✕ {b}</div>
      ))}
      {r.mood_txt && <div className="pe-row__line pe-row__mood" data-testid="pe-mood">{r.mood_txt} · context only</div>}
    </li>
  );
}

export function PremarketEntry() {
  const [data, setData] = useState<PePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const [showBlocked, setShowBlocked] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [pass, setPass] = useState<string>('');   // '' = let the ET clock decide
  const seq = useRef(0);

  const load = useCallback(() => {
    const my = ++seq.current;
    const q = pass ? `?pass=${encodeURIComponent(pass)}` : '';
    fetch(`${API}/supply-demand/premarket-entry${q}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: PePayload) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, [pass]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(t);
  }, [load]);

  const groups = useMemo(() => byGrade(data?.rows), [data]);
  const shown = useMemo(
    () => [...groups.READY, ...groups.WATCH], [groups],
  );

  return (
    <section className="pe" data-testid="premarket-entry">
      <header className="pe__head">
        <button type="button" className="pe__toggle" aria-expanded={open}
                onClick={() => setOpen((v) => !v)}>
          <h3 className="pe__title">🎯 Ready to enter</h3>
        </button>
        <span className="pe__count">{headline(data)}</span>
        <span className="pe__spacer" />
        <select className="pe__pass" aria-label="Which pass" value={pass}
                onChange={(e) => setPass(e.target.value)}>
          <option value="">Auto (by the clock)</option>
          <option value="premarket">Pre-market</option>
          <option value="session">Session</option>
        </select>
        <button type="button" className="pe__refresh" onClick={() => load()}>Refresh</button>
      </header>

      {open && (
        <div className="pe__body">
          <p className="pe__sub">
            The Back in Demand and Deep Demand names that are actually at their level,
            graded by the two standing gates and the measured drags. Mood rides along as
            context and never decides a grade. Not advice.
          </p>

          {err && <p className="pe__err">Could not load: {err}</p>}
          {data?.market_closed && (
            <p className="pe__closed">Market closed ({data.market_closed}) — showing the last session.</p>
          )}
          {data?.warming && <p className="pe__warming">{WARMING_TEXT}</p>}

          {!data?.warming && shown.length === 0 && !err && (
            <p className="pe__empty">{EMPTY_TEXT}</p>
          )}

          {shown.length > 0 && <ul className="pe__list">{shown.map((r) => <Row key={r.symbol} r={r} />)}</ul>}

          {groups.BLOCKED.length > 0 && (
            <div className="pe__blocked">
              <button type="button" className="pe__more" aria-expanded={showBlocked}
                      onClick={() => setShowBlocked((v) => !v)}>
                {BLOCKED_LABEL} ({groups.BLOCKED.length})
              </button>
              {showBlocked && <ul className="pe__list">{groups.BLOCKED.map((r) => <Row key={r.symbol} r={r} />)}</ul>}
            </div>
          )}

          {(data?.rules || []).length > 0 && (
            <div className="pe__rules">
              <button type="button" className="pe__more" aria-expanded={showRules}
                      onClick={() => setShowRules((v) => !v)}>
                ℹ️ What decides a grade
              </button>
              {showRules && (
                <ul className="pe__ruleslist">
                  {(data?.rules || []).map((l) => <li key={l}>{l}</li>)}
                </ul>
              )}
            </div>
          )}

          {data?.as_of && (
            <p className="pe__asof">
              {data.pass === 'premarket' ? 'Pre-market pass' : 'Session pass'} · {data.as_of}
              {data.zone_store_day ? ` · bands from ${data.zone_store_day}` : ''}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
