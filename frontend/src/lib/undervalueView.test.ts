/* 🏷️ Under Value vs peers — the `?uv=` param (2026-09-29, Ajay: "Use the same tab actually"). */
import { describe, expect, it } from 'vitest';
import { boardQuery } from './chartMaps';
import { parseUvView, uvViewParam, UV_VIEW_PARAM, UV_VIEW_PEERS, UV_VIEW_PSG } from './undervalueView';

describe('parseUvView / uvViewParam', () => {
  it('reads peers in any case or spacing', () => {
    expect(parseUvView('peers')).toBe(UV_VIEW_PEERS);
    expect(parseUvView(' PEERS ')).toBe(UV_VIEW_PEERS);
  });
  it('NEGATIVE: everything else is the 💎 default', () => {
    for (const v of [null, undefined, '', 'bogus', 'psg', 'peer', 'peers,psg']) {
      expect(parseUvView(v as string | null | undefined)).toBe(UV_VIEW_PSG);
    }
  });
  it('only the peers view writes a URL value', () => {
    expect(uvViewParam(UV_VIEW_PSG)).toBeNull();
    expect(uvViewParam(UV_VIEW_PEERS)).toBe('peers');
    expect(UV_VIEW_PARAM).toBe('uv');
  });
});

describe('boardQuery uv', () => {
  it('rides on the undervalue tab when peers', () => {
    expect(boardQuery({ tab: 'undervalue', uvView: 'peers', limit: 80 })).toContain('uv=peers');
    expect(boardQuery({ tab: 'undervalue', uvView: 'peers', phase: 'reached', limit: 80 }))
      .toBe('tab=undervalue&phase=reached&uv=peers&limit=80');
  });
  it('NEGATIVE: psg / absent / another tab send no uv', () => {
    expect(boardQuery({ tab: 'undervalue', uvView: 'psg', limit: 80 })).not.toContain('uv=');
    expect(boardQuery({ tab: 'undervalue', limit: 80 })).not.toContain('uv=');
    expect(boardQuery({ tab: 'gabbar', uvView: 'peers', limit: 80 })).not.toContain('uv=');
    expect(boardQuery({ tab: 'undervalue', uvView: 'PEERS', limit: 80 })).not.toContain('uv=');
  });
  it('NEGATIVE: the default query is byte-identical to the pre-toggle output', () => {
    // Captured on the untouched chartMaps.ts (origin/main 8d62a4c) before the edit.
    expect(boardQuery({ tab: 'undervalue', limit: 80 })).toBe('tab=undervalue&limit=80');
    expect(boardQuery({ tab: 'undervalue', limit: 80, phase: 'reached', sort: 'rvol', minTier: 'any' }))
      .toBe('tab=undervalue&phase=reached&limit=80&sort=rvol&min_tier=any');
  });
});
