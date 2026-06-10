/* /chart-school — the visual half of Learning (Ajay 2026-06-09: "I want to
 * understand the WHY behind the chart pattern… daily one or two charts to
 * identify the patterns… his candle stick reads as well").
 *
 * Sections:
 *  1. Daily chart quiz — 2 REAL historical charts from the scan universe, cut
 *     at the confirmation bar. Guess the pattern → reveal the why + what
 *     actually happened next (+21 bars, win or lose — honesty by design).
 *  2. Pattern library — Bulkowski geometry + the supply/demand WHY (overhead
 *     supply mechanics, Minervini pp.204-206), stats only in permitted framing.
 *  3. Candle reads — wick/body anatomy; the exact vocabulary the SEPA Watch
 *     (scalp_tape) alerts speak.
 *  4. The full 8-week curriculum (built in a companion session) + book order.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from '../components/InfoButton';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)', blue: '#4fc3f7' };

/* ── tiny pure-SVG candlestick chart for the quiz ─────────────────────────── */
type Bar = { t: string; o: number; h: number; l: number; c: number; v: number };

function CandleChart({ bars, line, lineLabel }: { bars: Bar[]; line?: number | null; lineLabel?: string }) {
  if (!bars.length) return null;
  const W = 640, H = 240, padR = 46, padY = 12;
  const lo = Math.min(...bars.map((b) => b.l));
  const hi = Math.max(...bars.map((b) => b.h), line || 0);
  const span = Math.max(hi - lo, 0.0001);
  const y = (p: number) => padY + (1 - (p - lo) / span) * (H - 2 * padY);
  const bw = (W - padR) / bars.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', background: 'var(--bg-sunken,#0f1115)', borderRadius: 10, border: '1px solid var(--hairline,#2a2a2a)' }}>
      {line != null && (
        <>
          <line x1={0} y1={y(line)} x2={W - padR} y2={y(line)} stroke={C.amber} strokeWidth={1.2} strokeDasharray="5,4" />
          <text x={W - padR + 3} y={y(line) + 4} fill={C.amber} fontSize="10">{lineLabel || line}</text>
        </>
      )}
      {bars.map((b, i) => {
        const x = i * bw + bw / 2;
        const up = b.c >= b.o;
        const col = up ? C.green : C.red;
        return (
          <g key={b.t}>
            <line x1={x} y1={y(b.h)} x2={x} y2={y(b.l)} stroke={col} strokeWidth={1} />
            <rect x={x - Math.max(bw * 0.32, 1)} y={y(Math.max(b.o, b.c))}
                  width={Math.max(bw * 0.64, 2)} height={Math.max(Math.abs(y(b.o) - y(b.c)), 1)} fill={col} />
          </g>
        );
      })}
      <text x={4} y={14} fill={C.sub} fontSize="10">{bars[0].t} → {bars[bars.length - 1].t} · daily</text>
    </svg>
  );
}

/* ── quiz ─────────────────────────────────────────────────────────────────── */
type QuizItem = {
  symbol: string; pattern: string; answer: string; choices: string[];
  bars: Bar[]; confirm_date: string; neckline: number; pattern_low: number;
  why: string; outcome_fwd_21d_pct: number; outcome_note: string;
};
type Quiz = { et_date: string; items: QuizItem[]; n?: number; error?: string; disclaimer?: string };

