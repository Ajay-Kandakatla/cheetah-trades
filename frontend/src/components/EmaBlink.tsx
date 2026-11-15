/* 🔀 9/21 EMA cross blinker — the card dot and the card line (2026-11-15, SPEC blinker §3.9, WP-E).
 *
 * Ajay 2026-11-15: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9 crossing over
 * 21 EMA please.." · "Yes and I need some sort of urgency or fast blink for the one are closer together than approaching
 * with sort also aligned with it".
 *
 * Both render the SERVED block (`ema_blink`) and nothing else: the dot's class is the served tier (its pulse speed lives
 * in styles/emaBlinkCard.css, fastest tier first), its label is the served sentence; the line prints the served sentence
 * verbatim. A block that does not blink renders nothing. The dot sits INLINE in the card head (never absolute, never
 * over the chart's axis). Information only, UNMEASURED — the FE types no word. */
import type { CmEmaBlink } from '../lib/chartMaps';
import { emaBlinkLine, emaBlinkTier } from '../lib/emaBlink';
import '../styles/emaBlinkCard.css';

const trimmed = (x: unknown): string => (typeof x === 'string' ? x.trim() : '');
const cls = (x: unknown): string | null => (typeof x === 'string' && /^[a-z_]+$/.test(x) ? x : null);

export function EmaBlinkDot({ block, testid }: { block?: CmEmaBlink | null; testid?: string }) {
  const tier = emaBlinkTier(block);
  if (!tier) return null;
  const text = trimmed(block?.text);
  const title = trimmed(block?.title);
  const label = text || title || undefined;
  return (
    <span className={`ema-blink-dot ema-blink-${tier}`} role="img" aria-label={label}
          title={title || text || undefined} data-testid={testid} />
  );
}

export function EmaBlinkLine({ block, sym, info }: { block?: CmEmaBlink | null; sym: string; info?: string | null }) {
  const line = emaBlinkLine(block);
  if (!line) return null;
  const state = cls(block?.state);
  const hover = trimmed(info) || line.title || undefined;
  return (
    <div className={`cm-note ema-blink-line${state ? ` ema-blink-${state}` : ''}`}
         data-testid={`ema-blink-${sym}`} title={hover}>
      {line.text}
    </div>
  );
}
