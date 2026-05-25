import { useState, type MouseEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useBreakouts, type BreakoutAlert } from '../hooks/useBreakouts';

/* ==========================================================================
   BreakoutAlertBanner — fixed-position toast stack at top-right of viewport.
   Renders on every page (mounted in App.tsx), polls /sepa/breakouts every 5min
   (SSE handles realtime updates; poll is the safety net).

   Layout — 2026-05-20 rewrite:
     The previous version put the ticker in the BODY and the kind in the
     HEADER, which meant: (a) if any of the body's optional fields were
     missing (last_close, day_change_pct), the body collapsed to a thin
     strip with just the empty <p> and the "details" button — making
     each card look like a header-only chip with no ticker and nothing
     to click; (b) the user got 18 stacked cards saying just "VOLUME
     BREAKOUT" / "STAGE 2 → 3 · TOPPING" with no context.

     Fix:
       - TICKER is now in the header next to the kind, ALWAYS visible.
       - Whole card is a navigation link to /sepa/{ticker}. Click anywhere
         (except the X close button) → open the ticker.
       - Body retains the price/day/reason/expand details for users who
         want context before navigating — but the card is usable even if
         the body collapses to nothing.

   Animation: pulse glow + shimmer + slide-in (unchanged).
   ========================================================================== */

function fmtKindLabel(kind: string): string {
  if (kind === 'volume_breakout')      return '🚀 Volume breakout';
  if (kind === 'rising_momentum')      return '📈 Rising momentum';
  if (kind === 'stage_breakdown_2_3')  return '⚠️ Stage 2 → 3 · Topping';
  if (kind === 'stage_breakdown_2_4')  return '🔻 Stage 2 → 4 · Cliff';
  if (kind === 'stage_breakdown_3_4')  return '🔻 Stage 3 → 4 · Decline';
  return kind;
}