function QuizCard({ item, idx }: { item: QuizItem; idx: number }) {
  const [picked, setPicked] = useState<string | null>(null);
  const navigate = useNavigate();
  const revealed = picked != null;
  const correct = picked === item.answer;
  return (
    <div style={{ padding: '0.8rem 0.9rem', borderRadius: 12, background: 'var(--bg-raised,#16181d)', border: '1px solid var(--hairline,#2a2a2a)', marginBottom: 14 }}>
      <div style={{ fontSize: '0.78rem', color: C.sub, marginBottom: 6 }}>
        Chart {idx + 1} — {revealed ? <b>{item.symbol}</b> : 'mystery ticker'} · the last bar shown is the moment of truth
      </div>
      <CandleChart bars={item.bars} line={revealed ? item.neckline : null} lineLabel={revealed ? `line ${item.neckline}` : undefined} />
      <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
        {item.choices.map((ch) => {
          const isAnswer = revealed && ch === item.answer;
          const isWrongPick = revealed && picked === ch && !correct;
          return (
            <button key={ch} disabled={revealed} onClick={() => setPicked(ch)}
              style={{ padding: '0.45rem 0.8rem', borderRadius: 8, cursor: revealed ? 'default' : 'pointer', fontSize: '0.8rem', fontWeight: 600,
                       border: `1px solid ${isAnswer ? C.green : isWrongPick ? C.red : 'var(--hairline,#2a2a2a)'}`,
                       background: isAnswer ? `${C.green}22` : isWrongPick ? `${C.red}18` : 'transparent', color: 'inherit' }}>
              {ch}
            </button>
          );
        })}
      </div>
      {revealed && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 700, color: correct ? C.green : C.red }}>
            {correct ? '✓ Correct' : `✗ It was: ${item.answer}`} — confirmed {item.confirm_date}
          </div>
          <p style={{ fontSize: '0.82rem', color: C.muted, margin: '6px 0' }}><b style={{ color: 'inherit' }}>Why it works (when it works):</b> {item.why}</p>
          <div style={{ fontSize: '0.82rem', padding: '0.45rem 0.6rem', borderRadius: 8, background: 'var(--bg-sunken,#0f1115)',
                        color: item.outcome_fwd_21d_pct >= 0 ? C.green : C.red }}>
            {item.outcome_note}
          </div>
          <button onClick={() => navigate(`/sepa/${encodeURIComponent(item.symbol)}`)}
                  style={{ marginTop: 8, background: 'transparent', border: '1px solid var(--hairline,#2a2a2a)', color: C.blue, borderRadius: 6, padding: '0.25rem 0.6rem', cursor: 'pointer', fontSize: '0.74rem' }}>
            Open {item.symbol} today →
          </button>
        </div>
      )}
    </div>
  );
}

