import { describe, it, expect } from 'vitest';
import { netDirection } from './optionsDirection';

describe('netDirection — plain bull/bear read for the SOIR panel', () => {
  it('uptrend reads Bullish even when the Schaeffer signal is NEUTRAL', () => {
    // the exact ARM case: trend up, fundamentals 77, contrarian signal NEUTRAL
    const nd = netDirection({ pillars: { trend: 'up', fundamental_score: 77 } });
    expect(nd.label).toBe('Bullish');
    expect(nd.color).toBe('#10b981');
    expect(nd.why).toMatch(/77\/100/);
  });

  it('downtrend reads Bearish', () => {
    expect(netDirection({ pillars: { trend: 'down', fundamental_score: 30 } }).label).toBe('Bearish');
  });

  it('falls back to the top-level trend when pillars is absent', () => {
    expect(netDirection({ trend: 'up', sepa_score: 60 }).label).toBe('Bullish');
  });

  it('neutral / unknown trend reads Neutral and never throws', () => {
    expect(netDirection({ pillars: { trend: 'neutral' } }).label).toBe('Neutral');
    expect(netDirection({}).label).toBe('Neutral');
    expect(netDirection({ trend: null, sepa_score: null }).label).toBe('Neutral');
  });
});
