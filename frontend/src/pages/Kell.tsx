/* /kell — Oliver Kell's Cycle of Price Action page.
 *
 * SEPARATE page from /sepa. The Kell scanners read the SAME SEPA
 * candidate list (universe parity) but produce Kell-specific pattern
 * detections (reversal_extension, wedge_pop, ema_crossback,
 * base_n_break, exhaustion_extension, wedge_drop) ranked safest → most
 * aggressive, with exhaustion_extension and wedge_drop as defensive
 * warnings (SELL signals, not entries).
 *
 * Architecture (mirror of Sepa.tsx but stripped down):
 *   - Reuse useSepaScan() for the candidate universe (the symbol-set is
 *     identical so we don't need a separate fetch).
 *   - Reuse useSetupsByKind() per active tab to fetch /setups/{kind} —
 *     the backend persists Kell rows in the SAME `setups` collection.
 *   - Reuse SepaCandidateCard with setupOverlay so the per-card UI is
 *     consistent across /sepa and /kell.
 *   - Reuse useLivePrices / useWhalesFlow / useOptionsPulse so chips
 *     and live-price overlay behave identically.
 *   - SKIP SepaFilterBar (no rating/RS filters here — Kell tabs are
 *     already SEPA-quality filtered upstream).
 *   - SKIP top-picks hero rail (Kell page is setup-focused, not
 *     ranked-by-conviction).
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSepaScan } from '../hooks/useSepa';
import type { SepaCandidate } from '../hooks/useSepa';
import { MarketRegimeBanner } from '../components/MarketRegimeBanner';
import { MarketClockStrip } from '../components/MarketClockStrip';
import { SepaCandidateCard } from '../components/SepaCandidateCard';
import { InfoButton } from '../components/InfoButton';
import { useOptionsPulse, type SoirRow } from '../hooks/useOptionsPulse';
import { useWhalesFlow } from '../hooks/useWhalesFlow';
import { useLivePrices } from '../hooks/useLivePrices';
import { usePageContext } from '../hooks/usePageContext';
import {
  KellSetupTabs,
  KELL_TAB_TO_KIND,
  KELL_KINDS,
  kellTabLabel,
  type KellTab,
} from '../components/KellSetupTabs';
import { KellSetupInfoBanner } from '../components/KellSetupInfoBanner';
import { KellSetupInfoPanel } from '../components/KellSetupInfoPanel';
import {
  useSetupsByKind,
  getCachedSetupCount,
  type Setup,
} from '../hooks/useSetupsByKind';
import { SetupOverlayStrip } from '../components/SetupOverlayStrip';

const PageInfo = (
  <>
    <p>
      <strong>Oliver Kell's Cycle of Price Action (CoPA)</strong> reframes
      stock setups as a recurring <em>cycle</em> rather than independent
      patterns. A typical Stage-2 leader rotates through these six phases:
    </p>
    <ul>
      <li><strong>Reversal Extension</strong> — bullish reversal bar after price extended below the 10 EMA.</li>
      <li><strong>Wedge Pop</strong> — first reclaim of the 10/20 EMA cluster after a downtrend.</li>
      <li><strong>EMA Crossback</strong> — first pullback to the EMAs in a confirmed new uptrend. Kell's safest add point.</li>
      <li><strong>Base n' Break</strong> — 5-15 day consolidation on the 10/20 EMA, then breakout on expanding volume.</li>
      <li><strong>Exhaustion Extension</strong> — 2nd or 3rd extension ≥8% above the 10 EMA. <em>SELL signal.</em></li>
      <li><strong>Wedge Drop</strong> — first close below both EMAs after Exhaustion. <em>Cycle end — SELL signal.</em></li>
    </ul>
    <p>
      Each Kell scanner reads the SAME SEPA candidate universe, so quality is
      already filtered upstream — the tabs surface pattern-specific entries
      with trigger / stop / target / R:R inline.
    </p>
  </>
);

const ResultsInfo = (
  <>
    <p>Each card shows the matched setup with an overlay strip carrying:</p>
    <ul>
      <li><strong>Trigger</strong> — buy at or above this price.</li>
      <li><strong>Stop</strong> — protective stop level.</li>
      <li><strong>Target</strong> — first-scale target.</li>
      <li><strong>R:R</strong> — reward divided by risk.</li>
    </ul>
    <p>
      The card body is the standard SEPA candidate view — composite score,
      RS rank, stage, signal chips, volume character. Click a card for the
      full ticker drill-in.
    </p>
  </>
);

/** A single setup row paired with the matching SEPA candidate (if any). */
type SetupRow = { setup: Setup; candidate: SepaCandidate | null };

