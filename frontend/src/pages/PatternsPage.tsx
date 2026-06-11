/* /patterns — on-demand bullish-reversal pattern scan ("full scan button like
 * SEPA"). Owner hits ⚡ Scan Patterns → background scan over the SEPA universe's
 * cached daily frames → confirmed/forming double bottoms + inverse H&S with
 * SEPA context, plus OUR universe's measured +21-bar outcomes per pattern
 * (self-validation) beside the practitioner base rates. A pattern without its
 * confirmation close is a shape, not a signal. Educational, not advice. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { useCurrentUser } from '../hooks/useUser';
import { InfoButton } from '../components/InfoButton';
import { PatternMatchCards } from '../components/PatternMatchCards';
import { PatternAccuracyMonthly } from '../components/PatternAccuracyMonthly';
import { ClampText } from '../components/Collapsible';
import { TickerCell } from '../components/TickerCell';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#8a93a6', gold: 'var(--gold,#c9a227)' };

type Sepa = { rs_rank?: number | null; score?: number | null; stage?: number | null; is_candidate?: boolean; is_buyable?: boolean };
type Pattern = {
  symbol: string; pattern: string; status: 'confirmed' | 'forming';
  lows: { date: string; price: number }[];
  neckline: number; pattern_low: number; target: number; stop: number; last_close: number;
  confirmed_date?: string; bars_since_confirm?: number; ext_past_confirm_pct?: number;
  to_confirm_pct?: number; sepa?: Sepa;
};
type Validation = Record<string, { n: number; pct_positive_21d: number; median_fwd_21d_pct: number; median_max_gain_21d_pct: number }>;
type Latest = {
  generated_at: number; symbols_scanned?: number; n_found: number; results: Pattern[];
  validation?: Validation; validation_note?: string; disclaimer?: string; note?: string;
};
type ScanStatus = { running: boolean; scope?: string; done: number; total: number; error?: string | null };
type AccConfirmed = {
  n: number; target_before_stop_pct?: number | null; stop_first_pct?: number | null;
  neither_pct?: number | null; pct_positive_21d?: number | null; median_fwd_21d_pct?: number | null;
  buyable_n?: number; buyable_target_before_stop_pct?: number | null;
};
type AccForming = { n: number; went_on_to_confirm_pct?: number | null; stopped_first_pct?: number | null; expired_pct?: number | null };
type Accuracy = {
  ok: boolean; patterns: Record<string, { confirmed?: AccConfirmed; forming?: AccForming }>;
  candles: Record<string, { n: number; direction_hit_pct?: number | null; median_fwd_5d_pct?: number | null }>;
  pending: number; since?: string | null; disclaimer?: string;
};
type CandleFormation = { name: string; date: string; read: string; note: string; stat?: string };
type Candles = {
  formations: CandleFormation[];
  last_bar?: { read?: string; date?: string; vol_ratio?: number | null } | null;
  trend?: string;
};
type Verdict = {
  symbol: string; sepa?: Sepa; matches: Pattern[]; historical?: Record<string, number>;
  candles?: Candles | null; no_match: boolean; error?: string; sources?: string[];
};
type QualLatest = {
  generated_at: number; n_symbols: number; n_matched?: number; n_candle_only?: number;
  n_no_match?: number; verdicts: Verdict[]; disclaimer?: string; note?: string;
};

const PATTERN_LABEL: Record<string, string> = {
  double_bottom: 'Double bottom (W)', inverse_head_shoulders: 'Inverse head & shoulders',
  triple_bottom: 'Triple bottom', cup_with_handle: 'Cup with handle',
};
// Practitioner base rates — Bulkowski database, quoted in the ONLY permitted
// framing (verified pass 2026-06-09): break-even failure rates with the full
// caveat. Never win rates, average rises, or expected returns.
const BULKOWSKI: Record<string, string> = {
  double_bottom: 'Bulkowski (daily bars, bull-market sample, hindsight-measured, no costs): break-even failure 12–16% across Adam/Eve variants; unconfirmed double bottoms continue LOWER 48% of the time',
  inverse_head_shoulders: 'Bulkowski (n=3,197; daily bars, hindsight-measured, no costs): break-even failure 11%, throwback rate 65%, rank 13 of 39',
  triple_bottom: 'Bulkowski (n>2,500; daily bars, bull-market sample, hindsight-measured, no costs): break-even failure 13%, throwback rate 65%, rank 12 of 39',
  cup_with_handle: 'Bulkowski (n=913; daily bars, bull-market, hindsight, no costs): break-even failure 5%, throwback 62%, rank 3 of 39 — yet his 1990–2024 lesson: 47% dropped substantially within two months of the breakout',
};
const CANDLE_META: Record<string, { label: string; icon: string }> = {
  hammer: { label: 'Hammer', icon: '🔨' },
  shooting_star: { label: 'Shooting star', icon: '☄️' },
  doji: { label: 'Doji', icon: '➖' },
  bullish_engulfing: { label: 'Bullish engulfing', icon: '🟢' },
  bearish_engulfing: { label: 'Bearish engulfing', icon: '🔴' },
  morning_star: { label: 'Morning star', icon: '🌅' },
};
const READ_COLOR: Record<string, string> = {
  bullish_reversal_setup: C.green, bearish_warning: C.red, indecision: C.muted,
};

const PageInfo = (
  <>
    <p><strong>Patterns</strong> — an on-demand scan for bullish-reversal geometry on daily bars:
      <strong> double bottoms</strong>, <strong>triple bottoms</strong>, <strong>inverse head &amp; shoulders</strong> and
      <strong> cup-with-handles</strong>, found across the SEPA universe's cached charts.</p>
    <p><strong>🎯 Scan Qualifiers</strong> answers <em>every</em> current SEPA qualifier: the pattern(s) its chart matches
      right now, recent candle formations (hammer, engulfing, morning star — each shown with Bulkowski's measured
      frequency AND the academic null), or an explicit <em>no pattern</em>. A chart-analysis input beside SEPA, VCP and volume.</p>
    <p>Discipline: a pattern only counts when it <strong>closes above its confirmation line</strong> (the interim peak / neckline) —
      before that it's listed as "forming", a shape to watch, not a signal. Targets use the measure rule; stops sit under the pattern low.</p>
    <p>Evidence, honestly: Lo, Mamaysky &amp; Wang (2000, J. Finance) found algorithmically-detected patterns carry
      <em> informational content</em> — not guaranteed profit. Bulkowski's base rates are daily-bar, no-cost statistics.
      So every scan also measures <strong>our own universe's</strong> +21-bar outcomes for historically confirmed patterns — that record is shown first.</p>
    <p className="mono">Not advice.</p>
  </>
);

export function PatternsPage() {
  const { user } = useCurrentUser();
  const navigate = useNavigate();
  const [latest, setLatest] = useState<Latest | null>(null);
  const [quals, setQuals] = useState<QualLatest | null>(null);
  const [acc, setAcc] = useState<Accuracy | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadLatest = useCallback(() => {
    fetch(`${API}/patterns/latest`, { cache: 'no-store' })
      .then((r) => r.json()).then(setLatest).catch((e) => setErr(String(e)));
    fetch(`${API}/patterns/qualifiers`, { cache: 'no-store' })
      .then((r) => r.json()).then(setQuals).catch(() => undefined);
    fetch(`${API}/patterns/accuracy`, { cache: 'no-store' })
      .then((r) => r.json()).then(setAcc).catch(() => undefined);
  }, []);

  useEffect(() => { loadLatest(); return () => { if (pollRef.current) window.clearInterval(pollRef.current); }; }, [loadLatest]);

  const startScan = async (scope: 'universe' | 'qualifiers') => {
    setErr(null);
    try {
      const r = await fetch(`${API}/patterns/scan`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setScanStatus({ ...(await r.json()), scope });
      pollRef.current = window.setInterval(async () => {
        try {
          const s: ScanStatus = await (await fetch(`${API}/patterns/scan/status`, { cache: 'no-store' })).json();
          setScanStatus(s);
          if (!s.running) {
            if (pollRef.current) window.clearInterval(pollRef.current);
            pollRef.current = null;
            loadLatest();
          }
        } catch { /* keep polling */ }
      }, 2000);
    } catch (e) {
      setErr(String(e));
    }
  };

  const confirmed = (latest?.results || []).filter((p) => p.status === 'confirmed');
  const forming = (latest?.results || []).filter((p) => p.status === 'forming');
  const val = latest?.validation || {};

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Bullish reversals · confirmation-line discipline</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Patterns
            <InfoButton inline title="Patterns">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">Double bottoms, triple bottoms, inverse H&amp;S &amp; cup-with-handles across the SEPA universe — confirmed vs forming, with our own measured record beside the book numbers.</p>
        </div>
        {user?.is_admin && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => startScan('qualifiers')} disabled={!!scanStatus?.running}
                    title="Answer EVERY current SEPA qualifier: which Bulkowski pattern its chart matches right now — or that it matches none"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem',
                             borderRadius: 8, cursor: scanStatus?.running ? 'wait' : 'pointer', fontWeight: 600,
                             fontSize: '0.8rem', background: 'transparent', color: C.gold,
                             border: `1px solid ${C.gold}88`, opacity: scanStatus?.running ? 0.7 : 1 }}>
              🎯 {scanStatus?.running && scanStatus.scope === 'qualifiers' ? 'Scanning…' : 'Scan Qualifiers'}
            </button>
            <button onClick={() => startScan('universe')} disabled={!!scanStatus?.running}
                    title="Scan the whole SEPA universe's cached daily charts for bullish-reversal patterns"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem',
                             borderRadius: 8, cursor: scanStatus?.running ? 'wait' : 'pointer', fontWeight: 600,
                             fontSize: '0.8rem', background: C.gold, color: '#1a1a1a', border: 'none',
                             opacity: scanStatus?.running ? 0.7 : 1 }}>
              ⚡ {scanStatus?.running && scanStatus.scope !== 'qualifiers' ? 'Scanning…' : 'Scan Patterns'}
            </button>
          </div>
        )}
      </div>

      {scanStatus?.running && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.76rem', color: C.muted, marginBottom: 4 }}>
            Scanning {scanStatus.done}/{scanStatus.total || '…'} charts (cached daily frames — no provider calls)
          </div>
          <div style={{ height: 8, borderRadius: 4, background: 'var(--bg-sunken,#0f1115)', overflow: 'hidden' }}>
            <div style={{ width: scanStatus.total ? `${(scanStatus.done / scanStatus.total) * 100}%` : '5%',
                          height: '100%', background: C.gold, transition: 'width 0.5s' }} />
          </div>
        </div>
      )}
      {scanStatus?.error && <p className="mono" style={{ color: C.red }}>Scan failed — {scanStatus.error}</p>}
      {err && <p className="mono" style={{ color: C.red }}>{err}</p>}

      {/* OUR universe's measured record — shown before any book number */}
      {Object.keys(val).length > 0 && (
        <div style={{ padding: '0.6rem 0.8rem', borderRadius: 10, background: 'var(--bg-sunken,#0f1115)',
                      border: '1px solid var(--hairline,#2a2a2a)', marginBottom: 12, fontSize: '0.78rem' }}>
          <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>
            Our universe's record — confirmed patterns, +21 trading days (gross, no costs)
          </div>
          {Object.entries(val).map(([k, v]) => (
            <div key={k} style={{ padding: '1px 0' }}>
              <b>{PATTERN_LABEL[k] || k}</b>: n={v.n} · {v.pct_positive_21d}% positive ·
              median {v.median_fwd_21d_pct > 0 ? '+' : ''}{v.median_fwd_21d_pct}% · median max gain +{v.median_max_gain_21d_pct}%
            </div>
          ))}
          {latest?.validation_note && <div style={{ color: C.sub, marginTop: 4, fontSize: '0.7rem' }}>{latest.validation_note}</div>}
        </div>
      )}

      {/* LIVE forward record — every flagged pattern, graded later against the
          real tape. This is the "are our patterns accurate?" ledger; it grows
          a row per flagged event from 2026-06-10 onward. */}
      {acc?.ok && (Object.keys(acc.patterns).length > 0 || Object.keys(acc.candles).length > 0 || acc.pending > 0) && (
        <div style={{ padding: '0.6rem 0.8rem', borderRadius: 10, background: 'var(--bg-sunken,#0f1115)',
                      border: '1px solid var(--hairline,#2a2a2a)', marginBottom: 12, fontSize: '0.78rem' }}>
          <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>
            📊 Live forward record — what WE flagged, graded against what happened
            {acc.since ? ` · since ${acc.since}` : ''} {acc.pending > 0 ? ` · ${acc.pending} awaiting their window` : ''}
          </div>
          {Object.entries(acc.patterns).map(([k, v]) => (
            <div key={k} style={{ padding: '1px 0' }}>
              <b>{PATTERN_LABEL[k] || k}</b>:
              {v.confirmed && v.confirmed.n > 0 && (
                <> confirmed n={v.confirmed.n} · <b style={{ color: (v.confirmed.target_before_stop_pct ?? 0) >= 50 ? C.green : C.amber }}>
                  {v.confirmed.target_before_stop_pct ?? '—'}%</b> hit target before stop ·
                  {' '}{v.confirmed.pct_positive_21d ?? '—'}% positive +21d
                  {v.confirmed.median_fwd_21d_pct != null && <> · median {v.confirmed.median_fwd_21d_pct > 0 ? '+' : ''}{v.confirmed.median_fwd_21d_pct}%</>}
                  {(v.confirmed.buyable_n ?? 0) > 0 && <> · <span title="The subset that ALSO cleared the full Minervini buy gate when flagged">⭐ buyable subset: {v.confirmed.buyable_target_before_stop_pct ?? '—'}% (n={v.confirmed.buyable_n})</span></>}
                </>
              )}
              {v.forming && v.forming.n > 0 && (
                <> {v.confirmed && v.confirmed.n > 0 ? ' · ' : ' '}forming n={v.forming.n} ·
                  {' '}{v.forming.went_on_to_confirm_pct ?? '—'}% went on to confirm · {v.forming.stopped_first_pct ?? '—'}% stopped first
                </>
              )}
            </div>
          ))}
          {Object.entries(acc.candles).map(([k, v]) => (
            <div key={k} style={{ padding: '1px 0' }}>
              <b>{CANDLE_META[k]?.label || k}</b> (candle): n={v.n} · {v.direction_hit_pct ?? '—'}% moved its way over 5 bars
              {v.median_fwd_5d_pct != null && <> · median {v.median_fwd_5d_pct > 0 ? '+' : ''}{v.median_fwd_5d_pct}%</>}
            </div>
          ))}
          {Object.keys(acc.patterns).length === 0 && Object.keys(acc.candles).length === 0 && (
            <div style={{ color: C.muted }}>Recording started — first grades land once flagged patterns complete their 21-bar window.</div>
          )}
          {acc.disclaimer && <div style={{ color: C.sub, marginTop: 4, fontSize: '0.68rem' }}>{acc.disclaimer}</div>}
        </div>
      )}

      {/* Month-by-month winners' record — perpetual, never pruned (2026-06-10). */}
      <PatternAccuracyMonthly />

      {/* Qualifier verdicts — every qualifier answered: match or no-match */}
      {quals && quals.verdicts && quals.verdicts.length > 0 && (
        <QualifierVerdicts q={quals} navigate={navigate} />
      )}
      {quals && (!quals.verdicts || quals.verdicts.length === 0) && user?.is_admin && (
        <div style={{ padding: '0.55rem 0.8rem', borderRadius: 10, marginBottom: 12, fontSize: '0.76rem',
                      color: C.muted, border: '1px dashed var(--hairline,#2a2a2a)' }}>
          🎯 {quals.note || 'No qualifier verdict scan yet'} — it answers every current SEPA qualifier:
          which pattern its chart matches right now, or that it matches none.
        </div>
      )}

      {!latest ? (
        <p className="mono" style={{ opacity: 0.7 }}>…loading</p>
      ) : latest.n_found === 0 ? (
        <div className="sepa-empty-card">
          <div className="eyebrow">{latest.note || 'No fresh patterns in the last scan'}</div>
          <p style={{ color: C.muted, margin: 0 }}>Hit ⚡ Scan Patterns to sweep the universe's cached daily charts (~1–2 min).</p>
        </div>
      ) : (
        <>
          {confirmed.length > 0 && <Section title={`Confirmed today / yesterday — closed above the line (${confirmed.length})`} rows={confirmed} navigate={navigate} />}
          {forming.length > 0 && <Section title={`Forming — NOT a signal: unconfirmed Ws continue lower 48% of the time (${forming.length})`} rows={forming} navigate={navigate} />}
          {latest.generated_at > 0 && (
            <p style={{ fontSize: '0.68rem', color: C.sub }}>
              Scanned {latest.symbols_scanned} charts · {new Date(latest.generated_at * 1000).toLocaleString()}
            </p>
          )}
        </>
      )}

      <p style={{ fontSize: '0.7rem', color: C.sub, marginTop: 12 }}>{latest?.disclaimer}</p>
    </div>
  );
}

