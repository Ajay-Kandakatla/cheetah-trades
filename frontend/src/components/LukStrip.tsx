/* LukStrip — 🥇 Luk's folded strip (2026-11-01, luk spec §3.10 / §3.13).
 *
 * The served `strip` block: 🧭 the QQQ / IWM state words (market_state — a state word, never a gate), then the
 * served push / record / external / cost / latency lines. FOLDED by default (`<details>` closed unless the server
 * serves `folded: false`). Every word on it is SERVED; this file types none. */
import { lukText, type LukStrip as LukStripBlock } from '../lib/luk';

export function LukStrip({ strip }: { strip?: LukStripBlock | null }) {
  if (!strip) return null;
  const ms = strip.market_state ?? null;
  const lines: Array<[string, string | null]> = [
    ['push', lukText(strip.push_text)], ['record', lukText(strip.record_text)],
    ['external', lukText(strip.external_text)], ['cost', lukText(strip.cost_text)],
    ['latency', lukText(strip.latency_text)],
  ];
  const shown = lines.filter(([, t]) => t);
  if (!ms && !shown.length) return null;
  return (
    <details className="luk-strip" data-testid="luk-strip" open={strip.folded === false}>
      <summary className="luk-strip-head" data-testid="luk-strip-head">{lukText(ms?.title) ?? 'ⓘ'}</summary>
      {ms && ms.rows?.length ? (
        <ul className="luk-market" data-testid="luk-market">
          {ms.rows.map((r) => (
            <li key={r.symbol} data-testid={`luk-market-${r.symbol}`}>
              <span className="luk-market-text">{r.text}</span>
              {lukText(r.dist_text) ? <span className="luk-muted"> {r.dist_text}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {lukText(ms?.note) ? <p className="luk-line luk-muted" data-testid="luk-market-note">{ms!.note}</p> : null}
      {shown.map(([k, t]) => (
        <p key={k} className="luk-line" data-testid={`luk-strip-${k}`}>{t}</p>
      ))}
    </details>
  );
}

export default LukStrip;
