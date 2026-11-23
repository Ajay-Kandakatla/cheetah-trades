/* 🎾 the 🎾 card drawn as the 👀 Watch tile — the lib (2026-11-23, rswatch spec §3.6 / §4 WP fe-grid).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 *
 * ggcPath's card param, the 🎾 predicate, the served ECHO (parseGgc keeps `card` only for the exact value) and ggcRow's
 * squeeze row — which splits ONLY on the caller's word AND the echo [C2]. Frames are CLONES of the 2026-11-15 Watch
 * fixture's OMH frames (3m relabelled 15m); the 🎾 card is a CLONE of the frozen 2026-10-13 hand fixture's FCHL with `tf`,
 * `ellipses` and an A+ marker set on the clone. Fixtures are never edited. NEGATIVES throughout: no squeeze opt, a plain
 * payload, junk echoes, an empty / absent `ellipses`, another `card.tf`, a doubled cross. Display only, UNMEASURED. */
import { describe, expect, it } from 'vitest';
import watchFixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import hand from '../components/__fixtures__/gajjala_board_2026_10_13.json';
import type { GgTile } from './gajjala';
import {
  GGC_CARD_PARAM, GGC_CARD_SQUEEZE, GGC_PATH, GGC_SQUEEZE_SETUPS, GGC_STRETCH_ORDER, ggcCardParam, ggcIsSqueeze, ggcPath,
  ggcRow, ggcRowSplit, parseGgc, type GgcPayload,
} from './gajjalaCardView';
import type { GgwRow } from './gajjalaWatch';
import { videoLayers } from './videoLook';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
const WATCH_ORDER = ['1m', '5m', '15m'];
const PRIOR_DAY = '2026-11-12';
const TAIL_N = 12;
const LEAD = 60;
const tailStamp = (i: number) => {
  const m = 15 * 60 + 5 * (i + 1);
  return `${PRIOR_DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};

/** One served frame: the Watch fixture's OMH frame relabelled; `squeeze` keeps the served cross markers + K5, plain clears them. */
function frame(sym: string, tf: string, squeeze: boolean) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  if (!squeeze) {
    f.tile.markers = [];
    f.ema_cross = null;
    f.uptrend = null;
  } else if (tf === '5m') {
    /* a hand-built prior tail (bars dated the prior day, 15:05 → 16:00) ahead of today, on a lead axis */
    const tail = Array.from({ length: TAIL_N }, (_, i) => ({ t: tailStamp(i), o: 3.9, h: 3.95, l: 3.85, c: 3.92, v: 1000 + i, s: 'post' }));
    f.tile.bars = [...tail, ...f.tile.bars];
    for (const c of f.tile.curves) c.values = [...tail.map(() => 3.9), ...c.values];
    f.axis = {
      ...f.axis,
      lead: LEAD,
      slots: f.axis.slots + LEAD,
      x: [...tail.map((_, i) => i), ...f.axis.x.map((s: number) => s + LEAD)],
      shade: [{ from_slot: TAIL_N, to_slot: LEAD, kind: 'post' }, ...f.axis.shade.map((s: any) => ({ ...s, from_slot: s.from_slot + LEAD, to_slot: s.to_slot + LEAD }))],
      ticks: [{ slot: 0, label: 'Nov 12' }, ...f.axis.ticks.map((t: any) => ({ ...t, slot: t.slot + LEAD }))],
    };
  }
  return f;
}
function rawPlain(sym: string) {
  return {
    state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
    text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf, false)),
  };
}
function rawSqueeze(sym: string, echo: unknown = GGC_CARD_SQUEEZE) {
  return { ...rawPlain(sym), frames: WATCH_ORDER.map((tf) => frame(sym, tf, true)), card: echo };
}
const plainP = (sym = 'FCHL') => parseGgc(rawPlain(sym)) as GgcPayload;
const squeezeP = (sym = 'FCHL') => parseGgc(rawSqueeze(sym)) as GgcPayload;

const ELLIPSES = [
  { kind: 'earlier_try', from_t: tailStamp(1), to_t: tailStamp(4), lo: 3.85, hi: 3.95, label: 'earlier try', tone: 'structure' },
  { kind: 'tennis_ball', from_t: '2026-11-13 07:00', to_t: '2026-11-13 07:30', lo: 4.0, hi: 4.2, label: 'tennis ball', tone: 'structure' },
];
/** The 🎾 card: FCHL of the frozen hand fixture, cloned; tf / ellipses / A+ marker / a cross marker set on the CLONE. */
function squeezeCard(over: Record<string, unknown> = {}): GgTile {
  const t = clone((hand as any).boards.reversal_squeeze.tiles[0]);
  t.tf = '5m';
  t.ellipses = clone(ELLIPSES);
  t.markers = [
    { date: '2026-11-13 07:30', kind: 'buy', label: 'A+' },
    { date: '2026-11-13 04:10', kind: 'ema_cross_up', label: 'card cross up' },
  ];
  t.bands = [{ kind: 'gg_entry', lo: 4.0, hi: 4.05, label: 'card entry band' }];
  return { ...t, ...over } as GgTile;
}
const bullCard = (): GgTile => ({ ...squeezeCard(), gajjala: { ...(squeezeCard().gajjala as any), setup: 'bull_flag' } } as GgTile);

describe('🎾 the route param', () => {
  it('ggcPath(sym) is unchanged (no ?); ggcPath(sym, GGC_CARD_SQUEEZE) ends ?card=squeeze; the param words', () => {
    expect(GGC_CARD_PARAM).toBe('card');
    expect(GGC_CARD_SQUEEZE).toBe('squeeze');
    expect(ggcPath(' OMH ')).toBe(`${GGC_PATH}/OMH`);
    expect(ggcPath('A/B')).toBe(`${GGC_PATH}/A%2FB`);
    expect(ggcPath('OMH')).not.toContain('?');
    expect(ggcPath('OMH', GGC_CARD_SQUEEZE)).toBe(`${GGC_PATH}/OMH?card=squeeze`);
    expect(ggcPath('OMH', GGC_CARD_SQUEEZE).endsWith('?card=squeeze')).toBe(true);
  });
  it('NEGATIVE: an empty / null / undefined card → today\'s URL exactly', () => {
    for (const c of ['', null, undefined]) expect(ggcPath('OMH', c as any)).toBe(`${GGC_PATH}/OMH`);
  });
});

describe('🎾 the predicate — the board\'s own 🎾 rule', () => {
  it('ggcIsSqueeze true for setup reversal_squeeze only; ggcCardParam follows', () => {
    expect([...GGC_SQUEEZE_SETUPS]).toEqual(['reversal_squeeze']);
    expect(ggcIsSqueeze({ gajjala: { setup: 'reversal_squeeze' } })).toBe(true);
    expect(ggcCardParam({ gajjala: { setup: 'reversal_squeeze' } })).toBe(GGC_CARD_SQUEEZE);
    expect(ggcIsSqueeze(squeezeCard())).toBe(true);
  });
  it('NEGATIVE: the four other setups, no gajjala, a null read, null, a junk setup → false / undefined', () => {
    for (const setup of ['bull_flag', 'kiss_fly', 'intraday_vcp', 'fade_ema']) {
      expect(ggcIsSqueeze({ gajjala: { setup } }), setup).toBe(false);
      expect(ggcCardParam({ gajjala: { setup } }), setup).toBeUndefined();
    }
    for (const c of [{}, { gajjala: null }, { gajjala: {} }, null, undefined, { gajjala: { setup: 'REVERSAL_SQUEEZE' } },
      { gajjala: { setup: ['reversal_squeeze'] } }]) {
      expect(ggcIsSqueeze(c as any)).toBe(false);
      expect(ggcCardParam(c as any)).toBeUndefined();
    }
  });
});

describe('🎾 parseGgc — the echo [C2]', () => {
  it('keeps card only for the exact served echo', () => {
    expect(squeezeP().card).toBe(GGC_CARD_SQUEEZE);
    expect(squeezeP().frames.map((f) => f.tf)).toEqual(WATCH_ORDER);
  });
  it('NEGATIVE: absent, "SQUEEZE", true, "watch" → no key at all', () => {
    expect('card' in plainP()).toBe(false);
    for (const junk of ['SQUEEZE', true, 'watch', '', 1, null]) {
      const p = parseGgc(rawSqueeze('FCHL', junk)) as GgcPayload;
      expect('card' in p, String(junk)).toBe(false);
    }
  });
  it('NEGATIVE: the default payload parses toEqual the pre-change object (no new key)', () => {
    const raw = rawPlain('FCHL');
    expect(parseGgc(raw)).toEqual({
      state: 'ok', symbol: 'FCHL', session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
      text: null, frames: (parseGgc(raw) as GgcPayload).frames,
    });
    expect(Object.keys(parseGgc(raw) as object).sort())
      .toEqual(['as_of_et', 'frames', 'in_window', 'is_today', 'session', 'stale', 'state', 'symbol', 'text']);
  });
});

describe('🎾 ggcRowSplit — the ONE test the tile switches on', () => {
  it('true only for a row carrying the echo', () => {
    expect(ggcRowSplit(ggcRow(squeezeCard(), squeezeP(), undefined, { plan: false, squeeze: true }))).toBe(true);
  });
  it('NEGATIVE: null, undefined, a loading row, a plain row, a junk card value', () => {
    expect(ggcRowSplit(null)).toBe(false);
    expect(ggcRowSplit(undefined)).toBe(false);
    const loading: GgwRow = { symbol: 'FCHL', state: 'loading', text: null, from_session: null, as_of_et: null, stale: false, frames: [], rang: [] };
    expect(ggcRowSplit(loading)).toBe(false);
    expect(ggcRowSplit(ggcRow(squeezeCard(), plainP(), undefined, { plan: false }))).toBe(false);
    expect(ggcRowSplit({ ...loading, card: 'SQUEEZE' } as any)).toBe(false);
  });
});

describe('🎾 ggcRow — the echo gates the split [C2]', () => {
  for (const look of [undefined, 'video'] as const) {
    it(`NEGATIVE (${look ?? 'no look'}): squeeze opt on a PLAIN payload deep-equals the row without the opt — no card key, 15 / 5 / 1, no ellipses`, () => {
      const card = squeezeCard();
      const a = ggcRow(card, plainP(), look, { plan: false, squeeze: true });
      const b = ggcRow(card, plainP(), look, { plan: false });
      expect(a).toEqual(b);
      expect('card' in a).toBe(false);
      expect(a.frames.map((f) => f.tf)).toEqual(['15m', '5m', '1m']);
      for (const f of a.frames) expect('ellipses' in f.tile, f.tf).toBe(false);
    });
    it(`NEGATIVE (${look ?? 'no look'}): a squeeze payload WITHOUT the squeeze opt → no card key; deep-equal to the pre-change row (served markers dropped, no ellipses)`, () => {
      const card = squeezeCard();
      for (const opts of [{ plan: false }, { plan: false, squeeze: false }, undefined]) {
        const r = ggcRow(card, squeezeP(), look, opts as any);
        expect('card' in r).toBe(false);
        expect(ggcRowSplit(r)).toBe(false);
        for (const f of r.frames) {
          expect('ellipses' in f.tile, f.tf).toBe(false);
          /* today's rule: the served markers are REPLACED by the card's own on card.tf only */
          if (f.tf !== '5m') expect(f.tile.markers, f.tf).toEqual([]);
          else expect(f.tile.markers.some((m) => m.label?.startsWith('🔀'))).toBe(false);
        }
      }
    });
  }

  for (const look of [undefined, 'video'] as const) {
    it(`the squeeze row (${look ?? 'no look'}): card key; served order; lines on every frame; served markers kept; A+ on card.tf only; ellipses on card.tf only`, () => {
      const card = squeezeCard();
      const p = squeezeP();
      const r = ggcRow(card, p, look, { plan: false, squeeze: true });
      expect(r.card).toBe(GGC_CARD_SQUEEZE);
      expect(r.frames.map((f) => f.tf)).toEqual(p.frames.map((f) => f.tf));
      expect(r.frames.map((f) => f.tf)).toEqual(WATCH_ORDER);
      expect(r.text).toBeNull();
      for (const f of r.frames) {
        const served = p.frames.find((x) => x.tf === f.tf)!;
        expect(f.tile.lines.length, f.tf).toBeGreaterThan(0);
        expect(f.tile.lines, f.tf).toEqual((look === 'video' ? videoLayers(card) : card).lines);
        /* the served cross diamonds are a frame layer — kept on every frame, under both looks */
        expect(f.tile.markers.slice(0, served.tile.markers.length), f.tf).toEqual(served.tile.markers);
        expect(served.tile.markers.length, f.tf).toBeGreaterThan(0);
        const aplus = f.tile.markers.filter((m) => m.kind === 'buy');
        if (f.tf === '5m') {
          expect(aplus.map((m) => m.label)).toEqual(['A+']);
          expect(f.tile.ellipses).toBe(card.ellipses);
        } else {
          expect(aplus, f.tf).toEqual([]);
          expect('ellipses' in f.tile, f.tf).toBe(false);
        }
        /* every frame-level key passes through */
        expect(f.uptrend, f.tf).toEqual(served.uptrend);
        expect(f.ema_cross, f.tf).toEqual(served.ema_cross);
        expect(f.axis, f.tf).toEqual(served.axis);
      }
    });
  }

  it('the card lines reach every frame (his tick 1) — the same array under no look as the card\'s own', () => {
    const card = squeezeCard();
    const r = ggcRow(card, squeezeP(), undefined, { plan: false, squeeze: true });
    for (const f of r.frames) expect(f.tile.lines, f.tf).toBe(card.lines);
  });

  it('the 5m tail reaches the row (prior-day bars + the lead axis), the ellipse stamps sit on its bars', () => {
    const r = ggcRow(squeezeCard(), squeezeP(), undefined, { plan: false, squeeze: true });
    const f5 = r.frames.find((f) => f.tf === '5m')!;
    expect(f5.tile.bars[0].t.startsWith(PRIOR_DAY)).toBe(true);
    expect(f5.axis!.x.length).toBe(f5.tile.bars.length);
    const stamps = new Set(f5.tile.bars.map((b) => b.t));
    for (const e of f5.tile.ellipses!) { expect(stamps.has(e.from_t)).toBe(true); expect(stamps.has(e.to_t)).toBe(true); }
  });

  it('📺: ellipses are read off the RAW card (never through videoLayers); the 🧪 band stripped, the served diamonds kept', () => {
    const card = squeezeCard();
    const r = ggcRow(card, squeezeP(), 'video', { plan: false, squeeze: true });
    const f5 = r.frames.find((f) => f.tf === '5m')!;
    expect(f5.tile.ellipses).toBe(card.ellipses);
    expect(f5.tile.ellipses).toHaveLength(2);
    for (const f of r.frames) {
      expect(f.tile.bands.some((b: any) => b.kind === 'gg_entry'), f.tf).toBe(false);
      expect(f.tile.markers.some((m) => m.kind === 'ema_cross_up' || m.kind === 'ema_cross_dn'), f.tf).toBe(true);
    }
    const plain = ggcRow(card, squeezeP(), undefined, { plan: false, squeeze: true });
    for (const f of plain.frames) expect(f.tile.bands.some((b: any) => b.kind === 'gg_entry'), f.tf).toBe(true);
  });

  it('NEGATIVE: card.ellipses [] or absent → no ellipses key on any frame', () => {
    for (const over of [{ ellipses: [] }, { ellipses: undefined }, { ellipses: null }]) {
      const r = ggcRow(squeezeCard(over), squeezeP(), undefined, { plan: false, squeeze: true });
      for (const f of r.frames) expect('ellipses' in f.tile, f.tf).toBe(false);
    }
  });

  it('NEGATIVE: card.tf 15m (the board\'s 15-min toggle) → the 5m frame carries no ellipses and no A+; the 15m frame does', () => {
    const r = ggcRow(squeezeCard({ tf: '15m' }), squeezeP(), undefined, { plan: false, squeeze: true });
    const f5 = r.frames.find((f) => f.tf === '5m')!;
    const f15 = r.frames.find((f) => f.tf === '15m')!;
    expect('ellipses' in f5.tile).toBe(false);
    expect(f5.tile.markers.some((m) => m.kind === 'buy')).toBe(false);
    expect(f15.tile.ellipses).toHaveLength(2);
    expect(f15.tile.markers.some((m) => m.kind === 'buy')).toBe(true);
  });

  it('NEGATIVE: a card cross marker is never doubled — the card\'s own ema_cross kinds are dropped on card.tf', () => {
    const card = squeezeCard();
    const p = squeezeP();
    const r = ggcRow(card, p, undefined, { plan: false, squeeze: true });
    const f5 = r.frames.find((f) => f.tf === '5m')!;
    const served5 = p.frames.find((f) => f.tf === '5m')!.tile.markers;
    expect(f5.tile.markers.some((m) => m.label === 'card cross up')).toBe(false);
    expect(f5.tile.markers.filter((m) => m.kind === 'ema_cross_up' || m.kind === 'ema_cross_dn'))
      .toEqual(served5.filter((m) => m.kind === 'ema_cross_up' || m.kind === 'ema_cross_dn'));
    expect(f5.tile.markers).toHaveLength(served5.length + 1);
  });

  it('NEGATIVE: a bull_flag card on the squeeze payload with the squeeze opt still splits only by the caller — the hook never passes it', () => {
    /* ggcRow obeys its opts; the hook decides the opt from ggcIsSqueeze(card) (hooks test). A bull-flag card WITHOUT the
       opt on any payload → no card key. */
    expect('card' in ggcRow(bullCard(), squeezeP(), undefined, { plan: false })).toBe(false);
  });

  it('NEGATIVE: the input payload and card are never mutated', () => {
    const card = squeezeCard();
    const p = squeezeP();
    const pc = clone(p);
    const cc = clone(card);
    ggcRow(card, p, 'video', { plan: false, squeeze: true });
    ggcRow(card, p, undefined, { plan: false, squeeze: true });
    expect(p).toEqual(pc);
    expect(card).toEqual(cc);
  });
});
