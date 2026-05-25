import type { TradePlan } from '../hooks/useSepa';
import { readAlertSettings } from '../hooks/useAlertSettings';

/* ==========================================================================
   TradePlanInline — compact one-line summary of a trade plan.

   Used on SEPA candidate cards (list view) and Options Pulse cards where
   we only have room for "buy at X, stop at Y, risk Z%" before the user
   clicks through. The full plan with all levels lives on the detail page.
   ========================================================================== */

type Props = {
  plan: TradePlan | null | undefined;
  /** Hide the source label (e.g. "VCP" / "current_price") — used when
   *  the parent already shows the setup type elsewhere. */
  hideSource?: boolean;
  /** Yesterday's official close — drives the -12% intraday structural-
   *  break level. Passed from the SEPA candidate card. */
  lastClose?: number | null;
};

export function TradePlanInline({ plan, hideSource = false, lastClose }: Props) {
  if (!plan) return null;
  const entry = plan.entry_recommended;
  const stop  = plan.stop.recommended;
  const risk  = plan.stop.risk_pct;
  const t1    = plan.targets.r1;
  const stopLabel = stopLabelText(plan.stop.recommended_label);
  // The intraday structural-break trigger. Default is Minervini's -12%
  // rule (any intraday move of -12%+ from prior close = structural
  // failure, exit immediately). User can tighten or loosen this in
  // Notifications → Alert thresholds (e.g. -10% for risk-off users,
  // -15% for high-volatility traders).
  const emergencyPct = readAlertSettings().intraday_emergency_pct;
  const emergency = lastClose != null
    ? lastClose * (1 - emergencyPct / 100)
    : null;

  return (
    <div className="trade-plan-inline mono"
         title={`${stopLabel}: ${plan.stop.reason}`}>
      <span className="tpi__cell tpi__cell--entry" title="Recommended buy point">
        <span className="tpi__lab">Buy</span>
        <span className="tpi__num">${entry.toFixed(2)}</span>
      </span>
      <span className="tpi__sep">·</span>
      <span
        className="tpi__cell tpi__cell--stop"
        title={
          `${plan.stop.reason}\n\n` +
          `⚠️ Evaluate at CLOSE (3:00 PM CT / 4:00 PM ET) — not on intraday wicks.\n` +
          `Per Minervini, decisions happen in the last 30 min of the session ` +
          `(2:30–3:00 PM CT). A pre-close touch of the stop level is noise; a ` +
          `close BELOW the stop is the actual signal. Exception: an intraday ` +
          `move of −12% or more from yesterday's close is a structural break — ` +
          `exit immediately regardless of clock.`
        }
      >
        <span className="tpi__lab">Stop</span>
        <span className="tpi__num">${stop.toFixed(2)}</span>
        {risk != null && (
          <span className="tpi__risk">−{risk.toFixed(1)}%</span>
        )}
        <span
          className="tpi__stop-when"
          aria-label="Stop is evaluated at close, not intraday"
          style={{
            marginLeft: '0.3rem',
            padding: '0 4px',
            fontSize: '0.6rem',
            border: '1px solid var(--warn, #d97706)',
            color: 'var(--warn, #d97706)',
            borderRadius: 3,
            letterSpacing: '0.03em',
            textTransform: 'uppercase',
            whiteSpace: 'nowrap',
            cursor: 'help',
          }}
        >
          @ close ⓘ
        </span>
      </span>
      {t1 != null && (
        <>
          <span className="tpi__sep">·</span>
          <span className="tpi__cell tpi__cell--target" title="First profit target = entry + 1R (cover risk + 1× reward)">
            <span className="tpi__lab">+1R</span>
            <span className="tpi__num">${t1.toFixed(2)}</span>
          </span>
        </>
      )}
      {emergency != null && (
        <>
          <span className="tpi__sep">·</span>
          <span
            className="tpi__cell tpi__cell--emergency"
            title={
              `Intraday structural-break level — exit IMMEDIATELY if price ` +
              `touches or breaks below $${emergency.toFixed(2)}, regardless of ` +
              `clock or the regular @-close stop.\n\n` +
              `Math: yesterday's close $${lastClose!.toFixed(2)} × ${(1 - emergencyPct/100).toFixed(2)} = ` +
              `$${emergency.toFixed(2)} (-${emergencyPct}% from prior close).\n\n` +
              `Per Minervini: "I'll take a 7-8% loss. What I won't take is a ` +
              `15% loss." A -${emergencyPct}% intraday move is no longer noise — ` +
              `it's the trend breaking down.\n\n` +
              `Change this threshold in Notifications → Alert thresholds.`
            }
            style={{ color: '#dc2626' }}
          >
            <span className="tpi__lab" style={{ color: '#dc2626' }}>⚠ Exit</span>
            <span className="tpi__num" style={{ color: '#dc2626' }}>${emergency.toFixed(2)}</span>
            <span
              style={{
                marginLeft: '0.25rem',
                padding: '0 4px',
                fontSize: '0.6rem',
                border: '1px solid #dc2626',
                color: '#dc2626',
                borderRadius: 3,
                letterSpacing: '0.03em',
                textTransform: 'uppercase',
                whiteSpace: 'nowrap',
                cursor: 'help',
              }}
            >−{emergencyPct}% intraday ⓘ</span>
          </span>
        </>
      )}
      {!hideSource && (
        <span className="tpi__source mono"
              title={sourceTooltip(plan.setup_source)}>
          {sourceShortLabel(plan.setup_source)}
        </span>
      )}
    </div>
  );
}

function stopLabelText(label: string): string {
  return {
    base_low: 'Stop · base low (VCP)',
    atr_2x:   'Stop · ATR×2 (volatility)',
    hard_pct: 'Stop · 7% hard cap (Minervini)',
  }[label] || `Stop · ${label}`;
}

function sourceShortLabel(s: string): string {
  return {
    VCP:           'VCP',
    POWER_PLAY:    'PP',
    current_price: 'no base',
  }[s] || s;
}

function sourceTooltip(s: string): string {
  return {
    VCP:           'Volatility Contraction Pattern — Minervini\'s preferred base',
    POWER_PLAY:    'Power Play — high-tight flag, post-IPO breakout',
    current_price: 'No clean base detected — entry from current close, stop = max(ATR×2, 7% hard cap)',
  }[s] || s;
}
