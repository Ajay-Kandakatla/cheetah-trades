import { useState, useMemo } from 'react';

/* ==========================================================================
   /glossary — every short form / acronym used across the app, grouped.
   Searchable. The single source of truth so nobody (including future-me)
   has to wonder what "PP" or "OBS" means.
   ========================================================================== */

type Term = { short: string; full: string; explain: string; group: string };

const TERMS: Term[] = [
  // ── SEPA framework ──
  { short: 'SEPA', full: 'Specific Entry Point Analysis', group: 'SEPA framework',
    explain: 'Mark Minervini\'s framework for finding stocks with the highest probability of a sharp upward move. Five gates: Trend Template, Relative Strength ≥ 70, Stage 2, tight base, risk-managed entry.' },
  { short: 'PP', full: 'Power Play', group: 'SEPA framework',
    explain: 'Minervini setup type. An explosive multi-week run-up of ≥100% in any 40-day window followed by tight consolidation. The "second-chance" entry — buy the consolidation, not the original move.' },
  { short: 'VCP', full: 'Volatility Contraction Pattern', group: 'SEPA framework',
    explain: 'Minervini\'s archetypal base: 2-6 successive pullbacks, each ~half the previous, with a tight (≤10%) right side. Indicates institutional accumulation at progressively higher lows.' },
  { short: 'RS', full: 'Relative Strength rank', group: 'SEPA framework',
    explain: 'IBD-style 1-99 percentile rank of a stock\'s 12-month total return vs every other US stock. RS ≥ 70 means it\'s outperforming 70% of the market — the Minervini gate.' },
  { short: 'CANSLIM', full: 'Capital · Annual earnings · Numbers · New highs · Supply/demand · Leader · Institutional sponsorship', group: 'SEPA framework',
    explain: 'William O\'Neil\'s 7-factor stock-picking framework. Used as a fundamentals overlay to score SEPA candidates beyond just price action.' },
  { short: 'ADR', full: 'Average Daily Range', group: 'SEPA framework',
    explain: 'Average % move per day over 20 sessions — a volatility measure. ≥4% is "leader-grade" volatility ideal for swing entries. Different from American Depositary Receipt (which is also called ADR but unrelated).' },
  { short: 'DM', full: 'Dual Momentum', group: 'SEPA framework',
    explain: 'Gary Antonacci\'s two-gate filter: 12-month return positive AND beats SPY. A momentum confirmation overlay.' },
  { short: 'S2 / Stage 2', full: 'Stage 2 — Advancing', group: 'SEPA framework',
    explain: 'Stan Weinstein\'s four-stage cycle. Stage 1 = Basing, Stage 2 = Advancing, Stage 3 = Topping, Stage 4 = Declining. Only Stage 2 stocks are SEPA buy candidates.' },
  { short: 'MA', full: 'Moving Average', group: 'SEPA framework',
    explain: 'Trend filter. SEPA uses 50-day, 150-day, and 200-day moving averages. Price must be above all three, and they must be in the right order, for the Trend Template to pass.' },

  // ── Calibration / Track page ──
  { short: 'OBS', full: 'Observations', group: 'Calibration / Track',
    explain: 'A signal observation = one row per (signal source, ticker, prediction time). Each starts pending and gets graded after its horizon expires. The Observations panel shows recent ones with hit/miss/partial status.' },
  { short: 'Hit', full: 'Hit', group: 'Calibration / Track',
    explain: 'Direction was right (stock went up when we said up) AND magnitude landed within 50%-150% of predicted. Full-credit win.' },
  { short: 'Miss', full: 'Miss', group: 'Calibration / Track',
    explain: 'Direction was wrong. Zero credit, contributes -1.0 to the accuracy score.' },
  { short: 'Partial', full: 'Partial', group: 'Calibration / Track',
    explain: 'Direction was right but magnitude was off (e.g. predicted +5%, got +0.8% or +12%). Half-point.' },
  { short: 'Hit %', full: 'Strict hit rate', group: 'Calibration / Track',
    explain: 'Hits ÷ N. Most conservative read. Above 65% = real edge; below 45% = noise.' },
  { short: 'w/Hit %', full: 'Weighted hit rate (tolerant)', group: 'Calibration / Track',
    explain: '(Hits + 0.5 × Partials) ÷ N. Counts partials as half a win. Less harsh than strict.' },
  { short: 'N', full: 'Sample size', group: 'Calibration / Track',
    explain: 'Number of graded observations from this source in the window. Below 5 = not enough data.' },
  { short: 'EV', full: 'Expected Value', group: 'Calibration / Track',
    explain: '(hit rate × avg win) + ((1 - hit rate) × avg loss). Even at sub-50% hit rate, EV > 0 means you make money on average.' },
  { short: 'pp', full: 'percentage points', group: 'Calibration / Track',
    explain: 'Difference between two percentages, NOT a percentage of a percentage. "BUY tier outperforms WATCH by 5pp" means 51% vs 46%, not 51% vs 48.6%.' },
  { short: 'cum', full: 'cumulative', group: 'Calibration / Track',
    explain: '"cum %" on the market chart = cumulative percentage change from the start of the window, not day-over-day.' },

  // ── Catalysts ──
  { short: 'FDA', full: 'Food and Drug Administration', group: 'Catalysts',
    explain: 'US drug approval body. Biotech catalysts are typically tied to FDA action dates (PDUFA dates, Adcom meetings, label expansions).' },
  { short: 'PDUFA', full: 'Prescription Drug User Fee Act date', group: 'Catalysts',
    explain: 'The FDA-set deadline for action on a drug application. Typically the biggest single-day biotech catalyst.' },
  { short: 'IV', full: 'Implied Volatility', group: 'Catalysts',
    explain: 'Options-market-implied expected volatility. IV crush = the expected drop in IV after a known event (earnings, FDA decision) resolves.' },
  { short: 'IPO', full: 'Initial Public Offering', group: 'Catalysts',
    explain: 'A company\'s first public stock offering. IPO age <2 years is a CANSLIM bonus signal in SEPA.' },

  // ── Markets & instruments ──
  { short: 'ETF', full: 'Exchange-Traded Fund', group: 'Markets & instruments',
    explain: 'A basket of underlying stocks traded as a single ticker. CANSLIM EPS / fundamentals don\'t apply; relevant metrics are AUM, expense ratio, holdings.' },
  { short: 'AUM', full: 'Assets Under Management', group: 'Markets & instruments',
    explain: 'Total dollar value of assets the fund manages. Used to gauge ETF liquidity / institutional interest.' },
  { short: 'mcap', full: 'Market Capitalization', group: 'Markets & instruments',
    explain: 'Share price × shares outstanding. The total dollar value of a company\'s equity.' },
  { short: 'OHLC', full: 'Open · High · Low · Close', group: 'Markets & instruments',
    explain: 'The four price points captured per bar in standard market data.' },
  { short: 'SPY', full: 'S&P 500 ETF', group: 'Markets & instruments',
    explain: 'The benchmark ETF tracking the S&P 500. Used as the market-context proxy throughout the app.' },
  { short: 'VIX', full: 'CBOE Volatility Index', group: 'Markets & instruments',
    explain: 'Implied volatility of S&P 500 options over the next 30 days. Above 20 = elevated fear; above 30 = panic.' },

  // ── Themes / pioneer tags ──
  { short: 'HAMR', full: 'Heat-Assisted Magnetic Recording', group: 'Pioneer themes',
    explain: 'New hard-drive technology enabling much higher storage density. The "AI Storage / HAMR" pioneer theme covers SNDK, MU, WDC, TER — the cluster you traded.' },
  { short: 'GLP-1', full: 'Glucagon-like peptide-1 (Ozempic / Wegovy class)', group: 'Pioneer themes',
    explain: 'The diabetes/obesity drug class that drove Eli Lilly and Novo Nordisk to historic highs. Pioneer theme covers the GLP-1 ecosystem.' },
  { short: 'SMR', full: 'Small Modular Reactor', group: 'Pioneer themes',
    explain: 'New nuclear reactor design — smaller, factory-built, deployable in distributed locations. Pioneer theme for the nuclear renaissance.' },

  // ── App / data plumbing ──
  { short: 'TTL', full: 'Time To Live', group: 'App / data plumbing',
    explain: 'How long a cached value stays valid before being refreshed. The /quote endpoint has a 60s TTL.' },
  { short: 'API', full: 'Application Programming Interface', group: 'App / data plumbing',
    explain: 'The backend HTTP endpoints the frontend calls. e.g. GET /sepa/scan returns the latest SEPA scan.' },
  { short: 'SSE', full: 'Server-Sent Events', group: 'App / data plumbing',
    explain: 'A protocol for the server to push updates to the browser over a single HTTP connection. Used for live SEPA scan progress.' },
  { short: 'cron', full: 'cron — scheduled job runner', group: 'App / data plumbing',
    explain: 'The Mac book pro M5 (this machine) runs scheduled jobs (post-close fast-scan, hourly breakout-watch, etc.) via supercronic inside a container.' },
  { short: 'Mongo', full: 'MongoDB', group: 'App / data plumbing',
    explain: 'The document database where scan history, observations, watchlist, and calibration data are persisted.' },

  // ── Time windows ──
  { short: '1m / 3m / 6m / 12m', full: '1-month / 3-month / 6-month / 12-month return', group: 'Time windows',
    explain: 'Trailing total return over the named period. 12m is the standard relative-strength window; the others are sub-window momentum checks for Dual Momentum.' },
];

