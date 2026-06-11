/* PatternAccuracyMonthly — the month-by-month winners' record (Ajay
 * 2026-06-10: "track how accurate the winning patterns have been throughout
 * the months going forward… I do not want the data to be pruned — available
 * perpetually"). Backed by GET /patterns/accuracy/monthly, which reads the
 * pattern_accuracy_monthly Mongo collection: one doc per calendar month,
 * upsert-only, no TTL, no deletes — it only ever grows.
 *
 * Sits on the Portfolio page (where the paper trading happens) and the
 * Patterns page. Honesty: measured frequencies, small months = wide error
 * bars — the n is printed right next to every %. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type MonthPattern = {
  confirmed_n: number;
  win_pct: number | null;
  stop_pct: number | null;
  median_fwd_21d_pct: number | null;
  buyable_n: number;
  buyable_win_pct: number | null;
  forming_n: number;
  forming_confirm_pct: number | null;
};

type MonthRow = {
  month: string;                       // "2026-06"
  n_observations: number;
  confirmed_n: number;
  overall_win_pct: number | null;
  patterns: Record<string, MonthPattern>;
  candles: Record<string, { n: number; direction_hit_pct: number | null }>;
};

type Resp = { ok: boolean; months: MonthRow[]; retention?: string; disclaimer?: string };

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };

const PATTERN_LABEL: Record<string, string> = {
  double_bottom: 'Double bottom',
  triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv. H&S',
  cup_with_handle: 'Cup w/ handle',
};

function winColor(p: number | null): string {
  if (p == null) return C.sub;
  if (p >= 60) return C.green;
  if (p >= 40) return C.amber;
  return C.red;
}

function monthLabel(m: string): string {
  const [y, mo] = m.split('-');
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[Number(mo) - 1] ?? mo} ${y}`;
}

function Cell({ p }: { p: MonthPattern | undefined }) {
  if (!p || (!p.confirmed_n && !p.forming_n)) {
    return <td style={{ padding: '5px 8px', textAlign: 'center', color: C.sub }}>—</td>;
  }
  return (
    <td style={{ padding: '5px 8px', textAlign: 'center' }}
        title={`confirmed ${p.confirmed_n} (win ${p.win_pct ?? '—'}% · stop ${p.stop_pct ?? '—'}%` +
               `${p.median_fwd_21d_pct != null ? ` · median +21d ${p.median_fwd_21d_pct}%` : ''})` +
               `${p.buyable_n ? ` · buyable subset ${p.buyable_win_pct ?? '—'}% of ${p.buyable_n}` : ''}` +
               `${p.forming_n ? ` · forming→confirmed ${p.forming_confirm_pct ?? '—'}% of ${p.forming_n}` : ''}`}>
      {p.confirmed_n > 0 ? (
        <span style={{ color: winColor(p.win_pct), fontWeight: 700 }}>
          {p.win_pct != null ? `${Math.round(p.win_pct)}%` : '—'}
          <span style={{ color: C.sub, fontWeight: 400 }}> ({p.confirmed_n})</span>
        </span>
      ) : (
        <span style={{ color: C.muted, fontSize: '0.74rem' }}>
          form {p.forming_confirm_pct != null ? `${Math.round(p.forming_confirm_pct)}%` : '—'} ({p.forming_n})
        </span>
      )}
    </td>
  );
}

export function PatternAccuracyMonthly() {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/patterns/accuracy/monthly`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => alive && setData(d))
      .catch(() => alive && setErr(true));
    return () => { alive = false; };
  }, []);

  if (err) return null;                       // fail quiet — host page must render
  const months = (data?.months || []).slice().reverse();   // newest first

  // Columns: every pattern seen anywhere in the series, busiest first.
  const patternCols = Array.from(
    months.reduce((m, row) => {
      for (const [k, p] of Object.entries(row.patterns || {})) {
        m.set(k, (m.get(k) || 0) + p.confirmed_n + p.forming_n);
      }
      return m;
    }, new Map<string, number>()),
  ).sort((a, b) => b[1] - a[1]).map(([k]) => k);

  return (
    <section className="top-picks">
      <div className="top-picks__head">
        <span className="eyebrow">📈 Pattern accuracy by month — perpetual ledger</span>
        <span className="top-picks__meta mono">
          {months.length ? `${months.length} month${months.length === 1 ? '' : 's'} on record` : ''}
        </span>
      </div>

      {!data && <p className="mono" style={{ opacity: 0.7 }}>…loading the monthly record</p>}

      {data && months.length === 0 && (
        <p style={{ color: C.muted, fontSize: '0.84rem' }}>
          No resolved observations yet — the ledger started recording 2026-06-10 and each
          pattern needs its 21-bar window to complete before it grades. The first month
          fills in as outcomes resolve; nothing is ever deleted.
        </p>
      )}

      {months.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: C.sub, fontSize: '0.68rem', textTransform: 'uppercase' }}>
                <th style={{ textAlign: 'left', padding: '3px 8px' }}>Month</th>
                <th style={{ textAlign: 'center', padding: '3px 8px' }}
                    title="target-before-stop across ALL confirmed patterns that month">Overall win</th>
                {patternCols.map((k) => (
                  <th key={k} style={{ textAlign: 'center', padding: '3px 8px' }}>{PATTERN_LABEL[k] || k}</th>
                ))}
                <th style={{ textAlign: 'center', padding: '3px 8px' }}
                    title="candle reads whose next-5-bar direction matched">Candles</th>
              </tr>
            </thead>
            <tbody>
              {months.map((row) => {
                const candN = Object.values(row.candles || {}).reduce((s, c) => s + c.n, 0);
                const candHits = Object.values(row.candles || {}).reduce(
                  (s, c) => s + (c.direction_hit_pct != null ? (c.direction_hit_pct / 100) * c.n : 0), 0);
                return (
                  <tr key={row.month} style={{ borderTop: '1px solid var(--hairline,#2a2a2a)' }}>
                    <td style={{ padding: '5px 8px', fontWeight: 600 }}>{monthLabel(row.month)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'center' }}>
                      {row.confirmed_n ? (
                        <span style={{ color: winColor(row.overall_win_pct), fontWeight: 800 }}>
                          {row.overall_win_pct != null ? `${Math.round(row.overall_win_pct)}%` : '—'}
                          <span style={{ color: C.sub, fontWeight: 400 }}> ({row.confirmed_n})</span>
                        </span>
                      ) : <span style={{ color: C.sub }}>—</span>}
                    </td>
                    {patternCols.map((k) => <Cell key={k} p={row.patterns?.[k]} />)}
                    <td style={{ padding: '5px 8px', textAlign: 'center', color: C.muted }}>
                      {candN ? `${Math.round((candHits / candN) * 100)}% (${candN})` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="top-picks__foot mono">
        win % = target hit before stop within 21 bars · stored forever in Mongo (no TTL, no pruning) ·
        small months = wide error bars — read the n · measured frequencies, not promises
      </p>
    </section>
  );
}