function QualifierVerdicts({ q, navigate }: { q: QualLatest; navigate: (p: string) => void }) {
  const matched = q.verdicts.filter((v) => v.matches.length > 0);
  const candleOnly = q.verdicts.filter((v) => v.matches.length === 0 && !v.no_match);
  const noMatch = q.verdicts.filter((v) => v.no_match);
  return (
    <div style={{ marginBottom: 18, padding: '0.7rem 0.85rem', borderRadius: 12,
                  border: `1px solid ${C.gold}44`, background: 'var(--bg-raised,#16181d)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ fontWeight: 800, fontSize: '0.9rem' }}>🎯 Qualifier verdicts</div>
        <span style={{ fontSize: '0.72rem', color: C.muted }}>
          {q.n_symbols} names (qualifiers + holdings + leaders) · {matched.length} match a pattern · {candleOnly.length} candle reads only · {noMatch.length} no pattern
        </span>
        {q.generated_at > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: '0.66rem', color: C.sub }}>
            {new Date(q.generated_at * 1000).toLocaleString()}
          </span>
        )}
      </div>

      {/* Tiny-card grid (Ajay 2026-06-09): minimal SEPA-style cards, ranked so
          ⭐ confirmed-pattern + full-Minervini-buy-gate confluence leads. */}
      {matched.length > 0 && <PatternMatchCards title={`Pattern matched (${matched.length})`} allLink={false} />}

      {candleOnly.length > 0 && (
        <>
          <div style={{ fontSize: '0.7rem', color: C.sub, textTransform: 'uppercase', margin: '10px 0 4px' }}>
            No chart pattern — candle reads only ({candleOnly.length})
          </div>
          {candleOnly.map((v) => <VerdictRow key={v.symbol} v={v} navigate={navigate} />)}
        </>
      )}

      {noMatch.length > 0 && (
        <>
          <div style={{ fontSize: '0.7rem', color: C.sub, textTransform: 'uppercase', margin: '10px 0 4px' }}>
            No pattern, no notable candles ({noMatch.length}) — that's an answer too
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {noMatch.map((v) => (
              <button key={v.symbol} onClick={() => navigate(`/sepa/${encodeURIComponent(v.symbol)}`)}
                      title={v.error ? v.error : `RS ${v.sepa?.rs_rank ?? '—'} · Stage ${v.sepa?.stage ?? '—'} — no pattern on the daily chart`}
                      style={{ fontSize: '0.72rem', padding: '2px 9px', borderRadius: 6, cursor: 'pointer',
                               background: 'var(--bg-sunken,#0f1115)', color: C.muted,
                               border: '1px solid var(--hairline,#2a2a2a)' }}>
                {v.symbol}
              </button>
            ))}
          </div>
        </>
      )}
      {q.disclaimer && <div style={{ fontSize: '0.7rem', color: C.sub, marginTop: 8 }}>{q.disclaimer}</div>}
    </div>
  );
}

