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

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)' };

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
type ScanStatus = { running: boolean; done: number; total: number; error?: string | null };

const PATTERN_LABEL: Record<string, string> = {
  double_bottom: 'Double bottom (W)', inverse_head_shoulders: 'Inverse head & shoulders',
};
// Practitioner base rates — Bulkowski database, quoted in the ONLY permitted
// framing (verified pass 2026-06-09): break-even failure rates with the full
// caveat. Never win rates, average rises, or expected returns.
const BULKOWSKI: Record<string, string> = {
  double_bottom: 'Bulkowski (daily bars, bull-market sample, hindsight-measured, no costs): break-even failure 12–16% across Adam/Eve variants; unconfirmed double bottoms continue LOWER 48% of the time',
  inverse_head_shoulders: 'Bulkowski (n=3,197; daily bars, hindsight-measured, no costs): break-even failure 11%, throwback rate 65%, rank 13 of 39',
};

const PageInfo = (
  <>
    <p><strong>Patterns</strong> — an on-demand scan for bullish-reversal geometry on daily bars:
      <strong> double bottoms</strong> and <strong>inverse head &amp; shoulders</strong>, found across the SEPA universe's cached charts.</p>
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
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadLatest = useCallback(() => {
    fetch(`${API}/patterns/latest`, { cache: 'no-store' })
      .then((r) => r.json()).then(setLatest).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => { loadLatest(); return () => { if (pollRef.current) window.clearInterval(pollRef.current); }; }, [loadLatest]);

  const startScan = async () => {
    setErr(null);
    try {
      const r = await fetch(`${API}/patterns/scan`, { method: 'POST', credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setScanStatus(await r.json());
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
          <p className="lede">Double bottoms &amp; inverse H&amp;S across the SEPA universe — confirmed vs forming, with our own measured record beside the book numbers.</p>
        </div>
        {user?.is_admin && (
          <button onClick={startScan} disabled={!!scanStatus?.running}
                  title="Scan the whole SEPA universe's cached daily charts for bullish-reversal patterns"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem',
                           borderRadius: 8, cursor: scanStatus?.running ? 'wait' : 'pointer', fontWeight: 600,
                           fontSize: '0.8rem', background: C.gold, color: '#1a1a1a', border: 'none',
                           opacity: scanStatus?.running ? 0.7 : 1 }}>
            ⚡ {scanStatus?.running ? 'Scanning…' : 'Scan Patterns'}
          </button>
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
          <div style={{ fontSize: '0.68rem', color: C.sub, textTransform: 'uppercase', marginBottom: 4 }}>
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

      {!latest ? (
        <p className="mono" style={{ opacity: 0.7 }}>…loading</p>
      ) : latest.n_found === 0 ? (
        <div className="sepa-empty-card">
          <div className="eyebrow">{latest.note || 'No fresh patterns in the last scan'}</div>
          <p style={{ color: C.muted, margin: 0 }}>Hit ⚡ Scan Patterns to sweep the universe's cached daily charts (~1–2 min).</p>
        </div>
      ) : (
        <>
          {confirmed.length > 0 && <Section title={`Confirmed — closed above the line (${confirmed.length})`} rows={confirmed} navigate={navigate} />}
          {forming.length > 0 && <Section title={`Forming — NOT a signal: unconfirmed Ws continue lower 48% of the time (${forming.length})`} rows={forming} navigate={navigate} />}
          {latest.generated_at > 0 && (
            <p style={{ fontSize: '0.68rem', color: C.sub }}>
              Scanned {latest.symbols_scanned} charts · {new Date(latest.generated_at * 1000).toLocaleString()}
            </p>
          )}
        </>
      )}

      <p style={{ fontSize: '0.66rem', color: C.sub, marginTop: 12 }}>{latest?.disclaimer}</p>
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

function Card({ p, navigate }: { p: Pattern; navigate: (path: string) => void }) {
  const s = p.sepa || {};
  const conf = p.status === 'confirmed';
  const ext = p.ext_past_confirm_pct;
  const extended = conf && ext != null && ext > 5;
  return (
    <div style={{ padding: '0.6rem 0.8rem', borderRadius: 10, marginBottom: 7,
                  background: 'var(--bg-raised,#16181d)',
                  border: `1px solid ${conf ? C.green + '55' : 'var(--hairline,#2a2a2a)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => navigate(`/sepa/${encodeURIComponent(p.symbol)}`)}
                style={{ fontWeight: 800, fontSize: '0.95rem', background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}>
          {p.symbol}
        </button>
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
      <div style={{ fontSize: '0.64rem', color: C.sub, marginTop: 4 }}>{BULKOWSKI[p.pattern]}</div>
    </div>
  );
}