/* ── pattern library (the WHY) ────────────────────────────────────────────── */
const PATTERNS = [
  {
    name: 'Double bottom (W)', emoji: 'W',
    svg: (
      <svg viewBox="0 0 320 150">
        <line x1="20" y1="50" x2="300" y2="50" stroke={C.amber} strokeWidth="1.2" strokeDasharray="5,4" />
        <text x="24" y="44" fill={C.amber} fontSize="10">pivot = middle peak (confirmation line)</text>
        <polyline points="20,30 70,120 115,60 160,128 200,65 230,45 250,38 285,18" fill="none" stroke={C.blue} strokeWidth="2" />
        <text x="50" y="138" fill={C.sub} fontSize="9">low 1</text>
        <text x="142" y="144" fill={C.sub} fontSize="9">low 2 — the test (often undercuts)</text>
      </svg>
    ),
    why: 'The second low is a TEST of the first: everyone who wanted out at that price sold the first time, so the retest finds no new supply. An undercut that snaps back is the shakeout — the last stops flushed. Nothing counts until a CLOSE above the middle peak; before that, unconfirmed Ws continue lower 48% of the time.',
    stat: 'Bulkowski (daily, hindsight, no costs): break-even failure 12–16% by Adam/Eve variant.',
    rules: 'Lows within ~3%, 23–35 bars apart, ≥10% interim peak. Buy: close above the peak. Stop: under the lower low.',
  },
  {
    name: 'Inverse head & shoulders', emoji: '👤',
    svg: (
      <svg viewBox="0 0 320 150">
        <line x1="20" y1="48" x2="300" y2="48" stroke={C.amber} strokeWidth="1.2" strokeDasharray="5,4" />
        <text x="24" y="42" fill={C.amber} fontSize="10">neckline</text>
        <polyline points="20,40 55,95 85,50 120,128 160,52 195,92 225,48 250,38 285,16" fill="none" stroke={C.blue} strokeWidth="2" />
        <text x="42" y="112" fill={C.sub} fontSize="9">shoulder</text>
        <text x="106" y="143" fill={C.sub} fontSize="9">head (panic low)</text>
        <text x="182" y="108" fill={C.sub} fontSize="9">higher low</text>
      </svg>
    ),
    why: "The head is the panic low. The right shoulder's HIGHER low is the tell — sellers tried to push it back and failed. The neckline close adds short-covering to fresh demand. The most-studied reversal in peer-reviewed work (FX + US indices) — predictive, but never a standalone profit machine.",
    stat: 'Bulkowski (n=3,197): break-even failure 11%, throwback 65% — expect the neckline retest.',
    rules: 'Head below both shoulders; shoulders ≈ equal (~1.5%). Buy: close above the neckline. Stop: under the right shoulder.',
  },
  {
    name: 'Cup with handle', emoji: '☕',
    svg: (
      <svg viewBox="0 0 320 150">
        <line x1="20" y1="42" x2="300" y2="42" stroke="#2e3a47" strokeWidth="1" strokeDasharray="4,4" />
        <path d="M30,42 C70,135 150,135 195,44" fill="none" stroke={C.blue} strokeWidth="2" />
        <polyline points="195,44 215,70 235,62 245,50 250,34 285,14" fill="none" stroke={C.blue} strokeWidth="2" />
        <text x="200" y="96" fill={C.amber} fontSize="10">handle: quiet downward drift</text>
        <text x="90" y="142" fill={C.sub} fontSize="9">rounded cup works through the supply</text>
      </svg>
    ),
    why: "The cup grinds through most of the overhead supply; the handle is the FINAL shakeout — a light-volume drift that clears the last weak hands right under the highs. A handle in the lower half of the cup (or wedging up) means supply is still in control.",
    stat: 'O’Neil’s flagship base; Bulkowski tracks it among the better bullish performers (same caveats).',
    rules: 'Handle in the upper half, drifting down on light volume. Buy: through the handle high. Stop: under the handle low.',
  },
  {
    name: 'Flat base', emoji: '📏',
    svg: (
      <svg viewBox="0 0 320 150">
        <line x1="20" y1="40" x2="300" y2="40" stroke={C.amber} strokeWidth="1.2" strokeDasharray="5,4" />
        <polyline points="20,135 60,45 80,64 105,46 125,62 150,45 170,60 195,46 215,58 235,45 252,52 262,26 290,12" fill="none" stroke={C.blue} strokeWidth="2" />
        <text x="70" y="90" fill={C.sub} fontSize="9">sideways shelf, ≤15% deep — boring on purpose</text>
      </svg>
    ),
    why: "Boring is bullish: weeks of sideways chop and the holders still refuse to sell — there is simply no supply. Often forms on top of a prior base ('base on base'). Tight weekly closes + a relative-strength line at highs = institutions sitting on the bid.",
    stat: 'O’Neil base family — taught by structure, not by a quoted success rate.',
    rules: '≤15% deep, 5+ weeks, after a prior run-up. Buy: through the base high. Red flag: wide-and-loose bars.',
  },
  {
    name: 'Bull flag (continuation — NOT a bounce)', emoji: '🚩',
    svg: (
      <svg viewBox="0 0 320 150">
        <polyline points="15,140 90,30" fill="none" stroke={C.blue} strokeWidth="2" />
        <polyline points="90,30 110,54 125,42 140,64 155,50 170,72" fill="none" stroke={C.blue} strokeWidth="2" />
        <polyline points="170,72 180,48 290,12" fill="none" stroke={C.blue} strokeWidth="2" />
        <text x="35" y="60" fill={C.sub} fontSize="9">pole (required)</text>
        <text x="105" y="100" fill={C.sub} fontSize="9">flag: light-volume drift against the trend</text>
      </svg>
    ),
    why: "A rest within a trend, not a bottom. The pole IS the pattern — without a sharp prior advance there is no flag. The drift shakes out momentum chasers while volume dries up; the trend then resumes. Don't confuse it with reversal patterns when hunting bounces.",
    stat: 'Red flag: the drift retraces more than half the pole.',
    rules: 'Sharp advance → 1–3 week light-volume drift. Buy: through the flag’s upper line. Stop: under the flag low.',
  },
];

