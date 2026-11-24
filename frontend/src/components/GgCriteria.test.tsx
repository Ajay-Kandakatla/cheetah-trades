/* GgCriteriaList — the ONE rule-row printer (2026-11-24, spec ggrun §3.5 / §4 fe-run). A PURE MOVE of the 🚩 card's
 * inline list: its HTML equals the legacy inline markup for ✓ / ✗ / · rows, in the given order. NEGATIVES: empty / null /
 * undefined → nothing; both rule-row surfaces (the 🚩 card and the 👀 ▶ Rules panel) mount it and neither calls
 * criteriaText( itself; it imports no CSS. */
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GgCriteriaList } from './GgCriteria';
import { criteriaText, type GgCriterion } from '../lib/gajjala';
import critSrc from './GgCriteria.tsx?raw';
import ggBoardSrc from './GajjalaBoard.tsx?raw';
import runSrc from './GgwRunRules.tsx?raw';

const ROWS: GgCriterion[] = [
  { key: 'k1', label: 'served row one', ok: true, value: 'served value', need: 'served need' },
  { key: 'k2', label: 'served row two', ok: false, value: null, need: 'served need two' },
  { key: 'k3', label: 'served row three', ok: null, value: 'served value three', need: null },
];

/** The 🚩 card's inline markup as it was before the move (GajjalaBoard.tsx, 2026-11-23). */
function Legacy({ criteria }: { criteria: GgCriterion[] | undefined }) {
  return criteria?.length ? (
    <ul className="gg-criteria" data-testid="gg-criteria">
      {criteria.map((c) => (
        <li key={c.key} className={c.ok === true ? 'gg-ok' : c.ok === false ? 'gg-miss' : 'gg-unjudged'}>
          {criteriaText(c)}
        </li>
      ))}
    </ul>
  ) : null;
}

afterEach(() => cleanup());

describe('GgCriteriaList', () => {
  it('HTML equals the legacy inline markup for ✓ / ✗ / · rows', () => {
    const a = render(<div><GgCriteriaList criteria={ROWS} /></div>).container.innerHTML;
    cleanup();
    const b = render(<div><Legacy criteria={ROWS} /></div>).container.innerHTML;
    expect(a).toBe(b);
    expect(a).toContain('class="gg-ok"');
    expect(a).toContain('class="gg-miss"');
    expect(a).toContain('class="gg-unjudged"');
  });
  it('rows in the given order, each the criteriaText of that row', () => {
    const { container } = render(<GgCriteriaList criteria={[ROWS[2], ROWS[0], ROWS[1]]} />);
    const lis = Array.from(container.querySelectorAll('li'));
    expect(lis.map((l) => l.textContent)).toEqual([criteriaText(ROWS[2]), criteriaText(ROWS[0]), criteriaText(ROWS[1])]);
    expect(lis[1].textContent).toBe('✓ served row one — served value (served need)');
  });
  it('NEGATIVE: empty / null / undefined → nothing at all', () => {
    for (const c of [[], null, undefined]) {
      const { container } = render(<div><GgCriteriaList criteria={c} /></div>);
      expect(container.innerHTML).toBe('<div></div>');
      cleanup();
    }
  });
  it('NEGATIVE: both surfaces mount it and neither prints a row itself; it imports no CSS', () => {
    for (const [f, s] of [['GajjalaBoard.tsx', ggBoardSrc], ['GgwRunRules.tsx', runSrc]] as const) {
      expect(s, f).toContain('<GgCriteriaList');
      expect(s, f).not.toContain('criteriaText(');
    }
    expect(ggBoardSrc.match(/<GgCriteriaList criteria=\{read\.criteria\} \/>/g)).toHaveLength(1);
    expect(ggBoardSrc).not.toMatch(/className="gg-criteria"/);
    expect(critSrc).not.toMatch(/\.css['"]/);
  });
});
