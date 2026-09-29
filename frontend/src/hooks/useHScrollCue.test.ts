/* The "more columns →" cue (🔥 Hottest, 2026-09-28). Ajay: "Can you fix the
 * horizontal columns hiding". */
import { createElement, useRef } from 'react';
import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hScrollCue, useHScrollCue } from './useHScrollCue';

const cols = [
  { label: 'Today', left: 200, width: 100 },
  { label: '5 days', left: 300, width: 100 },
  { label: 'Quality', left: 400, width: 100 },
  { label: 'Next ER', left: 500, width: 100 },
];

describe('hScrollCue (pure)', () => {
  it('NEGATIVE: a table that fits exactly shows no cue', () => {
    expect(hScrollCue({ scrollLeft: 0, clientWidth: 600, scrollWidth: 600, cols }))
      .toEqual({ left: false, right: false, offRight: [] });
  });
  it('NEGATIVE: 1px of overflow is within tolerance', () => {
    expect(hScrollCue({ scrollLeft: 0, clientWidth: 599, scrollWidth: 600, cols }).right).toBe(false);
  });
  it('overflow names the off-right columns in print order', () => {
    expect(hScrollCue({ scrollLeft: 0, clientWidth: 420, scrollWidth: 600, cols }))
      .toEqual({ left: false, right: true, offRight: ['Quality', 'Next ER'] });
  });
  it('scrolled to the end: nothing off-right, content under the sticky column', () => {
    expect(hScrollCue({ scrollLeft: 180, clientWidth: 420, scrollWidth: 600, cols }))
      .toEqual({ left: true, right: false, offRight: [] });
  });
});

/* A box with a table and a header row, geometry mocked per element. */
function Box({ labels }: { labels: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const cue = useHScrollCue(ref, labels, [labels.length]);
  return createElement('div', null,
    createElement('div', { 'data-testid': 'cue' }, JSON.stringify({ right: cue.right, offRight: cue.offRight })),
    createElement('div', { ref, 'data-testid': 'box', onScroll: cue.onScroll },
      createElement('table', null,
        createElement('thead', null, createElement('tr', null,
          createElement('th', null, 'Sector / Name'),
          createElement('th', null, 'Today'),
          createElement('th', null, 'Quality ⓘ 2▼'))))));
}

const proto = HTMLElement.prototype;
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function mockGeometry() {
  vi.spyOn(proto, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return this.getAttribute('data-testid') === 'box' ? 300 : 0;
  });
  vi.spyOn(proto, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return this.getAttribute('data-testid') === 'box' ? 500 : 0;
  });
  vi.spyOn(proto, 'offsetLeft', 'get').mockImplementation(function (this: HTMLElement) {
    const t = this.textContent || '';
    return t.startsWith('Today') ? 100 : t.startsWith('Quality') ? 250 : 0;
  });
  vi.spyOn(proto, 'offsetWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return this.tagName === 'TH' ? 150 : 0;
  });
}

describe('useHScrollCue (hook)', () => {
  it('observes BOTH the scroll box and its <table> (opening a group widens the table only)', () => {
    const targets: Element[] = [];
    class FakeRO {
      constructor(_cb: ResizeObserverCallback) { /* noop */ }
      observe(el: Element) { targets.push(el); }
      unobserve() { /* noop */ }
      disconnect() { /* noop */ }
    }
    vi.stubGlobal('ResizeObserver', FakeRO);
    const { getByTestId } = render(createElement(Box, { labels: ['Today', 'Quality'] }));
    const box = getByTestId('box');
    expect(targets).toContain(box);
    expect(targets).toContain(box.querySelector('table'));
  });

  it('labels come from the argument, never textContent (NEGATIVE: "Quality ⓘ 2▼" → "Quality")', () => {
    mockGeometry();
    const { getByTestId } = render(createElement(Box, { labels: ['Today', 'Quality'] }));
    const cue = JSON.parse(getByTestId('cue').textContent || '{}');
    expect(cue.right).toBe(true);
    expect(cue.offRight).toEqual(['Quality']);
    expect(cue.offRight.join(' ')).not.toMatch(/ⓘ|2▼/);
  });

  it('writes --hs-box-w on the box as its clientWidth', () => {
    mockGeometry();
    const { getByTestId } = render(createElement(Box, { labels: ['Today', 'Quality'] }));
    expect(getByTestId('box').style.getPropertyValue('--hs-box-w')).toBe('300px');
  });
});
