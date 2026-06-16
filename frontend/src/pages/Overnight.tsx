import { useState } from 'react';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { OvernightPanel } from '../components/OvernightPanel';
import { OptionsPulseSummary } from '../components/OptionsPulseSummary';
import { SupplyDemandSummary } from '../components/SupplyDemandSummary';

export function OvernightPage() {
  const [minGap, setMinGap] = useState<number>(0.5);

  return (
    <div className="cm-page">
      <MarketGaugeBanner />

      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">Methodology</div>
          <h1 className="display cm-pagehead__title">Overnight Tape</h1>
          <p className="lede">
            What moved while you slept and <em>why</em>. Premarket gaps from
            yesterday's RTH close, with auto-attached news catalysts —
            earnings, analyst calls, M&A, FDA, geopolitical, macro.
            Use this to know what you're walking into before you click buy.
          </p>
        </div>
      </header>

      <section className="overnight-controls">
        <div className="overnight-controls__group">
          <label className="eyebrow">Minimum gap</label>
          <div className="overnight-controls__btns">
            {[0.25, 0.5, 1, 2, 3].map((g) => (
              <button key={g} type="button"
                className={`sepa-btn sepa-btn--ghost ${minGap === g ? 'is-active' : ''}`}
                onClick={() => setMinGap(g)}>
                ≥{g}%
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Options Pulse — Schaeffer SOIR signals from the nightly cron.
          Sits above the gap list so the user can cross-reference: a
          ticker that gapped overnight AND shows up bullish here is a
          higher-confidence trade than the gap alone. */}
      <OptionsPulseSummary topN={5} />

      <OvernightPanel compact={false} minGapPct={minGap} />

      <section style={{ marginTop: 24 }}>
        <SupplyDemandSummary compact={true} />
      </section>

      <section className="overnight-explain">
        <h2 className="day-section__h">Why stocks move overnight</h2>
        <details>
          <summary><strong>The market isn't really closed.</strong></summary>
          <p>
            US equities trade in three sessions: <strong>premarket (4:00–9:30am ET)</strong>,
            <strong> regular (9:30am–4:00pm)</strong>, and <strong>after-hours (4:00–8:00pm)</strong>.
            On top of that, S&P/Nasdaq futures (ES/NQ) trade continuously
            from Sunday 6pm ET through Friday 5pm ET. So when you wake up to
            see your stock up 3%, that move happened in real trading.
          </p>
        </details>
        <details>
          <summary><strong>Common overnight catalysts (in rough order of impact)</strong></summary>
          <ol>
            <li><strong>Earnings releases</strong> — most companies report after 4pm or before 9:30am to give the market time to digest.</li>
            <li><strong>Macro data drops</strong> — CPI/PPI/jobs at 8:30am ET, FOMC at 2pm. Pre-market is often violent post-CPI.</li>
            <li><strong>Fed speakers</strong> — overnight Asia speeches by Fed members regularly move futures.</li>
            <li><strong>International markets</strong> — Nikkei + Shanghai + DAX trade while you sleep. China tariff news = US gap.</li>
            <li><strong>Analyst upgrades/downgrades</strong> — almost all published 6:00–8:00am ET.</li>
            <li><strong>Other companies' news</strong> — NVDA reports → AMD/AVGO/TSM all gap. Sector moves together.</li>
            <li><strong>Index rebalances</strong> — added/dropped from S&P, Russell, MSCI. Posted after 4pm.</li>
            <li><strong>M&A and 8-K filings</strong> — SEC filings hit after market close routinely.</li>
            <li><strong>Crypto</strong> — BTC trades 24/7. MSTR, COIN, MARA gap on overnight BTC moves.</li>
            <li><strong>Geopolitical</strong> — wars, sanctions, tariff news.</li>
          </ol>
        </details>
        <details>
          <summary><strong>Lesson learned: SNDK at $1002 → $1071</strong></summary>
          <p>
            Closed at $1002 yesterday, you placed a buy after-hours, filled at
            $1071 at next open. Why this happens:
          </p>
          <ol>
            <li>After 4:00pm, your broker queues the order. It does NOT execute against the 4pm close — it waits for the next session.</li>
            <li>Overnight, news/earnings/sector moves price in extended hours.</li>
            <li>At 9:30:00am, the <strong>opening auction</strong> matches all overnight buy/sell orders at a single clearing price. Bullish overnight = higher clearing price.</li>
            <li>You filled at the auction print, not yesterday's close.</li>
          </ol>
          <p><strong>Prevention: use limit orders.</strong> "Buy SNDK at $1010 limit, day" — only fills if price hits $1010 or below, otherwise no trade. Or wait for the open and watch how it prints first.</p>
        </details>
        <details>
          <summary><strong>How catalysts get attached</strong></summary>
          <p>
            For each gapping symbol, we pull all news headlines from Massive
            published since yesterday's 4pm close. Each headline is scored
            against a curated keyword dictionary (earnings, analyst, M&A,
            FDA, geopolitical, etc.) — the highest-scored headline becomes
            the attached catalyst.
          </p>
          <p>
            Limitations: keyword matching gets ~70-80% accuracy. Misses can
            happen when news titles are vague (e.g. "Stock Moves on Pop") or
            when the real catalyst is a peer's earnings (sector flow). For
            those, click into the symbol and read the full news feed.
          </p>
        </details>
      </section>
    </div>
  );
}