const GROUPS = Array.from(new Set(TERMS.map((t) => t.group)));

export default function GlossaryPage() {
  const [q, setQ] = useState('');
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return TERMS;
    return TERMS.filter((t) =>
      t.short.toLowerCase().includes(needle) ||
      t.full.toLowerCase().includes(needle) ||
      t.explain.toLowerCase().includes(needle) ||
      t.group.toLowerCase().includes(needle));
  }, [q]);

  const byGroup = useMemo(() => {
    const out: Record<string, Term[]> = {};
    for (const t of filtered) (out[t.group] ??= []).push(t);
    return out;
  }, [filtered]);

  return (
    <div className="gloss-page">
      <div className="gloss-page__title">
        <div>
          <div className="eyebrow">Reference</div>
          <h1 className="display gloss-page__h1">Glossary</h1>
          <p className="lede">
            Every short form used across the app, with a one-paragraph
            definition. The full forms also appear inline as tooltips
            wherever they show up — but if you ever forget, this is the
            canonical reference.
          </p>
        </div>
      </div>

      <input
        type="search"
        className="gloss-search"
        placeholder="Search a term (e.g. 'PP', 'observations', 'volatility')…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      {GROUPS.map((g) => (
        byGroup[g] && byGroup[g].length > 0 && (
          <section key={g} className="gloss-group">
            <h2 className="gloss-group__title">{g}</h2>
            <dl className="gloss-list">
              {byGroup[g].map((t) => (
                <div key={t.short + t.full} className="gloss-row">
                  <dt className="gloss-short mono">{t.short}</dt>
                  <dd className="gloss-def">
                    <div className="gloss-full">{t.full}</div>
                    <p className="gloss-explain">{t.explain}</p>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        )
      ))}

      {filtered.length === 0 && (
        <div className="gloss-empty">
          No matches for "<strong>{q}</strong>".
        </div>
      )}
    </div>
  );
}
