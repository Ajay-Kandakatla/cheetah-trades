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
    </div>
  );
}
