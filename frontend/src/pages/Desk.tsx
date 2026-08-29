/**
 * Desk — the daily pre-market trader report (Ajay 2026-08-28: "Add a cron
 * or daily routine use our data to do the analysis" through his pasted
 * momentum-trader persona).
 *
 * Read-only view over GET /desk/report: the cron builds one doc per ET
 * day at 8:40am. The page renders whatever the doc says — including
 * "nothing qualifies today", which is a first-class outcome here, not an
 * error state. Numbers come from the scorer; prose from the persona LLM
 * (or its deterministic fallback, labeled).
 */
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';

type Plan = { entry: number; stop: number; target1: number; target2: number;
              rr: number; risk_pct?: number | null };
type Idea = {
  symbol: string; module: string; score: number;
  parts: Record<string, number>; plan: Plan;
  size?: { shares: number; risk_dollars: number; cost: number } | null;
  industry?: string | null; theme?: string | null; sales_tier?: string | null;
  rs_rank?: number | null; earnings_in_days?: number | null;
  time_stop?: string; buyable?: boolean;
};
type Carried = { symbol: string; module?: string; status: string;
                 from?: string; last_close?: number };
type DeskReport = {
  date: string;
  params: Record<string, unknown>;
  regime: { verdict: string; label: string; drivers: string[];
            throttle: { note: string }; narrative?: string | null };
  book: Idea[]; watch: Idea[];
  cuts: { symbol: string; module: string; reasons: string[] }[];
  at_the_level: { gappers: any[]; gabbar_hits: any[] };
  position_ideas: { symbol: string; theme?: string | null; ps?: string;
                    rev_yoy?: string; psg?: string; why?: string }[];
  account: { value: number | null;
             knives: { ticker: string; verdict: string; signals: string[] }[] };
  context: { rotation?: { leading: string[]; lagging: string[];
                          havens: string[] } | null;
             gex?: Record<string, { regime?: string; date_et?: string }> | null;
             macro?: { level?: string; summary?: string } | null };
  carried_forward: Carried[];
  prose: { regime_lines: string[]; cards: Record<string, string>;
           bear_case: string; tilt_check: string; mind_changer: string;
           provider?: string };
  unavailable: string[]; nothing_qualifies: boolean; disclaimer: string;
};

const VERDICT_TONE: Record<string, string> = {
  RISK_ON: 'var(--positive)', MIXED: 'var(--warn)', RISK_OFF: 'var(--negative)',
};
const CARRIED_LABEL: Record<string, string> = {
  open: '🟢 open', target1_hit: '🎯 T1 hit', stopped: '🔴 stopped',
  not_triggered: '⏸ never triggered', no_new_bars: '… no bars yet',
  no_data: '❔ no data',
};

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      background: `color-mix(in srgb, ${color} 18%, transparent)`,
      color, border: `1px solid color-mix(in srgb, ${color} 45%, transparent)`,
      borderRadius: 'var(--r-2)', padding: '0.15rem 0.6rem',
      fontWeight: 700, fontSize: '0.9rem',
    }}>{text}</span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rot-section">
      <h3 style={{ margin: '0 0 0.6rem' }}>{title}</h3>
      {children}
    </section>
  );
}

function fmtParts(parts: Record<string, number>) {
  return ['catalyst', 'technical', 'asymmetry', 'liquidity', 'crowding']
    .map((k) => `${k.slice(0, 4)} ${parts[k] ?? 0}`).join(' · ');
}

