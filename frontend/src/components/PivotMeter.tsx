/* ==========================================================================
   PivotMeter — the visual "am I hopping on at the right time?" gauge.

   Encodes Minervini's buy rule (Trade Like a Stock Market Wizard, pp.197-205):
   you buy when price crosses ABOVE the pivot (the last tight contraction's high)
   on EXPANDING volume — after the right-side pullback tightens on dried volume.

   Two stacked readouts, both from data already on the card:
     • price track — stop · pivot · buy-zone, with a ▲ marker for where price is
       NOW and the % to the pivot. Instantly shows "about to trigger" vs "20% away".
     • volume gauge — today's volume vs the 1.5× breakout threshold, coloured
       🤫 dried (constructive) → ⚡ expanding (the trigger).
   The state badge flips 🟢 GO only when BOTH fire (price ≥ pivot AND volume
   expanding); otherwise Coiling / Wait / At-pivot / Extended.
   ========================================================================== */
import { BREAKOUT_VOL_MULT, type PivotTiming } from '../lib/pivotTiming';

const TONE_COLOR: Record<PivotTiming['tone'], string> = {
  go: '#10b981', warn: '#d97706', wait: '#eab308', bad: '#ef4444', none: '#64748b',
};
const STATE_DOT: Record<PivotTiming['state'], string> = {
  GO: '🟢', AT_PIVOT: '🟠', COILING: '🟡', WAIT: '🟡', NOT_STAGE2: '🟡', EXTENDED: '🔴', NONE: '⚪️',
};

function fmt(n: number | null, d = 2): string {
  return n == null ? '—' : n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function PivotMeter({ t }: { t: PivotTiming }) {
  if (!t.hasSetup || t.pivot == null || t.current == null) return null;
  const color = TONE_COLOR[t.tone];

  // Track domain: a little below the stop to a little above the buy-zone top,
  // always including the current price so the marker is on-scale.
  const zoneHi = t.zoneHi ?? t.pivot * 1.05;
  const lo = Math.min(t.stop ?? t.pivot * 0.92, t.current, t.pivot * 0.95);
  const hi = Math.max(zoneHi, t.current, t.pivot * 1.02);
  const span = hi - lo || 1;
  const pos = (x: number) => Math.max(0, Math.min(100, ((x - lo) / span) * 100));
  const pivotPos = pos(t.pivot);
  const zoneHiPos = pos(zoneHi);
  const curPos = pos(t.current);

  // Volume gauge: full bar = 2× avg; threshold tick at 1.5×.
  const vr = t.volRatio ?? 0;
  const volFill = Math.max(0, Math.min(100, (vr / 2) * 100));
  const thrPos = (BREAKOUT_VOL_MULT / 2) * 100;
  const volColor = t.breakingOut ? '#10b981' : t.drying ? '#38bdf8' : '#64748b';

  const distTxt =
    t.distToPivotPct == null ? '' :
    t.distToPivotPct < -0.05 ? `${Math.abs(t.distToPivotPct).toFixed(1)}% below` :
    t.distToPivotPct > 0.05 ? `${t.distToPivotPct.toFixed(1)}% past` : 'at pivot';

  return (
    <div className="pivot-meter">
      <div className="pivot-meter__head">
        <span className="pivot-meter__badge" style={{ color, borderColor: color }}>
          {STATE_DOT[t.state]} {t.label}
        </span>
        {t.pivotTight && (
          <span
            className="pivot-meter__tight"
            title={`Final contraction ${t.finalContractionPct?.toFixed(1)}% — a textbook-tight Minervini pivot (≤5%; book pp.198/202: FSII 5% handle, VIVO 3%).`}
          >
            ⚡ tight pivot {t.finalContractionPct != null ? `${t.finalContractionPct.toFixed(0)}%` : ''}
          </span>
        )}
      </div>

      {/* price track: stop ── pivot │ buy-zone ── with a ▲ for current price */}
      <div className="pivot-meter__track" title="Where price is now relative to the pivot buy point and the buy zone.">
        <div
          className="pivot-meter__zone"
          style={{ left: `${pivotPos}%`, width: `${Math.max(0, zoneHiPos - pivotPos)}%` }}
        />
        <div className="pivot-meter__pivot" style={{ left: `${pivotPos}%` }} />
        <div className="pivot-meter__cur" style={{ left: `${curPos}%`, borderTopColor: color }} />
      </div>
      <div className="pivot-meter__scale mono">
        <span>stop {fmt(t.stop)}</span>
        <span className="pivot-meter__pivot-lbl">pivot {fmt(t.pivot)}</span>
        <span>now {fmt(t.current)} · {distTxt}</span>
      </div>

      {/* volume gauge: today vs the 1.5× breakout line */}
      <div className="pivot-meter__vol" title="Today's volume vs the 50-day average. A volume-confirmed breakout needs ≥ 1.5× (book p.203).">
        <div className="pivot-meter__vol-bar">
          <div className="pivot-meter__vol-fill" style={{ width: `${volFill}%`, background: volColor }} />
          <div className="pivot-meter__vol-thr" style={{ left: `${thrPos}%` }} />
        </div>
        <span className="pivot-meter__vol-lbl mono" style={{ color: volColor }}>
          {vr ? `${vr.toFixed(1)}×` : '—'} {t.breakingOut ? '⚡ expanding' : t.drying ? '🤫 dried' : 'vol'}
        </span>
      </div>

      {/* Plain-English one-liner — decodes the gauge into "what's happening +
          what you're waiting on" so the user doesn't have to read the meter.
          Ajay 2026-06-03: "what am I waiting on, dumbed down". */}
      {plainCaption(t) && (
        <p className="pivot-meter__caption" style={{ borderColor: color }}>
          {plainCaption(t)}
        </p>
      )}
    </div>
  );
}

/** One dumbed-down sentence per pivot state: what's happening, and — crucially —
 *  what has to happen next (the thing the user is "waiting on"). Mirrors the
 *  state machine in pivotTiming.ts. */
function plainCaption(t: PivotTiming): string | null {
  const pivot = `$${fmt(t.pivot)}`;
  const stop = t.stop != null ? `$${fmt(t.stop)}` : 'your stop';
  const vr = t.volRatio ? `${t.volRatio.toFixed(1)}×` : 'light';
  const dist = t.distToPivotPct == null ? '' : `${Math.abs(t.distToPivotPct).toFixed(1)}%`;
  switch (t.state) {
    case 'GO':
      return `✅ It pushed above the buy line (${pivot}) on a volume surge — the breakout is confirmed. Plan your exit if it closes below ${stop}.`;
    case 'AT_PIVOT':
      return `Price is sitting right on the buy line (${pivot}). Waiting on: volume to jump to 1.5×+ the average (it's ${vr} now) to confirm the breakout.`;
    case 'COILING':
      return `It's coiling tight just under the buy line (${pivot}) on quiet volume — a constructive sign. Waiting on: a push above ${pivot} on heavy volume (it's ${dist} away).`;
    case 'WAIT':
      return `Still ${dist} below the buy line (${pivot}). Waiting on: price to climb up to ${pivot} and volume to surge to 1.5×+.`;
    case 'NOT_STAGE2':
      return `It's at the price, but the stock isn't in a confirmed uptrend (Stage 2) yet — not a buy by the rules. Waiting on: a proper Stage 2 advance first.`;
    case 'EXTENDED':
      return `It's already ${dist} past the buy line — too far above to chase safely. Waiting on: a fresh base to form before the next entry.`;
    default:
      return null;
  }
}
