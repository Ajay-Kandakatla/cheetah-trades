/* sepaTabs — the SEPA page's landing-tab rule.
 *
 * Ajay 2026-09-03: "when ever I click on SEPA I need it to go Supply and
 * Demand tab in all pages." The bare link (no ?tab=, no #hash) is what every
 * ticker click in the app produces, so the default here IS the behaviour he
 * asked for. Purposed deep links (?tab=insider from the insider chip, legacy
 * #volume from older cards) must keep working — those are the other half.
 */
import { describe, it, expect } from 'vitest';
import { DEFAULT_TAB, HASH_TO_TAB, TABS, resolveSepaTab, scrollActiveTabIntoView } from './sepaTabs';

describe('resolveSepaTab', () => {
  it('lands on Supply / Demand when nothing is asked for', () => {
    expect(DEFAULT_TAB).toBe('supply');
    expect(resolveSepaTab(null, '')).toBe('supply');
  });

  it('honours a purposed ?tab= deep link', () => {
    expect(resolveSepaTab('insider', '')).toBe('insider');
    expect(resolveSepaTab('setup', '')).toBe('setup');
  });

  it('keeps the old default reachable by asking for it', () => {
    // 'chart' is no longer the default but is still a real tab.
    expect(resolveSepaTab('chart', '')).toBe('chart');
  });

  it('?tab= beats a #hash when both are present', () => {
    expect(resolveSepaTab('insider', '#volume')).toBe('insider');
  });

  it('maps legacy #hash deep links to their merged tabs', () => {
    expect(resolveSepaTab(null, '#volume')).toBe('breakout');
    expect(resolveSepaTab(null, '#dual-momentum')).toBe('ranking');
    expect(resolveSepaTab(null, '#sales')).toBe('analysis');
    expect(resolveSepaTab(null, '#orderflow')).toBe('tape');
  });

  it('accepts a hash with or without the leading # and in any case', () => {
    expect(resolveSepaTab(null, 'insider')).toBe('insider');
    expect(resolveSepaTab(null, '#INSIDER')).toBe('insider');
  });

  it('every hash target is a real tab', () => {
    for (const t of Object.values(HASH_TO_TAB)) expect(TABS).toContain(t);
  });

  // --- negatives ---

  it('falls to Supply / Demand on an unknown ?tab=', () => {
    expect(resolveSepaTab('bogus', '')).toBe('supply');
  });

  it('falls to Supply / Demand on an unknown #hash', () => {
    expect(resolveSepaTab(null, '#bogus')).toBe('supply');
  });

  it('an unknown ?tab= does not swallow a valid #hash', () => {
    // The hash is the older deep-link form; a bad ?tab= must not mask it.
    expect(resolveSepaTab('bogus', '#volume')).toBe('breakout');
  });

  it('is case-sensitive on ?tab= (tabs are written lower-case by setTab)', () => {
    expect(resolveSepaTab('INSIDER', '')).toBe('supply');
  });

  it('survives null / undefined / empty inputs', () => {
    expect(resolveSepaTab(null, null)).toBe('supply');
    expect(resolveSepaTab(undefined, undefined)).toBe('supply');
    expect(resolveSepaTab('', '')).toBe('supply');
    expect(resolveSepaTab('', '#')).toBe('supply');
  });
});

describe('scrollActiveTabIntoView (phone landing on the 4th-of-14 tab)', () => {
  it('scrolls the active button into view and reports it', () => {
    const nav = document.createElement('nav');
    for (const id of ['chart', 'setup', 'analysis', 'supply']) {
      const b = document.createElement('button');
      b.className = 'sepa-tab' + (id === 'supply' ? ' is-active' : '');
      b.textContent = id;
      nav.appendChild(b);
    }
    const calls: unknown[] = [];
    Element.prototype.scrollIntoView = function (this: Element, arg?: unknown) { calls.push([this, arg]); } as any;
    expect(scrollActiveTabIntoView(nav)).toBe(true);
    expect(calls).toHaveLength(1);
    expect((calls[0] as any)[0].textContent).toBe('supply');
    expect((calls[0] as any)[1]).toEqual({ block: 'nearest', inline: 'center' });
  });
  it('is a no-op without a nav, without an active tab, or where scrollIntoView is missing', () => {
    expect(scrollActiveTabIntoView(null)).toBe(false);
    expect(scrollActiveTabIntoView(undefined)).toBe(false);
    const nav = document.createElement('nav');
    nav.innerHTML = '<button class="sepa-tab">chart</button>';
    expect(scrollActiveTabIntoView(nav)).toBe(false);
    const nav2 = document.createElement('nav');
    nav2.innerHTML = '<button class="sepa-tab is-active">supply</button>';
    const saved = Element.prototype.scrollIntoView;
    // @ts-expect-error jsdom without scrollIntoView
    delete Element.prototype.scrollIntoView;
    expect(scrollActiveTabIntoView(nav2)).toBe(false);
    Element.prototype.scrollIntoView = saved;
  });
});
