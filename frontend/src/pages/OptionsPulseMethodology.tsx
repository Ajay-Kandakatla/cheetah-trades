import { Link } from 'react-router-dom';

/* ==========================================================================
   /options/methodology — full write-up of the SOIR / Schaeffer framework.

   This page exists so the user can understand exactly:
     1. What every number on the Options Pulse page means
     2. The formulas used to compute each one
     3. How to actually trade off the signals (the part most blogs skip)
     4. Where the framework comes from (citations)

   Length-over-brevity is the right tradeoff here — this is reference
   material, not the dashboard. The dashboard links to it from the
   InfoButton on /options.
   ========================================================================== */

export default function OptionsPulseMethodologyPage() {
  return (
    <div className="op-method">
      <header className="op-method__head">
        <div className="eyebrow">Methodology</div>
        <h1 className="display">Options Pulse — How it works</h1>
        <p className="lede">
          Every number on the Options Pulse page, the formulas behind
          them, and how to actually use the signals. This is reference
          material — bookmark it.
        </p>
        <p className="mono" style={{ opacity: 0.65 }}>
          Back to the live page: <Link to="/options">/options</Link>
        </p>
      </header>

      <section className="op-method__section">
        <h2>1. What this is</h2>
        <p>
          <strong>Options Pulse</strong> is an implementation of <strong>Bernie
          Schaeffer's Expectational Analysis</strong> — a published, contrarian
          framework for using the options crowd's positioning as a sentiment
          extreme detector. Schaeffer's Investment Research has run this
          methodology since 1981; the canonical reference is{' '}
          <em>Bernie Schaeffer, "The Option Advisor: Wealth-Building Techniques
          Using Equity & Index Options" (Wiley, 1997)</em>.
        </p>
        <p>
          The core insight: when retail and short-vol funds get heavily
          positioned in one direction, those positions become fuel for the
          OPPOSITE move. A stock with too many puts open (relative to history)
          attracts buy-to-cover pressure on any rally; a stock with too many
          calls open is vulnerable to disappointment selling. Academic
          backing: <em>Pan & Poteshman (2006), "The Information in Option
          Volume for Future Stock Prices," Review of Financial Studies</em>{' '}
          showed that put/call ratios have predictive power for individual
          stock returns.
        </p>
      </section>

      <section className="op-method__section">
        <h2>2. The three pillars</h2>
        <p>
          Schaeffer's published rule: signals only fire when{' '}
          <strong>all three pillars line up</strong>. Sentiment alone gets you
          whipsawed; trend + sentiment + fundamental confluence is the edge.
          This is structurally identical to how SEPA stacks technical +
          fundamental + market-regime gates.
        </p>
        <table className="op-method__table">
          <thead>
            <tr>
              <th>Pillar</th>
              <th>Bullish requirement</th>
              <th>Bearish requirement</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Technical</strong></td>
              <td>Stage-2 uptrend: price &gt; 50d &gt; 200d, 200d slope ≥ 0</td>
              <td>Stage-4 downtrend: price &lt; 50d &lt; 200d, 200d slope ≤ 0</td>
              <td>Reused from SEPA scanner</td>
            </tr>
            <tr>
              <td><strong>Fundamental</strong></td>
              <td>SEPA composite score ≥ 50</td>
              <td>(any)</td>
              <td>Reused from SEPA scoring</td>
            </tr>
            <tr>
              <td><strong>Sentiment (SOIR)</strong></td>
              <td>SOIR percentile ≥ 80th (52w)</td>
              <td>SOIR percentile ≤ 20th (52w)</td>
              <td>Schaeffer 1997</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="op-method__section">
        <h2>3. The formulas</h2>

        <h3>3.1 SOIR (Schaeffer's Open Interest Ratio)</h3>
        <pre className="op-method__formula">
{`SOIR = (sum of PUT open interest) / (sum of CALL open interest)
       across all strikes in the front 3 expirations`}
        </pre>
        <p>
          Open interest is the number of outstanding options contracts that
          haven't been closed. We aggregate across the front 3 expiry months
          because that's where liquidity concentrates — LEAPS pollute the
          ratio with stale positioning. Per-symbol, we pull every strike in
          each of those 3 expiries and sum the OI columns separately for
          puts and calls.
        </p>

        <h3>3.2 Percentile rank (vs trailing 52 weeks)</h3>
        <pre className="op-method__formula">
{`pct(today) = ( count of historical days where SOIR < today's SOIR )
              / ( total historical days collected )
              × 100

requires ≥ 30 days of history → time_series percentile
otherwise                     → cross_section percentile (rank vs today's universe)`}
        </pre>
        <p>
          The raw SOIR number is meaningless alone — every ticker has its
          own baseline (a high-vol meme stock and a quiet utility have
          completely different put/call habits). The signal is the percentile
          rank vs the same ticker's own history. We auto-fall back to a
          cross-section percentile (rank vs today's universe) for the first
          30 days while time-series history accumulates.
        </p>

        <h3>3.3 Expected move (1 standard deviation by expiry)</h3>
        <pre className="op-method__formula">
{`Expected Move ≈ (ATM call mid + ATM put mid) / spot
              ≈ 1 standard deviation of the price distribution at expiry

(derived from Black-Scholes — the ATM straddle premium is approximately
 0.8 × spot × IV × √DTE, which collapses to roughly the 1-SD move)`}
        </pre>
        <p>
          We compute this from the front-most expiration's ATM straddle bid/ask
          mids. It's the market's consensus on how big a move is "priced in"
          before the next monthly expiration — useful for sanity-checking
          whether your SEPA breakout target is realistic vs what the options
          market is pricing.
        </p>

        <h3>3.4 ATM IV</h3>
        <pre className="op-method__formula">
{`ATM IV = average( implied_volatility_of_ATM_call, implied_volatility_of_ATM_put )

reported as annualized percentage`}
        </pre>
        <p>
          The implied vol on the at-the-money options. High IV (vs the
          ticker's own range) makes long-premium strategies expensive and
          favors selling; low IV makes long calls/puts cheaper. Useful for
          sizing decisions on a SEPA candidate — "is this breakout cheap to
          play with calls?"
        </p>

        <h3>3.5 Volume SOIR (intraday sentiment)</h3>
        <pre className="op-method__formula">
{`SOIR_volume = (sum of today's PUT volume) / (sum of today's CALL volume)
              across same front-3-month strikes`}
        </pre>
        <p>
          Same shape as SOIR but using today's contract volume instead of
          standing OI. SOIR_volume is more reactive (intraday) while SOIR is
          more durable (positioning). When they diverge — high SOIR but low
          volume_SOIR — the crowd's standing put position is being sold INTO
          the rally, which strengthens the bullish read.
        </p>
      </section>

      <section className="op-method__section">
        <h2>4. How to use this — playbook</h2>

        <h3>4.1 As a confirmation layer on SEPA candidates</h3>
        <p>
          Open the SEPA list and any candidate that <em>also</em> shows up as{' '}
          <strong>BULLISH</strong> on Options Pulse is a higher-confidence long.
          Two independent published frameworks pointing the same direction
          beats either alone. Position-size up; stop wider.
        </p>

        <h3>4.2 As a contrarian filter</h3>
        <p>
          A SEPA candidate showing <strong>BEARISH</strong> on Options Pulse
          (rare but happens) means the crowd is loaded with calls AGAINST a
          name your trend filter likes. Either:
        </p>
        <ul>
          <li>The trend has shifted and SEPA hasn't caught up yet → wait one more close</li>
          <li>Or the crowd is right, the trend is exhausted → take a smaller position</li>
        </ul>
        <p>This kind of disagreement is itself information — don't ignore it.</p>

        <h3>4.3 Sizing with expected move</h3>
        <p>
          If SEPA gives you a pivot at $120 and a stop at $114 (5% risk), and
          Options Pulse shows expected-move ±$8 (6.7%) for the front month —
          the options market is pricing a move slightly bigger than your
          stop range. That's normal. If expected move is &lt;3% on a name
          where your stop is 5% wide, the options market doesn't think your
          breakout will reach target — review the setup quality.
        </p>

        <h3>4.4 Historical validation (the date scrubber)</h3>
        <p>
          Use the date filter at the top of <Link to="/options">/options</Link>
          {' '}to load any past day's SOIR scan and review what signals it
          flagged. The standard validation flow:
        </p>
        <ol>
          <li>Pick a date 30+ days back (long enough for outcomes to show)</li>
          <li>Note the BULLISH names on that date</li>
          <li>Pull each name's chart — did the trend continue / extend?</li>
          <li>If most worked → you can trust live signals more aggressively</li>
          <li>If most failed → the regime may not be supporting contrarian setups (check VIX / market regime that day)</li>
        </ol>
        <p>
          This is the same validation pattern SEPA's history scrubber enables.
          Both pages exist so you build evidence about the methodology
          BEFORE risking capital on it.
        </p>

        <h3>4.5 What this is NOT</h3>
        <ul>
          <li><strong>Not</strong> an options-trading recommendation — this tells you what the underlying is likely to do, not which option to buy.</li>
          <li><strong>Not</strong> a day-trading signal — SOIR moves on a daily/weekly cadence, not intraday.</li>
          <li><strong>Not</strong> a substitute for stop-losses — even with all 3 pillars green, a 5-7% stop below pivot is mandatory.</li>
          <li><strong>Not</strong> reliable for tickers with thin options chains (sub-$5 stocks, micro-caps). The scanner will skip these.</li>
        </ul>
      </section>

      <section className="op-method__section">
        <h2>5. Universe + refresh schedule</h2>
        <ul>
          <li><strong>Universe:</strong> Russell 1000 (~1000 names) + your watchlist + SEPA candidates + 20 mega-cap context tickers.</li>
          <li><strong>Concurrency:</strong> 10 parallel HTTP workers via Python ThreadPoolExecutor — ~3-5 min for the full universe.</li>
          <li><strong>Cron:</strong> Mon-Fri 5:30pm ET (after fast-scan) + Sunday 9pm ET.</li>
          <li><strong>Source:</strong> yfinance options chains — free, decent coverage for Russell 1000. Sub-$5 names + foreign ADRs sometimes return empty chains; those are silently skipped.</li>
          <li><strong>Storage:</strong> Mongo collections{' '}<code>soir_history</code>{' '}(time series, 52-week retention) and{' '}<code>soir_latest</code>{' '}(current snapshot per ticker).</li>
        </ul>
      </section>

      <section className="op-method__section">
        <h2>6. The classifier (Python pseudocode)</h2>
        <pre className="op-method__formula">
{`def classify(soir_pct, trend, sepa_score):
    if soir_pct is None:
        return "NEUTRAL"   # not enough history yet

    # BULLISH: trend up + crowd loaded with puts + non-bad fundamentals
    if trend == "up" and soir_pct >= 80:
        if sepa_score is None or sepa_score >= 50:
            return "BULLISH"
        return "WATCH"     # sentiment + trend OK, fundamentals weak

    # BEARISH: trend down + crowd loaded with calls
    if trend == "down" and soir_pct <= 20:
        return "BEARISH"

    # Partial alignment — flagged neutral, watch for the other pillar
    return "NEUTRAL"`}
        </pre>
      </section>

      <section className="op-method__section">
        <h2>7. References</h2>
        <ul>
          <li>Schaeffer, Bernie. <em>The Option Advisor: Wealth-Building Techniques Using Equity & Index Options</em>. Wiley, 1997. (Canonical write-up)</li>
          <li>Pan, Jun &amp; Poteshman, Allen M. "The Information in Option Volume for Future Stock Prices." <em>Review of Financial Studies</em> 19.3 (2006): 871-908.</li>
          <li>Schaeffer's Investment Research: <a href="https://www.schaeffersresearch.com" target="_blank" rel="noreferrer">schaeffersresearch.com</a> — source of the published SOIR methodology.</li>
          <li>McMillan, Larry G. <em>McMillan on Options</em>, 2nd ed. Wiley, 2004. (Sister methodology — daily PCR with 21-day SMA bands)</li>
          <li>Natenberg, Sheldon. <em>Option Volatility & Pricing</em>. McGraw-Hill, 1994. (Implied vol / Greeks bible)</li>
        </ul>
      </section>
    </div>
  );
}
