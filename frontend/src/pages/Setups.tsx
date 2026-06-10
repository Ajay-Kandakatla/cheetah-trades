/* Setups — bull-regime intraday + short-swing setups.
 *
 *  Three tabs over a single API surface:
 *
 *     PEG  (Power Earnings Gap) — multi-day hold, gap-day high break
 *     ORB  (Opening Range Breakout) — same-day, 9:30-9:45 range break
 *     Inside-Day — 1-3 day hold, compression-bar break
 *
 *  Each row shows: ticker · trigger · stop · target · R:R · status.
 *  Tap any row → opens the SEPA candidate detail page for that ticker
 *  with `?from=<kind>` so the page can highlight setup context. (Stays
 *  in-app; we don't deep-link to Fidelity since order placement should
 *  feel deliberate, not one-tap.)
 *
 *  Data shape (matches backend/setups/store.py.make_setup):
 *    {_id, kind, symbol, trigger, stop, target, rr, risk_pct, reward_pct,
 *     status, generated_at, expires_at, meta: {...kind-specific}}
 *
 *  Bear-regime behavior: backend short-circuits the scanners when the
 *  regime classifier says "bear", so this page just shows an empty list
 *  with a banner explaining why. By design (user chose to sit out bears).
 */
import { useEffect, useState, type ReactNode } from 'react';
import { TickerName } from '../components/TickerCell';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { SetupExplainer } from '../components/SetupExplainer';
import { usePageContext } from '../hooks/usePageContext';

type Kind = 'peg' | 'orb' | 'inside_day';

type Setup = {
  _id: string;
  kind: Kind;
  symbol: string;
  trigger: number;
  stop: number;
  target: number;
  rr: number;
  risk_pct: number;
  reward_pct: number;
  status: 'pending' | 'triggered' | 'expired' | 'stopped';
  generated_at: number;
  expires_at: number;
  triggered_at?: number | null;
  triggered_price?: number | null;
  meta?: Record<string, unknown>;
};

const TAB_META: Record<Kind, {
  label:  string;
  icon:   string;
  blurb:  string;
  hold:   string;
  target: string;
}> = {
  peg: {
    label:  'PEG',
    icon:   '⚡',
    blurb:  'Power Earnings Gap — buy when a quality name takes out the high of its gap-day (≥ 5% gap on ≥ 4× volume).',
    hold:   '3–10 days',
    target: '3–8%',
  },
  orb: {
    label:  'ORB',
    icon:   '🎯',
    blurb:  'Opening Range Breakout — buy a break of the 9:30–9:45 range high on confirming volume. Exit by close.',
    hold:   'same day',
    target: '1–2%',
  },
  inside_day: {
    label:  'Inside-Day',
    icon:   '📦',
    blurb:  "Compression-bar break — buy a break of yesterday's high when yesterday's bar sat inside the prior day's range.",
    hold:   '1–3 days',
    target: '1.5–3%',
  },
};

const STATUS_COLOR: Record<Setup['status'], string> = {
  pending:   '#9aa8c8',
  triggered: '#22c55e',
  expired:   '#6a6a72',
  stopped:   '#ef4444',
};

function fmtPrice(n: number): string {
  return n >= 100 ? n.toFixed(2) : n.toFixed(3);
}

