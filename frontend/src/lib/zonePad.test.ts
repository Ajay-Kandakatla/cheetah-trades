import { describe, it, expect } from 'vitest';
import {
  clipStrip, keyPadStrip, padPctText, padStrip, padTitle, PAD_KINDS, KEY_PAD_TONES,
} from './zonePad';

/* 🧱 The 1% pad under demand floors and support key levels (Ajay 2026-09-30:
 * "if the demand zone or key level is 133, it holding at 132"). The pad is
 * SERVED (backend level_pad.pad_fields / key_levels.chart_lines); these helpers
 * only accept or refuse it. Worked example from the spec: band 133.00–135.00,
 * pad_lo 131.67; PWL 133.00, pad_price 131.67. */

describe('padStrip — a served demand pad', () => {
  it('the worked example: demand 133–135 with pad_lo 131.67 → strip 131.67–133', () => {
    expect(padStrip({ kind: 'demand', lo: 133, hi: 135, pad_lo: 131.67 }))
      .toEqual({ lo: 131.67, hi: 133 });
  });

  it('the board band on the per-ticker views pads too', () => {
    expect(padStrip({ kind: 'board_demand', lo: 133, pad_lo: 131.67 }))
      .toEqual({ lo: 131.67, hi: 133 });
  });

  it('pads exactly the backend-padded kinds', () => {
    expect([...PAD_KINDS]).toEqual(['demand', 'board_demand']);
  });

  // --- negatives ---
  it('NEGATIVE: no pad_lo, null, NaN, Infinity or a string → no strip', () => {
    for (const pad_lo of [undefined, null, NaN, Infinity, -Infinity, '131.67', {}]) {
      expect(padStrip({ kind: 'demand', lo: 133, pad_lo } as never)).toBeNull();
    }
  });

  it('NEGATIVE: pad_lo at or above the drawn lo → no strip (a pad is UNDER the floor)', () => {
    expect(padStrip({ kind: 'demand', lo: 133, pad_lo: 133 })).toBeNull();
    expect(padStrip({ kind: 'demand', lo: 133, pad_lo: 133.5 })).toBeNull();
  });

  it('NEGATIVE: zero / negative pad_lo or a junk lo → no strip', () => {
    expect(padStrip({ kind: 'demand', lo: 133, pad_lo: 0 })).toBeNull();
    expect(padStrip({ kind: 'demand', lo: 133, pad_lo: -1 })).toBeNull();
    expect(padStrip({ kind: 'demand', lo: NaN, pad_lo: 131.67 })).toBeNull();
    expect(padStrip({ kind: 'demand', lo: '133', pad_lo: 131.67 } as never)).toBeNull();
  });

  it('NEGATIVE: supply, board_supply, base, fvg or a missing kind never draw a pad', () => {
    for (const kind of ['supply', 'board_supply', 'base', 'fvg_demand', 'neutral', undefined, '']) {
      expect(padStrip({ kind, lo: 133, pad_lo: 131.67 })).toBeNull();
    }
  });

  it('NEGATIVE: null / non-object → null, never a throw', () => {
    expect(padStrip(null)).toBeNull();
    expect(padStrip(undefined)).toBeNull();
    expect(padStrip('demand' as never)).toBeNull();
  });
});

describe('keyPadStrip — a served 🔑 support-low pad', () => {
  it('PWL 133 with pad_price 131.67 → strip 131.67–133', () => {
    expect(keyPadStrip({ tone: 'key', price: 133, pad_price: 131.67 }))
      .toEqual({ lo: 131.67, hi: 133 });
    expect(keyPadStrip({ tone: 'key_broken', price: 133, pad_price: 131.67 }))
      .toEqual({ lo: 131.67, hi: 133 });
    expect([...KEY_PAD_TONES]).toEqual(['key', 'key_broken']);
  });

  // --- negatives ---
  it('NEGATIVE: a high (pad_price null / absent) draws nothing', () => {
    expect(keyPadStrip({ tone: 'key', price: 140, pad_price: null })).toBeNull();
    expect(keyPadStrip({ tone: 'key', price: 140 })).toBeNull();
  });

  it('NEGATIVE: pad_price at / above the level, NaN, string → nothing', () => {
    expect(keyPadStrip({ tone: 'key', price: 133, pad_price: 133 })).toBeNull();
    expect(keyPadStrip({ tone: 'key', price: 133, pad_price: 134 })).toBeNull();
    expect(keyPadStrip({ tone: 'key', price: 133, pad_price: NaN })).toBeNull();
    expect(keyPadStrip({ tone: 'key', price: 133, pad_price: '131.67' } as never)).toBeNull();
    expect(keyPadStrip({ tone: 'key', price: NaN, pad_price: 131.67 })).toBeNull();
  });

  it('NEGATIVE: a non-key tone carrying pad_price draws nothing', () => {
    for (const tone of ['stop', 'buy', 'neutral', 'now', undefined]) {
      expect(keyPadStrip({ tone, price: 133, pad_price: 131.67 })).toBeNull();
    }
    expect(keyPadStrip(null)).toBeNull();
  });
});

describe('clipStrip — only the part on the chart', () => {
  it('inside the domain → unchanged', () => {
    expect(clipStrip({ lo: 131.67, hi: 133 }, { lo: 120, hi: 140 })).toEqual({ lo: 131.67, hi: 133 });
  });
  it('partly under the domain → cut at the domain floor', () => {
    expect(clipStrip({ lo: 131.67, hi: 133 }, { lo: 132, hi: 140 })).toEqual({ lo: 132, hi: 133 });
  });
  // --- negatives ---
  it('NEGATIVE: wholly off the chart → null, never pinned to the edge', () => {
    expect(clipStrip({ lo: 131.67, hi: 133 }, { lo: 133, hi: 140 })).toBeNull();
    expect(clipStrip({ lo: 131.67, hi: 133 }, { lo: 140, hi: 150 })).toBeNull();
    expect(clipStrip({ lo: 131.67, hi: 133 }, { lo: 100, hi: 120 })).toBeNull();
  });
  it('NEGATIVE: junk strip or domain → null', () => {
    expect(clipStrip(null, { lo: 1, hi: 2 })).toBeNull();
    expect(clipStrip({ lo: 1, hi: 2 }, null)).toBeNull();
    expect(clipStrip({ lo: 1, hi: 2 }, { lo: NaN, hi: 3 })).toBeNull();
  });
});

describe('padTitle / padPctText — words from served numbers only', () => {
  it('the band title names the served pct', () => {
    expect(padTitle('Support', { lo: 131.67, hi: 133 }, 1))
      .toBe('Support pad 131.67–133.00 — 1% under the drawn edge, where stops sit');
  });
  it('NEGATIVE: no served pct → no typed "1%", and never NaN / undefined / bounce', () => {
    const t = padTitle('Support', { lo: 131.67, hi: 133 }, undefined);
    expect(t).toBe('Support pad 131.67–133.00 — under the drawn edge, where stops sit');
    for (const bad of [NaN, null, '1', 0, -1]) {
      const s = padTitle('Support', { lo: 131.67, hi: 133 }, bad);
      expect(s).not.toMatch(/NaN|undefined|null|bounce|1%/i);
    }
    expect(padPctText(NaN)).toBe('');
    expect(padPctText(0)).toBe('');
  });
});
