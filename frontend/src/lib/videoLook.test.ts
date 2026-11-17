/* 📺 videoLayers + the video look's constants (spec ggvideo 2026-11-17, WP-B pc-video-look).
 * Ajay 2026-11-16: "the graphs in the videos are so clear like I can easily identify the trend"; 2026-11-17 "Yes to all
 * defaults" (#4: hide the 🧪 band, the ➖ diamonds, the 📶/🎾 circles; keep the A+ tag, trigger/stop, the now line, volume). */
import { describe, expect, it } from 'vitest';
import {
  VIDEO_LOOK_CURVE_TONES, VIDEO_LOOK_H, VIDEO_LOOK_LINE_TONES, VIDEO_LOOK_MARKER_KINDS, VIDEO_PANEL_STYLE, videoLayers,
} from './videoLook';
import { GGW_PANEL } from './gajjalaWatch';
import type { CmTile } from './chartMaps';
import SRC from './videoLook.ts?raw';

const bars = [
  { t: '2026-11-16 09:35', o: 1, h: 1.1, l: 0.9, c: 1.05, v: 100 },
  { t: '2026-11-16 09:40', o: 1.05, h: 1.2, l: 1, c: 1.15, v: 200 },
];
const full = (): CmTile & Record<string, unknown> => ({
  symbol: 'ONFO', href: '/sepa/ONFO', bars, why: 'why', stats: [{ k: 'k', v: 'v' }],
  bands: [{ kind: 'gg_entry', lo: 0.95, hi: 1.1, label: 'entry zone' }],
  lines: [
    { price: 1.1, label: 'TRIGGER 1.10', tone: 'buy', text: '1.10' },
    { price: 0.9, label: 'STOP 0.90', tone: 'stop', text: '0.90' },
    { price: 1.15, label: 'now', tone: 'now' },
    { price: 1.4, label: 'TARGET 1.40', tone: 'target' },
    { price: 1.0, label: 'kc', tone: 'keltner' },
  ],
  curves: [
    { tone: 'ema9', label: '9 EMA', values: [1, 1.05] },
    { tone: 'ema21', label: '21 EMA', values: [1, 1.02] },
    { tone: 'keltner', label: 'KC mid', values: [1, 1.01] },
  ],
  markers: [
    { date: bars[1].t, kind: 'buy', label: 'A+' },
    { date: bars[0].t, kind: 'ema_cross_up', label: 'x' },
    { date: bars[1].t, kind: 'ema_cross_dn', label: 'y' },
    { date: bars[0].t, kind: 'kc_sq' },
    { date: bars[0].t, label: 'no kind' },
  ],
  ellipses: [{ kind: 'base', from_t: bars[0].t, to_t: bars[1].t, lo: 0.9, hi: 1.2, label: 'base', tone: 'structure' }],
  amd_raids: { raids: [] } as unknown as CmTile['amd_raids'],
  vol_avg: { len: 50, values: [null, 150] },
  gajjala: { setup: 'horizontal_fade' },
  axis: { slots: 192, x: [66, 67] },
  badges: [{ text: 'b', tone: 'good' }],
});

describe('videoLayers', () => {
  it('keeps only the listed tones / kinds; bands + ellipses []; amd_raids absent', () => {
    const v = videoLayers(full());
    expect(v.lines.map((l) => l.tone)).toEqual(['buy', 'stop', 'now']);
    expect(v.curves!.map((c) => c.tone)).toEqual(['ema9', 'ema21']);
    expect(v.markers.map((m) => m.kind)).toEqual(['buy']);
    expect(v.bands).toEqual([]);
    expect(v.ellipses).toEqual([]);
    expect('amd_raids' in v).toBe(false);
  });

  it('the kept line / curve / marker objects are the SAME references (filtered, never copied)', () => {
    const t = full();
    const v = videoLayers(t);
    expect(v.lines[0]).toBe(t.lines[0]);
    expect(v.curves![1]).toBe(t.curves![1]);
    expect(v.markers[0]).toBe(t.markers[0]);
  });

  it('every other key is the SAME reference', () => {
    const t = full();
    const v = videoLayers(t) as Record<string, unknown>;
    const stripped = new Set(['lines', 'curves', 'markers', 'bands', 'ellipses', 'amd_raids']);
    const others = Object.keys(t).filter((k) => !stripped.has(k));
    expect(others.length).toBeGreaterThan(8);
    for (const k of others) expect(v[k]).toBe((t as Record<string, unknown>)[k]);
    expect(Object.keys(v).filter((k) => !stripped.has(k)).sort()).toEqual(others.sort());
  });

  it('NEGATIVE: the input is deep-equal after the call (never mutated) and the result is a NEW object', () => {
    const t = full();
    const before = structuredClone(t);
    const v = videoLayers(t);
    expect(t).toEqual(before);
    expect(v).not.toBe(t);
    expect(t.lines).toHaveLength(5);
    expect(t.bands).toHaveLength(1);
    expect('amd_raids' in t).toBe(true);
  });

  it('NEGATIVE: missing / null layer arrays → [] (never throws); null entries dropped', () => {
    const t = { symbol: 'X', href: '/x', bars, why: '', stats: [] } as unknown as CmTile;
    const v = videoLayers(t);
    expect(v.lines).toEqual([]);
    expect(v.curves).toEqual([]);
    expect(v.markers).toEqual([]);
    const n = videoLayers({ ...full(), lines: [null as never, { price: 1, label: 'B', tone: 'buy' }] });
    expect(n.lines.map((l) => l.tone)).toEqual(['buy']);
  });

  it('NEGATIVE: a tone outside the lists never survives (target / keltner / ema_cross_* / kc_sq / no kind)', () => {
    const v = videoLayers(full());
    expect(v.lines.some((l) => l.tone === 'target' || l.tone === 'keltner')).toBe(false);
    expect(v.curves!.some((c) => c.tone === 'keltner')).toBe(false);
    expect(v.markers.some((m) => m.kind !== 'buy')).toBe(false);
  });
});

describe('the video look constants', () => {
  it('the lists his call #4 named', () => {
    expect([...VIDEO_LOOK_LINE_TONES]).toEqual(['buy', 'stop', 'now']);
    expect([...VIDEO_LOOK_CURVE_TONES]).toEqual(['ema9', 'ema21']);
    expect([...VIDEO_LOOK_MARKER_KINDS]).toEqual(['buy']);
    expect(VIDEO_LOOK_H).toBe(283);
  });

  it('VIDEO_PANEL_STYLE = GGW_PANEL (ONE source), --ink included', () => {
    const s = VIDEO_PANEL_STYLE as Record<string, string>;
    expect(s.background).toBe(GGW_PANEL.bg);
    expect(s['--surface']).toBe(GGW_PANEL.bg);
    expect(s['--bg-raised']).toBe(GGW_PANEL.bg);
    expect(s['--bg-sunken']).toBe(GGW_PANEL.bg);
    expect(s['--cm-card']).toBe(GGW_PANEL.bg);
    expect(s['--rule']).toBe(GGW_PANEL.grid);
    expect(s['--ink']).toBe(GGW_PANEL.text);
    expect(s['--text-muted']).toBe(GGW_PANEL.dim);
    expect(s['--positive']).toBe(GGW_PANEL.up);
    expect(s['--negative']).toBe(GGW_PANEL.down);
  });

  it('NEGATIVE: the source carries no clock literal and no retyped panel rgb()', () => {
    expect(SRC).not.toContain('04' + ':00');
    expect(SRC).not.toMatch(/rgb\(/);
  });
});