/* ── candle reads (ties to the SEPA Watch alerts) ─────────────────────────── */
function MiniCandle({ o, h, l, c, label }: { o: number; h: number; l: number; c: number; label: string }) {
  const span = h - l, y = (p: number) => 8 + (1 - (p - l) / span) * 104;
  const up = c >= o, col = up ? C.green : C.red;
  return (
    <div style={{ textAlign: 'center' }}>
      <svg viewBox="0 0 60 120" style={{ width: 44 }}>
        <line x1="30" y1={y(h)} x2="30" y2={y(l)} stroke={col} strokeWidth="2" />
        <rect x="18" y={y(Math.max(o, c))} width="24" height={Math.max(Math.abs(y(o) - y(c)), 2)} fill={col} />
      </svg>
      <div style={{ fontSize: '0.66rem', color: C.muted, maxWidth: 90 }}>{label}</div>
    </div>
  );
}

const CANDLE_READS = [
  { title: 'Strong body (≥60%) closing at the extreme', read: 'One side controlled the whole auction. THROUGH a level on ≥1.5× volume this is your 🟢 BREAKOUT_STRONG alert.', candle: { o: 10, h: 21, l: 9.5, c: 20.5 } },
  { title: 'Upper-wick rejection (wick ≥2× body)', read: 'Buyers pushed through the level, sellers slammed it back — supply showed up. Your 🟠 REJECTION alert. In open air it’s noise.', candle: { o: 12, h: 22, l: 11.5, c: 12.5 } },
  { title: 'Hammer / lower-wick (dip got bought)', read: 'Only means something AT support after a flush, on volume. Bulkowski’s own database ranks the lone hammer near-random.', candle: { o: 19, h: 20.5, l: 9, c: 20 } },
  { title: 'Doji (body <5%) — undecided', read: 'The auction ended where it started. A STATE, never a reversal signal (Horton 2009 found little predictive value). At a level = your STALL chip: move coming, direction unknown.', candle: { o: 15, h: 20, l: 10, c: 15.2 } },
];

/* ── page ─────────────────────────────────────────────────────────────────── */
const PageInfo = (
  <>
    <p><strong>Chart School</strong> — pattern recognition with the <em>why</em>, not just the shape.</p>
    <p>The daily quiz uses REAL historical charts from your own scan universe, cut at the confirmation bar, and always shows what actually happened next — win or lose. Pattern stats appear only as Bulkowski break-even failure rates with their caveats (daily bars, hindsight, no costs), and the candle section teaches the exact vocabulary your SEPA Watch alerts speak.</p>
    <p className="mono">The academic record: patterns carry information, not guaranteed profit (Lo-Mamaysky-Wang 2000). Education, not advice.</p>
  </>
);

