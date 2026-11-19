/* 🚫 the 👀 Watch's broker mark — the board block parser and the row word (2026-11-19, spec watchfid §3.3, WP-C).
 *
 * Ajay 2026-11-19 asked for a button on the Watch that puts a name on his 🚫 list (the broker word, served) and keeps it
 * off the Watch. The server serves the board's `broker` block (backend chart_maps/gajjala_watch/broker.py, owner GET
 * only) and every row's `broker_text`. This module parses the block and picks the row word; it types NO word — every
 * string is served (tab.BROKER_FLAG_TEXT / BROKER_FLAG_ICON / BROKER_FAULT_TEXT). It imports nothing from
 * gajjalaWatch.ts (that module imports this one — no cycle). Display only; UNMEASURED. */

/** The board's served 🚫 block: `toggle` = the button glyph, `text` = the served word, `title` = the button's hover,
 *  `editable` = the list was read (only then is the button drawn), and the three served head lines. */
export type GgwBroker = {
  toggle: string; text: string; title: string | null; editable: boolean;
  fault_text: string | null; auto_text: string | null; auto_fault_text: string | null;
};

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);

/** The served block, or null for junk / an older server (needs a served non-empty `toggle` and `text`). `editable` is
 *  true ONLY when the server said `true`. */
export function parseGgwBroker(v: unknown): GgwBroker | null {
  if (!isObj(v)) return null;
  const toggle = str(v.toggle);
  const text = str(v.text);
  if (!toggle || !text) return null;
  return {
    toggle, text, title: str(v.title), editable: v.editable === true,
    fault_text: str(v.fault_text), auto_text: str(v.auto_text), auto_fault_text: str(v.auto_fault_text),
  };
}

/** The row's served broker word: the row's own `broker_text` first, else the 🚩 card tags' word (an older server
 *  serves only that one); blank → null. */
export function ggwBrokerText(row: { broker_text?: string | null; tags?: { broker_text: string | null } | null }): string | null {
  return str(row?.broker_text) ?? str(row?.tags?.broker_text) ?? null;
}
