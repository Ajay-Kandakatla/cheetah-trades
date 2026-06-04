/* MacroRiskBadge / MacroMarketStrip — the macro / geopolitical RISK overlay.

   Ajay 2026-06-04: "a separate Macro score; WAR usually affects the overall
   trade; look at major news" + "some shifts only affect Semis, some oil." So
   there are two surfaces:

     • MacroMarketStrip — the ONE market-wide read, shown once at the top of a
       list (the whole tape is Severe/Elevated/… right now).
     • MacroRiskBadge — a per-NAME chip. On a list it's passed `marketScore`
       and renders ONLY when this name diverges from the market base (a
       sector/ticker headwind or tailwind) — so a chip on a row MEANS something
       instead of stamping the same number on every line. Off a list (no
       marketScore) it renders the full standalone badge (card enrichment).

   Higher = more risk. Green calm → red severe. An analytical gauge, not advice. */
export type MacroRisk = {
  score: number | null;
  level: 'low' | 'elevated' | 'high' | 'severe' | 'unknown';
  drivers?: string[];
  sector?: string;
};

export type MacroFactor = { label: string; direction?: string; severity?: number };
export type MacroMarket = {
  score: number | null;
  level: MacroRisk['level'];
  summary?: string | null;
  factors?: MacroFactor[];
  provider?: string;
};

const META: Record<string, { cls: string; emoji: string; label: string }> = {
  low:      { cls: 'mrisk--low',      emoji: '🟢', label: 'Low' },
  elevated: { cls: 'mrisk--elevated', emoji: '🟡', label: 'Elevated' },
  high:     { cls: 'mrisk--high',     emoji: '🟠', label: 'High' },
  severe:   { cls: 'mrisk--severe',   emoji: '🔴', label: 'Severe' },
};

// A name needs to sit at least this far off the market base for its own chip to
// be worth showing — below it, the market strip already says everything.
const DIVERGE_MIN = 3;

export function MacroRiskBadge({
  risk,
  compact = false,
  marketScore = null,
}: {
  risk?: MacroRisk | null;
  compact?: boolean;
  marketScore?: number | null;
}) {
  if (!risk || risk.score == null || risk.level === 'unknown') return null;
  const m = META[risk.level] ?? META.elevated;
  const drivers = (risk.drivers ?? []).filter(Boolean);
  const sector = risk.sector && risk.sector !== 'broad' ? risk.sector : null;

  // List mode: only surface when this name carries DIFFERENT risk than the tape.
  const delta = marketScore != null ? Math.round(risk.score - marketScore) : null;
  if (delta != null && Math.abs(delta) < DIVERGE_MIN) return null;

  const tip =
    `Macro risk ${Math.round(risk.score)}/100 — ${m.label}` +
    (delta != null ? ` (${delta >= 0 ? '+' : ''}${delta} vs market)` : '') + '.' +
    (drivers.length ? `\nDrivers:\n  ${drivers.join('\n  ')}` : '') +
    (sector ? `\nSector: ${sector}.` : '') +
    `\n↑ raises risk · ↓ tailwind (lowers it). Reads the current macro + major news` +
    `\n(war, oil, rates, chip policy, key exec/company catalysts) routed to this name's` +
    `\nsector/ticker. An analytical gauge, not advice.`;

  // Divergence chip — sector + signed delta makes the sector story explicit
  // ("semis carry +8 over the tape"); fall back to the absolute score off-list.
  return (
    <span className={`mrisk ${m.cls}`} title={tip}>
      🌍 {delta != null
        ? <>{sector ? `${sector} ` : ''}{delta >= 0 ? '▲' : '▼'}{Math.abs(delta)}</>
        : <>{compact ? '' : 'Macro '}{m.label}<span className="mrisk__score">{Math.round(risk.score)}</span></>}
    </span>
  );
}

export function MacroMarketStrip({ market }: { market?: MacroMarket | null }) {
  if (!market || market.score == null || market.level === 'unknown') return null;
  const m = META[market.level] ?? META.elevated;
  const factors = (market.factors ?? []).map((f) => f?.label).filter(Boolean).slice(0, 3) as string[];
  const tip =
    `Market-wide macro risk ${Math.round(market.score)}/100 — ${m.label}.` +
    (factors.length ? `\nDrivers:\n  ${factors.join('\n  ')}` : '') +
    `\nThe overall backdrop. A row shows its own chip only when that name carries` +
    `\ndifferent (sector- or ticker-specific) risk. An analytical gauge, not advice.`;
  return (
    <div className={`mrisk-strip ${m.cls}`} title={tip}>
      <span className="mrisk-strip__lead">🌍 Market macro</span>
      <span className="mrisk-strip__lvl">{m.emoji} {m.label}</span>
      <span className="mrisk-strip__score">{Math.round(market.score)}</span>
      {(market.summary || factors.length) ? (
        <span className="mrisk-strip__sum">{market.summary || factors.join(' · ')}</span>
      ) : null}
    </div>
  );
}
