/* HotPullbackBoard — the 🔥 Hot Pullback tab.
 *
 * Ajay 2026-09-09: "Can you create a new tab for hot pull back like 21 day
 * moving average drops but have a reversal from demand zones? The drop should
 * be someting like DYN today which bounced back quick. I wanna see such names
 * whcih dropped huge but have been hot in the market. Are having reversals"
 *
 * Backend: GET /supply-demand/hot-pullback (supply_demand/hot_pullback.py).
 * Every number rendered here comes off that payload, including the study block
 * and the rule lines — nothing about the strategy is typed into this file, so
 * the screen cannot drift from the module that enforces it.
 *
 * The one thing this component insists on: the measured HORIZON is printed
 * beside every row. The edge dies by day five (p=0.450), and a board that
 * showed the entry without that would be lying by omission.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

export type HpBand = { kind?: string; lo: number; hi: number; touches?: number | null; strength?: number | null };
export type HpPlan = {
  entry_note?: string | null; trigger?: number | null; trigger_note?: string | null;
  stop?: number | null; stop_note?: string | null; risk_from_close_pct?: number | null;
  target?: number | null; target_note?: string | null; target_pct?: number | null;
  rr?: number | null; horizon?: string | null;
};
export type HpRow = {
  symbol: string; date?: string | null; live?: boolean;
  close?: number | null; open?: number | null; high?: number | null; low?: number | null;
  prev_close?: number | null; change_pct?: number | null;
  ma21?: number | null; high_10d?: number | null;
  above_52w_low_pct?: number | null; flush_pct?: number | null; under_ma21_pct?: number | null;
  dollar_vol_musd?: number | null; vol_x?: number | null;
  reversal?: { off_low_pct: number; range_pos: number } | null;
  band?: HpBand | null; plan?: HpPlan | null; misses?: string[];
};
export type HpStudy = Record<string, number>;
export type HpPayload = {
  warming?: boolean; universe?: string; as_of?: string | null; zone_store_day?: string | null;
  scanned?: number | null; n?: number | null; rows?: HpRow[]; near_miss?: HpRow[];
  study?: HpStudy | null; rules?: string[]; cached?: boolean; error?: string | null;
};

export const EMPTY_TEXT = 'No hot name flushed into a demand band and turned today. This is a rare setup — 65 in two years.';
export const WARMING_TEXT = 'Scanning the universe for hot names that flushed into demand…';
export const NEAR_MISS_LABEL = 'One rule short';
const POLL_MS = 120_000;

export function pct(v: number | null | undefined, digits = 1): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}
export function money(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `$${v >= 1000 ? v.toFixed(0) : v.toFixed(2)}`;
}
export function bandText(b: HpBand | null | undefined): string {
  if (!b || typeof b.lo !== 'number' || typeof b.hi !== 'number') return '—';
  const t = typeof b.touches === 'number' && b.touches > 0 ? ` · ${b.touches}× tested` : '';
  return `$${b.lo.toFixed(2)}–${b.hi.toFixed(2)}${t}`;
}
/** The one-line headline. Says how rare the setup is so an empty board reads as
 *  information rather than as something being broken. */
export function headline(d: HpPayload | null): string {
  if (!d) return '';
  if (d.warming) return WARMING_TEXT;
  const n = d.n ?? 0;
  const scanned = d.scanned ?? 0;
  const near = (d.near_miss || []).length;
  const base = n === 1 ? '1 name' : `${n} names`;
  return `${base} of ${scanned.toLocaleString()} scanned${near ? ` · ${near} one rule short` : ''}`;
}
/** The measured line the board leads with — built from the payload's study. */
export function studyLine(s: HpStudy | null | undefined): string {
  if (!s) return '';
  // Two decimals on purpose: these are quoted STUDY figures, and rounding
  // +2.85% to "+2.9%" misstates a measured result on a board he trades from.
  return `Measured on ${s.events} events across ${s.names} names: entering at the next open returned a median `
    + `${pct(s.next_open_fwd1_pct, 2)} by the next close and ${pct(s.next_open_fwd2_pct, 2)} by day two `
    + `(${s.next_open_up2_pct}% up), against a placebo of ${pct(s.placebo_fwd1_pct, 2)} / ${pct(s.placebo_fwd3_pct, 2)}. `
    + `The edge is gone by day five (p=${s.fwd5_p}). Worst three-day in the sample: ${pct(s.worst_3d_pct)}.`;
}

