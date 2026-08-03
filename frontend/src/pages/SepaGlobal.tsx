/* SEPA Global — the minimal, beginner-friendly scanner (Ajay 2026-06-23).
 *
 * Same Minervini scan as the admin /sepa page, dumbed down: a traffic-light
 * verdict, plain English, and a clear risk number — no VCP / ADR / stage / CMF
 * jargon, and just three filters. Reads the SAME /sepa/scan feed (useSepaScan);
 * the simplification is all presentation (lib/sepaGlobal). */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSepaScan } from '../hooks/useSepa';
import type { SepaCandidate } from '../hooks/useSepa';
import { useLivePrices } from '../hooks/useLivePrices';
import { useMyFeatures } from '../hooks/useMyFeatures';
import { toGlobalCard, toGlobalDetail, filterForTab, type GlobalTab } from '../lib/sepaGlobal';
import { SepaGlobalCard } from '../components/SepaGlobalCard';
import { SepaGlobalDetailModal } from '../components/SepaGlobalDetailModal';
import { InfoButton } from '../components/InfoButton';

const TABS: { key: GlobalTab; label: string; hint: string }[] = [
  { key: 'buy',     label: 'Buy now',     hint: 'Confirmed breakouts you can act on today' },
  { key: 'watch',   label: 'Watch',       hint: 'Setting up — wait for the breakout' },
  { key: 'leaders', label: 'Top leaders', hint: 'Every strong stock in a confirmed uptrend' },
];

const HowItWorks = (
  <>
    <p>
      These are strong stocks in confirmed up-trends, found with trader Mark
      Minervini’s rules — the same engine the full scanner uses, shown simply.
    </p>
    <ul>
      <li><strong>Buy zone</strong> 🟢 — broke out on heavy volume; in the price range to buy now.</li>
      <li><strong>Watch</strong> 🟡 — setting up nicely but hasn’t broken out yet. Be patient.</li>
      <li><strong>Leader</strong> ⚪ — a strong up-trend stock to keep on your radar.</li>
      <li><strong>Avoid</strong> 🔴 — big investors look to be selling. Stay away.</li>
    </ul>
    <p>
      <strong>Always know your risk first.</strong> Each card shows the price to
      buy and the price to <em>sell if you’re wrong</em> (the stop) plus how much
      you’d risk. Minervini’s #1 rule: cut losses early.
    </p>
    <p className="mono">Educational only — not financial advice.</p>
  </>
);

export function SepaGlobalPage() {
  const { data, loading, scanning, refetch } = useSepaScan();
  const livePrices = useLivePrices();
  const navigate = useNavigate();
  // Full-SEPA users jump straight to the ticker detail page (Ajay 2026-07-17:
  // "take me to individual tickers instead of opening up a small modal");
  // Global-only friends keep the simple modal — the /sepa/:symbol route is
  // feature-gated and would bounce them to the landing page.
  const { features } = useMyFeatures();
  const hasFullSepa = features.has('sepa');
  const [tab, setTab] = useState<GlobalTab>('leaders');
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState<SepaCandidate | null>(null);

  const candidates = (data?.candidates as SepaCandidate[] | undefined) ?? [];
  const liveFor = (sym: string) => livePrices[sym.toUpperCase()];

  const counts = useMemo(() => ({
    buy: filterForTab(candidates, 'buy').length,
    watch: filterForTab(candidates, 'watch').length,
    leaders: filterForTab(candidates, 'leaders').length,
  }), [candidates]);

  const rows = useMemo(() => {
    let r = filterForTab(candidates, tab);
    const needle = q.trim().toUpperCase();
    if (needle) {
      r = r.filter(
        (x) => x.symbol.toUpperCase().includes(needle) ||
               (x.name ?? '').toUpperCase().includes(needle),
      );
    }
    return r;
  }, [candidates, tab, q]);

  const safeToLong = data?.market_context?.safe_to_long;

  return (
    <div className="sepa-page" style={{ maxWidth: 760, margin: '0 auto' }}>
      <div className="sepa-page__title" style={{ marginBottom: '0.35rem' }}>
        <div className="eyebrow">Minervini · simplified</div>
        <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          🌍 SEPA Global
          <InfoButton inline title="How SEPA Global works">{HowItWorks}</InfoButton>
        </h1>
        <p style={{ color: 'var(--cm-slate, #94a3b8)', margin: '0.15rem 0 0', fontSize: '0.9rem' }}>
          Strong stocks in confirmed up-trends — Minervini’s rules, in plain English.
        </p>
      </div>

      {/* Risk-first market note — don't fight a hostile tape. */}
      {data && safeToLong === false && (
        <div
          style={{
            border: '1px solid var(--negative, #f87171)', borderRadius: 8,
            padding: '0.45rem 0.7rem', margin: '0.4rem 0', fontSize: '0.84rem',
            color: 'var(--negative, #f87171)',
          }}
        >
          ⚠️ The overall market looks weak right now. Even strong stocks fail in a
          falling market — be extra careful, or wait.
        </div>
      )}

      {/* Three minimal filters */}
      <div style={{ display: 'flex', gap: '0.4rem', margin: '0.6rem 0', flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`sepa-chip ${tab === t.key ? 'is-active' : ''}`}
            title={t.hint}
            onClick={() => setTab(t.key)}
            style={{
              cursor: 'pointer',
              ...(tab === t.key
                ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 }
                : {}),
            }}
          >
            {t.label} <span style={{ opacity: 0.7 }}>({counts[t.key]})</span>
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search ticker…"
          aria-label="Search ticker"
          style={{
            flex: '1 1 120px', minWidth: 110, padding: '0.3rem 0.6rem',
            borderRadius: 8, border: '1px solid var(--cm-border, #2a2f3a)',
            background: 'var(--cm-card, #161a22)', color: 'inherit',
          }}
        />
      </div>

      {loading && candidates.length === 0 && (
        <p style={{ color: 'var(--cm-slate, #94a3b8)' }}>Loading the latest scan…</p>
      )}

      {!loading && rows.length === 0 && (
        <div style={{ color: 'var(--cm-slate, #94a3b8)', padding: '1rem 0' }}>
          {tab === 'buy' ? (
            <p>
              Nothing in the buy zone right now — that’s normal and fine. In
              Minervini’s method, patience is free. Check <strong>Watch</strong> or{' '}
              <strong>Top leaders</strong> for names setting up.
            </p>
          ) : (
            <p>No matches{q ? ` for “${q}”` : ''} in the latest scan yet.</p>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
        {rows.map((r) => (
          <SepaGlobalCard
            key={r.symbol}
            card={toGlobalCard(r, liveFor(r.symbol))}
            onClick={() => (hasFullSepa
              ? navigate(`/sepa/${encodeURIComponent(r.symbol)}`)
              : setSelected(r))}
          />
        ))}
      </div>

      {selected && (
        <SepaGlobalDetailModal
          detail={toGlobalDetail(selected, liveFor(selected.symbol))}
          onClose={() => setSelected(null)}
        />
      )}

      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
        <button className="sepa-chip" onClick={() => refetch?.()} disabled={scanning}
          style={{ cursor: 'pointer' }}>
          ↻ Refresh
        </button>
        <span style={{ fontSize: '0.74rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Educational only — not financial advice.
        </span>
      </div>
    </div>
  );
}
