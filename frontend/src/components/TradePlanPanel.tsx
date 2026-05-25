import type { TradePlan } from '../hooks/useSepa';

/* ==========================================================================
   TradePlanPanel — full trade-plan panel for the SEPA candidate detail page.

   Shows ALL the levels a swing trader needs to make a decision without
   opening another chart:
     • Entry zone (aggressive / standard / pullback)
     • Stop strategies side-by-side (base low / ATR×2 / hard 7%)
     • Targets at 1R / 2R / 3R + nearest resistance
     • Key chart levels (MAs, 52w high/low, recent swings)

   Methodology citations on hover so the user knows where each number
   came from (Minervini for the 7% stop, Wilder for ATR, etc.).
   ========================================================================== */

type Props = { plan: TradePlan };

export function TradePlanPanel({ plan }: Props) {
  const e = plan.entries;
  const s = plan.stop;
  const t = plan.targets;
  const lv = plan.levels;
  return (
    <section className="trade-plan-panel">
      <header>
        <h3>Trade plan</h3>
        <p className="trade-plan-panel__lede">
          Analyst-grade entry / stop / target levels. Stop methodology follows
          Minervini's 7% hard cap + O'Neil's 2×ATR volatility-adjustment;
          targets are R-multiples calibrated against nearest resistance.{' '}
          <span className="mono" style={{ opacity: 0.7 }}>setup: {plan.setup_source}</span>
        </p>
      </header>

      <div className="trade-plan-panel__grid">
        <div className="trade-plan-panel__cell trade-plan-panel__cell--entry"
             title={`Aggressive entry — buy at the pivot. Buy zone $${plan.buy_zone.lo}-$${plan.buy_zone.hi} (Minervini's 2.5% above-pivot rule).`}>
          <div className="eyebrow">Buy</div>
          <div className="trade-plan-panel__cell-num mono">${e.aggressive.toFixed(2)}</div>
          <div className="trade-plan-panel__cell-sub">
            zone ${plan.buy_zone.lo} – ${plan.buy_zone.hi}
          </div>
        </div>
        <div className="trade-plan-panel__cell"
             title="Standard entry — pivot + 1% buffer. Wait for confirmed breakout above pivot before entering.">
          <div className="eyebrow">Confirmed entry</div>
          <div className="trade-plan-panel__cell-num mono">${e.standard.toFixed(2)}</div>
          <div className="trade-plan-panel__cell-sub">+1% above pivot</div>
        </div>
        {e.pullback != null && (
          <div className="trade-plan-panel__cell"
               title="Pullback entry — buy on a pullback to the rising 50d MA. Lower-risk re-entry for stage-2 names.">
            <div className="eyebrow">Pullback entry</div>
            <div className="trade-plan-panel__cell-num mono">${e.pullback.toFixed(2)}</div>
            <div className="trade-plan-panel__cell-sub">50d MA support</div>
          </div>
        )}
        <div className="trade-plan-panel__cell trade-plan-panel__cell--stop"
             title={s.reason}>
          <div className="eyebrow">Stop ({s.recommended_label.replace('_', ' ')})</div>
          <div className="trade-plan-panel__cell-num mono">${s.recommended.toFixed(2)}</div>
          <div className="trade-plan-panel__cell-sub">
            {s.risk_pct != null && `−${s.risk_pct.toFixed(1)}% risk`}
          </div>
        </div>
        {t.r1 != null && (
          <div className="trade-plan-panel__cell trade-plan-panel__cell--target"
               title="First profit scale = entry + 1R (covers risk + 1× reward).">
            <div className="eyebrow">Target +1R</div>
            <div className="trade-plan-panel__cell-num mono">${t.r1.toFixed(2)}</div>
            <div className="trade-plan-panel__cell-sub">scale ¼ position</div>
          </div>
        )}
        {t.r2 != null && (
          <div className="trade-plan-panel__cell trade-plan-panel__cell--target"
               title="2R is Minervini's published profit zone — scale half here, trail stop on the rest.">
            <div className="eyebrow">Target +2R</div>
            <div className="trade-plan-panel__cell-num mono">${t.r2.toFixed(2)}</div>
            <div className="trade-plan-panel__cell-sub">scale ½ · trail stop</div>
          </div>
        )}
        {t.r3 != null && (
          <div className="trade-plan-panel__cell trade-plan-panel__cell--target"
               title="3R = stretch target. Only kept if name keeps making higher highs on rising volume.">
            <div className="eyebrow">Target +3R</div>
            <div className="trade-plan-panel__cell-num mono">${t.r3.toFixed(2)}</div>
            <div className="trade-plan-panel__cell-sub">stretch · trail tight</div>
          </div>
        )}
      </div>

      {/* All-stop comparison so the user can see WHY this stop was picked */}
      <details className="trade-plan-panel__details">
        <summary><strong>Stop methodology</strong> — three strategies, recommended is highest (least painful) below entry</summary>
        <ul className="mono" style={{ marginTop: '0.5rem', lineHeight: 1.7 }}>
          {Object.entries(s.candidates).map(([k, v]) => (
            <li key={k}>
              <strong>${v.toFixed(2)}</strong>
              {' — '}
              {{
                base_low: 'VCP base low (tightest technical stop)',
                atr_2x:   'Entry − 2×ATR(14) (volatility-adjusted)',
                hard_pct: 'Entry − 7% (Minervini hard cap, never hold past)',
              }[k] || k}
              {k === s.recommended_label && <strong style={{ color: 'var(--gold)' }}> ← recommended</strong>}
            </li>
          ))}
        </ul>
        <p className="mono" style={{ marginTop: '0.5rem', fontSize: '0.78rem', opacity: 0.75 }}>
          Decision rule: pick the highest of the three (least pain), capped at 7%
          below entry. If your VCP base low is tighter than 7%, use it — it's
          a real technical level. If it's wider than 7%, the hard cap wins —
          you don't want a single trade taking more than 7% on a swing.
        </p>
      </details>

      {/* Key chart levels — supports + resistances the user should know */}
      <details className="trade-plan-panel__details">
        <summary><strong>Key chart levels</strong> — moving averages, 52w range, swing pivots</summary>
        <div className="trade-plan-panel__levels mono" style={{ marginTop: '0.5rem' }}>
          {lv.ma20 != null  && <div>MA20:  <strong>${lv.ma20.toFixed(2)}</strong> {lv.ma20  > e.aggressive ? '· short-term resistance' : '· short-term support'}</div>}
          {lv.ma50 != null  && <div>MA50:  <strong>${lv.ma50.toFixed(2)}</strong> {lv.ma50  > e.aggressive ? '· near-term resistance' : '· near-term support (key for stage-2)'}</div>}
          {lv.ma200 != null && <div>MA200: <strong>${lv.ma200.toFixed(2)}</strong> {lv.ma200 > e.aggressive ? '· major resistance' : '· major support — break = stage change'}</div>}
          {lv.week52_high != null && <div>52w high: <strong>${lv.week52_high.toFixed(2)}</strong> · primary breakout target</div>}
          {lv.week52_low  != null && <div>52w low:  <strong>${lv.week52_low.toFixed(2)}</strong> · invalidation level</div>}
          {lv.swing_highs.length > 0 && (
            <div>
              Recent swing highs: <strong>{lv.swing_highs.slice(0, 3).map((p) => `$${p.toFixed(2)}`).join(' · ')}</strong>
              {' '}<span style={{ opacity: 0.7 }}>(horizontal resistance)</span>
            </div>
          )}
          {lv.swing_lows.length > 0 && (
            <div>
              Recent swing lows: <strong>{lv.swing_lows.slice(0, 3).map((p) => `$${p.toFixed(2)}`).join(' · ')}</strong>
              {' '}<span style={{ opacity: 0.7 }}>(horizontal support)</span>
            </div>
          )}
          {plan.atr != null && (
            <div>ATR(14): <strong>${plan.atr.toFixed(2)}</strong> · typical daily range</div>
          )}
          {t.nearest_resistance != null && t.reward_to_risk != null && (
            <div style={{ marginTop: '0.4rem' }}>
              Nearest resistance: <strong>${t.nearest_resistance.toFixed(2)}</strong>
              {' · '}reward-to-risk to it: <strong>{t.reward_to_risk.toFixed(2)}R</strong>
              {t.reward_to_risk < 2 && <span style={{ color: 'var(--cm-amber)' }}> (low — wait for tighter setup)</span>}
            </div>
          )}
        </div>
      </details>
    </section>
  );
}
