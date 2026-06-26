import { describe, it, expect } from 'vitest';
import { aiSectorSortValue } from './breakoutSort';

describe('aiSectorSortValue — breakout list leads with AI-sector winners', () => {
  it('any AI-sector name outranks any non-AI name', () => {
    const chips = aiSectorSortValue({ ai_sector_rank: 0, conviction: 1 });   // weak chips name
    const nonAi = aiSectorSortValue({ ai_sector_rank: null, is_buyable: true, conviction: 99 });
    expect(chips).toBeGreaterThan(nonAi);   // sector beats even a buyable 99-conviction non-AI name
  });

  it('higher-priority sector (lower rank) sorts above a lower-priority one', () => {
    const chips = aiSectorSortValue({ ai_sector_rank: 0, conviction: 10 });   // chips
    const water = aiSectorSortValue({ ai_sector_rank: 5, conviction: 90 });   // cooling
    expect(chips).toBeGreaterThan(water);
  });

  it('within the same sector, buyable + conviction break the tie', () => {
    const a = aiSectorSortValue({ ai_sector_rank: 2, is_buyable: true, conviction: 50 });
    const b = aiSectorSortValue({ ai_sector_rank: 2, is_buyable: false, conviction: 95 });
    expect(a).toBeGreaterThan(b);   // buyable (1e9) dominates the 0-100 conviction
  });

  it('null rank is treated as non-AI (99) and never throws', () => {
    expect(aiSectorSortValue({})).toBe(0);
  });
});
