/* AdminTodos — WHO sees the page, and the bundle-leak guard (2026-09-20).
 *
 * The page used to decide admin-ness by comparing `user.email` against a
 * hardcoded Gmail address. That literal shipped in the JS bundle — anyone
 * could grep the static assets for the owner's personal address. The gate is
 * now the server flag `is_admin` from /auth/me, which is `auth.is_admin_email`
 * — the SAME function main.py uses to stealth-404 /admin/todos and
 * /admin/todos/recipients, so the client and the server agree.
 *
 * `is_primary_admin` is deliberately NOT the flag here: it is one address,
 * narrower than the endpoint's own gate, and would 404 a house co-owner the
 * backend lets through.
 *
 * The user hook is mocked; /auth/me never runs. `fetch` is stubbed because the
 * page loads its recipient allowlist on mount.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import type { CurrentUser } from '../hooks/useUser';

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({
  useCurrentUser: () => ({ user: userRet, loading: userRet === null }),
}));

import AdminTodosPage from './AdminTodos';
import pageSrc from './AdminTodos.tsx?raw';

const base: CurrentUser = {
  email: 'someone@example.com',
  display_name: 'Someone',
  given_name: 'Some',
  picture: null,
  is_default_user: false,
  is_admin: false,
};

/** Recipient allowlist the backend would serve an admin. Placeholder
 *  addresses only — a real one in this file would itself trip the
 *  contracts.mjs bundle scan, which walks every .ts/.tsx under src/. */
const RECIPIENTS = ['owner@example.com', 'cohouse@example.com'];

function stubFetch(status: number) {
  const f = vi.fn(async () => ({
    ok: status === 200,
    status,
    json: async () => ({ recipients: RECIPIENTS }),
  })) as unknown as typeof fetch;
  vi.stubGlobal('fetch', f);
  return f;
}

beforeEach(() => { userRet = null; });
afterEach(() => { userRet = null; vi.unstubAllGlobals(); });

describe('AdminTodos — the gate is the server flag', () => {
  it('renders the form for a user carrying is_admin', async () => {
    userRet = { ...base, is_admin: true };
    stubFetch(200);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Admin · cross-user todos')).toBeInTheDocument();
    expect(screen.queryByText('Not found.')).toBeNull();
    // The allowlist arrived and the picker is populated.
    await waitFor(() => expect(screen.getByText(/cohouse@example\.com/)).toBeInTheDocument());
  });

  it('renders the form for the primary admin too (is_primary_admin is not the gate)', async () => {
    userRet = { ...base, is_admin: true, is_primary_admin: true };
    stubFetch(200);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Admin · cross-user todos')).toBeInTheDocument();
  });

  // ---- NEGATIVES ----------------------------------------------------------

  it('stealth-404s a signed-in user without the flag', async () => {
    userRet = { ...base, is_admin: false };
    stubFetch(200);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Not found.')).toBeInTheDocument();
    expect(screen.queryByText('Admin · cross-user todos')).toBeNull();
  });

  it('stealth-404s when /auth/me omits is_admin entirely (older payload)', async () => {
    userRet = { ...base } as CurrentUser;
    delete (userRet as Partial<CurrentUser>).is_admin;
    stubFetch(200);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Not found.')).toBeInTheDocument();
  });

  it('an email that merely LOOKS like the owner grants nothing without the flag', async () => {
    // The pre-fix code decided on the address. Now the address is inert:
    // same email, flag false → 404.
    userRet = { ...base, email: RECIPIENTS[0], is_admin: false };
    stubFetch(200);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Not found.')).toBeInTheDocument();
  });

  it('still 404s when the flag is true but the backend refuses the allowlist', async () => {
    // Backend is the real gate: a 404 from /admin/todos/recipients wins over
    // an optimistic client flag.
    userRet = { ...base, is_admin: true };
    stubFetch(404);
    render(<AdminTodosPage />);
    expect(await screen.findByText('Not found.')).toBeInTheDocument();
  });

  it('shows nothing admin-ish while the user fetch is still in flight', async () => {
    userRet = null;
    stubFetch(200);
    await act(async () => { render(<AdminTodosPage />); });
    // `user` null → neither the 404 branch nor a denied flag; the page must
    // not assert either verdict yet.
    expect(screen.queryByText('Not found.')).toBeNull();
  });
});

describe('AdminTodos — the owner address never reaches the bundle', () => {
  it('carries no email-address literal in its source', () => {
    // Mirrors the contracts.mjs scan of src/ for the owner's address, stated
    // generally so no personal address is spelled in this file either — the
    // scan walks every .ts/.tsx under src/, tests included.
    const literals = pageSrc.match(/(['"`])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\1/g) || [];
    expect(literals).toEqual([]);
  });

  it('reads the flag rather than comparing user.email', () => {
    expect(/const isAdmin = !!user\?\.is_admin;/.test(pageSrc)).toBe(true);
    expect(/user\?\.email \|\| ''\)\.toLowerCase\(\) ===/.test(pageSrc)).toBe(false);
  });
});