function fmtAgo(epoch: number): string {
  const sec = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  if (sec < 60)    return `${sec}s ago`;
  if (sec < 3600)  return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

function PegMetaCell({ meta }: { meta?: Record<string, unknown> }): ReactNode {
  if (!meta) return null;
  const gap = meta.gap_pct as number | undefined;
  const vol = meta.vol_mult as number | undefined;
  const days = meta.days_ago as number | undefined;
  const hint = meta.catalyst_hint as string | undefined;
  return (
    <span style={{ fontSize: '0.72rem', color: '#9a9aa3' }}>
      {gap != null  && <>gap {gap.toFixed(1)}% · </>}
      {vol != null  && <>vol {vol.toFixed(1)}× · </>}
      {days != null && <>{days}d ago{hint ? ` · ${hint}` : ''}</>}
    </span>
  );
}

function OrbMetaCell({ meta }: { meta?: Record<string, unknown> }): ReactNode {
  if (!meta) return null;
  const rh = meta.range_high as number | undefined;
  const rl = meta.range_low  as number | undefined;
  const rp = meta.range_pct  as number | undefined;
  return (
    <span style={{ fontSize: '0.72rem', color: '#9a9aa3' }}>
      {rl != null && rh != null && <>range {fmtPrice(rl)}–{fmtPrice(rh)}</>}
      {rp != null && <> · {rp.toFixed(2)}%</>}
    </span>
  );
}

function InsideDayMetaCell({ meta }: { meta?: Record<string, unknown> }): ReactNode {
  if (!meta) return null;
  const rng = meta.today_range_pct as number | undefined;
  const yhi = meta.yesterday_high as number | undefined;
  const ylo = meta.yesterday_low  as number | undefined;
  return (
    <span style={{ fontSize: '0.72rem', color: '#9a9aa3' }}>
      {rng != null && <>range {rng.toFixed(2)}%</>}
      {yhi != null && ylo != null && <> · prev {fmtPrice(ylo)}–{fmtPrice(yhi)}</>}
    </span>
  );
}

function SetupRow({ s }: { s: Setup }) {
  const upcomingExpiry = s.expires_at - Math.round(Date.now() / 1000);
  const expiresSoon = upcomingExpiry > 0 && upcomingExpiry < 6 * 3600;
  const meta = s.meta || {};
  return (
    <Link
      to={`/sepa/${s.symbol}?from=${s.kind}`}
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) auto',
        alignItems: 'center',
        gap: '0.6rem',
        padding: '0.7rem 0.85rem',
        background: 'rgba(20,20,22,0.65)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 8,
        textDecoration: 'none',
        color: 'inherit',
        marginBottom: '0.5rem',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
          <span style={{ fontWeight: 700, fontSize: '1.02rem' }}>{s.symbol}<TickerName symbol={s.symbol} width={18} /></span>
          <span style={{
            fontSize: '0.66rem',
            color: STATUS_COLOR[s.status],
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}>
            {s.status}
            {s.status === 'triggered' && s.triggered_price != null && (
              <> @ {fmtPrice(s.triggered_price)}</>
            )}
          </span>
          {expiresSoon && (
            <span style={{ fontSize: '0.62rem', color: '#f59e0b' }}>
              · expires {Math.round(upcomingExpiry / 3600)}h
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.78rem', color: '#cfcfd4', marginTop: 2 }}>
          buy ≥ <strong>{fmtPrice(s.trigger)}</strong>
          {'  '}· stop <span style={{ color: '#ef4444' }}>{fmtPrice(s.stop)}</span>
          {'  '}· tgt <span style={{ color: '#22c55e' }}>{fmtPrice(s.target)}</span>
          {'  '}· R:R <strong>{s.rr.toFixed(2)}</strong>
        </div>
        <div style={{ marginTop: 2 }}>
          {s.kind === 'peg' &&        <PegMetaCell        meta={meta} />}
          {s.kind === 'orb' &&        <OrbMetaCell        meta={meta} />}
          {s.kind === 'inside_day' && <InsideDayMetaCell  meta={meta} />}
        </div>
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.66rem', color: '#6a6a72' }}>
        <div>{s.risk_pct.toFixed(1)}% risk</div>
        <div style={{ marginTop: 2 }}>{fmtAgo(s.generated_at)}</div>
      </div>
    </Link>
  );
}

export default function SetupsPage() {
  const [tab, setTab] = useState<Kind>('peg');
  const [setups, setSetups] = useState<Setup[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [err, setErr] = useState<string | null>(null);
  const [includeNonPending, setIncludeNonPending] = useState<boolean>(false);
  const { setPageContext } = usePageContext();

  // Page context for ChatWidget — tells Claude which tab is active and
  // which tickers are currently surfaced. Lets users ask "should I take
  // the AAPL PEG?" and have the assistant answer against the row data.
  useEffect(() => {
    setPageContext({
      page:        'setups',
      active_tab:  tab,
      setup_count: setups.length,
      setups: setups.slice(0, 15).map((s) => ({
        symbol:  s.symbol,
        trigger: s.trigger,
        stop:    s.stop,
        target:  s.target,
        rr:      s.rr,
        status:  s.status,
      })),
    });
    return () => setPageContext(null);
  }, [tab, setups, setPageContext]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    const url = `${API}/setups/${tab}?only_pending=${includeNonPending ? 'false' : 'true'}&limit=100`;
    fetch(url, { credentials: 'include' })
      .then(async r => {
        if (!r.ok) {
          const t = await r.text().catch(() => '');
          throw new Error(t || `HTTP ${r.status}`);
        }
        return r.json();
      })
      .then(j => {
        if (cancelled) return;
        setSetups((j?.setups || []) as Setup[]);
      })
      .catch(e => {
        if (cancelled) return;
        setErr(String(e?.message || e));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tab, includeNonPending]);

  const meta = TAB_META[tab];

  return (
    <div className="cm-page">
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ — Bull-regime setups</div>
          <h1 className="display cm-pagehead__title">Setups</h1>
          <p className="lede">
            Three mechanical, bull-only setups built on top of your SEPA candidate list.
            Trigger / stop / target are pre-computed so you can place the orders at
            Fidelity in 60 seconds. <strong>The scanners short-circuit during bear
            regimes — that's by design, not a bug.</strong>
          </p>
        </div>
      </header>

      <div role="tablist" style={{
        display: 'flex',
        gap: '0.4rem',
        marginBottom: '1rem',
        flexWrap: 'wrap',
      }}>
        {(['peg', 'orb', 'inside_day'] as Kind[]).map(k => {
          const active = tab === k;
          return (
            <button
              key={k}
              role="tab"
              aria-selected={active}
              onClick={() => setTab(k)}
              style={{
                padding: '0.5rem 0.95rem',
                background: active ? 'rgba(212,175,55,0.14)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? 'rgba(212,175,55,0.42)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 999,
                color: active ? '#f3e8c8' : '#cfcfd4',
                fontFamily: 'inherit',
                fontWeight: active ? 700 : 500,
                fontSize: '0.84rem',
                cursor: 'pointer',
              }}
            >
              {TAB_META[k].icon} {TAB_META[k].label}
            </button>
          );
        })}
      </div>

      <section style={{
        padding: '0.8rem 1rem',
        background: 'rgba(20,20,22,0.55)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 10,
        marginBottom: '0.6rem',
      }}>
        <div style={{ fontSize: '0.92rem', marginBottom: 4 }}>
          {meta.icon} <strong>{meta.label}</strong>
        </div>
        <div style={{ fontSize: '0.82rem', color: '#cfcfd4', lineHeight: 1.5 }}>
          {meta.blurb}
        </div>
        <div style={{ marginTop: 6, fontSize: '0.72rem', color: '#9a9aa3' }}>
          hold {meta.hold} · target {meta.target}
        </div>
      </section>

      {/* Collapsible deep-dive: anatomy + worked example + Fidelity steps
          + pitfalls. Collapsed by default — power users don't need it
          every visit, but it's there the first time you open a tab. */}
      <SetupExplainer kind={tab} />

      <label style={{
        display: 'inline-flex',
        gap: '0.4rem',
        alignItems: 'center',
        fontSize: '0.78rem',
        color: '#9a9aa3',
        marginBottom: '0.7rem',
        cursor: 'pointer',
      }}>
        <input
          type="checkbox"
          checked={includeNonPending}
          onChange={(e) => setIncludeNonPending(e.target.checked)}
        />
        include triggered / expired
      </label>

      {err && (
        <div style={{
          padding: '0.6rem 0.8rem',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 4,
          color: '#fca5a5',
          fontSize: '0.84rem',
          marginBottom: '0.8rem',
        }}>
          {err}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#9a9aa3', fontSize: '0.85rem' }}>loading…</div>
      ) : setups.length === 0 ? (
        <div style={{
          padding: '1.2rem 1rem',
          background: 'rgba(20,20,22,0.55)',
          border: '1px dashed rgba(255,255,255,0.1)',
          borderRadius: 8,
          color: '#9a9aa3',
          fontSize: '0.85rem',
          lineHeight: 1.55,
        }}>
          No {meta.label} setups right now. This is normal — these scanners are
          opportunistic. Common reasons for an empty list:
          <ul style={{ marginTop: 6, paddingLeft: '1.1rem' }}>
            <li>Market regime is bearish (scanner short-circuits)</li>
            <li>No SEPA candidate met the strict gap/range/compression filter today</li>
            <li>Yesterday's cron hasn't run yet (PEG/Inside-Day refresh at 6:30 PM ET)</li>
          </ul>
        </div>
      ) : (
        <div>
          {setups.map(s => <SetupRow key={s._id} s={s} />)}
        </div>
      )}
    </div>
  );
}
