/* /patterns — on-demand bullish-reversal pattern scan ("full scan button like
 * SEPA"). Owner hits ⚡ Scan Patterns → background scan over the SEPA universe's
 * cached daily frames → confirmed/forming double bottoms + inverse H&S with
 * SEPA context, plus OUR universe's measured +21-bar outcomes per pattern
 * (self-validation) beside the practitioner base rates. A pattern without its
 * confirmation close is a shape, not a signal. Educational, not advice. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useMyFeatures } from '../hooks/useMyFeatures';
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
  median_target_dist_pct?: number | null; median_stop_dist_pct?: number | null;
  expectancy_pct?: number | null;
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
  n_no_match?: number; n_qualifiers?: number; n_universe_only?: number;
  verdicts: Verdict[]; disclaimer?: string; note?: string;
};

/* The verdict sweep went from 313 names to the whole universe on 2026-09-10,
 * so the "no pattern" bucket went from a couple of dozen chips to ~2,000 of
 * them in one flex-wrap. Render a readable head and count the rest: the value
 * of that bucket is knowing the name WAS looked at, which the count carries
 * just as well as two thousand DOM nodes. */
const NO_MATCH_SHOWN = 300;

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
      <strong> cup-with-handles</strong>, found across the <strong>whole universe's</strong> cached charts — every name we
      carry, not only the names that pass the SEPA gates (Ajay 2026-09-10: "I want them to run against all").</p>
    <p><strong>⚡ Scan ALL names</strong> is the full-universe sweep, and it is what the confirmed/forming board below shows.
      <strong> 🎯 Qualifier verdicts only</strong> is the smaller, different job: it answers <em>every</em> current SEPA
      qualifier (plus holdings, at-pivot and leaders) with the pattern(s) its chart matches right now, recent candle
      formations (hammer, engulfing, morning star — each shown with Bulkowski's measured frequency AND the academic null),
      or an explicit <em>no pattern</em>. That complete-answer set is what fills the 📐 chips on the SEPA, Portfolio and
      Leaderboard rows; it does not refresh the board below.</p>
    <p><strong>The board is wider than the phone.</strong> A pattern only reaches your phone if the name is sitting
      <strong> at a demand zone</strong> — inside an eligible demand band, or reversing off one and no more than 5% above it.
      Everything else stays here on the board to be read, not pushed.</p>
    <p><strong>There is no size floor on this path, and you should know it.</strong> The $1B rule you set on 2026-09-03 only
      decides which names get a demand zone pre-built overnight; a name without one can still have a zone built on demand
      (up to 40 a run) with <em>no</em> market-cap check. So widening the sweep does make a small, thin name more likely to
      reach you than before. If you want a real size floor on pattern pushes, say so and it becomes a gate — I have not
      added one on my own.</p>
    <p>Discipline: a pattern only counts when it <strong>closes above its confirmation line</strong> (the interim peak / neckline) —
      before that it's listed as "forming", a shape to watch, not a signal. Targets use the measure rule; stops sit under the pattern low.</p>
    <p>Evidence, honestly: Lo, Mamaysky &amp; Wang (2000, J. Finance) found algorithmically-detected patterns carry
      <em> informational content</em> — not guaranteed profit. Bulkowski's base rates are daily-bar, no-cost statistics.
      So every scan also measures <strong>our own universe's</strong> +21-bar outcomes for historically confirmed patterns — that record is shown first.</p>
    <p className="mono">Not advice.</p>
  </>
);

/* Ajay 2026-09-09: "Can you move chart patterns in to the Chartmaps page
 * please and show the winning charts". `embedded` drops the page title block —
 * Chart Maps draws its own tab header and blurb — and keeps everything else,
 * including the admin rescan buttons he uses. ONE implementation, mounted
 * twice; /patterns redirects to the tab (the Catalysts precedent). */
export function PatternsBoard() {
  return <PatternsBody embedded />;
}


/* /patterns → Chart Maps (Ajay 2026-09-09). Kept under its old export name so
 * App.tsx's route still compiles, and every existing deep link — the 📐 push
 * taps, ✨ NEW highlights, bookmarks — lands on the new home.
 *
 * `patterns` and `chart-maps` are two SEPARATE access features, both opt-in per
 * user (backend/access/store.py). A user granted Patterns but not Chart Maps
 * must keep the board: redirecting them would bounce off the chart-maps
 * FeatureRoute onto "/" with no message. Exactly the Catalysts posture, for
 * exactly the same reason. */
