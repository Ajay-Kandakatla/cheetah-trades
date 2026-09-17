/* IndexZones — SPY and QQQ, pinned to the top of the Back in Demand tab.
 *
 * Ajay 2026-09-16, verbatim: "Can you create a SPY demand and supply zone
 * please for me? and also QQQ supply and demand zone and keep them always in
 * the in demand zone page. I need everything calculation overnight."
 * then, same morning: "I wanna see charts with multiple zones" · "For both QQQ
 * and SPY" · "SPX*" · "Sorry SPY only my bad" — final scope SPY and QQQ, and
 * the headline ask is a PICTURE, not a list.
 *
 * "KEEP THEM ALWAYS" is the whole design. This strip is NOT a row in the
 * board: it renders while the scan is warming, while the board is erroring,
 * when nothing matched, and when his filters have cut the grid to zero. It is
 * never filtered, never ordered and never gated by the board's controls
 * (phase / room / liquidity / limit) — those controls describe a universe
 * pass, and these two tickers are not in it. When the board payload carries no
 * index_zones at all — a 500, a cache written before this shipped — the strip
 * asks the endpoint for the stored doc ITSELF, once per page load, rather than
 * telling him nothing was written when something was.
 *
 * "EVERYTHING CALCULATION OVERNIGHT" — the bands are computed by the nightly
 * job (backend/supply_demand/index_zones.py) and stored. This component READS
 * the served doc and derives no band of its own; it does not re-cluster and it
 * does not re-sort. The ladder is printed in the order it arrives.
 *
 * TWO RESOLUTIONS, BOTH EXISTING SETTINGS. `board` is the geometry the demand
 * engine and every tile under this strip already draw with
 * (demand_reentry.zone_geom) — 7 bands on each index. `fine` is the
 * price_zones module's own default geometry — 14 bands on SPY, 13 on QQQ,
 * roughly a third as wide. Neither number was invented here and neither was
 * copied off a hand-drawn note: this app's own precedent
 * (gabbar_backtest_2026_08_31) is that hand-drawn levels are contaminated as a
 * measurement, so we draw OUR bands. The toggle names which set the rest of
 * the page is drawn with, because reading a fine band as the board's band is
 * the one mistake a second resolution makes possible.
 *
 * BROKEN SUPPORT IS RESISTANCE — "when a demand zone is broken, it becomes a
 * supply zone and similarly when a supply zone is broken, it becomes a demand
 * zone". That is already how this engine works: the band keeps its origin for
 * COLOUR only, and the nearest band above and below are picked over every
 * band whatever its kind. It is why the ceiling can be a demand band, and the
 * card says which kind each edge is rather than leaving it to the colour.
 *
 * TWO BASES, NEVER MIXED. The bands and the bars are CLOSED daily bars and
 * every card says so above the numbers. A live print, when the backend sends
 * one, lands in its own labelled line and in its own keys (live_*), and it can
 * only say WHERE PRICE IS STANDING inside that structure — it never moves a
 * band and it is never drawn on the chart. This is the 2026-09-16 hot-sectors
 * correction applied up front: a column labelled with today that carried a
 * different session's snapshot was the worst bug of that week.
 *
 * IT IS CONTEXT. It gates nothing, orders nothing, alerts nothing and enters
 * no lane. Every structural S/D read this app measured this month came back
 * null (band_structure no_signal, deep_levels no_signal, enterable no_signal),
 * so no copy here may read as a forecast.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import type {
  CmBand, CmBar, CmIndexZoneBand, CmIndexZoneEdge, CmIndexZoneRead,
  CmIndexZoneResolution, CmIndexZones, CmTile,
} from '../lib/chartMaps';
import { PatternChart } from './PatternChart';
import { StudyNote } from './StudyNote';

/** The two he asked for, in his order. Named because the strip must render a
 *  placeholder card for a symbol the overnight job did NOT write — "keep them
 *  always" is not satisfied by rendering only what happened to arrive. The
 *  backend's own list is index_zones.INDEXES; a third index is one edit on
 *  each side. */
export const INDEX_ZONE_SYMBOLS = ['SPY', 'QQQ'] as const;

