/* 🚩 Gajjala card → ⤢ three-chart view — the FE plumbing (2026-11-16, ggcard3 spec §3.2, WP-A).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like
 * in the Watch list... Also put a SEPA page link for it separaetely on the card I I want to but default its 3 chart
 * extension with 1 min, 3 min and 5 mins" and then "Actually instead of 3 mins make it 15 mins timeframe".
 *
 * ONE read-only GET (backend chart_maps/gajjala/card_frames.py, route `/chart-maps/gajjala/frames/{symbol}`) serves the
 * three frames from the docs the 🚩 5-minute pass and the 1-minute loop already store. Each frame is the 👀 Watch's frame
 * block (lib/gajjalaWatch.parseFrame reads it) plus its own served stamp / stale flag / empty words. This module holds
 * the route, the order, the parser and the overlay of the OPEN card's plan (lines, bands, markers, plan line) onto the
 * served frames. The ONE FE sentence is GGC_FETCH_FAILED (the request itself failed — there is no payload to serve one).
 * UNMEASURED — a chart view is information, not an entry. */
import type { GgTile } from './gajjala';
import { parseFrame, type GgwFrame, type GgwRow } from './gajjalaWatch';
import { videoLayers } from './videoLook';

/** The frames route base (== backend card_frames.API_BASE — a backend source-read test pins equality). */
export const GGC_PATH = '/chart-maps/gajjala/frames';
export const ggcPath = (sym: string): string => `${GGC_PATH}/${encodeURIComponent(sym.trim())}`;
/** His frames 1 / 5 / 15, stacked big → small top to bottom (the Watch's convention — HIS CALL #1). The 👀 Watch keeps
 *  its own GGW_STRETCH_ORDER (5 / 3 / 1). */
export const GGC_STRETCH_ORDER = ['15m', '5m', '1m'] as const;
/** The ONE FE sentence (the GET itself failed — no payload to serve a reason). */
export const GGC_FETCH_FAILED = 'Could not load the three charts.';

export type GgcPayload = {
  state: 'ok'; symbol: string; session: string | null; is_today: boolean; in_window: boolean;
  as_of_et: string | null; stale: boolean; text: string | null; frames: GgwFrame[];
};
export type GgcError = { state: 'error'; reason: string | null };

const isObj = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);

/** The served answer, a served error (its reason verbatim), or null for junk (no symbol, no frames list, another state). */
export function parseGgc(raw: unknown): GgcPayload | GgcError | null {
  if (!isObj(raw)) return null;
  if (raw.state === 'error') return { state: 'error', reason: str(raw.reason) };
  if (raw.state !== 'ok' || !str(raw.symbol) || !Array.isArray(raw.frames)) return null;
  const symbol = raw.symbol as string;
  return {
    state: 'ok',
    symbol,
    session: str(raw.session),
    is_today: raw.is_today === true,
    in_window: raw.in_window === true,
    as_of_et: str(raw.as_of_et),
    stale: raw.stale === true,
    text: str(raw.text),
    frames: raw.frames.map((f: unknown) => parseFrame(f, symbol)).filter((f: GgwFrame | null): f is GgwFrame => !!f),
  };
}

/** The card's plan on the served frames: `lines` + `bands` of the card on EVERY frame (prices, frame-free); `markers`
 *  ONLY on the frame whose tf === card.tf (PatternChart maps them by date — a mark outside the frame's bars drops). The
 *  head line = the served `text` (no bars at all), else the card's served plan line, else none.
 *  📺 2026-11-17 (video view spec §3.4, his call #4): `look === 'video'` strips the overlay through the SAME
 *  lib/videoLook.videoLayers the cards use — no 🧪 band, no ➖ diamonds; BUY / STOP / now + the A+ tag kept. `look`
 *  absent → the card's own `lines` / `bands` / `markers` references, byte-identical to before. */
export function ggcRow(card: GgTile, p: GgcPayload, look?: 'video'): GgwRow {
  const src = look === 'video' ? videoLayers(card) : card;
  const lines = Array.isArray(src.lines) ? src.lines : [];
  const bands = Array.isArray(src.bands) ? src.bands : [];
  const markers = Array.isArray(src.markers) ? src.markers : [];
  return {
    symbol: p.symbol,
    state: p.text ? 'no_bars' : 'ok',
    text: p.text ?? card.gajjala?.plan_text ?? null,
    from_session: p.is_today ? null : p.session,
    as_of_et: p.as_of_et,
    stale: p.stale,
    frames: p.frames.map((f) => ({
      ...f,
      tile: { ...f.tile, lines, bands, markers: card.tf != null && f.tf === card.tf ? markers : [] },
    })),
    rang: [],
  };
}
