/* /scalping — Phase-1 documented intraday patterns with an honest net-of-cost
 * overlay. Built 2026-06-09 from a vetted research pass (docs/scalping_methodology.md).
 *
 * Detectors: Stocks-in-Play 5-min ORB (Zarattini 2024) + volatility-normalized
 * shock-fade (Zawadowski 2004), gated by the intraday-momentum regime (Gao 2018),
 * the live spread, and a gross-beside-net cost read. EDUCATIONAL, NOT ADVICE —
 * and the page leads with the base-rate reality that this activity is net-losing
 * for the large majority of retail traders.
 */
import { useState } from 'react';
import { InfoButton } from '../components/InfoButton';
import { IntradayChart } from '../components/IntradayChart';
import { useDayBars } from '../hooks/useDayTrading';
import { useScalpingSignals, type ScalpSignal, type ScalpRegime } from '../hooks/useScalpingSignals';
import { BacktestPanel, PaperPanel } from '../components/ScalpingResearchPanels';
import { SepaWatchPanel } from '../components/SepaWatchPanel';
import { LiveTapeRead } from '../components/LiveTapeRead';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';
import { PatternChips } from '../components/PatternChips';
import { OnDemandPatternScan } from '../components/OnDemandPatternScan';
import { RallyScanPanel } from '../components/RallyScanPanel';
import { useDayUniverse } from '../hooks/useDayTrading';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };

const PageInfo = (
  <>
    <p><strong>Scalping</strong> — live, documented intraday patterns. Every signal is shown
      <strong> gross beside net-of-cost</strong>, with the win rate it would need just to break even.</p>
    <ul>
      <li><strong>Stocks-in-Play 5-min ORB</strong> — Zarattini, Barbon &amp; Aziz (2024), SSRN 4729284. Edge lives in the relative-volume filter.</li>
      <li><strong>Volatility-normalized shock fade</strong> — Zawadowski, Andor &amp; Kertesz (2004), arXiv cond-mat/0406696. The spread can eat the whole reversal.</li>
      <li><strong>Intraday-momentum regime</strong> — Gao, Han, Li &amp; Zhou (2018), JFE 129(2). A direction gate, not a single-name magnitude.</li>
    </ul>
    <p className="mono">Documented patterns ≠ proven retail edges. Account-level studies find ~80–99% of
      retail day-traders net lose after costs. Educational, not advice.</p>
  </>
);

function Pill({ text, color, bg }: { text: string; color: string; bg: string }) {
  return <span style={{ fontSize: '0.66rem', fontWeight: 700, color, background: bg, border: `1px solid ${color}55`, borderRadius: 5, padding: '1px 6px', whiteSpace: 'nowrap' }}>{text}</span>;
}

function RegimeBar({ r }: { r: ScalpRegime }) {
  const color = r.bias === 'long_bias' ? C.green : r.bias === 'short_bias' ? C.red : C.muted;
  const icon = r.bias === 'long_bias' ? '▲' : r.bias === 'short_bias' ? '▼' : r.bias === 'pending' ? '…' : '↔';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0.55rem 0.8rem', borderRadius: 10, background: `${color}14`, border: `1px solid ${color}44`, marginBottom: 12 }}>
      <span style={{ fontSize: '1.1rem', color }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, color, fontSize: '0.86rem' }}>Intraday-momentum regime — {r.bias.replace('_', ' ')}</div>
        <div style={{ fontSize: '0.76rem', color: C.muted }}>{r.label}</div>
      </div>
      <span style={{ fontSize: '0.62rem', color: C.sub, maxWidth: 230, textAlign: 'right' }}>{r.note}</span>
    </div>
  );
}

function num(n: number | null | undefined, d = 2) { return n == null ? '—' : n.toFixed(d); }

