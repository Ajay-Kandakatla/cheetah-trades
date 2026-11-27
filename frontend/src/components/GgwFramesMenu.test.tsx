/* GgwFramesMenu — 👀 Watch frames dropdown (2026-11-27, spec watch5m rev 2 §3.3). Ajay: "Give me a drop down or multi
 * select like button to toggle 1 mins and 15 mins 5 mins by default..". NEGATIVES: no options → nothing rendered; the
 * lone on-frame cannot be unticked; a stored unserved frame never shows ticked; Escape closes the menu and a `document`
 * bubble listener (GgwStretch's) does NOT see that key — a second Escape does. */
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GGW_FRAMES_EVERY, GGW_FRAMES_WORDS, ggwToggleFrame, ggwVolAvgTitle } from '../lib/ggwFrames';
import { GgwFramesMenu } from './GgwFramesMenu';

const OPTS = [{ tf: '1m', label: '1-min' }, { tf: '5m', label: '5-min' }, { tf: '15m', label: '15-min' }];

function mk(over: Partial<Parameters<typeof GgwFramesMenu>[0]> = {}) {
  const onToggle = vi.fn();
  const onVolAvg = vi.fn();
  const r = render(
    <GgwFramesMenu options={OPTS} on={['5m']} onToggle={onToggle} volAvg={false} onVolAvg={onVolAvg}
                   title={GGW_FRAMES_WORDS.boardTitle} testid="ggw-frames" {...over} />,
  );
  return { ...r, onToggle, onVolAvg };
}
const btn = () => screen.getByTestId('ggw-frames-btn');
const box = (tf: string) => screen.getByTestId(`ggw-frames-${tf}`) as HTMLInputElement;