export function Desk() {
  const [params, setParams] = useSearchParams();
  const date = params.get('date') || '';
  const [report, setReport] = useState<DeskReport | null>(null);
  const [runs, setRuns] = useState<{ date: string; verdict?: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const qs = date ? `?date=${encodeURIComponent(date)}` : '';
      const res = await fetch(`${API}/desk/report${qs}`, { credentials: 'include' });
      const j = await res.json();
      if (!res.ok || !j.ok) throw new Error(j.note || `HTTP ${res.status}`);
      setReport(j.report as DeskReport);
    } catch (e: any) {
      setErr(e?.message || 'failed to load');
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    let dead = false;
    fetch(`${API}/desk/history?limit=20`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (!dead && j?.runs) setRuns(j.runs); })
      .catch(() => {});
    return () => { dead = true; };
  }, []);

  if (loading) return <div className="card" style={{ margin: '1rem' }}>Loading the desk…</div>;
  if (err || !report) {
    return (
      <div className="card" style={{ margin: '1rem' }}>
        <h2>🧠 Desk</h2>
        <p>{err || 'No report.'}</p>
        <p style={{ opacity: 0.75 }}>The cron writes one report each weekday at 8:40am ET.</p>
      </div>
    );
  }

  const r = report;
  const tone = VERDICT_TONE[r.regime.verdict] || 'var(--warn)';

  return (
    <div style={{ padding: '0 1rem 2rem', maxWidth: 1080, margin: '0 auto' }}>
      <header style={{ display: 'flex', alignItems: 'baseline', gap: '0.8rem',
                       flexWrap: 'wrap', margin: '1rem 0 0.4rem' }}>
        <h2 style={{ margin: 0 }}>🧠 Desk</h2>
        <Pill text={r.regime.verdict.replace('_', '-')} color={tone} />
        <span style={{ opacity: 0.8 }}>{r.date}</span>
        {runs.length > 1 && (
          <select
            value={date || r.date}
            onChange={(e) => setParams(e.target.value === runs[0]?.date
              ? {} : { date: e.target.value })}
            style={{ marginLeft: 'auto' }}
            aria-label="report date"
          >
            {runs.map((x) => (
              <option key={x.date} value={x.date}>
                {x.date} {x.verdict ? `· ${x.verdict}` : ''}
              </option>
            ))}
          </select>
        )}
      </header>
      <p style={{ margin: '0 0 0.3rem', opacity: 0.85 }}>
        Throttle: {r.regime.throttle?.note}
        {r.account.value != null && <> · account ≈ ${Math.round(r.account.value).toLocaleString()}</>}
        {r.prose.provider === 'deterministic' && <> · <em>persona prose offline — deterministic text</em></>}
      </p>
      {r.prose.regime_lines?.map((l, i) => (
        <p key={i} style={{ margin: '0.15rem 0', opacity: 0.9 }}>{l}</p>
      ))}

      {r.account.knives.length > 0 && (
        <Section title="⚠️ Your holdings first">
          <ul style={{ margin: 0 }}>
            {r.account.knives.map((k) => (
              <li key={k.ticker}>
                <strong>{k.ticker}</strong> — {k.verdict}
                {k.signals.length > 0 && <> ({k.signals.join('; ')})</>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.nothing_qualifies ? (
        <Section title="Today's book">
          <div className="card" style={{ padding: '1rem', fontWeight: 600 }}>
            Nothing qualifies today. That is the answer, not a failure —
            cash is a position.
          </div>
        </Section>
      ) : (
        <Section title="Today's book">
          <div className="rot-scroll" style={{ overflowX: 'auto' }}>
            <table className="rot-table">
              <thead>
                <tr>
                  <th>Ticker</th><th>Mod</th><th>Score</th><th>Entry</th>
                  <th>Stop</th><th>T1 / T2</th><th>R:R</th><th>Shares</th>
                  <th>Time stop</th>
                </tr>
              </thead>
              <tbody>
                {r.book.map((i) => (
                  <tr key={i.symbol}>
                    <td>
                      <strong>{i.symbol}</strong>
                      {i.theme && <span style={{ opacity: 0.7 }}> · {i.theme}</span>}
                      {typeof i.earnings_in_days === 'number' && (
                        <span style={{ color: 'var(--warn)' }}> · ER {i.earnings_in_days}d</span>
                      )}
                    </td>
                    <td>{i.module}</td>
                    <td title={fmtParts(i.parts)}><strong>{i.score}</strong></td>
                    <td>{i.plan.entry}</td>
                    <td>{i.plan.stop}</td>
                    <td>{i.plan.target1} / {i.plan.target2}</td>
                    <td>{i.plan.rr}R</td>
                    <td>{i.size ? `${i.size.shares} (~$${Math.round(i.size.cost).toLocaleString()})` : '—'}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{i.time_stop}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ opacity: 0.7, margin: '0.4rem 0 0', fontSize: '0.85rem' }}>
            Hover a score for its sub-parts (catalyst 25 · technical 25 ·
            asymmetry 20 · liquidity 15 · crowding 15). Sized at{' '}
            {String((r.params as any).risk_pct_per_trade)}% risk per trade.
          </p>
        </Section>
      )}

      {Object.keys(r.prose.cards || {}).length > 0 && (
        <Section title="Thesis cards">
          {r.book.map((i) => r.prose.cards[i.symbol] && (
            <div className="card" key={i.symbol} style={{ margin: '0.5rem 0', padding: '0.7rem 0.9rem' }}>
              <strong>{i.symbol}</strong> — {r.prose.cards[i.symbol]}
            </div>
          ))}
        </Section>
      )}

      {!r.nothing_qualifies && r.prose.bear_case && (
        <Section title={`The bear case — ${r.book[0]?.symbol ?? ''}`}>
          <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{r.prose.bear_case}</p>
        </Section>
      )}

      {(r.at_the_level.gabbar_hits.length > 0 || r.at_the_level.gappers.length > 0) && (
        <Section title="At the level (module A)">
          {r.at_the_level.gabbar_hits.map((h: any, i: number) => (
            <p key={i} style={{ margin: '0.15rem 0' }}>
              🎯 <strong>{h.symbol}</strong> ${h.price} {h.state === 'in' ? 'inside' : `${h.dist_pct}% from`} Gabbar {h.label} (${h.lo}–${h.hi})
            </p>
          ))}
          {r.at_the_level.gappers.map((g: any, i: number) => (
            <p key={`g${i}`} style={{ margin: '0.15rem 0' }}>
              ⚡ <strong>{g.symbol || g.ticker}</strong> pre-market {g.change_pct ?? g.gap_pct}%
            </p>
          ))}
        </Section>
      )}

      {r.position_ideas.length > 0 && (
        <Section title="Position ideas (module C — Under Value)">
          <ul style={{ margin: 0 }}>
            {r.position_ideas.map((p) => (
              <li key={p.symbol}>
                <strong>{p.symbol}</strong>
                {p.psg && <> · PSG {p.psg}</>}
                {p.rev_yoy && <> · {p.rev_yoy}</>}
                {p.why && <span style={{ opacity: 0.8 }}> — {p.why}</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.watch.length > 0 && (
        <Section title="Watch, don't touch">
          <ul style={{ margin: 0 }}>
            {r.watch.map((w) => (
              <li key={w.symbol}>
                <strong>{w.symbol}</strong> ({w.score}) — promotes on a
                score ≥ 70 print with entry {w.plan?.entry ?? '—'} holding
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.cuts.length > 0 && (
        <Section title="Cut list">
          <ul style={{ margin: 0 }}>
            {r.cuts.map((c) => (
              <li key={c.symbol}>
                <strong>{c.symbol}</strong> — {c.reasons.join('; ')}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.carried_forward.length > 0 && (
        <Section title="Carried forward (yesterday's book, graded)">
          <ul style={{ margin: 0 }}>
            {r.carried_forward.map((c) => (
              <li key={`${c.from}-${c.symbol}`}>
                <strong>{c.symbol}</strong> ({c.from}) — {CARRIED_LABEL[c.status] || c.status}
                {typeof c.last_close === 'number' && <> · last {c.last_close}</>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Tilt check & what changes my mind">
        <p style={{ margin: '0.15rem 0' }}>{r.prose.tilt_check}</p>
        <p style={{ margin: '0.15rem 0' }}>{r.prose.mind_changer}</p>
        {r.context.rotation && (
          <p style={{ margin: '0.15rem 0', opacity: 0.8 }}>
            Rotation: leading {r.context.rotation.leading.join(', ')} · lagging{' '}
            {r.context.rotation.lagging.join(', ')}
          </p>
        )}
        {r.context.macro?.summary && (
          <p style={{ margin: '0.15rem 0', opacity: 0.8 }}>
            Macro ({r.context.macro.level}): {r.context.macro.summary}
          </p>
        )}
      </Section>

      <footer style={{ opacity: 0.65, fontSize: '0.85rem', marginTop: '1.2rem' }}>
        <p style={{ margin: '0.15rem 0' }}>
          Not scored (no verified source): {r.unavailable.join(' · ')}
        </p>
        <p style={{ margin: '0.15rem 0' }}>{r.disclaimer}</p>
      </footer>
    </div>
  );
}

export default Desk;