/** The two geometries the backend serves. Both are EXISTING settings in this
 *  app, named after the module that owns each. */
export type IzResKey = 'fine' | 'board';
export const IZ_RES_KEYS: IzResKey[] = ['fine', 'board'];
export const IZ_RES_LABEL: Record<IzResKey, string> = { fine: 'Fine', board: 'Board' };
/** What each one IS, in his words, so the toggle is not two bare nouns. The
 *  `board` line names the set the rest of the page is drawn with — that is the
 *  whole reason the toggle has to be labelled at all. */
export const IZ_RES_WHAT: Record<IzResKey, string> = {
  fine: 'the finer setting — more, narrower bands',
  board: 'the set the demand engine and every tile under this strip are drawn with',
};

/** A number, or null for anything that is not one. A missing field must read
 *  UNKNOWN — it must never fall through to a zero that prints as a price. */
export function izNum(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** A price, 2dp, or an em dash. Never a zero standing in for "not sent". */
export function izPrice(v: unknown): string {
  const n = izNum(v);
  return n == null ? '—' : n.toFixed(2);
}

/** A distance as an unsigned percentage — the direction is carried by the
 *  word beside it ("above" / "below"), never by a sign the backend did not
 *  promise. */
export function izDist(v: unknown): string {
  const n = izNum(v);
  return n == null ? '—' : `${Math.abs(n).toFixed(2)}%`;
}

/** "749.53 – 779.37", or an em dash on either side that did not arrive. A
 *  malformed band still prints a row: a silently dropped band is worse than a
 *  visibly incomplete one. */
export function izRange(b: Pick<CmIndexZoneBand, 'lo' | 'hi'> | null | undefined): string {
  return `${izPrice(b?.lo)} – ${izPrice(b?.hi)}`;
}

/** "the 2026-09-15 close", or just "the close" when the doc carried no date.
 *  Every stored number on this card is on that session and says so — a
 *  distance with no basis sitting under a live line that says price is
 *  somewhere else is exactly the hot-sectors bug. */
export function izCloseRef(asOf?: string | null): string {
  return asOf ? `the ${asOf} close` : 'the close';
}

/** Where the stored CLOSE stands relative to one band, in words. Built from
 *  the served `side` and `dist_pct` — this component measures nothing — and it
 *  names the close, and the session, every time. */
export function izWhere(b: CmIndexZoneBand | null | undefined, asOf?: string | null): string {
  if (!b) return '';
  const ref = izCloseRef(asOf);
  if (b.side === 'in') return `${ref} is inside this band`;
  if (b.side === 'above' || b.side === 'below') {
    const d = izNum(b.dist_pct);
    return d == null ? `${b.side} ${ref}` : `${izDist(d)} ${b.side} ${ref}`;
  }
  return '';
}

/** "demand band 759.48 – 762.04" — each nearest band prints its KIND, never left to
 *  the colour. A demand band overhead is Pankaj's broken-zone flip made
 *  visible: the engine picks the nearest band on each side whatever its
 *  origin, so a ceiling that reads "demand" is support price has already gone
 *  under. */
export function izEdge(e: CmIndexZoneEdge | null | undefined): string {
  if (!e) return '';
  const kind = e.kind === 'supply' ? 'supply' : e.kind === 'demand' ? 'demand' : null;
  return `${kind ? `${kind} band ` : ''}${izRange(e)}`;
}

/** The basis line that sits over every number in the card body. It names the
 *  session the bands were drawn from and says the job that drew them ran
 *  overnight — the two facts that keep a stored band from being read as a
 *  live one. */
export function izBasis(read: Pick<CmIndexZoneRead, 'as_of' | 'close'>): string {
  const on = read.as_of ? ` ${read.as_of}` : '';
  const close = izNum(read.close);
  return `bands and chart: closed daily bars through the${on} close`
    + (close == null ? '' : ` (${close.toFixed(2)})`)
    + ' · drawn overnight, not re-drawn on this page';
}

/** The live overlay, in words, or null when the backend sent no live print.
 *  It is a SEPARATE sentence with the word "live" in it, and it says out loud
 *  that it does not move a band.
 *
 *  `live_side` is measured against the WHOLE stored structure, not against
 *  "the band it was last in" — above means above every stored band, below
 *  means below every one of them, and `between` is the open air between two.
 *  A band is named ONLY when the backend sent `live_in_band`. */
export function izLiveLine(read: CmIndexZoneRead): string | null {
  const px = izNum(read.live_px);
  if (px == null) return null;
  const parts = [`live print ${px.toFixed(2)}`];
  if (read.live_in_band) {
    parts.push(`standing in the ${read.live_in_band.kind} band ${izRange(read.live_in_band)}`);
  } else if (read.live_side === 'above') {
    parts.push('above every stored band');
  } else if (read.live_side === 'below') {
    parts.push('below every stored band');
  } else if (read.live_side === 'between') {
    parts.push('in the open air between two stored bands, inside none of them');
  }
  // The backend's own label for what this number is. LABELLED, never dropped
  // into the list bare — "· live" on its own says nothing.
  if (read.price_basis) parts.push(`basis: ${String(read.price_basis)}`);
  return `${parts.join(' · ')} — a live print; it says where price is, it does not move a band.`;
}

/* ── resolutions ─────────────────────────────────────────────────────────── */

/** The top-level keys, read as a resolution. This is what a doc written before
 *  the two-resolution payload shipped carries, and it stays the fallback so an
 *  old cache renders a full card instead of an empty one. */
export function izFlatView(read: CmIndexZoneRead): CmIndexZoneResolution {
  return {
    bands: read.bands, in_band: read.in_band, ceiling: read.ceiling, floor: read.floor,
    room_pct: read.room_pct, drop_pct: read.drop_pct, sentence: read.sentence,
  };
}

/** Which resolutions this read actually carries, with usable bands. Returns an
 *  empty object for a legacy doc — the caller then draws the flat view and
 *  shows NO toggle, because a toggle with one arm is a lie about what is
 *  stored. */
export function izResolutions(read: CmIndexZoneRead): Partial<Record<IzResKey, CmIndexZoneResolution>> {
  const src = read?.resolutions;
  if (!src || typeof src !== 'object') return {};
  const out: Partial<Record<IzResKey, CmIndexZoneResolution>> = {};
  for (const k of IZ_RES_KEYS) {
    const v = (src as Record<string, CmIndexZoneResolution | null | undefined>)[k];
    // DRAWABLE, not merely present. `index_zones._unavailable()` stores
    // `bands: []`, so a symbol whose frame failed to load arrives as a real
    // resolution with nothing in it — and the card would open on "Fine · 0
    // zones" with a full Board set one click away (2026-09-16 review).
    if (v && typeof v === 'object' && izDrawable(v.bands).length) out[k] = v;
  }
  return out;
}

/** The backend's own default, honoured when it named one it actually sent.
 *  Falls back to fine, then to whatever exists — never to a key with no
 *  bands behind it. */
export function izDefaultRes(read: CmIndexZoneRead, payloadDefault?: string | null): IzResKey {
  const have = izResolutions(read);
  // The backend names its default at the PAYLOAD level, not per read — so
  // reading it off the read alone was always undefined on the real wire and
  // the page only opened on fine because the local fallback said so. Take the
  // read's own key when a future payload carries one, else the payload's.
  const asked = read?.default_resolution ?? payloadDefault;
  if (asked === 'fine' || asked === 'board') {
    if (have[asked]) return asked;
  }
  if (have.fine) return 'fine';
  if (have.board) return 'board';
  return 'fine';
}

/** The read whose LIVE overlay belongs to `view`.
 *
 *  Each resolution carries its own live_* keys because `index_zones.with_live`
 *  recurses into them — the print's position depends on which bands you are
 *  looking at. Returns the view's overlay when it has one, else the flat
 *  legacy keys, so an older stored doc still says something true. */
export function izLiveSource(read: CmIndexZoneRead,
                             view: CmIndexZoneResolution): CmIndexZoneRead {
  const v = view as unknown as Record<string, unknown>;
  const hasOwn = v && (v.live_side != null || v.live_px != null);
  if (!hasOwn) return read;
  return { ...read, ...(v as Partial<CmIndexZoneRead>) } as CmIndexZoneRead;
}

/** The set to draw: the chosen resolution, or the flat legacy view. */
export function izView(read: CmIndexZoneRead, key: IzResKey): CmIndexZoneResolution {
  return izResolutions(read)[key] || izFlatView(read);
}

/** Only the bands that can be DRAWN — both edges finite. A band with a null
 *  edge still prints a row in the ladder (see BandRow); it cannot be a
 *  rectangle on a price axis. */
export function izDrawable(bands: unknown): CmIndexZoneBand[] {
  if (!Array.isArray(bands)) return [];
  return bands.filter((b: any) => b && izNum(b.lo) != null && izNum(b.hi) != null
                                  && (b.hi as number) >= (b.lo as number)) as CmIndexZoneBand[];
}

/** The chart tile, in the shape every Chart Maps tile already feeds
 *  PatternChart: bars + bands (+ one line). Nothing is computed here — the
 *  bars are the served closed daily bars and the bands are the served levels.
 *  Returns null when the doc carried no bars, and the card then shows the
 *  ladder alone rather than an empty frame. */
export function izTile(read: CmIndexZoneRead, view: CmIndexZoneResolution): CmTile | null {
  const bars: CmBar[] = Array.isArray(read?.bars)
    ? read.bars.filter((b: any) => b && izNum(b.o) != null && izNum(b.h) != null
                                   && izNum(b.l) != null && izNum(b.c) != null)
    : [];
  if (!bars.length) return null;
  const sym = String(read?.symbol || '');
  const bands: CmBand[] = izDrawable(view?.bands).map((b) => {
    const kind: CmBand['kind'] = b.kind === 'supply' ? 'supply' : 'demand';
    const inIt = b.side === 'in';
    return {
      kind,
      lo: b.lo,
      hi: b.hi,
      // The <title> and the hover readout come off this label, so it carries
      // the kind, the range, and — for the one band the close finished inside
      // — that fact, named as the close and not as "price".
      label: `${kind}${inIt ? ` · ${izCloseRef(read.as_of)} inside` : ''}`,
    };
  });
  const close = izNum(read.close);
  return {
    symbol: sym,
    name: read.name ?? null,
    href: `/sepa/${sym}?tab=supply`,
    bars,
    bands,
    // `lineLabels` appends the price for tone 'now' (chartMaps.nowLabelText),
    // so `close 760.12` rendered as "close 760.12 760.12". And tone 'now' is
    // the LIVE-print colour on every other tile of this page — a closed-bar
    // close drawn in the live colour is the exact basis confusion this strip
    // exists to prevent. Label + tone both corrected 2026-09-16.
    lines: close == null ? [] : [{ price: close, label: 'close', tone: 'neutral' }],
    markers: [],
    stats: [],
    why: '',
  };
}

/* ── the strip's own fetch ───────────────────────────────────────────────── */

/* F1, 2026-09-16: the board's `load()` only setData()s on success, so a 500
 * on /chart-maps left the strip with no payload and it said "the overnight job
 * has not written one" — about a doc that exists and is fine. "Keep them
 * always" has to survive the board failing, so the strip asks for the stored
 * doc itself. ONE request per page load, shared by both cards through the
 * module-level promise, exactly like useGrowthTags. A failure is quiet and
 * says WHICH fact it is: a request that failed is not an empty store. */
export type IzFallback = { state: 'ok' | 'error'; data: CmIndexZones | null };

let fbCache: IzFallback | null = null;
let fbInFlight: Promise<IzFallback> | null = null;

/** tests only */
export function _resetIndexZonesFallback(): void {
  fbCache = null;
  fbInFlight = null;
}

export function fetchIndexZones(): Promise<IzFallback> {
  if (fbCache) return Promise.resolve(fbCache);
  if (fbInFlight) return fbInFlight;
  fbInFlight = fetch(`${API}/supply-demand/index-zones`, {
    credentials: 'include', cache: 'no-store',
  })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((j) => {
      fbCache = { state: 'ok', data: (j && typeof j === 'object' ? j : null) as CmIndexZones | null };
      return fbCache;
    })
    .catch(() => {
      // Cache the miss too: two cards must not retry it twice, and a strip
      // that is context must not hammer an endpoint that is down.
      fbCache = { state: 'error', data: null };
      return fbCache;
    })
    .finally(() => { fbInFlight = null; });
  return fbInFlight;
}

/* ── rendering ───────────────────────────────────────────────────────────── */

function BandRow({ b, asOf }: { b: CmIndexZoneBand; asOf?: string | null }) {
  const kind = b?.kind === 'supply' ? 'supply' : b?.kind === 'demand' ? 'demand' : 'band';
  const inIt = b?.side === 'in';
  const touches = izNum(b?.touches);
  const strength = izNum(b?.strength);
  const meta = [
    touches == null ? null : `${touches} touch${touches === 1 ? '' : 'es'}`,
    strength == null ? null : `strength ${strength}`,
  ].filter(Boolean).join(' · ');
  return (
    <li className={`iz-band iz-band-${kind}${inIt ? ' iz-band-in' : ''}`}
        data-kind={kind} data-side={b?.side || 'unknown'}>
      <span className="iz-band-kind">{kind}</span>
      <span className="iz-band-range">{izRange(b)}</span>
      {meta ? <span className="iz-band-meta">{meta}</span> : null}
      <span className="iz-band-where">{izWhere(b, asOf)}</span>
    </li>
  );
}

function ResToggle(
  { symbol, value, have, onPick }: {
    symbol: string; value: IzResKey;
    have: Partial<Record<IzResKey, CmIndexZoneResolution>>;
    onPick: (k: IzResKey) => void;
  },
) {
  const keys = IZ_RES_KEYS.filter((k) => have[k]);
  // One arm is not a choice — a legacy doc shows no toggle rather than a
  // control that cannot move.
  if (keys.length < 2) return null;
  return (
    <div className="iz-res" role="group" data-testid={`index-zone-res-${symbol}`}
         aria-label={`${symbol} zone resolution`}>
      {keys.map((k) => {
        const n = izDrawable(have[k]?.bands).length;
        return (
          <button key={k} type="button"
                  className={`iz-res-btn${value === k ? ' iz-res-on' : ''}`}
                  data-testid={`index-zone-res-${k}-${symbol}`}
                  aria-pressed={value === k}
                  title={`${IZ_RES_LABEL[k]} — ${IZ_RES_WHAT[k]}`}
                  onClick={() => onPick(k)}>
            {IZ_RES_LABEL[k]} · {n} zone{n === 1 ? '' : 's'}
          </button>
        );
      })}
      <span className="iz-res-note" data-testid={`index-zone-res-note-${symbol}`}>
        {`${IZ_RES_LABEL[value]} — ${IZ_RES_WHAT[value]}. Both are the same closed daily bars.`}
      </span>
    </div>
  );
}

/** What the strip actually knows about this symbol right now. These are four
 *  DIFFERENT facts and the card says which one it is — F1, 2026-09-16: the old
 *  card told him the overnight job had not written a doc whenever the BOARD
 *  request 500'd, about a doc that was sitting there fine. */
export type IzPhase = 'read' | 'loading' | 'error' | 'empty';

function IndexCard(
  { symbol, read, phase, payloadDefault }:
  { symbol: string; read?: CmIndexZoneRead | null; phase: IzPhase;
    payloadDefault?: string | null },
) {
  const ok = Boolean(read && typeof read === 'object');
  const have = useMemo(
    () => (ok ? izResolutions(read as CmIndexZoneRead) : {}), [ok, read]);
  const [res, setRes] = useState<IzResKey>('fine');
  // The backend names the default; honour it once the doc has arrived, and
  // again if the doc's OWN default changes. Keyed on the default itself, not
  // on the object identity — the board polls every 10s while a scan warms, and
  // a fresh object each time would silently snap a resolution he had picked
  // back to fine under his cursor.
  const wantDefault = ok ? izDefaultRes(read as CmIndexZoneRead, payloadDefault) : null;
  const seenDefault = useRef<string | null>(null);
  useEffect(() => {
    if (!wantDefault || seenDefault.current === wantDefault) return;
    seenDefault.current = wantDefault;
    setRes(wantDefault);
  }, [wantDefault]);

  // The quiet placeholder. "Keep them always" means a card, always. The copy
  // names WHICH fact it is: a request in flight, a request that failed and an
  // empty store are three things, and only the last one is the overnight job's
  // fault.
  if (!ok) {
    return (
      <div className="iz-card iz-card-empty" data-testid={`index-zone-${symbol}`}
           data-phase={phase}>
        <div className="iz-head">
          <strong className="iz-sym">{symbol}</strong>
        </div>
        {phase === 'loading' ? (
          <p className="iz-placeholder" data-testid={`index-zone-loading-${symbol}`}>
            Reading the stored structure for {symbol}…
          </p>
        ) : phase === 'error' ? (
          <p className="iz-placeholder" data-testid={`index-zone-failed-${symbol}`}>
            Could not load the stored structure for {symbol} — the board request failed and
            this strip's own request failed too. That is a request failure, not an empty
            store: the overnight doc may be sitting there fine.
          </p>
        ) : (
          <p className="iz-placeholder" data-testid={`index-zone-empty-${symbol}`}>
            No stored structure for {symbol} yet — the overnight job has not written one.
            Nothing else on this board depends on it.
          </p>
        )}
      </div>
    );
  }

  const doc = read as CmIndexZoneRead;
  const view = izView(doc, res);
  // Defensive on every served collection: a malformed payload must cost this
  // strip its numbers, never the board it is pinned above.
  const bands = Array.isArray(view.bands) ? view.bands.filter(Boolean) : [];
  // THE OVERLAY BELONGS TO THE SET ON SCREEN (2026-09-16 review). The backend
  // recurses with_live() into every resolution, so each set carries its own
  // live_side / live_in_band. Reading the flat keys printed the BOARD overlay
  // under the FINE chart: board bands are ~3% wide and fine ~1.1%, so a print
  // that is "in" under board is routinely "between" under fine — and the
  // sentence then named a band drawn on no surface he can see. Fall back to
  // the flat keys only for a legacy doc that carries no per-set overlay.
  const live = izLiveLine(izLiveSource(doc, view));
  const summary = view.sentence
    ? String(view.sentence)
    : `${symbol}: structure stored${doc.as_of ? ` from the ${doc.as_of} close` : ''}.`;
  const ceiling = view.ceiling || null;
  const floor = view.floor || null;
  const tile = izTile(doc, view);

  return (
    <div className="iz-card" data-testid={`index-zone-${symbol}`}>
      <div className="iz-head">
        <strong className="iz-sym">{symbol}</strong>
        {doc.name ? <span className="iz-name">{String(doc.name)}</span> : null}
      </div>
      <p className="iz-basis" data-testid={`index-zone-basis-${symbol}`}>{izBasis(doc)}</p>
      {live ? (
        <p className="iz-live" data-testid={`index-zone-live-${symbol}`}>{live}</p>
      ) : null}

      <ResToggle symbol={symbol} value={res} have={have} onPick={setRes} />

      {/* THE CHART — his headline ask, "I wanna see charts with multiple
        * zones". Drawn by the SAME component every tile on this page uses, fed
        * the same way (bars + bands + lines), so a band here and a band on a
        * tile below cannot come to look like two different things. Every band
        * in the selected set is drawn; supply and demand take the page's own
        * red and green; the close the bands were drawn from is the one line on
        * it. No live print is ever drawn here. */}
      {tile ? (
        <div className="iz-chart" data-testid={`index-zone-chart-${symbol}`}>
          <PatternChart tile={tile} height={168} />
        </div>
      ) : (
        <p className="iz-placeholder" data-testid={`index-zone-nochart-${symbol}`}>
          The stored doc carried no bars for {symbol}, so there is nothing to draw — the
          levels below are unaffected.
        </p>
      )}

      <StudyNote id={`index-zones-${symbol}`}
                 testId={`index-zone-note-${symbol}`}
                 className="iz-note"
                 glyph="🧭"
                 headline={summary}>
        <p className="iz-edges" data-testid={`index-zone-edges-${symbol}`}>
          {ceiling
            ? `Ceiling ${izEdge(ceiling)}, ${izDist(ceiling.dist_pct)} up`
            : 'No band overhead in the stored structure'}
          {' · '}
          {floor
            ? `Floor ${izEdge(floor)}, ${izDist(floor.dist_pct)} down`
            : 'No band beneath in the stored structure'}
          {` — measured from ${izCloseRef(doc.as_of)} above, not from a live print. `}
          {'Either side can be either kind: a demand band broken through is overhead from '
           + 'then on, and a supply band broken through is support, so the nearest band on '
           + 'each side is taken whatever it started as.'}
        </p>
        {bands.length ? (
          <ol className="iz-ladder" data-testid={`index-zone-ladder-${symbol}`}>
            {bands.map((b, i) => (
              <BandRow key={`${symbol}-${res}-${i}-${b?.lo}-${b?.hi}`} b={b} asOf={doc.as_of} />
            ))}
          </ol>
        ) : (
          <p className="iz-placeholder" data-testid={`index-zone-noladder-${symbol}`}>
            The stored doc carried no bands for {symbol}.
          </p>
        )}
        <p className="iz-dim">
          Every level above is last night's closed-bar structure, printed in the order
          it was served. Context only — it gates nothing, orders nothing, alerts nothing
          and enters nothing. Not advice.
        </p>
      </StudyNote>
    </div>
  );
}

/** The pinned strip. `data` is the board payload's `index_zones` key; absent,
 *  null or malformed sends the strip to its OWN request for the stored doc,
 *  and only when that comes back empty does it draw placeholders. Never
 *  nothing, and never a crash. */
export default function IndexZones({ data }: { data?: CmIndexZones | null }) {
  const fromBoard = data && typeof data === 'object' && data.indexes
    && typeof data.indexes === 'object' ? data : null;
  const [fallback, setFallback] = useState<IzFallback | null>(null);

  // Only when the board gave us nothing usable. A board that answered keeps
  // this strip on ONE payload — no second request, no chance of two sessions
  // on one card.
  useEffect(() => {
    if (fromBoard) return;
    let live = true;
    void fetchIndexZones().then((r) => { if (live) setFallback(r); });
    return () => { live = false; };
  }, [fromBoard]);

  const doc: CmIndexZones | null = fromBoard || fallback?.data || null;
  const indexes = doc?.indexes && typeof doc.indexes === 'object' ? doc.indexes : {};
  const phase: IzPhase = fromBoard ? 'read'
    : fallback == null ? 'loading'
    : fallback.state === 'error' ? 'error' : 'empty';
  // SESSIONS, from the key that counts sessions. `stale_days` is CALENDAR days
  // and saying "3 sessions old" over a 3-calendar-day gap across a weekend is
  // a different number wearing the wrong word — so calendar days, when that is
  // all the doc carries, say "calendar days".
  const sessions = izNum(doc?.stale_sessions);
  const days = izNum(doc?.stale_days);
  const age = sessions != null && sessions > 0
    ? ` · ${sessions} session${sessions === 1 ? '' : 's'} old`
    : sessions == null && days != null && days > 0
      ? ` · stored ${days} calendar day${days === 1 ? '' : 's'} ago`
      : '';
  return (
    <section className="iz" role="complementary" aria-label="SPY and QQQ zones"
             data-testid="index-zones">
      <div className="iz-strip-head">
        <span className="iz-strip-title">🧭 SPY · QQQ zones</span>
        <em className="iz-strip-sub">
          supply and demand bands, computed overnight from closed daily bars
          {doc?.date ? ` · stored ${doc.date}` : ''}
          {age}
          {' · pinned here, never filtered by the board controls below'}
        </em>
      </div>
      {doc?.note ? <p className="iz-dim" data-testid="index-zones-note">{String(doc.note)}</p> : null}
      <div className="iz-cards">
        {INDEX_ZONE_SYMBOLS.map((sym) => (
          <IndexCard key={sym} symbol={sym} read={indexes[sym]} phase={phase}
                     payloadDefault={doc?.default_resolution ?? null} />
        ))}
      </div>
    </section>
  );
}

export { IndexZones };
