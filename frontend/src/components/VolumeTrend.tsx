/* ==========================================================================
   VolumeTrend — the multi-day "is volume building or fading?" mini-histogram.

   Complements the PivotMeter's SINGLE-day relative-volume gauge ("1.5×
   expanding") with the TREND: the last ~20 trading days of volume, each bar
   green on an up-close day and red on a down-close day, with the 50-day
   average drawn as a dashed reference line. Rising green bars above the line =
   institutions accumulating; red bars dwarfing green = distribution.

   This is the accumulation footprint Minervini reads off the tape — "more up
   days on above-average volume than down days" (Trade Like a Stock Market
   Wizard, p.71-72). Volume is Ajay's primary indicator (2026-05-28), so this
   sits on every card, not just names with a setup.

   Data comes from row.volume:
     • vol_spark           — signed-volume series (the bars). Absent on old
                             cached scans → we fall back to the verdict + the
                             accumulation/distribution-day read so it's never
                             blank.
     • accumulation_strength, accumulation_days_25, distribution_days_25,
       up_down_vol_ratio, cmf_signal — drive the plain-English verdict.
   Display-only; never part of any score.
   ========================================================================== */

type VolLike = {
  vol_spark?: number[] | null;
  avg_vol_50?: number | null;
  accumulation_strength?: 'strong' | 'accumulating' | 'neutral' | 'distributing';
  accumulation_days_25?: number | null;
  distribution_days_25?: number | null;
  up_down_vol_ratio?: number | null;
  cmf_signal?: 'inflow' | 'neutral' | 'outflow';
};

const UP = '#10b981';
const DOWN = '#ef4444';
const FLAT = '#94a3b8';

export function VolumeTrend({ vol }: { vol?: VolLike | null }) {
  if (!vol) return null;

  const spark = Array.isArray(vol.vol_spark) ? vol.vol_spark : [];
  const accumDays = vol.accumulation_days_25 ?? null;
  const distDays = vol.distribution_days_25 ?? null;
  const strength = vol.accumulation_strength ?? null;
  const cmf = vol.cmf_signal ?? null;
  const ratio = vol.up_down_vol_ratio ?? null;

  // Nothing to show at all (e.g. illiquid name with no volume read) — bail so
  // we don't render an empty box.
  if (!spark.length && strength == null && accumDays == null) return null;

  // Verdict direction — prefer the backend's accumulation_strength label;
  // otherwise infer from up- vs down-volume day counts.
  const dir: 'up' | 'down' | 'flat' =
    strength === 'strong' || strength === 'accumulating' ? 'up' :
    strength === 'distributing' ? 'down' :
    accumDays != null && distDays != null
      ? (accumDays > distDays + 1 ? 'up' : distDays > accumDays + 1 ? 'down' : 'flat')
      : 'flat';
  const color = dir === 'up' ? UP : dir === 'down' ? DOWN : FLAT;
  const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '→';
  const label =
    strength === 'strong' ? 'strong accumulation' :
    strength === 'accumulating' ? 'accumulating' :
    strength === 'distributing' ? 'distributing' :
    dir === 'up' ? 'building' : dir === 'down' ? 'fading' : 'neutral';

  // Plain-English caption — readable by a non-technical user (the "expand to
  // other people" direction): no field names, no jargon.
  const parts: string[] = [];
  if (accumDays != null && distDays != null)
    parts.push(`${accumDays} up-volume days vs ${distDays} down (last 25)`);
  if (ratio != null) parts.push(`up/down volume ${ratio.toFixed(2)}×`);
  if (cmf === 'inflow') parts.push('money flowing in');
  else if (cmf === 'outflow') parts.push('money flowing out');
  const caption = parts.join(' · ');

  // Sparkline geometry — bar height ∝ |volume| / window max; the 50-day
  // average becomes a dashed line so above-average bars read at a glance.
  const maxAbs = spark.length ? Math.max(1, ...spark.map((v) => Math.abs(v))) : 1;
  const avgPct =
    vol.avg_vol_50 && vol.avg_vol_50 > 0
      ? Math.min(100, (vol.avg_vol_50 / maxAbs) * 100)
      : null;

  const title =
    'Volume trend — the last ~20 trading days of volume. Green bars are up-close ' +
    'days, red bars are down-close days; the dashed line is the 50-day average ' +
    'volume. Rising green bars above the line mean institutions are accumulating; ' +
    'heavy red means distribution. Minervini reads this footprint off the tape ' +
    '(Trade Like a Stock Market Wizard, p.71-72).';

  return (
    <div className="vol-trend" title={title}>
      <div className="vol-trend__head">
        <span className="vol-trend__title">📊 Volume trend</span>
        <span className="vol-trend__verdict" style={{ color }}>{arrow} {label}</span>
      </div>
      {spark.length > 0 && (
        <div className="vol-trend__spark" aria-hidden="true">
          {avgPct != null && (
            <div className="vol-trend__avg" style={{ bottom: `${avgPct}%` }} title="50-day average volume" />
          )}
          {spark.map((v, i) => {
            const h = Math.max(6, (Math.abs(v) / maxAbs) * 100);
            const isUp = v >= 0;
            return (
              <div
                key={i}
                className="vol-trend__bar"
                style={{ height: `${h}%`, background: isUp ? UP : DOWN, opacity: isUp ? 0.9 : 0.68 }}
              />
            );
          })}
        </div>
      )}
      {caption && <div className="vol-trend__caption mono">{caption}</div>}
    </div>
  );
}
