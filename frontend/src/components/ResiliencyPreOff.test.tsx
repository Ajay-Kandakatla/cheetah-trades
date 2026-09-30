/* 🛡️ Resiliency — the 🌅 pre-market volume check is OFF (follow-up 2026-09-30).
 *
 * resiliency_tab.PM_VOLUME_VERIFIED = False: the snapshot's pre-market shares
 * and the cached 1-minute bars disagree, so the volume leg is not compared.
 * Every surface he reads must say so plainly — the 🌅 box is greyed with its
 * SERVED one-line reason, and neither the ✨ entry nor the tab blurb promises
 * the 1.5× pre-market volume bar while that flag is False.
 *
 * Negatives: the other boxes (and every Dual Momentum box) are untouched; a
 * ticked OFF box stays clickable so it can be unticked; a malformed reason
 * greys nothing. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { DualMomentumFilters } from './DualMomentumBoardNote';
import { NEW_FEATURES } from '../lib/newFeatures';
import { TAB_META } from '../lib/chartMaps';
import { RES_FILTER_KEYS } from '../lib/resiliencyFilters';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const REASON = 'volume check off until the two volume sources are reconciled';
const item = (key: string, on = false, extra: Record<string, unknown> = {}) =>
  ({ key, label: `L-${key}`, on, pass: 7, fail: 1, no_read: 0, hidden: 0, note: `N-${key}`, ...extra });
const filters = (items: unknown[], active: string[] = []) => ({
  keys: ['t1', 't2', 'eod', 'pre'], active, pool: 8, mode: 'any', mode_param: 'res_mode',
  mode_all_label: 'M-all', passed_all: null, passed_any: null, shown: null, hidden: 0,
  items, line: null, note: 'F-note', measured: false,
});
const mount = (f: unknown, dm = false) => {
  const onToggle = vi.fn();
  render(dm
    ? <DualMomentumFilters filters={f} onToggle={onToggle} />
    : <DualMomentumFilters filters={f} onToggle={onToggle} knownKeys={RES_FILTER_KEYS} testIdPrefix="cm-res" />);
  return onToggle;
};
const box = (id: string) => screen.getByTestId(id) as HTMLInputElement;

afterEach(cleanup);

describe('🌅 OFF box — greyed with the served reason', () => {
  it('disables the 🌅 box, prints the served reason in place of its count', () => {
    const onToggle = mount(filters([item('t1'), item('t2'), item('eod'),
      item('pre', false, { off: true, off_reason: REASON })]));
    expect(box('cm-res-filter-pre').disabled).toBe(true);   // a browser sends no click to it
    expect(screen.getByTestId('cm-res-filter-off-pre').textContent).toBe(` · ${REASON}`);
    const label = box('cm-res-filter-pre').closest('label')!;
    expect(label.className).toContain('cm-dim');
    expect(label.textContent).not.toContain('· 7');
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('NEGATIVE: the other boxes stay live with their counts', () => {
    const onToggle = mount(filters([item('t1'), item('t2'), item('eod'),
      item('pre', false, { off: true, off_reason: REASON })]));
    for (const k of ['t1', 't2', 'eod']) {
      expect(box(`cm-res-filter-${k}`).disabled).toBe(false);
      expect(box(`cm-res-filter-${k}`).closest('label')!.textContent).toContain('· 7');
      expect(screen.queryByTestId(`cm-res-filter-off-${k}`)).toBeNull();
    }
    fireEvent.click(box('cm-res-filter-t1'));
    expect(onToggle).toHaveBeenCalledWith('t1');
  });

  it('NEGATIVE: an OFF box already ticked (a stale URL) stays clickable so it can be unticked', () => {
    const onToggle = mount(filters([item('pre', true, { off: true, off_reason: REASON })], ['pre']));
    expect(box('cm-res-filter-pre').disabled).toBe(false);
    expect(screen.getByTestId('cm-res-filter-off-pre')).toBeTruthy();
    fireEvent.click(box('cm-res-filter-pre'));
    expect(onToggle).toHaveBeenCalledWith('pre');
  });

  it('NEGATIVE: off without a served reason greys nothing (the page never composes one)', () => {
    mount(filters([item('pre', false, { off: true, off_reason: '' })]));
    expect(box('cm-res-filter-pre').disabled).toBe(false);
    expect(screen.queryByTestId('cm-res-filter-off-pre')).toBeNull();
    expect(box('cm-res-filter-pre').closest('label')!.textContent).toContain('· 7');
  });

  it('NEGATIVE: Dual Momentum boxes (no `off` served) render exactly as before', () => {
    mount(filters(['amd', 'zone', 'level'].map((k) => item(k))), true);
    for (const k of ['amd', 'zone', 'level']) {
      expect(box(`cm-dm-filter-${k}`).disabled).toBe(false);
      expect(screen.queryByTestId(`cm-dm-filter-off-${k}`)).toBeNull();
    }
  });
});

describe('no copy promises the pre-market volume bar while PM_VOLUME_VERIFIED is False', () => {
  const PROMISE = /1\.5×|by the same minute|pre-market volume against its own usual volume|pre-market tape is bullish/;

  it('the ✨ entry and the tab blurb say the check is OFF (tied to the backend flag)', async () => {
    const py = await readSource('../backend/chart_maps/resiliency_tab.py');
    const flag = /^PM_VOLUME_VERIFIED = (True|False)\b/m.exec(py);
    expect(flag).not.toBeNull();
    const entry = NEW_FEATURES.find((f) => f.id === 'chart-maps-resiliency-2026-09-30');
    expect(entry).toBeTruthy();
    const blurb = TAB_META.resiliency.blurb;
    if (flag![1] === 'False') {
      for (const txt of [entry!.label, blurb]) {
        expect(txt).not.toMatch(PROMISE);
        expect(txt).toContain('volume check is OFF');
      }
      // the served reason the box prints is the backend's one constant
      expect(py).toContain(`PRE_OFF_REASON = "${REASON}"`);
    }
  });

  it('NEGATIVE: the pin catches the old promise wording', () => {
    const old = "🌅 Bullish tape pre-market — the pre-market print above yesterday's close on at least 1.5× the name's usual pre-market volume by the same minute.";
    expect(old).toMatch(PROMISE);
  });
});
