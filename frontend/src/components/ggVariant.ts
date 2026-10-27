/* ggVariant — which 🚩 Gajjala page a GajjalaBoard draws (2026-10-27, BUILD_SPEC27 §3.8).
 *
 * Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
 * please." and "do everything and also add the track record for it from today..".
 *
 * ONE board component, two pages: 🚩 Gajjala's (5-minute bars, `gajjala`) and 🚩 Gajjala's 1-min (`gajjala_1m`). The
 * only thing the FE knows per page is its endpoint base — the values below == backend chart_maps/gajjala/variant.py
 * `api_base` (contract-pinned by WP-E); every word, frame and number on either page is SERVED. The board GETs `base`,
 * POSTs `${base}/scan`, and hands `base` to the 🕰️ entry tape through GgVariantContext (`${base}/entry-tape`), so a
 * 1-minute row never reads a 5-minute tape. The broker list stays ONE list under /chart-maps/gajjala/… (GG_BROKER_PATH).
 * UNMEASURED.
 */
import { createContext, useContext } from 'react';

export type GgVariantKey = 'gajjala' | 'gajjala_1m';

/** The page's endpoint base — == backend variant.py GG5.api_base / GG1.api_base. */
export const GG_VARIANT_BASE: Readonly<Record<GgVariantKey, string>> = {
  gajjala: '/chart-maps/gajjala',
  gajjala_1m: '/chart-maps/gajjala-1m',
};

/** A known variant key, else 'gajjala' (fail to 🚩 Gajjala's, as variant.of does). */
export function ggVariantKey(v: unknown): GgVariantKey {
  return typeof v === 'string' && Object.prototype.hasOwnProperty.call(GG_VARIANT_BASE, v) ? (v as GgVariantKey) : 'gajjala';
}

/** The page's endpoint base for a variant key (unknown → 🚩 Gajjala's). */
export function ggBase(v: unknown): string {
  return GG_VARIANT_BASE[ggVariantKey(v)];
}

/** The board's variant, for the components it mounts (the 🕰️ entry tape). Default = 🚩 Gajjala's. */
export const GgVariantContext = createContext<GgVariantKey>('gajjala');

/** The variant of the board this component sits in. */
export function useGgVariant(): GgVariantKey {
  return useContext(GgVariantContext);
}