export function KellPage() {
  const { data } = useSepaScan();
  const { setPageContext } = usePageContext();
  const navigate = useNavigate();

  const openSymbol = (sym: string, e?: React.MouseEvent) => {
    const url = `/sepa/${encodeURIComponent(sym)}`;
    if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate(url, { state: { from: '/kell', label: 'Kell' } });
  };

  // ── Active tab — persists in URL hash so sharing a Kell tab link
  // (e.g. /kell#tab=base_n_break) lands the user on the right view.
  const [activeTab, setActiveTab] = useState<KellTab>(() => {
    if (typeof window === 'undefined') return 'all';
    const m = window.location.hash.match(/tab=([a-z_]+)/);
    const candidate = m?.[1] as KellTab | undefined;
    const valid: KellTab[] = [
      'all', 'base_n_break', 'ema_crossback', 'wedge_pop',
      'reversal_extension', 'exhaustion_extension', 'wedge_drop',
    ];
    return candidate && valid.includes(candidate) ? candidate : 'all';
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (activeTab === 'all') {
      if (window.location.hash.startsWith('#tab=')) window.location.hash = '';
    } else {
      window.location.hash = `tab=${activeTab}`;
    }
  }, [activeTab]);

  const activeKind = KELL_TAB_TO_KIND[activeTab];

  // For a single-kind tab, the existing useSetupsByKind hook is enough.
  // For 'all', we fan out per-kind fetches and merge — done below via
  // the dedicated useAllKellSetups hook.
  const {
    setups: tabSetups,
    loading: tabLoading,
    error: tabError,
  } = useSetupsByKind(activeKind);

  // ── Combined 'all' tab: fetch each Kell kind once and merge. We reuse
  // useSetupsByKind so the module-level cache is shared with per-tab
  // fetches — no duplicate API calls when the user flips between 'all'
  // and a specific kind. Each kind is its own hook call (React rules
  // require static hook order, so we expand all 6 here explicitly).
  const bnb = useSetupsByKind(activeTab === 'all' ? 'base_n_break' : null);
  const emc = useSetupsByKind(activeTab === 'all' ? 'ema_crossback' : null);
  const wp  = useSetupsByKind(activeTab === 'all' ? 'wedge_pop' : null);
  const re  = useSetupsByKind(activeTab === 'all' ? 'reversal_extension' : null);
  const ex  = useSetupsByKind(activeTab === 'all' ? 'exhaustion_extension' : null);
  const wd  = useSetupsByKind(activeTab === 'all' ? 'wedge_drop' : null);

  const allKellSetups: Setup[] = useMemo(() => {
    if (activeTab !== 'all') return [];
    const merged = [
      ...bnb.setups, ...emc.setups, ...wp.setups,
      ...re.setups,  ...ex.setups,  ...wd.setups,
    ];
    // Sort by R:R desc — best risk/reward floats up. Exhaustion/Wedge
    // Drop rows have rr ~= 0 (no real target) so they sink to the
    // bottom of the combined feed, which is the intended order:
    // entries first, warnings last.
    merged.sort((a, b2) => (b2.rr || 0) - (a.rr || 0));
    return merged;
  }, [activeTab, bnb.setups, emc.setups, wp.setups, re.setups, ex.setups, wd.setups]);

  const allLoading = activeTab === 'all' && (
    bnb.loading || emc.loading || wp.loading || re.loading || ex.loading || wd.loading
  );

  // Effective setup list for the currently-active tab.
  const currentSetups: Setup[] = activeTab === 'all' ? allKellSetups : tabSetups;

  // ── Build a fast symbol → SepaCandidate lookup off the SEPA scan so
  // matched setups render with the full candidate card body.
  const source: SepaCandidate[] = useMemo(() => {
    return (data?.all_results || data?.candidates || []) as SepaCandidate[];
  }, [data]);
  const candidateBySymbol = useMemo(() => {
    const m = new Map<string, SepaCandidate>();
    for (const row of source) m.set(row.symbol.toUpperCase(), row);
    return m;
  }, [source]);

  const setupRows: SetupRow[] = useMemo(() => {
    return currentSetups.map((s) => ({
      setup: s,
      candidate: candidateBySymbol.get(s.symbol.toUpperCase()) ?? null,
    }));
  }, [currentSetups, candidateBySymbol]);

  // ── Shared overlays: options chip, whale flow, live price — same
  // hooks the SEPA page uses, so cards look identical.
  const { data: optionsScan } = useOptionsPulse();
  const optionsBySymbol = useMemo(() => {
    const map = new Map<string, SoirRow>();
    for (const row of optionsScan?.rows || []) {
      if (row.symbol) map.set(row.symbol.toUpperCase(), row);
    }
    return map;
  }, [optionsScan]);
  const whalesFlow = useWhalesFlow();
  const livePrices = useLivePrices();

  // ── Tab counts. Active tab uses live state; others read the
  // module-level cache in useSetupsByKind.
  const tabCounts = useMemo<Partial<Record<KellTab, number | null>>>(() => {
    const out: Partial<Record<KellTab, number | null>> = {};
    if (activeTab === 'all') {
      out.all = allKellSetups.length;
    } else {
      const a = currentSetups.length;
      out[activeTab] = a;
      // 'all' tab count = sum of cached counts across kinds.
      let sum = 0;
      let anyCached = false;
      for (const k of KELL_KINDS) {
        const v2 = getCachedSetupCount(k);
        if (v2 != null) { sum += v2; anyCached = true; }
      }
      if (anyCached) out.all = sum;
    }
    for (const k of KELL_KINDS) {
      const tab = k as KellTab;
      if (tab === activeTab) continue;
      out[tab] = getCachedSetupCount(k);
    }
    return out;
  }, [activeTab, allKellSetups.length, currentSetups.length]);

  // ── Page context for ChatWidget. Snapshot the active tab + counts +
  // top visible setups so the assistant can answer "what's in the wedge
  // drop tab?" or "should I take MU on the base break?"
  useEffect(() => {
    const top_visible = setupRows.slice(0, 12).map(({ setup, candidate }) => ({
      symbol:  setup.symbol,
      kind:    setup.kind,
      trigger: setup.trigger,
      stop:    setup.stop,
      target:  setup.target,
      rr:      setup.rr,
      score:   candidate?.score,
      rating:  candidate?.rating,
      rs_rank: candidate?.rs_rank,
    }));

    const tab_counts: Record<string, number | null> = {};
    (Object.keys(tabCounts) as KellTab[]).forEach((t) => {
      const v2 = tabCounts[t];
      if (v2 != null) tab_counts[t] = v2;
    });

    const active_setups = setupRows.slice(0, 5).map(({ setup }) => ({
      symbol:  setup.symbol,
      trigger: setup.trigger,
      stop:    setup.stop,
      target:  setup.target,
      rr:      setup.rr,
      kind:    setup.kind,
    }));

    setPageContext({
      page:             'kell-list',
      active_kell_tab:  activeTab,
      tab_counts,
      active_setups,
      top_visible,
    });
    return () => setPageContext(null);
  }, [activeTab, setupRows, tabCounts, setPageContext]);

  const isLoading = activeTab === 'all' ? allLoading : tabLoading;
  const errorMsg = activeTab === 'all'
    ? (bnb.error || emc.error || wp.error || re.error || ex.error || wd.error || null)
    : tabError;

  return (
    <div className="sepa-page">
      <MarketRegimeBanner />
      <MarketClockStrip />

      <div className="sepa-page__title">
        <InfoButton title="Oliver Kell — Cycle of Price Action">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 06 — Methodology</div>
          <h1 className="display sepa-page__h1">
            Oliver Kell · Cycle of Price Action
          </h1>
          <p className="lede">
            Six pattern detectors per Kell's <em>Victory in Stock Trading</em>:
            wedge drops, reversal extensions, volatility compressions, base
            breaks, power trends — plus climax-run warnings. Same SEPA
            universe, different lens.
          </p>
        </div>
      </div>

      <KellSetupTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tabCounts={tabCounts}
      />

      <KellSetupInfoBanner activeTab={activeTab} />

      <div
        style={{
          display:        'flex',
          gap:            '1rem',
          alignItems:     'flex-start',
          flexWrap:       'wrap',
        }}
      >
        <div style={{ flex: '1 1 600px', minWidth: 0 }}>
          {isLoading ? (
            <div
              className="sepa-empty-card"
              style={{ color: '#9a9aa3', fontSize: '0.92rem' }}
            >
              loading {kellTabLabel(activeTab)}…
            </div>
          ) : errorMsg ? (
            <div className="sepa-empty-card">
              <div className="eyebrow">Couldn't load Kell setups</div>
              <p style={{ color: '#fca5a5' }}>{errorMsg}</p>
            </div>
          ) : setupRows.length === 0 ? (
            <div className="sepa-empty-card">
              <div className="eyebrow">No {kellTabLabel(activeTab)} setups</div>
              <p>
                No {kellTabLabel(activeTab)} setups today. Common reasons:
                bear regime (most Kell scanners short-circuit), no symbols
                meet the strict pattern requirements, or the scanner hasn't
                run yet (Kell scanners refresh nightly between 7:05–7:30 PM ET).
              </p>
            </div>
          ) : (
            <section className="sepa-results">
              <InfoButton title="Results">{ResultsInfo}</InfoButton>
              <div className="sepa-grid">
                {setupRows.map(({ setup, candidate }) => {
                  const sym = setup.symbol.toUpperCase();
                  if (candidate) {
                    return (
                      <SepaCandidateCard
                        key={`${setup.kind}-${candidate.symbol}-${setup._id || ''}`}
                        row={candidate}
                        soir={optionsBySymbol.get(sym)}
                        whalesFlow={whalesFlow.get(sym)}
                        livePrice={livePrices[sym]}
                        setupOverlay={<SetupOverlayStrip setup={setup} />}
                        onSelect={(e) => openSymbol(candidate.symbol, e)}
                      />
                    );
                  }
                  // Placeholder when the setup's symbol isn't in the
                  // currently-loaded SEPA source (e.g. all_results not
                  // hydrated yet). Surface the match anyway.
                  return (
                    <div
                      key={setup._id || `${setup.kind}-${setup.symbol}`}
                      className="sepa-card-with-overlay"
                    >
                      <SetupOverlayStrip setup={setup} />
                      <article
                        className="sepa-card"
                        role="button"
                        tabIndex={0}
                        onClick={(e) => openSymbol(setup.symbol, e)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') openSymbol(setup.symbol);
                        }}
                        title="Cmd/Ctrl-click to open in new tab"
                        style={{ cursor: 'pointer' }}
                      >
                        <header className="sepa-card__head">
                          <div className="sepa-card__sym">
                            <div className="sepa-card__sym-line">
                              <strong>{setup.symbol}</strong>
                              <span
                                style={{
                                  marginLeft: 8,
                                  fontSize: '0.7rem',
                                  color: '#9aa8c8',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.06em',
                                }}
                              >
                                {setup.kind.replace(/_/g, ' ')}
                              </span>
                            </div>
                            <div
                              className="sepa-card__name"
                              style={{ color: '#9a9aa3', fontSize: '0.78rem', marginTop: 4 }}
                            >
                              Setup match — no live SEPA row loaded for this symbol
                            </div>
                          </div>
                        </header>
                      </article>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
        <KellSetupInfoPanel activeTab={activeTab} />
      </div>
    </div>
  );
}

export default KellPage;