export function PatternsPage() {
  const f = useMyFeatures();
  if (!f.loaded) {
    // Decide after the features fetch; never flash a redirect the user may not
    // be allowed to follow.
    return (
      <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#888', fontSize: '0.9rem' }}>
        Loading…
      </div>
    );
  }
  if (!f.features.has('chart-maps')) return <PatternsBody />;
  return <Navigate replace to="/chart-maps?tab=patterns" />;
}


function PatternsBody({ embedded = false }: { embedded?: boolean }) {
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

  const startScan = async (scope: 'universe' | 'qualifiers', refreshToday = true) => {
    setErr(null);
    try {
      const r = await fetch(`${API}/patterns/scan`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope, refresh_today: refreshToday }),
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
    <div className={embedded ? '' : 'sepa-page'}>
      <div className="sepa-page__title" style={embedded ? { marginBottom: 4 } : undefined}>
        <div hidden={embedded}>
          <div className="eyebrow">Bullish reversals · confirmation-line discipline</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Patterns
            <InfoButton inline title="Patterns">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">Double bottoms, triple bottoms, inverse H&amp;S &amp; cup-with-handles across the <b>whole universe</b> — every name, not just the SEPA qualifiers — confirmed vs forming, with our own measured record beside the book numbers. Phone alerts stay narrower than this board on purpose: only names sitting at a demand zone push — there is no size floor on that path, see ℹ️.</p>
        </div>
        {user?.is_admin && (
          /* Ajay 2026-09-10: "The chart patterns are only looking at qualified
           * sepa list I want them to run against all". The gold button he
           * actually clicks now sweeps the FULL universe and refreshes the
           * confirmed/forming board below. The qualifier verdict scan is a
           * genuinely different product — an explicit answer for EVERY
           * qualifier including "no pattern", which is what feeds the 📐 chips
           * — so it keeps its button, demoted to secondary. Both labels and
           * both tooltips now carry their scope and their name count, so which
           * one covers what is unambiguous on sight. */
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => startScan('universe', true)} disabled={!!scanStatus?.running}
                    title={`Sweep EVERY name in the full universe — ${latest?.symbols_scanned ? `all ${latest.symbols_scanned.toLocaleString()} charts on the last run` : 'roughly 2,650 charts'}, not just the SEPA qualifiers — for bullish-reversal geometry, refreshing each chart's TODAY bar with the live close first, so a breakout confirming this session shows up now (not after the post-close run). Geometry still uses the full daily history; only the trigger freshness is "today". This is the scan that fills the confirmed/forming board below. ~1–2 min. A wider board is mostly NOT more phone alerts: a pattern push still has to be sitting at a demand zone. Note there is no market-cap floor on that path — see the ℹ️ panel.`}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.45rem 0.9rem',
                             borderRadius: 8, cursor: scanStatus?.running ? 'wait' : 'pointer', fontWeight: 700,
                             fontSize: '0.8rem', minHeight: 36, background: C.gold, color: '#1a1a1a', border: 'none',
                             opacity: scanStatus?.running ? 0.7 : 1 }}>
              ⚡ {scanStatus?.running && scanStatus.scope !== 'qualifiers' ? 'Sweeping all names…' : 'Scan ALL names (full universe)'}
            </button>
            <button onClick={() => startScan('qualifiers', true)} disabled={!!scanStatus?.running}
                    title={`Re-answer EVERY name with an explicit verdict — ${quals?.n_symbols ? `${quals.n_symbols.toLocaleString()} names on the last run` : 'the whole universe'} — so each one reads as a pattern, a candle read, or an explicit "no pattern". That complete answer set is what fills the 📐 chips on the SEPA, Portfolio and Leaderboard rows, and "no pattern" is the point: a blank chip used to mean "never looked". Slower than the sweep beside it, not faster — it runs the candle reads and a ledger write per name on top of the detectors — and it does NOT refresh the confirmed/forming board below.`}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.45rem 0.9rem',
                             borderRadius: 8, cursor: scanStatus?.running ? 'wait' : 'pointer', fontWeight: 600,
                             fontSize: '0.8rem', minHeight: 36, background: 'transparent', color: C.gold,
                             border: `1px solid ${C.gold}88`, opacity: scanStatus?.running ? 0.7 : 1 }}>
              🎯 {scanStatus?.running && scanStatus.scope === 'qualifiers'
                    ? 'Re-answering every name…'
                    : `Verdict for every name${quals?.n_symbols ? ` (${quals.n_symbols.toLocaleString()})` : ''}`}
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
      {/* "show the winning charts" (Ajay 2026-09-09). The board-level door into
        * the ledger; every card has the same link filtered to its own pattern. */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                    margin: '2px 0 10px', fontSize: '0.74rem', color: C.sub }}>
        <button type="button" onClick={() => navigate(winnersHref(null))}
                title="Past Winners: every setup in your own ledger that reached its measure-rule target before its stop, drawn with the confirmation bar marked — and the stop-first losses counted from the same denominator, because a winners-only wall is a highlight reel."
                style={{ fontSize: '0.72rem', fontWeight: 700, color: C.gold, background: 'transparent',
                         border: `1px solid ${C.gold}88`, borderRadius: 7, padding: '3px 10px',
                         cursor: 'pointer', minHeight: 0 }}>
          🏆 Show the winning charts
        </button>
        <span>the ones that actually reached target before stop — study the base BEFORE the confirmation bar</span>
      </div>
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
                  {v.confirmed.target_before_stop_pct ?? '—'}%</b>{' '}
                  <span title={`Races THIS pattern's own bracket — median target ${v.confirmed.median_target_dist_pct ?? '—'}% away vs stop ${v.confirmed.median_stop_dist_pct ?? '—'}% away. Stop distances differ ~2x across patterns, so never compare this % across patterns raw.`}>
                    hit target before stop (tgt {v.confirmed.median_target_dist_pct ?? '—'}% / stop {v.confirmed.median_stop_dist_pct ?? '—'}% away)
                  </span>
                  {v.confirmed.expectancy_pct != null && <> · <b style={{ color: v.confirmed.expectancy_pct > 0 ? C.green : C.red }}
                    title="Gross expectancy per decided trade: avg win% minus avg loss%, no costs — the cross-pattern comparable number">
                    {v.confirmed.expectancy_pct > 0 ? '+' : ''}{v.confirmed.expectancy_pct}%/trade</b></>} ·
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
          <p style={{ color: C.muted, margin: 0 }}>Hit ⚡ Scan ALL names to sweep every chart in the universe's cached daily frames (~1–2 min).</p>
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
        <div style={{ fontWeight: 800, fontSize: '0.9rem' }}>🎯 Verdict for every name</div>
        <span style={{ fontSize: '0.72rem', color: C.muted }}>
          {q.n_symbols.toLocaleString()} names swept{q.n_qualifiers ? ` (${q.n_qualifiers} of them SEPA qualifiers)` : ''} · {matched.length} match a pattern · {candleOnly.length} candle reads only · {noMatch.length} no pattern
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
            {noMatch.slice(0, NO_MATCH_SHOWN).map((v) => (
              <button key={v.symbol} onClick={() => navigate(`/sepa/${encodeURIComponent(v.symbol)}`)}
                      title={v.error ? v.error : `RS ${v.sepa?.rs_rank ?? '—'} · Stage ${v.sepa?.stage ?? '—'} — no pattern on the daily chart`}
                      style={{ fontSize: '0.72rem', padding: '2px 9px', borderRadius: 6, cursor: 'pointer',
                               background: 'var(--bg-sunken,#0f1115)', color: C.muted,
                               border: '1px solid var(--hairline,#2a2a2a)' }}>
                {v.symbol}
              </button>
            ))}
            {noMatch.length > NO_MATCH_SHOWN && (
              <span data-testid="no-match-more"
                    style={{ fontSize: '0.72rem', padding: '2px 9px', color: C.sub, alignSelf: 'center' }}>
                +{(noMatch.length - NO_MATCH_SHOWN).toLocaleString()} more looked at, no pattern
              </span>
            )}
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

