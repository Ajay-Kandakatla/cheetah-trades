/* LukCard — one 🥇 Luk's setup card (2026-11-01, luk spec §3.10 / §3.13).
 *
 * <PatternChart> draws the served 5-minute bars with the served hourly-frame curves the way GajjalaBoard.tsx draws a
 * 🚩 tile (lukChartTile maps the served bars5 / curves5 / vol_avg5 onto the house CmTile keys — structural only), then
 * the served state label, the frame, the trigger / stop / R texts, the listed reason, every criterion ✓ / ✗ / · with
 * its served value and need, and the served chips (wrapping — 📱 430 px: the card is min-width: 0 and every chip
 * wraps). A `listed` card keeps its trigger / stop / R: listed is a rule saying "not A+", never a hidden plan. Every
 * word and number is SERVED; this file types none.
 *
 * 2026-11-01 — the house chips (🚀 growth, 🩳 short interest, 🧨 explosive, 🎯 enterable) are mounted by LukBoard
 * (one page-level bounce-room POST feeds the 🧨 / 🎯 reads) and handed in as `houseChips`; this card only PLACES
 * them: above the chart (PatternChart is told to skip its own copies via outerChips, so a card never shows a chip
 * twice) or in the head when there are no bars.
 *
 * 2026-11-11 — a served `not_reread: true` (strictly true) with a served sentence prints that sentence as an amber
 * .luk-not-reread pill in the pills row and replaces the bottom read-at line (the pill carries the same time). A blank
 * sentence → no pill, the plain line prints; this file types no word. */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { OuterChip } from '../lib/cardLadder';
import { LUK_CHIP_KEYS, lukChartTile, lukMark, lukText, type LukTile } from '../lib/luk';

/** The chips LukBoard mounts itself — PatternChart skips exactly these. */
export const LUK_OUTER_CHIPS: ReadonlyArray<OuterChip> = ['growth', 'short', 'explosive', 'enterable'];

export function LukCard({ tile: t, focus = false, houseChips = null }: {
  tile: LukTile; focus?: boolean;
  /** 🚀 / 🩳 / 🧨 / 🎯 mounted by LukBoard (prop-fed reads); null → none. */
  houseChips?: ReactNode;
}) {
  const chart = lukChartTile(t);
  const house = houseChips ? (
    <span className="luk-house-chips" data-testid={`luk-house-chips-${t.symbol}`}>{houseChips}</span>
  ) : null;
  const chips = LUK_CHIP_KEYS.map((k) => [k, lukText(t.chips?.[k])] as const).filter(([, v]) => v);
  const notReread = t.not_reread === true ? lukText(t.not_reread_text) : null;
  return (
    <div className={`luk-card luk-state-${(t.state || '').replace(/[^a-z_]/gi, '')}${focus ? ' luk-focus' : ''}`}
         data-testid={`luk-tile-${t.symbol}`} data-state={t.state}
         data-not-reread={notReread ? 'true' : undefined}>
      {chart.bars.length ? (
        <>
          {house}
          <PatternChart tile={chart} outerChips={LUK_OUTER_CHIPS} />
        </>
      ) : (
        <div className="luk-row-head">
          {lukText(t.href) ? <Link to={t.href!} data-testid={`luk-tile-link-${t.symbol}`}>{t.symbol}</Link>
                           : <strong>{t.symbol}</strong>}
          {house}
        </div>
      )}
      <div className="luk-extras">
        <div className="luk-pills">
          <span className={`luk-state luk-state-${(t.state || '').replace(/[^a-z_]/gi, '')}`}
                data-testid={`luk-state-${t.symbol}`}>{t.state_label}</span>
          {lukText(t.frame_text) ? <span className="luk-frame" data-testid={`luk-frame-${t.symbol}`}>{t.frame_text}</span> : null}
          {notReread ? <span className="luk-not-reread" data-testid={`luk-not-reread-${t.symbol}`}>{notReread}</span> : null}
        </div>
        {lukText(t.trigger_text) ? <p className="luk-plan" data-testid={`luk-trigger-${t.symbol}`}>{t.trigger_text}</p> : null}
        {lukText(t.stop_text) ? <p className="luk-plan" data-testid={`luk-stop-${t.symbol}`}>{t.stop_text}</p> : null}
        {lukText(t.listed_why) ? <p className="luk-line luk-why" data-testid={`luk-why-${t.symbol}`}>{t.listed_why}</p> : null}
        {t.criteria?.length ? (
          <ul className="luk-criteria" data-testid={`luk-criteria-${t.symbol}`}>
            {t.criteria.map((c) => (
              <li key={c.key} className={c.ok === true ? 'luk-ok' : c.ok === false ? 'luk-miss' : 'luk-unjudged'}
                  data-testid={`luk-crit-${t.symbol}-${c.key}`}>
                {lukMark(c.ok)} {c.label}
                {lukText(c.value) ? <> — {c.value}</> : null}
                {lukText(c.need) ? <span className="luk-muted"> ({c.need})</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {chips.length ? (
          <div className="luk-chip-row" data-testid={`luk-chips-${t.symbol}`}>
            {chips.map(([k, v]) => (
              <span key={k} className="cm-badge cm-badge-muted luk-chip" data-testid={`luk-chip-${t.symbol}-${k}`}>{v}</span>
            ))}
          </div>
        ) : null}
        {!notReread && lukText(t.read_at_text) ? <p className="luk-line luk-muted" data-testid={`luk-read-at-${t.symbol}`}>{t.read_at_text}</p> : null}
      </div>
    </div>
  );
}

export default LukCard;