function Row({ r }: { r: HpRow }) {
  const rev = r.reversal;
  return (
    <li className="hp-row" data-testid="hp-row">
      <div className="hp-row__head">
        <a className="hp-row__sym" href={`/chart-maps?tab=support&symbol=${encodeURIComponent(r.symbol)}`}>{r.symbol}</a>
        <span className="hp-row__px">{money(r.close)}</span>
        <span className="hp-row__chg is-dn">{pct(r.change_pct)}</span>
        {r.date && <span className="hp-row__date">{r.date}</span>}
        {r.vol_x ? <span className="hp-row__vol">{r.vol_x.toFixed(1)}× volume</span> : null}
      </div>
      <div className="hp-row__facts">
        <span><b>{pct(r.flush_pct)}</b> off the 10-day high</span>
        <span><b>{pct(r.under_ma21_pct)}</b> under the 21-day line</span>
        {rev && <span>closed <b>{pct(rev.off_low_pct)}</b> off the low</span>}
        {rev && <span><b>{Math.round(rev.range_pos * 100)}%</b> up the day&rsquo;s range</span>}
        <span>demand band <b>{bandText(r.band)}</b></span>
      </div>
      {r.plan && (
        <div className="hp-row__plan" data-testid="hp-plan">
          <span>entry: <b>{r.plan.entry_note}</b></span>
          {r.plan.trigger != null && <span>or over <b>{money(r.plan.trigger)}</b></span>}
          <span>stop <b>{money(r.plan.stop)}</b> ({pct(r.plan.risk_from_close_pct)} risk)</span>
          {r.plan.target != null && <span>target <b>{money(r.plan.target)}</b> ({pct(r.plan.target_pct)})</span>}
          <span className="hp-row__horizon">{r.plan.horizon}</span>
        </div>
      )}
    </li>
  );
}

export function HotPullbackBoard() {
  const [data, setData] = useState<HpPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showNear, setShowNear] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const seq = useRef(0);

  const load = useCallback(() => {
    const my = ++seq.current;
    fetch(`${API}/supply-demand/hot-pullback`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: HpPayload) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(t);
  }, [load]);

  const rows = useMemo(() => data?.rows || [], [data]);
  const near = useMemo(() => data?.near_miss || [], [data]);

  return (
    <section className="hp" data-testid="hot-pullback">
      <p className="hp__study" data-testid="hp-study">{studyLine(data?.study)}</p>
      <div className="hp__bar">
        <span className="hp__count">{headline(data)}</span>
        <span className="hp__spacer" />
        <button type="button" className="hp__refresh" onClick={() => load()}>Refresh</button>
      </div>

      {err && <p className="hp__err">Could not load: {err}</p>}
      {data?.warming && <p className="hp__note">{WARMING_TEXT}</p>}
      {!data?.warming && !err && rows.length === 0 && <p className="hp__note">{EMPTY_TEXT}</p>}

      {rows.length > 0 && <ul className="hp__list">{rows.map((r) => <Row key={r.symbol} r={r} />)}</ul>}

      {near.length > 0 && (
        <div className="hp__near">
          <button type="button" className="hp__more" aria-expanded={showNear}
                  onClick={() => setShowNear((v) => !v)}>
            {NEAR_MISS_LABEL} ({near.length})
          </button>
          {showNear && (
            <ul className="hp__nearlist">
              {near.map((r) => (
                <li key={r.symbol} data-testid="hp-near">
                  <a href={`/chart-maps?tab=support&symbol=${encodeURIComponent(r.symbol)}`}>{r.symbol}</a>
                  {' '}{money(r.close)} {pct(r.change_pct)} — {(r.misses || [])[0]}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(data?.rules || []).length > 0 && (
        <div className="hp__rules">
          <button type="button" className="hp__more" aria-expanded={showRules}
                  onClick={() => setShowRules((v) => !v)}>
            ℹ️ What decides a row
          </button>
          {showRules && (
            <ul className="hp__ruleslist">{(data?.rules || []).map((l) => <li key={l}>{l}</li>)}</ul>
          )}
        </div>
      )}

      {data?.as_of && (
        <p className="hp__asof">
          {data.as_of}{data.zone_store_day ? ` · bands from ${data.zone_store_day}` : ''}
        </p>
      )}
    </section>
  );
}
