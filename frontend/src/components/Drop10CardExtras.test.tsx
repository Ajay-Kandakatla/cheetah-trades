/* Drop10CardExtras — the served 💥 line and its fold under one 🔻 card. */
import { describe, expect, it, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import Drop10CardExtras from './Drop10CardExtras';
import FIXTURE from './__fixtures__/drop10_tab_2026_10_02.json';
import type { CmTile } from '../lib/chartMaps';

const TILES = (FIXTURE as unknown as { default: { tiles: CmTile[] } }).default.tiles;
const IART = TILES.find((t) => t.symbol === 'IART') as CmTile;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

afterEach(() => cleanup());

describe('Drop10CardExtras', () => {
  it('prints the served 💥 line and, folded, the group line and every on-file item with its link', () => {
    render(<Drop10CardExtras tile={IART} />);
    const d = IART.drop10!;
    expect(screen.getByTestId('cm-drop10-hit-IART').textContent).toBe(d.hit.text);
    const fold = screen.getByTestId('cm-drop10-fold-IART');
    expect(fold.tagName).toBe('DETAILS');
    expect((fold as HTMLDetailsElement).open).toBe(false);
    expect(screen.getByTestId('cm-drop10-group-IART').textContent).toBe(d.group!.line);
    d.items.forEach((it, j) => {
      const p = screen.getByTestId(`cm-drop10-item-IART-${j}`);
      expect(p.textContent).toBe(it.text);
      const a = p.querySelector('a');
      if (it.url) expect(a?.getAttribute('href')).toBe(it.url); else expect(a).toBeNull();
    });
    expect(screen.queryByTestId('cm-drop10-empty-IART')).toBeNull();
  });

  it('NEGATIVE: no item on file prints the served "nothing on file" sentence, never an empty fold', () => {
    const t = clone(IART);
    t.drop10!.items = [];
    t.drop10!.empty = 'nothing on file: earnings, 8-K / offering; guidance: this app stores none';
    render(<Drop10CardExtras tile={t} />);
    expect(screen.getByTestId('cm-drop10-empty-IART').textContent).toBe(t.drop10!.empty);
    expect(screen.queryByTestId('cm-drop10-item-IART-0')).toBeNull();
  });

  it('NEGATIVE: an item with no text is dropped; an item with no url is plain text', () => {
    const t = clone(IART);
    t.drop10!.items = [
      { kind: 'news', date: '2026-10-02', text: '', url: 'https://x.test', source: 'n' },
      { kind: 'news', date: '2026-10-02', text: 'T-1', url: null, source: 'n' },
    ];
    render(<Drop10CardExtras tile={t} />);
    expect(screen.getByTestId('cm-drop10-item-IART-0').textContent).toBe('T-1');
    expect(screen.getByTestId('cm-drop10-item-IART-0').querySelector('a')).toBeNull();
    expect(screen.queryByTestId('cm-drop10-item-IART-1')).toBeNull();
  });

  it('NEGATIVE: a tile with no drop10 block renders nothing', () => {
    const t = clone(IART);
    delete (t as Partial<CmTile>).drop10;
    const { container } = render(<Drop10CardExtras tile={t} />);
    expect(container.innerHTML).toBe('');
  });
});