function AlertCard({ alert, isNew, onDismiss }: {
  alert: BreakoutAlert; isNew: boolean; onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const location = useLocation();
  const ctx = alert.context ?? {};
  const day = ctx.day_change_pct;
  // Defensive fallback — backend should always populate ticker, but if
  // a malformed row sneaks through we still want to render something
  // recognizable instead of an empty card.
  const ticker = (alert.ticker || '').trim() || '?';

  // Stop propagation when the user clicks inside the body's interactive
  // elements (close X, expand details button). Without this, clicks on
  // the body bubble up to the wrapping <Link> and navigate away when
  // the user just meant to expand the row.
  const stop = (e: MouseEvent) => e.stopPropagation();

  return (
    <article
      className={`bk-alert bk-alert--${alert.kind} ${isNew ? 'is-new' : ''} ${expanded ? 'is-expanded' : ''}`}
      role="alert"
    >
      <Link
        to={`/sepa/${encodeURIComponent(ticker)}`}
        state={{ from: location.pathname + location.search, label: 'alert' }}
        className="bk-alert__link"
        aria-label={`Open ${ticker} · ${fmtKindLabel(alert.kind)}`}
      >
        <header className="bk-alert__head">
          <span className="bk-alert__ticker mono">{ticker}</span>
          <span className="bk-alert__kind">{fmtKindLabel(alert.kind)}</span>
          {/* Close X — stop propagation so it doesn't trigger the Link. */}
          <button
            type="button"
            className="bk-alert__close"
            onClick={(e) => { stop(e); onDismiss(); }}
            onMouseDown={stop}   /* prevent the Link's :active state on press */
            aria-label="Dismiss alert"
          >
            ✕
          </button>
        </header>

        <div className="bk-alert__body">
          {(ctx.last_close != null || day != null) && (
            <div className="bk-alert__price-row">
              {ctx.last_close != null && (
                <span className="bk-alert__price mono">${ctx.last_close.toFixed(2)}</span>
              )}
              {day != null && (
                <span className={`bk-alert__day mono ${day >= 0 ? 'is-up' : 'is-down'}`}>
                  {day >= 0 ? '▲' : '▼'} {Math.abs(day).toFixed(2)}%
                </span>
              )}
            </div>
          )}

          {alert.reason && (
            <p className="bk-alert__reason">{alert.reason}</p>
          )}

          <button
            type="button"
            className="bk-alert__expand"
            onClick={(e) => { stop(e); setExpanded(!expanded); }}
            onMouseDown={stop}
          >
            {expanded ? '▾ less' : '▸ details'}
          </button>

          {expanded && (
            <dl className="bk-alert__details" onClick={stop}>
              {alert.kind === 'volume_breakout' && (
                <>
                  {ctx.score != null && <><dt>Score</dt><dd className="mono">{ctx.score.toFixed(0)} {ctx.rating}</dd></>}
                  {ctx.rs_rank != null && <><dt>RS rank</dt><dd className="mono">{ctx.rs_rank}</dd></>}
                  {ctx.stage_label && <><dt>Stage</dt><dd className="mono">{ctx.stage_label}</dd></>}
                  {ctx.entry_setup?.type && <><dt>Setup</dt><dd className="mono">{ctx.entry_setup.type}</dd></>}
                  {ctx.pioneer_themes && ctx.pioneer_themes.length > 0 && (
                    <><dt>Themes</dt><dd className="mono">{ctx.pioneer_themes.join(' · ')}</dd></>
                  )}
                </>
              )}
              {alert.kind === 'rising_momentum' && (
                <>
                  <dt>Days on list</dt><dd className="mono">{ctx.days_on_list}</dd>
                  <dt>RS climb</dt>
                  <dd className="mono">
                    {ctx.first_rs} → {ctx.last_rs}
                    <span className="bk-up"> (+{ctx.rs_delta})</span>
                  </dd>
                  <dt>Score climb</dt>
                  <dd className="mono">
                    {ctx.first_score?.toFixed(0)} → {ctx.last_score?.toFixed(0)}
                    <span className="bk-up"> (+{ctx.score_delta?.toFixed(0)})</span>
                  </dd>
                  {ctx.last_rating && <><dt>Tier</dt><dd className="mono">{ctx.last_rating}</dd></>}
                  {ctx.pioneer_themes && ctx.pioneer_themes.length > 0 && (
                    <><dt>Themes</dt><dd className="mono">{ctx.pioneer_themes.join(' · ')}</dd></>
                  )}
                </>
              )}
              {alert.kind.startsWith('stage_breakdown') && (
                <>
                  {ctx.prior_stage != null && ctx.current_stage != null && (
                    <>
                      <dt>Stage shift</dt>
                      <dd className="mono">
                        S{ctx.prior_stage} → S{ctx.current_stage}
                      </dd>
                    </>
                  )}
                  {ctx.score != null && <><dt>SEPA score</dt><dd className="mono">{ctx.score.toFixed(0)} {ctx.rating}</dd></>}
                  {ctx.rs_rank != null && <><dt>RS rank</dt><dd className="mono">{ctx.rs_rank}</dd></>}
                  {ctx.dist_200_pct != null && (
                    <>
                      <dt>vs 200-day</dt>
                      <dd className={`mono ${ctx.dist_200_pct < 0 ? 'is-down' : 'is-up'}`}>
                        {ctx.dist_200_pct >= 0 ? '+' : ''}{ctx.dist_200_pct.toFixed(1)}%
                      </dd>
                    </>
                  )}
                </>
              )}
            </dl>
          )}
        </div>
      </Link>
    </article>
  );
}

export function BreakoutAlertBanner() {
  const { alerts, newAlerts, dismiss, dismissAll } = useBreakouts();

  if (alerts.length === 0) return null;

  const newIds = new Set(newAlerts.map((a) => a._id));

  return (
    <aside className="bk-stack" aria-label="Active breakout alerts">
      <header className="bk-stack__head">
        <span className="bk-stack__count">
          {alerts.length} active alert{alerts.length === 1 ? '' : 's'}
        </span>
        {alerts.length > 1 && (
          <button
            type="button"
            className="bk-stack__dismiss-all"
            onClick={dismissAll}
            title="Dismiss all alerts"
          >
            Dismiss all
          </button>
        )}
      </header>
      <div className="bk-stack__list">
        {alerts.map((a) => (
          <AlertCard
            key={a._id}
            alert={a}
            isNew={newIds.has(a._id)}
            onDismiss={() => dismiss(a._id)}
          />
        ))}
      </div>
    </aside>
  );
}