/* "show the winning charts" (Ajay 2026-09-09). Not a second implementation:
 * 🏆 Past Winners already draws the ledger's setups that reached the
 * measure-rule target before their stop, already filters by pattern, and
 * already prints the stop-first losses from the same denominator. This is the
 * link from a pattern to its OWN winning charts, which is the only honest way
 * to use this board — none of these patterns beats the placebo. */
export function winnersHref(pattern?: string | null): string {
  return `/chart-maps?tab=winners${pattern ? `&pattern=${encodeURIComponent(pattern)}` : ''}`;
}


function Card({ p, navigate }: { p: Pattern; navigate?: (path: string) => void }) {
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
        <button type="button"
                onClick={() => (navigate ? navigate(winnersHref(p.pattern))
                                         : window.location.assign(winnersHref(p.pattern)))}
                title={`Past Winners, filtered to ${PATTERN_LABEL[p.pattern] || p.pattern}: the charts in your own ledger that reached the measure-rule target before the stop, with the stop-first losses counted from the same denominator. Study what the base looked like BEFORE the confirmation bar.`}
                style={{ fontSize: '0.66rem', fontWeight: 700, color: C.gold, background: 'transparent',
                         border: `1px solid ${C.gold}55`, borderRadius: 5, padding: '1px 7px',
                         cursor: 'pointer', minHeight: 0 }}>
          🏆 winning charts
        </button>
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