export function ChartSchool() {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/flashcards/chart-quiz`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setQuiz).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Learning · patterns & candles, with the why</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Chart School
            <InfoButton inline title="Chart School">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">Daily real-chart quiz from your own universe, the supply/demand mechanics behind every base, and the candle reads your alerts speak.</p>
        </div>
      </div>

      {/* 1 — daily quiz */}
      <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', margin: '8px 0 6px' }}>
        Today's quiz {quiz?.et_date ? `· ${quiz.et_date}` : ''} — name the pattern before the reveal
      </div>
      {err && <p className="mono" style={{ color: C.red }}>Couldn't load the quiz — {err}</p>}
      {!quiz && !err && <p className="mono" style={{ opacity: 0.7 }}>…picking today's charts</p>}
      {quiz?.error && <p className="mono" style={{ color: C.amber }}>{quiz.error}</p>}
      {quiz?.items?.map((it, i) => <QuizCard key={`${quiz.et_date}-${it.symbol}`} item={it} idx={i} />)}

      {/* 2 — the why behind every base */}
      <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', margin: '18px 0 6px' }}>
        The master key — why patterns work at all
      </div>
      <div style={{ padding: '0.7rem 0.9rem', borderRadius: 12, background: 'var(--bg-raised,#16181d)', border: `1px solid ${C.gold}44`, marginBottom: 12, fontSize: '0.85rem', lineHeight: 1.5 }}>
        Every bullish base — VCP, cup-and-handle, double bottom, flat base — is the <b>same story in different shapes</b>: price returns to a resistance level where trapped buyers and profit-takers want out; each visit absorbs more of that overhead supply; when the sellers are exhausted, even modest demand pushes it through. <b>The pattern doesn't predict the breakout — the behavior at resistance does</b>: shallower pullbacks, volume drying up, price tightening just under the line, relative strength, and an early-in-the-trend base. <span style={{ color: C.sub }}>(Minervini, TLSMW pp.204–206 · curriculum week 2)</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 12 }}>
        {PATTERNS.map((p) => (
          <div key={p.name} style={{ padding: '0.7rem 0.8rem', borderRadius: 12, background: 'var(--bg-raised,#16181d)', border: '1px solid var(--hairline,#2a2a2a)' }}>
            <div style={{ fontWeight: 800, marginBottom: 4 }}>{p.emoji} {p.name}</div>
            <div style={{ background: 'var(--bg-sunken,#0f1115)', borderRadius: 8 }}>{p.svg}</div>
            <p style={{ fontSize: '0.78rem', color: C.muted, margin: '6px 0' }}><b style={{ color: 'inherit' }}>Why:</b> {p.why}</p>
            <div style={{ fontSize: '0.72rem', color: C.sub }}>{p.rules}</div>
            <div style={{ fontSize: '0.68rem', color: C.amber, marginTop: 4 }}>{p.stat}</div>
          </div>
        ))}
      </div>

      {/* 3 — candle reads */}
      <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', margin: '18px 0 6px' }}>
        Candle reads — the language your SEPA Watch alerts speak
      </div>
      <div style={{ padding: '0.7rem 0.9rem', borderRadius: 12, background: 'var(--bg-raised,#16181d)', border: '1px solid var(--hairline,#2a2a2a)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 12 }}>
          {CANDLE_READS.map((cr) => (
            <div key={cr.title} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <MiniCandle {...cr.candle} label="" />
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700 }}>{cr.title}</div>
                <div style={{ fontSize: '0.74rem', color: C.muted }}>{cr.read}</div>
              </div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: '0.7rem', color: C.sub, marginTop: 10 }}>
          The honesty rule: candle patterns standalone are weak-to-null in the academic record (no 5-min candle rule survived
          costs in Duvinage et&nbsp;al. 2013). A read only means something <b>at a level, with volume</b> — which is exactly how your
          🕯 scalp-tape alerts are gated, and why each one self-grades against the next 30 minutes on /scalping.
        </p>
      </div>

      {/* 4 — go deeper */}
      <div style={{ fontSize: '0.72rem', color: C.sub, textTransform: 'uppercase', margin: '18px 0 6px' }}>Go deeper</div>
      <div style={{ padding: '0.7rem 0.9rem', borderRadius: 12, background: 'var(--bg-raised,#16181d)', border: '1px solid var(--hairline,#2a2a2a)', fontSize: '0.8rem' }}>
        <p style={{ margin: '0 0 6px' }}>
          📚 <a href="/trading-curriculum.html" target="_blank" rel="noreferrer" style={{ color: C.blue, fontWeight: 700 }}>
            The 8-week curriculum →
          </a>{' '}
          <span style={{ color: C.muted }}>(built in your companion session: S/R & price action, base patterns, pullbacks & tennis-ball action, liquidity/ICT, macro, fundamentals, the trade plan)</span>
        </p>
        <p style={{ margin: 0, color: C.muted }}>
          Book order: Minervini <i>TLSMW</i> → <i>Think & Trade Like a Champion</i> → O'Neil <i>HTMMIS</i> → Weinstein → Bulkowski's <i>Encyclopedia</i> (reference) → <i>TraderLion Model Book</i>.
          Hourly learning pushes now include <b>chart patterns</b> (3a/8a/12p ET) and <b>candle reads</b> (6a/7p ET) — browse them all on <a href="/learn" style={{ color: C.blue }}>/learn</a>.
        </p>
      </div>

      <p style={{ fontSize: '0.66rem', color: C.sub, marginTop: 12 }}>
        Educational, not advice. Pattern statistics are historical tendencies with heavy caveats — risk management is what keeps you in the game, not pattern accuracy.
      </p>
    </div>
  );
}