function SignalCard({ s, selected, onSelect }: { s: ScalpSignal; selected: boolean; onSelect: () => void }) {
  const sideColor = s.side === 'long' ? C.green : C.red;
  const nc = s.net_of_cost;
  const sp = s.spread;
  const dim = !s.tradeable;
  const { verdicts } = usePatternVerdicts();
  return (
    <div onClick={onSelect} style={{
      padding: '0.7rem 0.85rem', borderRadius: 10, cursor: 'pointer',
      background: selected ? 'var(--bg-raised,#1b1e24)' : 'var(--bg-raised,#16181d)',
      border: `1px solid ${selected ? sideColor + '88' : 'var(--hairline,#2a2a2a)'}`,
      opacity: dim ? 0.6 : 1, marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 800, fontSize: '1rem' }}>{s.symbol}</span>
        <Pill text={s.side.toUpperCase()} color={sideColor} bg={`${sideColor}18`} />
        <Pill text={s.status === 'armed' ? 'ARMED · buy-stop' : s.status.toUpperCase()} color={C.amber} bg={`${C.amber}14`} />
        <span style={{ fontSize: '0.74rem', color: C.muted }}>{s.strategy_label}</span>
        {!s.tradeable && <Pill text="SPREAD GATE" color={C.red} bg={`${C.red}14`} />}
        {s.regime_aligned === false && <Pill text="vs REGIME" color={C.amber} bg={`${C.amber}14`} />}
        {/* Daily pattern confluence — a scalp on a name whose DAILY chart is
            also forming/confirming a pattern carries swing context. */}
        <PatternChips v={verdicts.get(s.symbol.toUpperCase())} max={1} />
      </div>

      {/* Levels */}
      <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: '0.8rem', flexWrap: 'wrap' }}>
        <span>entry <b>{num(s.entry)}</b></span>
        <span style={{ color: C.red }}>stop {num(s.stop)}</span>
        <span style={{ color: C.green }}>target {num(s.target)}</span>
        <span style={{ color: C.muted }}>risk {num(s.risk_pct)}% · reward {num(s.reward_pct)}%</span>
        {s.rel_vol != null && <span style={{ color: C.muted }}>RVOL {num(s.rel_vol, 1)}×</span>}
        {s.move_pct != null && <span style={{ color: C.muted }}>{num(s.move_pct, 1)}% @ {num(s.sigma_multiple, 1)}σ</span>}
      </div>

      {/* Spread gate */}
      {sp && (
        <div style={{ marginTop: 5, fontSize: '0.74rem', color: sp.state === 'tight' ? C.green : sp.state === 'unknown' ? C.muted : C.amber }}>
          spread: {sp.spread_pct != null ? `${num(sp.spread_pct)}%` : 'unknown'} — {sp.note}
        </div>
      )}

      {/* GROSS beside NET — the honesty */}
      {nc && (
        <div style={{ marginTop: 6, padding: '0.45rem 0.6rem', borderRadius: 8, background: 'var(--bg-sunken,#0f1115)', border: '1px solid var(--hairline,#2a2a2a)' }}>
          <div style={{ display: 'flex', gap: 16, fontSize: '0.76rem', flexWrap: 'wrap' }}>
            <span><span style={{ color: C.sub }}>GROSS R:R</span> <b>{num(s.reward_pct / Math.max(s.risk_pct, 0.01), 2)}</b></span>
            <span><span style={{ color: C.sub }}>round-trip cost</span> <b>{nc.round_trip_cost_pct == null ? '—' : `${num(nc.round_trip_cost_pct)}%`}</b></span>
            <span><span style={{ color: C.sub }}>NET breakeven win-rate</span> <b style={{ color: (nc.breakeven_win_rate_pct ?? 0) >= 60 ? C.red : C.amber }}>{nc.breakeven_win_rate_pct == null ? '—' : `${nc.breakeven_win_rate_pct}%`}</b></span>
          </div>
          <div style={{ fontSize: '0.7rem', color: C.muted, marginTop: 3 }}>{nc.verdict}</div>
        </div>
      )}

      <div style={{ fontSize: '0.64rem', color: C.sub, marginTop: 5 }}>{s.reasons[0]} · <span style={{ opacity: 0.8 }}>{s.source}</span></div>
    </div>
  );
}

type Tab = 'watch' | 'live' | 'backtest' | 'paper';

