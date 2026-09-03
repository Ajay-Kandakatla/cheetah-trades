/* RussellWatch — names about to be ADDED to the Russell 2000, and R2000
 * names sized for PROMOTION to the R1000.
 *
 * Ajay 2026-09-01, off the EMAT chatter: "check if there are more stock
 * like about to get added to russel 2000 or 1000 ... so we can track
 * those entries." Adds force index-fund buying at reconstitution;
 * promotions are usually NET tracker selling (more money follows R2000)
 * — the promotion table says so instead of implying a buy.
 *
 * Reads /catalysts/russell-watch. The payload's baseline/method notes are
 * RENDERED, not swallowed — the method is an approximation and the
 * membership snapshot is a manual file that goes stale after each recon.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export type AddEvent = {
  key: string; kind: 'reconstitution' | 'ipo_add'; label: string;
  rank_day: string; prelim: string; effective_close: string; in_index: string;
  lists_published: boolean; listed?: string | null;
};
type Row = {
  symbol: string; board: string; market_cap: number;
  price?: number | null; change_pct?: number | null; dollar_volume?: number | null;
  /** First build that flagged this name (ledger; seeded from the prior board). */
  first_seen?: string | null;
  /** Listing date from the profile provider — decides IPO-window vs reconstitution. */
  listed?: string | null;
  /** The FTSE event that would carry it in; null = calendar not loaded that far. */
  add_event?: AddEvent | null;
};
type Schedule = {
  verified_on: string; sources: string[]; upcoming: Array<Omit<AddEvent, 'lists_published' | 'listed'> & { ipo_window?: string[] }>; note: string;
};
type Payload = {
  adds_r2000: Row[]; promotions_r1000: Row[];
  schedule?: Schedule;
  bands: { r2000_p25_cap?: number | null; r1000_p10_cap?: number | null };
  baseline: { files_date?: string | null; note: string };
  coverage: { pool: number; no_cap_data: number; note: string };
  method_note: string; as_of: string;
};

const fmtCap = (v: number) =>
  v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`;

/* "Sep 21" from an ISO date (no timezone shift: dates are calendar days). */
export const mdy = (iso?: string | null) => {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return '—';
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
};

/* The add date column (Ajay 2026-09-02: "add the dates of these candidates
 * additions"): the day it would be IN the index, how it gets there, and the
 * honesty flag once FTSE's preliminary list is already out. */
export function AddsCell({ e }: { e?: AddEvent | null }) {
  if (!e) return <td className="og__num mono pcw__dim" title="FTSE calendar not loaded this far — verify on lseg.com/ftse-russell">schedule n/a</td>;
  const how = e.kind === 'ipo_add' ? 'IPO add' : 'recon';
  const title = `${e.label}: rank day ${mdy(e.rank_day)} · preliminary list ${mdy(e.prelim)} · effective after the close ${mdy(e.effective_close)} · in the index ${mdy(e.in_index)}`
    + (e.listed ? ` · listed ${e.listed}` : '')
    + (e.lists_published ? ' · FTSE\'s preliminary list is already out — this row is a guess at it, check the list' : '');
  return (
    <td className={`og__num mono rw__adds${e.lists_published ? ' is-listed' : ''}`} title={title}>
      <b>{mdy(e.in_index)}</b> <span className="pcw__dim">{how}{e.lists_published ? ' · list out' : ''}</span>
    </td>
  );
}

function Table({ title, hint, rows, band }: {
  title: string; hint: string; rows: Row[]; band?: number | null;
}) {
  return (
    <div className="rw__table">
      <h3 className="day-section__h">{title}</h3>
      <p className="rw__hint">{hint}{band ? <> Band floor ≈ <b>{fmtCap(band)}</b>.</> : null}</p>
      {rows.length === 0 ? (
        <div className="day-empty">No names clear the band right now.</div>
      ) : (
        <table className="og__table">
          <thead>
            <tr>
              <th>Symbol</th><th className="og__num">Mkt cap</th>
              <th className="og__num">Last</th><th className="og__num">Today</th>
              <th className="og__num">$ Vol today</th>
              <th className="og__num" title="first build that flagged this name">On list since</th>
              <th className="og__num" title="the day it would be IN the index, per FTSE's published calendar">Adds</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol}>
                <td className="og__sym"><TickerLink ticker={r.symbol} /></td>
                <td className="og__num mono">{fmtCap(r.market_cap)}</td>
                <td className="og__num mono">{r.price != null ? `$${r.price.toFixed(2)}` : '—'}</td>
                <td className={`og__num ${((r.change_pct ?? 0) >= 0) ? 'og__up' : 'og__dn'}`}>
                  {r.change_pct != null ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="og__num mono">{r.dollar_volume != null ? fmtCap(r.dollar_volume) : '—'}</td>
                <td className="og__num mono pcw__dim" title={r.first_seen ?? 'ledger unavailable'}>{mdy(r.first_seen)}</td>
                <AddsCell e={r.add_event} />
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function RussellWatch() {
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const my = ++seq.current;
    fetch(`${API}/catalysts/russell-watch`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) setData(j); })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);

  if (err) return <div className="cm-note cm-note-warn">Russell watch unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Sizing the field against the current index bands…</div>;

  return (
    <section className="day-section rw">
      <h2 className="day-section__h">Russell inclusion watch</h2>
      {data.schedule ? (
        <p className="rw__hint rw__sched">
          {data.schedule.upcoming.length === 0 ? (
            <>FTSE calendar loaded through {mdy(data.schedule.verified_on)} only — verify the next cycle on lseg.com/ftse-russell.</>
          ) : data.schedule.upcoming.map((e, i) => (
            <span key={e.key}>{i ? ' · ' : 'Next: '}<b>{e.label}</b> — rank day {mdy(e.rank_day)}, preliminary list {mdy(e.prelim)}, in the index {mdy(e.in_index)}</span>
          ))}
          <span className="pcw__dim"> · FTSE dates, verified {data.schedule.verified_on}</span>
        </p>
      ) : null}
      <Table
        title="→ Russell 2000 add candidates"
        hint="Not in the R3000 baseline, cap already inside the R2000 band — trackers must BUY these at the next reconstitution."
        rows={data.adds_r2000}
        band={data.bands?.r2000_p25_cap}
      />
      <Table
        title="→ Russell 1000 promotion candidates"
        hint="Current R2000 members sized for the R1000. Caution: promotions are usually NET SELLING by index funds — more money tracks the R2000 they leave."
        rows={data.promotions_r1000}
        band={data.bands?.r1000_p10_cap}
      />
      <p className="rw__note">
        Baseline: iShares files dated <b>{data.baseline?.files_date || 'unknown'}</b> — {data.baseline?.note}
      </p>
      {data.schedule?.note ? <p className="rw__note">{data.schedule.note}</p> : null}
      <p className="rw__note">{data.method_note}</p>
      <p className="rw__note">Coverage: {data.coverage?.pool} names watched, {data.coverage?.no_cap_data} without cap data yet — {data.coverage?.note}.</p>
    </section>
  );
}
