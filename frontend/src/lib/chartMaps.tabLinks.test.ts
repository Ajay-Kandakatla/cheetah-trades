/* ⌘-click on Chart Maps tabs (Ajay 2026-09-24): "add Command clicks to the
 * Tabs in chart maps so I can open new tabs.. Of that specific Section".
 *
 * The two pure halves. `tabSearch` is the ONE address both a plain click and a
 * ⌘-click land on, so they can never disagree; `isPlainLeftClick` is the one
 * click the strip keeps for itself — every other click is the browser's. */
import { describe, expect, it } from 'vitest';
import { isPlainLeftClick, tabSearch } from './chartMaps';

describe('tabSearch — the address of one tab', () => {
  it('sets the tab', () => {
    expect(tabSearch(new URLSearchParams(''), 'hot_sectors')).toBe('tab=hot_sectors');
  });

  it('keeps everything else, so the new browser tab opens set up like this one', () => {
    const q = new URLSearchParams(tabSearch(
      new URLSearchParams('tab=support&symbol=NVDA&window=1y&days=252'), 'zones'));
    expect(q.get('tab')).toBe('zones');
    expect(q.get('symbol')).toBe('NVDA');
    expect(q.get('window')).toBe('1y');
    expect(q.get('days')).toBe('252');
  });

  it('drops `pattern` — it names a pattern INSIDE Past Winners and nothing else', () => {
    const q = new URLSearchParams(tabSearch(
      new URLSearchParams('tab=winners&pattern=cup_handle'), 'vcp'));
    expect(q.has('pattern')).toBe(false);
    expect(q.get('tab')).toBe('vcp');
  });

  it('NEGATIVE: never mutates the params it was handed (React Router owns them)', () => {
    const live = new URLSearchParams('tab=winners&pattern=cup_handle');
    tabSearch(live, 'vcp');
    expect(live.toString()).toBe('tab=winners&pattern=cup_handle');
  });

  it('replaces an existing tab rather than appending a second one', () => {
    expect(new URLSearchParams(tabSearch(new URLSearchParams('tab=vcp'), 'ict'))
      .getAll('tab')).toEqual(['ict']);
  });
});

describe('isPlainLeftClick — the one click the strip keeps', () => {
  const click = (over: Partial<{ button: number; metaKey: boolean; ctrlKey: boolean;
                                 shiftKey: boolean; altKey: boolean }> = {}) => ({
    button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...over,
  });

  it('an unmodified primary click switches in place', () => {
    expect(isPlainLeftClick(click())).toBe(true);
  });

  it.each([
    ['⌘ (mac new tab)', { metaKey: true }],
    ['Ctrl (windows/linux new tab)', { ctrlKey: true }],
    ['⇧ (new window)', { shiftKey: true }],
    ['⌥ (download)', { altKey: true }],
    ['middle button', { button: 1 }],
    ['secondary button', { button: 2 }],
  ])('NEGATIVE: %s is the browser’s, never intercepted', (_label, over) => {
    expect(isPlainLeftClick(click(over))).toBe(false);
  });
});
