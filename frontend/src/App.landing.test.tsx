import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from './hooks/useUser';

/* "/" for the primary owner → 🚩 Gajjala's tab (Ajay 2026-11-10: "Then default my landing page to Gajjala's tab in
 * chartmaps on the app always."). SmartLanding waits for features + menu + /auth/me, resolves through
 * pickLanding(f.features, !!menu.is_admin), then ownerLanding(…, is_primary_admin). Everyone else keeps today's target.
 * NEGATIVES: plain user, co-owner (is_admin, not primary), a non-chart-maps winner, user still loading (loader, no
 * navigation), a failed /auth/me (today's target, never a stuck loader). */

let features = { loaded: true, features: new Set<string>(), catalog: [], email: null as string | null };
let menuState = { loaded: true, menu: { is_admin: false } as any };
let userState: { user: CurrentUser | null; loading: boolean } = { user: null, loading: false };

vi.mock('./hooks/useMyFeatures', () => ({ useMyFeatures: () => features, hasFeatureOrLoading: () => true }));
vi.mock('./hooks/useMyMenu', () => ({ useMyMenu: () => menuState }));
vi.mock('./hooks/useUser', () => ({ useCurrentUser: () => userState }));

import { SmartLanding } from './App';

const mkUser = (is_admin: boolean, is_primary_admin?: boolean): CurrentUser => ({
  email: 'someone@example.test', display_name: 'X', given_name: null, picture: null,
  is_default_user: false, is_admin, ...(is_primary_admin === undefined ? {} : { is_primary_admin }),
});

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

function landAt(): string | null {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<SmartLanding />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
  return screen.queryByTestId('where')?.textContent ?? null;
}

const ALL = ['chart-maps', 'sepa-global', 'sepa', 'portfolio', 'morning'];

beforeEach(() => {
  features = { loaded: true, features: new Set(ALL), catalog: [], email: null };
  menuState = { loaded: true, menu: { is_admin: false } };
  userState = { user: null, loading: false };
});

describe('SmartLanding', () => {
  it("the primary owner lands on /chart-maps?tab=gajjala", () => {
    menuState = { loaded: true, menu: { is_admin: true } };
    userState = { user: mkUser(true, true), loading: false };
    expect(landAt()).toBe('/chart-maps?tab=gajjala');
  });

  it('NEGATIVE: a plain user lands on the bare /chart-maps', () => {
    userState = { user: mkUser(false, false), loading: false };
    expect(landAt()).toBe('/chart-maps');
  });

  it('NEGATIVE: a user payload with no is_primary_admin key keeps the bare path', () => {
    userState = { user: mkUser(false), loading: false };
    expect(landAt()).toBe('/chart-maps');
  });

  it('NEGATIVE: a co-owner (is_admin true, is_primary_admin false) keeps the bare path', () => {
    menuState = { loaded: true, menu: { is_admin: true } };
    userState = { user: mkUser(true, false), loading: false };
    expect(landAt()).toBe('/chart-maps');
  });

  it('NEGATIVE: a non-chart-maps winner never gets a tab param, even for the primary owner', () => {
    features = { loaded: true, features: new Set(['sepa-global', 'sepa']), catalog: [], email: null };
    menuState = { loaded: true, menu: { is_admin: true } };
    userState = { user: mkUser(true, true), loading: false };
    expect(landAt()).toBe('/sepa-global');
  });

  it('NEGATIVE: user still loading → the loader, no navigation', () => {
    menuState = { loaded: true, menu: { is_admin: true } };
    userState = { user: null, loading: true };
    expect(landAt()).toBeNull();
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('NEGATIVE: features or menu still loading → the loader, no navigation', () => {
    userState = { user: mkUser(true, true), loading: false };
    features = { ...features, loaded: false };
    expect(landAt()).toBeNull();
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it("NEGATIVE: a failed /auth/me read → today's target, never a stuck loader", () => {
    menuState = { loaded: true, menu: { is_admin: true } };
    userState = { user: null, loading: false };
    expect(landAt()).toBe('/chart-maps');
    expect(screen.queryByText('Loading…')).toBeNull();
  });

  it('NEGATIVE: nothing accessible → the 404, never a redirect', () => {
    features = { loaded: true, features: new Set(), catalog: [], email: null };
    userState = { user: mkUser(true, true), loading: false };
    expect(landAt()).toBeNull();
    expect(screen.getByText('Not found.')).toBeInTheDocument();
  });
});
