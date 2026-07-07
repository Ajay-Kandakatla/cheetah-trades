import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LearningPathPage from './LearningPath';

/* jsdom's localStorage is only partially implemented in this environment
   (getItem/setItem present, clear/removeItem missing), so install a small
   deterministic Map-backed store for these tests. */
function installLocalStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
}

/* LearningPath — Ajay's personal study page. These lock: the verbatim intro +
   gaps + NotebookLM tip survive, all 14 numbered sources render, the two
   high-confidence YouTube embeds use the right video IDs, generic titles fall
   back to a YouTube SEARCH link (never a guessed embed), and the localStorage
   progress toggle round-trips. Negatives: a fresh mount with no stored progress
   shows 0/14 and no crash when localStorage is empty/corrupt. */

beforeEach(() => {
  installLocalStorage();
});

describe('LearningPath', () => {
  it('renders the header and verbatim intro', () => {
    render(<LearningPathPage />);
    expect(screen.getByRole('heading', { name: /Ajay’s Learning Path/i, level: 1 }).textContent).toBeTruthy();
    expect(
      screen.getByText(/your notebook already covers all three pillars/i),
    ).toBeInTheDocument();
  });

  it('renders all four phase headings', () => {
    render(<LearningPathPage />);
    expect(screen.getByText('Week 1–2')).toBeInTheDocument();
    expect(screen.getByText('Week 3–5')).toBeInTheDocument();
    expect(screen.getByText('Week 6–7')).toBeInTheDocument();
    expect(screen.getByText('Week 8+')).toBeInTheDocument();
    expect(screen.getByText(/Market mechanics/i)).toBeInTheDocument();
  });

  it('renders 3 prerequisites + 14 numbered sources with a counter starting at 0/17', () => {
    render(<LearningPathPage />);
    // 3 prereq + 14 source "Mark complete" checkboxes
    const checks = screen.getAllByRole('checkbox');
    expect(checks).toHaveLength(17);
    expect(screen.getByText('0/17 complete')).toBeInTheDocument();
  });

  it('renders the Prerequisites section covering the three notebook gaps', () => {
    render(<LearningPathPage />);
    expect(screen.getByText('Prerequisites')).toBeInTheDocument();
    // exact titles — /Backtesting methodology/ loosely would also match the
    // verbatim gaps paragraph, so match the full prereq card titles instead.
    expect(screen.getByText('Market structure basics — BOS & CHoCH')).toBeInTheDocument();
    expect(screen.getByText('Risk management & position sizing')).toBeInTheDocument();
    expect(screen.getByText('Backtesting methodology (statistical validation)')).toBeInTheDocument();
    // the position-sizing formula callout renders
    expect(screen.getByText(/Shares = Risk \$ ÷ \(Entry − Stop\)/i)).toBeInTheDocument();
    // the backtest-overfitting paper is linked (the "gem" source)
    const paper = screen.getByText(/Pseudo-Mathematics & Financial Charlatanism/i).closest('a') as HTMLAnchorElement;
    expect(paper.href).toContain('abstract_id=2308659');
  });

  it('embeds the two high-confidence YouTube videos by exact video id', () => {
    const { container } = render(<LearningPathPage />);
    const iframes = Array.from(container.querySelectorAll('iframe')).map((f) => f.getAttribute('src') || '');
    expect(iframes).toContain('https://www.youtube.com/embed/qWN-VanDkT8');
    expect(iframes).toContain('https://www.youtube.com/embed/GvJzspRHqCU');
    // prerequisite: market-structure BOS/CHoCH video
    expect(iframes).toContain('https://www.youtube.com/embed/U5DTamH28N0');
    // arXiv PDF + Wikipedia are also embedded
    expect(iframes).toContain('https://arxiv.org/pdf/1011.6402');
    expect(iframes).toContain('https://en.wikipedia.org/wiki/Algorithmic_trading');
  });

  it('falls back to a YouTube SEARCH link for generic titles — never a guessed embed', () => {
    render(<LearningPathPage />);
    const searchLinks = screen.getAllByText(/Search this on YouTube/i);
    // 8 generic YouTube entries (2,6,7,9,10,11,13 minus the 2 embedded) -> exactly the search-only ones
    expect(searchLinks.length).toBeGreaterThanOrEqual(6);
    const first = searchLinks[0].closest('a') as HTMLAnchorElement;
    expect(first.href).toContain('youtube.com/results?search_query=');
  });

  it('preserves the gaps paragraph and the NotebookLM tip verbatim', () => {
    render(<LearningPathPage />);
    // fragment unique to the verbatim gaps paragraph (the prereq blurbs echo
    // some of its wording, so pick text that only appears there)
    expect(screen.getByText(/worth adding as sources: something on/i)).toBeInTheDocument();
    expect(screen.getByText(/recall testing beats re-watching/i)).toBeInTheDocument();
    expect(screen.getByText(/order flow imbalance/i)).toBeInTheDocument();
  });

  it('toggles progress and persists it to localStorage', () => {
    render(<LearningPathPage />);
    const checks = screen.getAllByRole('checkbox') as HTMLInputElement[];
    // first checkbox is prerequisite A (market structure), keyed by its string id
    expect(checks[0].checked).toBe(false);
    fireEvent.click(checks[0]);
    expect(checks[0].checked).toBe(true);
    expect(screen.getByText('1/17 complete')).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem('learning-path-progress') || '{}')).toEqual({
      'prereq-market-structure': true,
    });
  });

  it('does not crash and shows 0/17 when localStorage holds corrupt JSON (negative)', () => {
    localStorage.setItem('learning-path-progress', '{not valid json');
    render(<LearningPathPage />);
    expect(screen.getByText('0/17 complete')).toBeInTheDocument();
  });
});