export function ScalpingPage() {
  const [profile] = useState<'aggressive' | 'conservative'>('aggressive');
  const { data, loading, error } = useScalpingSignals(profile);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('watch');
  const bars = useDayBars(selected, 1);
  // Today's movers (same universe the Day Trading page scans) + any live
  // signal symbols — the set the 📐 on-demand pattern scan runs against.
  const universe = useDayUniverse();
  const scanSyms = Array.from(new Set([
    ...universe.symbols, ...(data?.signals || []).map((s) => s.symbol)]));

  const TabBtn = ({ id, label }: { id: Tab; label: string }) => (
    <button onClick={() => setTab(id)} style={{
      padding: '0.4rem 0.9rem', borderRadius: 8, cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600,
      border: `1px solid ${tab === id ? 'var(--gold,#c9a227)' : 'var(--hairline,#2a2a2a)'}`,
      background: tab === id ? 'var(--gold,#c9a227)' : 'transparent',
      color: tab === id ? '#1a1a1a' : 'inherit',
    }}>{label}</button>
  );

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Intraday · documented patterns</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Scalping
            <InfoButton inline title="Scalping">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">Live ORB + shock-fade signals, gated by the intraday-momentum regime, the live spread, and a gross-beside-net cost read.</p>
        </div>
      </div>

      {/* Persistent full honesty banner */}
      <div style={{ padding: '0.6rem 0.8rem', borderRadius: 10, background: `${C.red}12`, border: `1px solid ${C.red}44`, marginBottom: 14, fontSize: '0.8rem', lineHeight: 1.45 }}>
        <strong style={{ color: C.red }}>Educational — not advice.</strong> These are <em>documented patterns, not proven retail edges.</em> Account-level
        studies find <strong>~80–99% of retail day-traders net lose</strong> after costs. Every signal shows <strong>gross beside net-of-cost</strong> and the
        win rate it needs just to break even — no backtest changes that base rate. The last 30 minutes are auction-dominated and especially hostile.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <TabBtn id="watch" label="SEPA Watch" />
        <TabBtn id="live" label="Live signals" />
        <TabBtn id="backtest" label="Backtest (~1mo)" />
        <TabBtn id="paper" label="Paper trade" />
      </div>

      {/* 🚀 Confirmed bullish + room to rally a few $ (Ajay 2026-06-10) —
          on-demand: pattern ✓ ≤1d or full buy gate, no bearish candle,
          typical daily range ≥ $2, live tape check on the leaders. */}
      <RallyScanPanel profile={profile} onChart={(s) => setSelected(s)} />

      {/* 📐 On-demand daily-pattern scan of today's movers + live signal names
          (Ajay 2026-06-10: the on-demand scan button this page was missing). */}
      <OnDemandPatternScan symbols={scanSyms}
                           title="📐 Daily patterns — today's movers, scanned on demand" />

      {tab === 'watch' && <SepaWatchPanel active={tab === 'watch'} onChart={(s) => setSelected(s)} />}
      {tab === 'backtest' && <BacktestPanel active={tab === 'backtest'} />}
      {tab === 'paper' && <PaperPanel active={tab === 'paper'} />}

      {tab === 'live' && loading && !data && <p className="mono" style={{ opacity: 0.7 }}>…scanning the tape</p>}
      {tab === 'live' && error && <p className="mono" style={{ color: C.red }}>Couldn't load signals — {error}</p>}

      {tab === 'live' && data && (
        <>
          <RegimeBar r={data.regime} />

          {!data.market_open ? (
            <div className="sepa-empty-card">
              <div className="eyebrow">Market closed</div>
              <p style={{ color: C.muted }}>Scalping signals run during the regular session (9:30–16:00 ET). The intraday-momentum regime above forms after 10:00 ET.</p>
            </div>
          ) : data.signals.length === 0 ? (
            <div className="sepa-empty-card">
              <div className="eyebrow">No qualifying setups right now</div>
              <p style={{ color: C.muted }}>Nothing clears the RelVol / volatility / spread gates this minute. That's normal — most minutes have no edge. Re-checks every 45s.</p>
            </div>
          ) : (
            <div style={{ fontSize: '0.72rem', color: C.sub, marginBottom: 6 }}>
              {data.signals.length} signal{data.signals.length === 1 ? '' : 's'} · {data.as_of_et} · re-checks every 45s
            </div>
          )}

          {data.signals.map((s) => (
            <SignalCard key={`${s.symbol}-${s.strategy}`} s={s} selected={selected === s.symbol} onSelect={() => setSelected(s.symbol)} />
          ))}

          <p style={{ fontSize: '0.66rem', color: C.sub, marginTop: 14 }}>{data.disclaimer}</p>
        </>
      )}

      {/* Live intraday chart for the selected name — shared by the Watch + Live tabs */}
      {(tab === 'watch' || tab === 'live') && selected && bars.data && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <strong>{selected} — live 1-min (VWAP + opening range)</strong>
            <button onClick={() => setSelected(null)} style={{ background: 'transparent', border: '1px solid var(--hairline,#2a2a2a)', color: 'inherit', borderRadius: 6, padding: '0.2rem 0.55rem', cursor: 'pointer', fontSize: '0.74rem' }}>Close chart</button>
          </div>
          {/* The pattern-reading strip: latest 5-min candle vs pivot / daily
              pattern line / VWAP / OR + the daily pattern verdict chip. */}
          <LiveTapeRead symbol={selected} />
          <IntradayChart data={bars.data} signals={[]} />
        </div>
      )}
    </div>
  );
}