// Where this name lives in the app — the reverse cross-link (chip → that page).
const SOURCE_META: Record<string, { icon: string; label: string; to: string } | undefined> = {
  holding: { icon: '💼', label: 'Holding', to: '/portfolio' },
  leader: { icon: '🏆', label: 'Leader', to: '/leaderboard' },
  at_pivot: { icon: '🎯', label: 'At pivot', to: '/leaderboard' },
};

function VerdictRow({ v, navigate }: { v: Verdict; navigate: (p: string) => void }) {
  const s = v.sepa || {};
  const formations = v.candles?.formations || [];
  const sources = (v.sources || []).map((k) => SOURCE_META[k]).filter(Boolean) as
    { icon: string; label: string; to: string }[];
  return (
    <div style={{ padding: '0.45rem 0.6rem', borderRadius: 8, marginBottom: 5,
                  background: 'var(--bg-sunken,#0f1115)', border: '1px solid var(--hairline,#2a2a2a)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TickerCell symbol={v.symbol} size="0.88rem" />
        {s.is_buyable && <span style={{ fontSize: '0.72rem', color: C.green }}>✅ buyable</span>}
        {sources.map((m) => (
          <button key={m.label} onClick={() => navigate(m.to)}
                  title={`This name is on your ${m.label === 'Holding' ? 'Portfolio' : 'Leaderboard'} — click to open`}
                  style={{ fontSize: '0.72rem', color: C.muted, cursor: 'pointer', background: 'transparent',
                           border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 5, padding: '4px 8px' }}>
            {m.icon} {m.label}
          </button>
        ))}
        {s.rs_rank != null && <span style={{ fontSize: '0.72rem', color: C.muted }}>RS {s.rs_rank}</span>}
        {s.stage != null && <span style={{ fontSize: '0.72rem', color: C.muted }}>Stage {s.stage}</span>}
        {v.matches.map((p, i) => {
          const conf = p.status === 'confirmed';
          return (
            <span key={`${p.pattern}-${i}`}
                  title={`${BULKOWSKI[p.pattern] || ''}\nline ${p.neckline} · target ${p.target} (measure rule) · stop ${p.stop}`}
                  style={{ fontSize: '0.72rem', fontWeight: 700, color: conf ? C.green : C.amber,
                           border: `1px solid ${(conf ? C.green : C.amber)}55`,
                           background: `${conf ? C.green : C.amber}14`, borderRadius: 5, padding: '1px 7px' }}>
              {PATTERN_LABEL[p.pattern] || p.pattern} · {conf ? `CONFIRMED ${p.confirmed_date || ''}` : `forming, ${p.to_confirm_pct}% to line`}
            </span>
          );
        })}
        {formations.map((f) => (
          <span key={`${f.name}-${f.date}`} title={`${f.note}\n${f.stat || ''}`}
                style={{ fontSize: '0.7rem', color: READ_COLOR[f.read] || C.muted,
                         border: `1px solid ${(READ_COLOR[f.read] || C.muted)}44`, borderRadius: 5, padding: '1px 6px' }}>
            {CANDLE_META[f.name]?.icon || '🕯'} {CANDLE_META[f.name]?.label || f.name} {f.date.slice(5)}
          </span>
        ))}
        {v.matches.length === 0 && formations.length === 0 && (
          <span style={{ fontSize: '0.72rem', color: C.sub }}>no pattern</span>
        )}
      </div>
      {v.candles?.last_bar?.read && (
        <div style={{ fontSize: '0.72rem', color: C.sub, marginTop: 3 }}>{v.candles.last_bar.read}</div>
      )}
    </div>
  );
}

function Section({ title, rows, navigate }: { title: string; rows: Pattern[]; navigate: (p: string) => void }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', margin: '10px 0 6px' }}>{title}</div>
      {rows.map((p, i) => <Card key={`${p.symbol}-${p.pattern}-${i}`} p={p} navigate={navigate} />)}
    </div>
  );
}

function Card({ p }: { p: Pattern; navigate?: (path: string) => void }) {
  const s = p.sepa || {};
  const conf = p.status === 'confirmed';
  const ext = p.ext_past_confirm_pct;
  const extended = conf && ext != null && ext > 5;
  return (
    <div style={{ padding: '0.6rem 0.8rem', borderRadius: 10, marginBottom: 7,
                  background: 'var(--bg-raised,#16181d)',
                  border: `1px solid ${conf ? C.green + '55' : 'var(--hairline,#2a2a2a)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TickerCell symbol={p.symbol} size="0.95rem" />
        <span style={{ fontSize: '0.74rem', color: C.muted }}>{PATTERN_LABEL[p.pattern] || p.pattern}</span>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: conf ? C.green : C.amber,
                       border: `1px solid ${(conf ? C.green : C.amber)}55`, background: `${conf ? C.green : C.amber}14`,
                       borderRadius: 5, padding: '1px 7px' }}>
          {conf ? `CONFIRMED ${p.confirmed_date || ''}` : `FORMING · ${p.to_confirm_pct}% to the line`}
        </span>
        {extended && <span style={{ fontSize: '0.68rem', color: C.amber }}>⚠ +{ext}% past the line — extended</span>}
        {s.is_buyable && <span style={{ fontSize: '0.68rem', color: C.green }}>✅ SEPA buyable</span>}
        {!s.is_buyable && s.is_candidate && <span style={{ fontSize: '0.68rem', color: C.muted }}>SEPA candidate</span>}
        <span style={{ marginLeft: 'auto', fontVariantNumeric: 'tabular-nums', fontSize: '0.82rem' }}>${p.last_close}</span>
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 4, fontSize: '0.74rem', color: C.muted, flexWrap: 'wrap' }}>
        <span>line <b>{p.neckline}</b></span>
        <span style={{ color: C.green }}>target {p.target} <span style={{ color: C.sub }}>(measure rule)</span></span>
        <span style={{ color: C.red }}>stop {p.stop}</span>
        <span>lows {p.lows.map((l) => `${l.price} (${l.date.slice(5)})`).join(' · ')}</span>
        {s.rs_rank != null && <span>RS {s.rs_rank}</span>}
        {s.stage != null && <span>Stage {s.stage}</span>}
      </div>
      <ClampText lines={1} style={{ fontSize: '0.7rem', color: C.sub, marginTop: 4 }}>{BULKOWSKI[p.pattern]}</ClampText>
    </div>
  );
}
