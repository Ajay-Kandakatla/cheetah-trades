import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/* GlobalSearch — the ⌘K palette (Ajay 2026-09-06). Menu + router navigate +
   the analytics / new-feature hooks are mocked so the palette renders
   standalone; the ranking itself is covered in lib/navSearch.test.ts. */

const navigateMock = vi.fn();
const trackMock = vi.fn();
const markSeenMock = vi.fn();
let isNewRet = false;

vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});
vi.mock('../hooks/useMyMenu', () => ({
  useMyMenu: () => ({
    loaded: true,
    menu: {
      primary:  [{ to: '/morning', label: 'Morning Brief', feature: 'morning' }, { to: '/chart-maps', label: '🗺️ Chart Maps', feature: 'chart-maps' }],
      scanners: [{ to: '/sepa', label: 'SEPA', feature: 'sepa' }],
      misc:     [{ to: '/alerts', label: '🔔 Alerts', feature: 'alerts' }, { to: '/supply-demand', label: 'Supply / Demand', feature: 'supply-demand' }],
      profile:  [{ to: '/notifications', label: 'Notifications', feature: 'notifications' }],
      admin:    [],
      is_owner: true,
      is_admin: true,
    },
  }),
}));
vi.mock('../hooks/useNewFeatures', () => ({
  useNewFeatures: () => ({ isNew: () => isNewRet, markSeen: markSeenMock, isNewRoute: () => false, unseen: [] }),
}));
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => trackMock(k) }));

import { GlobalSearch } from './GlobalSearch';

const subgroupOf = (f?: string) => ({ alerts: 'Signals', 'supply-demand': 'Screeners' }[f ?? ''] ?? 'More');
const renderIt = (props: { compact?: boolean } = {}) =>
  render(<MemoryRouter initialEntries={['/morning']}><GlobalSearch subgroupOf={subgroupOf} {...props} /></MemoryRouter>);

const dialog = () => screen.queryByRole('dialog', { name: 'Search pages' });
const input = () => screen.getByPlaceholderText('Search pages… (e.g. notification)') as HTMLInputElement;
const optionLabels = () => screen.getAllByRole('option').map((o) => o.querySelector('.cm-search__label')?.textContent);

beforeEach(() => { isNewRet = false; });
afterEach(() => { vi.clearAllMocks(); });

describe('GlobalSearch — trigger', () => {
  it('desktop pill reads "Search" with the shortcut hint and opens on click', () => {
    renderIt();
    const btn = screen.getByRole('button', { name: 'Search pages' });
    expect(btn.textContent).toContain('Search');
    expect(btn.querySelector('kbd')?.textContent).toMatch(/⌘K|Ctrl K/);
    expect(dialog()).toBeNull();
    fireEvent.click(btn);
    expect(dialog()).not.toBeNull();
    expect(document.activeElement).toBe(input());
  });

  it('compact trigger is icon-only with aria-label "Search"', () => {
    renderIt({ compact: true });
    const btn = screen.getByRole('button', { name: 'Search' });
    expect(btn.textContent).not.toContain('Search');
    expect(btn.querySelector('kbd')).toBeNull();
    fireEvent.click(btn);
    expect(dialog()).not.toBeNull();
  });

  it('wears the ✨ dot while the feature is unseen and marks it seen on first open', () => {
    isNewRet = true;
    renderIt();
    expect(document.querySelector('.nav-new-dot')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Search pages' }));
    expect(markSeenMock).toHaveBeenCalledWith('global-search');
  });
});

describe('GlobalSearch — shortcuts', () => {
  it('opens on Ctrl+K and toggles closed on a second Ctrl+K', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(dialog()).not.toBeNull();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(dialog()).toBeNull();
  });

  it('opens on ⌘K (meta) too', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'K', metaKey: true });
    expect(dialog()).not.toBeNull();
  });

  it('opens on "/" when focus is not in a text field, and NOT when it is', () => {
    renderIt();
    const field = document.createElement('textarea');
    document.body.appendChild(field);
    fireEvent.keyDown(field, { key: '/' });
    expect(dialog()).toBeNull();
    field.remove();
    fireEvent.keyDown(document.body, { key: '/' });
    expect(dialog()).not.toBeNull();
  });

  it('a plain "k" without a modifier does nothing', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k' });
    expect(dialog()).toBeNull();
  });
});

describe('GlobalSearch — palette', () => {
  it('blank query lists the menu in order with group chips', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    const opts = screen.getAllByRole('option');
    expect(opts).toHaveLength(8);                       // capped at the result limit
    expect(opts[0]).toHaveTextContent('Morning Brief');
    expect(opts[0]).toHaveTextContent('Primary');
    expect(opts[1]).toHaveTextContent('Chart Maps');    // menu order, tabs follow their parent
    expect(opts[2]).toHaveTextContent('Chart Maps ▸ Demand zones');
    fireEvent.change(input(), { target: { value: 'alerts' } });
    const alerts = screen.getAllByRole('option').find((o) => o.textContent?.includes('Alerts'))!;
    expect(alerts).toHaveTextContent('Tools ▸ Signals');
  });

  it('typing filters — "notification" shows Notifications first and Alerts too', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const labels = optionLabels();
    expect(labels[0]).toBe('Notifications');
    expect(labels).toContain('🔔 Alerts');
    expect(labels).not.toContain('Morning Brief');
  });

  it('ArrowDown + Enter navigates to the SECOND result and tracks the pick', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const labels = optionLabels();
    expect(labels.length).toBeGreaterThan(1);
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith('/alerts');
    expect(trackMock).toHaveBeenCalledWith('global-search');
    expect(dialog()).toBeNull();
  });

  it('ArrowUp from the top wraps to the last result', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const n = screen.getAllByRole('option').length;
    fireEvent.keyDown(input(), { key: 'ArrowUp' });
    expect(screen.getAllByRole('option')[n - 1]).toHaveAttribute('aria-selected', 'true');
  });

  it('Enter on the first result navigates there; a click on a row does the same', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'sepa' } });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa');
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'in demand' } });
    fireEvent.click(screen.getByText('Chart Maps ▸ Demand zones'));
    expect(navigateMock).toHaveBeenLastCalledWith('/chart-maps?tab=zones');
  });

  it('Esc closes; backdrop click closes; the panel itself does not', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.keyDown(input(), { key: 'Escape' });
    expect(dialog()).toBeNull();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.mouseDown(dialog()!);
    expect(dialog()).not.toBeNull();
    fireEvent.mouseDown(screen.getByTestId('global-search-backdrop'));
    expect(dialog()).toBeNull();
  });

  it('shows the "No matches" state and Enter then navigates nowhere', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'zzqqxx' } });
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByRole('status')).toHaveTextContent('No matches for “zzqqxx”');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(trackMock).not.toHaveBeenCalled();
  });

  it('reopening starts from a blank query and the first row', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'alerts' } });
    fireEvent.keyDown(input(), { key: 'Escape' });
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(input().value).toBe('');
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true');
  });
});
