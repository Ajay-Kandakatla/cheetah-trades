/* SepaWatchPanel — the SEPA-cross tape watch tab: watched names (holdings +
 * buyable + at-pivot + leaderboard) with the live 5-min candle read at their
 * levels, today's alerts (each self-graded vs the next 30 min), the live
 * per-state hit-rate, and the historical tape-read validation. Reads, not
 * predictions; the track record grades the system in public. */
import { useState } from 'react';
import { useSepaWatch, useTapeBacktest, type WatchRow, type WatchAlert } from '../hooks/useSepaWatch';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };

const STATE_COLOR: Record<string, string> = {
  BREAKOUT_STRONG: C.green, RECLAIM: C.green,
  BREAKOUT_WEAK: C.amber, STALL: C.muted,
  REJECTION: C.amber, BREAKDOWN: C.red,
};
const TAG_LABEL: Record<string, string> = {
  HOLDING: '💼', BUYABLE: '✅', AT_PIVOT: '🎯', LEADER: '🏆',
};

function fmtState(s: string) { return s.replace(/_/g, ' '); }
function vColor(v: string) { return v === 'constructive' ? C.green : v === 'deteriorating' ? C.red : C.muted; }

function WickBodyBar({ upper, body, lower, dir }: { upper: number; body: number; lower: number; dir: string }) {
  // tiny horizontal anatomy bar: lower wick | body | upper wick
  const w = 64;
  const bodyColor = dir === 'up' ? C.green : dir === 'down' ? C.red : C.muted;
  return (
    <span title={`body ${(body * 100).toFixed(0)}% · upper wick ${(upper * 100).toFixed(0)}% · lower wick ${(lower * 100).toFixed(0)}%`}
          style={{ display: 'inline-flex', width: w, height: 8, borderRadius: 3, overflow: 'hidden', background: 'var(--bg-sunken,#0f1115)', verticalAlign: 'middle' }}>
      <span style={{ width: `${lower * 100}%`, background: `${C.muted}66` }} />
      <span style={{ width: `${body * 100}%`, background: bodyColor }} />
      <span style={{ width: `${upper * 100}%`, background: `${C.muted}66` }} />
    </span>
  );
}