describe('GgwFramesMenu', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('closed by default; the button shows the on-frames\' served labels + ▾ (default "5-min ▾")', () => {
    mk();
    expect(screen.queryByTestId('ggw-frames-menu')).toBeNull();
    expect(btn()).toHaveTextContent('5-min ▾');
    expect(btn().textContent).toBe('5-min ▾');
    expect(btn()).toHaveAttribute('aria-expanded', 'false');
    expect(btn()).toHaveAttribute('aria-haspopup', 'true');
    expect(btn()).toHaveAttribute('title', GGW_FRAMES_WORDS.boardTitle);
    expect(btn()).toHaveClass('ggw-btn', 'ggw-frames-btn');
    expect(screen.getByTestId('ggw-frames').tagName).toBe('SPAN');
    expect(screen.getByTestId('ggw-frames')).toHaveClass('ggw-frames');
  });

  it('two frames on → both labels in served order, joined " · "', () => {
    mk({ on: ['15m', '1m'] });
    expect(btn().textContent).toBe('1-min · 15-min ▾');
  });

  it('opens a role=group with one checkbox per option then the volume item; NOT a <details>', () => {
    const { container } = mk();
    fireEvent.click(btn());
    const menu = screen.getByTestId('ggw-frames-menu');
    expect(menu).toHaveAttribute('role', 'group');
    expect(btn()).toHaveAttribute('aria-expanded', 'true');
    const items = menu.querySelectorAll('label.ggw-frames-item');
    expect(items).toHaveLength(4);
    expect(Array.from(items).map((l) => l.textContent)).toEqual(['1-min', '5-min', '15-min', GGW_FRAMES_WORDS.volAvg]);
    expect(items[3]).toHaveClass('ggw-frames-item--vol');
    expect(items[3]).toHaveAttribute('title', ggwVolAvgTitle());
    expect(box('5m').checked).toBe(true);
    expect(box('1m').checked).toBe(false);
    expect(box('15m').checked).toBe(false);
    expect(container.querySelector('details')).toBeNull();
  });

  it('a tick calls onToggle(tf) and the menu stays open', () => {
    const { onToggle } = mk();
    fireEvent.click(btn());
    fireEvent.click(box('15m'));
    expect(onToggle).toHaveBeenCalledWith('15m');
    expect(screen.getByTestId('ggw-frames-menu')).toBeInTheDocument();
  });

  it('the lone on-frame\'s box is disabled with the title; NEGATIVE: a click on it calls nothing', () => {
    const { onToggle } = mk();
    fireEvent.click(btn());
    expect(box('5m').disabled).toBe(true);
    expect(box('5m')).toHaveAttribute('title', GGW_FRAMES_WORDS.lastOn);
    expect(box('1m').disabled).toBe(false);
    expect(box('1m')).not.toHaveAttribute('title');
    fireEvent.click(box('5m'));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('the every-token → every box ticked, none disabled', () => {
    mk({ on: [GGW_FRAMES_EVERY] });
    expect(btn().textContent).toBe('1-min · 5-min · 15-min ▾');
    fireEvent.click(btn());
    for (const o of OPTS) { expect(box(o.tf).checked).toBe(true); expect(box(o.tf).disabled).toBe(false); }
  });

  it('NEGATIVE: a stored unserved frame never shows ticked — the 5-min fallback is', () => {
    mk({ on: ['3m'] });
    expect(btn().textContent).toBe('5-min ▾');
    fireEvent.click(btn());
    expect(box('5m').checked).toBe(true);
    expect(box('5m').disabled).toBe(true);
    expect(screen.queryByTestId('ggw-frames-3m')).toBeNull();
  });

  it('the volume item reflects volAvg and calls onVolAvg', () => {
    const { onVolAvg, rerender, onToggle } = mk();
    fireEvent.click(btn());
    const v = screen.getByTestId('ggw-frames-volavg') as HTMLInputElement;
    expect(v.checked).toBe(false);
    fireEvent.click(v);
    expect(onVolAvg).toHaveBeenCalledTimes(1);
    rerender(<GgwFramesMenu options={OPTS} on={['5m']} onToggle={onToggle} volAvg onVolAvg={onVolAvg}
                            title={GGW_FRAMES_WORDS.boardTitle} testid="ggw-frames" />);
    expect((screen.getByTestId('ggw-frames-volavg') as HTMLInputElement).checked).toBe(true);
  });

  it('wired to ggwToggleFrame: ticks stay in served order and the menu stays open across ticks', () => {
    function Live() {
      const [on, setOn] = useState<string[]>(['5m']);
      return <GgwFramesMenu options={OPTS} on={on} onToggle={(tf) => setOn((p) => ggwToggleFrame(OPTS.map((o) => o.tf), p, tf))}
                            volAvg={false} onVolAvg={() => {}} title={GGW_FRAMES_WORDS.stretchTitle} testid="ggw-sframes" />;
    }
    render(<Live />);
    fireEvent.click(screen.getByTestId('ggw-sframes-btn'));
    fireEvent.click(screen.getByTestId('ggw-sframes-15m'));
    fireEvent.click(screen.getByTestId('ggw-sframes-1m'));
    expect(screen.getByTestId('ggw-sframes-btn').textContent).toBe('1-min · 5-min · 15-min ▾');
    fireEvent.click(screen.getByTestId('ggw-sframes-5m'));
    expect(screen.getByTestId('ggw-sframes-btn').textContent).toBe('1-min · 15-min ▾');
    expect(screen.getByTestId('ggw-sframes-menu')).toBeInTheDocument();
  });

  it('closes on the button and on a pointerdown outside; a pointerdown inside keeps it open', () => {
    mk();
    fireEvent.click(btn());
    fireEvent.click(btn());
    expect(screen.queryByTestId('ggw-frames-menu')).toBeNull();
    fireEvent.click(btn());
    fireEvent.pointerDown(box('1m'));
    expect(screen.getByTestId('ggw-frames-menu')).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByTestId('ggw-frames-menu')).toBeNull();
  });

  it('Escape closes the menu and a document BUBBLE listener does NOT see it; a second Escape does reach it', () => {
    const seen: string[] = [];
    const bubble = (e: KeyboardEvent) => { seen.push(e.key); };
    document.addEventListener('keydown', bubble);
    try {
      mk();
      fireEvent.click(btn());
      fireEvent.keyDown(box('1m'), { key: 'Escape' });
      expect(screen.queryByTestId('ggw-frames-menu')).toBeNull();
      expect(seen).toEqual([]);
      fireEvent.keyDown(document.body, { key: 'Escape' });
      expect(seen).toEqual(['Escape']);
    } finally {
      document.removeEventListener('keydown', bubble);
    }
  });

  it('NEGATIVE: another key while open passes through and keeps the menu open', () => {
    const seen: string[] = [];
    const bubble = (e: KeyboardEvent) => { seen.push(e.key); };
    document.addEventListener('keydown', bubble);
    try {
      mk();
      fireEvent.click(btn());
      fireEvent.keyDown(box('1m'), { key: 'ArrowRight' });
      expect(seen).toEqual(['ArrowRight']);
      expect(screen.getByTestId('ggw-frames-menu')).toBeInTheDocument();
    } finally {
      document.removeEventListener('keydown', bubble);
    }
  });

  it('NEGATIVE: no options → renders nothing', () => {
    const { container } = mk({ options: [] });
    expect(container.innerHTML).toBe('');
    expect(screen.queryByTestId('ggw-frames')).toBeNull();
  });
});
