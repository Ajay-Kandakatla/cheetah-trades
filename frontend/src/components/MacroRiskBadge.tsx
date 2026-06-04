/* MacroRiskBadge — per-name macro / geopolitical RISK pill.

   Ajay 2026-06-04: "a separate Macro score; WAR usually affects the overall
   trade; look at major news." Shows how risky the CURRENT macro environment is
   to being long this name right now (war, sanctions, oil, rates, debt…),
   layered on top of the SEPA score. Higher = more risk. Green = calm, red =
   severe. An analytical gauge, not advice.

   Data: the `macro_risk` object the backend attaches to leaderboard rows and
   card enrichment — { score, level, drivers, sector }. */
export type MacroRisk = {
  score: number | null;
  level: 'low' | 'elevated' | 'high' | 'severe' | 'unknown';
  drivers?: string[];
  sector?: string;
};

const META: Record<string, { cls: string; emoji: string; label: string }> = {
  low:      { cls: 'mrisk--low',      emoji: '🟢', label: 'Low' },
  elevated: { cls: 'mrisk--elevated', emoji: '🟡', label: 'Elevated' },
  high:     { cls: 'mrisk--high',     emoji: '🟠', label: 'High' },
  severe:   { cls: 'mrisk--severe',   emoji: '🔴', label: 'Severe' },
};

export function MacroRiskBadge({ risk, compact = false }: { risk?: MacroRisk | null; compact?: boolean }) {
  if (!risk || risk.score == null || risk.level === 'unknown') return null;
  const m = META[risk.level] ?? META.elevated;
  const drivers = (risk.drivers ?? []).filter(Boolean);
  const tip =
    `Macro risk ${Math.round(risk.score)}/100 — ${m.label}.` +
    (drivers.length ? `\nDrivers: ${drivers.join('; ')}.` : '') +
    (risk.sector && risk.sector !== 'broad' ? `\nSector: ${risk.sector}.` : '') +
    `\nHow risky the current macro/geopolitical backdrop is for being long this name. Not advice.`;
  return (
    <span className={`mrisk ${m.cls}`} title={tip}>
      🌍 {compact ? '' : 'Macro '}{m.label}
      <span className="mrisk__score">{Math.round(risk.score)}</span>
    </span>
  );
}