function Row({ r, onChart }: { r: WatchRow; onChart: (s: string) => void }) {
  const read = r.read;
  const sc = read ? (STATE_COLOR[read.state] || C.muted) : 'var(--hairline,#2a2a2a)';
  return (
    <div style={{ padding: '0.55rem 0.7rem', borderRadius: 10, marginBottom: 6,
                  background: 'var(--bg-raised,#16181d)', border: `1px solid ${read?.severity === 'alert' ? sc + '77' : 'var(--hairline,#2a2a2a)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => onChart(r.symbol)} title="Open the live chart"
                style={{ fontWeight: 800, fontSize: '0.95rem', background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}>
          {r.symbol}
        </button>
        <span style={{ fontSize: '0.72rem' }}>{r.tags.map((t) => TAG_LABEL[t] || t).join(' ')}</span>
        {read ? (
          <span style={{ fontSize: '0.7rem', fontWeight: 700, color: sc, border: `1px solid ${sc}55`, background: `${sc}14`, borderRadius: 5, padding: '1px 7px' }}>
            {fmtState(read.state)}
          </span>
        ) : (
          <span style={{ fontSize: '0.7rem', color: C.sub }}>no read</span>
        )}
        {read && <span style={{ fontSize: '0.72rem', color: vColor(read.verdict), fontWeight: 600 }}>{read.verdict}</span>}
        <span style={{ marginLeft: 'auto', fontVariantNumeric: 'tabular-nums', fontSize: '0.82rem' }}>${r.last_price}</span>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: '0.72rem', color: C.muted, alignItems: 'center', flexWrap: 'wrap' }}>
        {read && <WickBodyBar upper={read.metrics.upper_wick_pct} body={read.metrics.body_pct} lower={read.metrics.lower_wick_pct} dir={read.metrics.dir} />}
        {read?.metrics.vol_ratio != null && <span>{read.metrics.vol_ratio}× vol</span>}
        {r.vs_pivot_pct != null && <span>pivot {r.vs_pivot_pct > 0 ? '+' : ''}{r.vs_pivot_pct}%</span>}
        {r.vs_vwap_pct != null && <span>VWAP {r.vs_vwap_pct > 0 ? '+' : ''}{r.vs_vwap_pct}%</span>}
      </div>
      {read && read.severity === 'alert' && (
        <div style={{ fontSize: '0.72rem', color: C.muted, marginTop: 4 }}>{read.reasons[0]}</div>
      )}
    </div>
  );
}

function AlertRow({ a }: { a: WatchAlert }) {
  const sc = STATE_COLOR[a.state] || C.muted;
  const t = new Date(a.fired_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <div style={{ display: 'flex', gap: 10, fontSize: '0.76rem', padding: '2px 0', alignItems: 'center' }}>
      <span style={{ color: C.sub, width: 58 }}>{t}</span>
      <b style={{ width: 54 }}>{a.dedup.split(':')[0]}</b>
      <span style={{ color: sc, width: 130 }}>{fmtState(a.state)}</span>
      {a.fwd_pct == null
        ? <span style={{ color: C.sub }}>grading in 30m…</span>
        : <span style={{ color: a.graded === 'hit' ? C.green : C.red, fontWeight: 600 }}>
            +30m {a.fwd_pct > 0 ? '+' : ''}{a.fwd_pct}% · {a.graded?.toUpperCase()}
          </span>}
    </div>
  );
}

export function SepaWatchPanel({ active, onChart }: { active: boolean; onChart: (s: string) => void }) {
  const { data, error } = useSepaWatch(active);
  const [showValidation, setShowValidation] = useState(false);
  const bt = useTapeBacktest(active && showValidation);

  if (error) return <p className="mono" style={{ color: C.red }}>Couldn't load the watch — {error}</p>;
  if (!data) return <p className="mono" style={{ opacity: 0.7 }}>…loading the SEPA watch</p>;

  const tr = data.live_track_record || {};
  const trEntries = Object.entries(tr);

  return (
    <div>
      {/* Live self-graded track record */}
      <div style={{ padding: '0.55rem 0.75rem', borderRadius: 10, background: 'var(--bg-sunken,#0f1115)', border: '1px solid var(--hairline,#2a2a2a)', marginBottom: 12, fontSize: '0.78rem' }}>
        <div style={{ fontSize: '0.68rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>
          Live track record — every alert graded vs the next 30 min
        </div>
        {trEntries.length === 0
          ? <span style={{ color: C.muted }}>No graded alerts yet — fills in as the watch runs live sessions.</span>
          : trEntries.map(([state, s]) => (
              <span key={state} style={{ marginRight: 16 }}>
                <span style={{ color: STATE_COLOR[state] || C.muted, fontWeight: 700 }}>{fmtState(state)}</span>
                {' '}<b>{s.hit_rate_pct}%</b> hit ({s.n}) · med {s.median_fwd_30m_pct != null ? `${s.median_fwd_30m_pct > 0 ? '+' : ''}${s.median_fwd_30m_pct}%` : '—'}
              </span>
            ))}
        <button onClick={() => setShowValidation(!showValidation)}
                style={{ marginLeft: 8, background: 'transparent', border: '1px solid var(--hairline,#2a2a2a)', color: 'inherit', borderRadius: 6, padding: '0.1rem 0.5rem', cursor: 'pointer', fontSize: '0.7rem' }}>
          {showValidation ? 'hide' : 'show'} historical validation
        </button>
      </div>

      {showValidation && (
        <div style={{ padding: '0.55rem 0.75rem', borderRadius: 10, background: `${C.amber}0d`, border: `1px solid ${C.amber}33`, marginBottom: 12, fontSize: '0.76rem' }}>
          {bt.loading && <span className="mono" style={{ opacity: 0.7 }}>…classifying ~15 days of candles (first run warms the cache)</span>}
          {bt.error && <span style={{ color: C.red }}>validation failed — {bt.error}</span>}
          {bt.data && !bt.data.error && (
            <>
              <div style={{ fontSize: '0.68rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>
                Does the read work? {bt.data.days}d · {bt.data.symbols_used} names · {bt.data.n_events} events (OR/day-high/VWAP contexts — no historical pivot)
              </div>
              {Object.entries(bt.data.by_state).map(([state, s]) => (
                <div key={state} style={{ padding: '1px 0' }}>
                  <span style={{ color: STATE_COLOR[state] || C.muted, fontWeight: 700 }}>{fmtState(state)}</span>
                  {' '}n={s.n} · median +30m {s.median_fwd_30m_pct > 0 ? '+' : ''}{s.median_fwd_30m_pct}%
                  {s.follow_through_pct != null && <> · follow-through <b>{s.follow_through_pct}%</b></>}
                </div>
              ))}
              <div style={{ marginTop: 4, color: C.muted }}>{bt.data.verdict}</div>
            </>
          )}
        </div>
      )}

      {!data.market_open && (
        <div className="sepa-empty-card" style={{ marginBottom: 10 }}>
          <div className="eyebrow">Market closed</div>
          <p style={{ color: C.muted, margin: 0 }}>
            The watch runs every 5 minutes during the session (9:30–16:00 ET) and pushes alerts as candle reads
            trigger at the levels. Below is the last snapshot{data.generated_at ? '' : ' (none yet today)'}.
          </p>
        </div>
      )}

      {/* Watched names */}
      {data.rows.length > 0 ? (
        <>
          <div style={{ fontSize: '0.7rem', color: C.sub, marginBottom: 6 }}>
            {data.n_watched} watched (💼 holding · ✅ buyable · 🎯 at-pivot · 🏆 leader) · snapshot {data.generated_at ? new Date(data.generated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
          </div>
          {data.rows.map((r) => <Row key={r.symbol} r={r} onChart={onChart} />)}
        </>
      ) : (
        <p style={{ color: C.muted, fontSize: '0.84rem' }}>No snapshot yet — the first cron tick of the session populates this.</p>
      )}

      {/* Today's alerts */}
      {data.alerts_today.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: '0.7rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>Alerts today ({data.alerts_today.length})</div>
          {data.alerts_today.map((a) => <AlertRow key={a.dedup} a={a} />)}
        </div>
      )}

      <p style={{ fontSize: '0.66rem', color: C.sub, marginTop: 14 }}>{data.disclaimer}</p>
    </div>
  );
}
