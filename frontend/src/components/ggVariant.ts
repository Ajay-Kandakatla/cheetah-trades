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
 *
 * 🧪 Gajjala · Audited (2026-11-01). Ajay: "I would like you to create a new tab for Gajjals when you modifiy with audit
 * of End of day.." "Gajjals-Audited" "So we can keep track of improvements on this tab". A third page on the same board:
 * `gajjala_audited` → GET /chart-maps/gajjala-audited (== backend variant.py GGA.api_base). The same 5-minute pass and
 * the same reads as 🚩 Gajjala's, filtered by the audit overlay — every word of it SERVED. Shadow only. UNMEASURED.
 *
 * 🥇 Luk's 🏁 (2026-11-02). Ajay: "Can you make Luk's track record similar to Gajjal's". Luk's 🏁 draws through the
 * SAME 🏁 row / tape components, so the 📈 tape inside it must read Luk's route: `luk` → /chart-maps/luk (== backend
 * chart_maps/luk/variant.py LUK.api_base); ggTapePath('luk') = /chart-maps/luk/entry-tape (== lib/luk LUK_TAPE_PATH).
 * Only the 🏁 tape uses it — no GajjalaBoard is mounted on Luk's base. UNMEASURED.
 */
import { createContext, useContext } from 'react';

export type GgVariantKey = 'gajjala' | 'gajjala_1m' | 'gajjala_audited' | 'luk';

/** The page's endpoint base — == backend variant.py GG5.api_base / GG1.api_base / GGA.api_base, luk/variant.py LUK.api_base. */
export const GG_VARIANT_BASE: Readonly<Record<GgVariantKey, string>> = {
  gajjala: '/chart-maps/gajjala',
  gajjala_1m: '/chart-maps/gajjala-1m',
  gajjala_audited: '/chart-maps/gajjala-audited',
  luk: '/chart-maps/luk',
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
