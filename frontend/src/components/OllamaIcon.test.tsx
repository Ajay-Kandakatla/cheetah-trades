import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { CurrentUser } from '../hooks/useUser';

/* OllamaIcon (Ajay 2026-09-14: "Give me a private icon for ajaykandakatl
   email for chatting with ollama model"). The only contract that matters is
   WHO: the primary admin and nobody else — and specifically not a house
   owner who carries `is_admin`. The user hook is mocked; the icon renders
   inside a MemoryRouter because it is a NavLink. */
let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: userRet === null }) }));

import { OllamaIcon, OLLAMA_ICON, OLLAMA_ICON_TITLE } from './OllamaIcon';

const base: CurrentUser = {
  email: 'someone@example.com', display_name: 'Someone', given_name: 'Some',
  picture: null, is_default_user: false, is_admin: false,
};

function mount(compact = false, at = '/') {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <OllamaIcon compact={compact} />
    </MemoryRouter>,
  );
}

afterEach(() => { userRet = null; });

describe('OllamaIcon — who sees it', () => {
  it('renders for the primary admin and links to /ollama', () => {
    userRet = { ...base, is_admin: true, is_primary_admin: true };
    mount();
    const a = screen.getByTestId('ollama-icon') as HTMLAnchorElement;
    expect(a.getAttribute('href')).toBe('/ollama');
    expect(a.getAttribute('title')).toBe(OLLAMA_ICON_TITLE);
    expect(a.textContent).toContain(OLLAMA_ICON);
    expect(a.textContent).toContain('Ollama');
    expect(a.className).not.toContain('is-active');
  });

  it('renders NOTHING for a house owner who only has is_admin', () => {
    userRet = { ...base, is_admin: true, is_primary_admin: false };
    mount();
    expect(screen.queryByTestId('ollama-icon')).toBeNull();
  });

  it('renders nothing when the flag is absent (older /auth/me payload)', () => {
    userRet = { ...base, is_admin: true };
    mount();
    expect(screen.queryByTestId('ollama-icon')).toBeNull();
  });

  it('renders nothing for a stranger and nothing while the user is loading', () => {
    userRet = { ...base };
    const { unmount } = mount();
    expect(screen.queryByTestId('ollama-icon')).toBeNull();
    unmount();
    userRet = null;
    mount();
    expect(screen.queryByTestId('ollama-icon')).toBeNull();
  });
});

describe('OllamaIcon — shape', () => {
  it('compact drops the word, keeps the glyph and the accessible name', () => {
    userRet = { ...base, is_primary_admin: true };
    mount(true);
    const a = screen.getByTestId('ollama-icon');
    expect(a.className).toContain('ollama-icon--compact');
    expect(a.textContent).toBe(OLLAMA_ICON);
    expect(a.getAttribute('aria-label')).toBe(OLLAMA_ICON_TITLE);
  });

  it('outlines itself on the /ollama page', () => {
    userRet = { ...base, is_primary_admin: true };
    mount(false, '/ollama');
    expect(screen.getByTestId('ollama-icon').className).toContain('is-active');
  });

  it('never carries an email address', () => {
    userRet = { ...base, email: 'ajay@example.com', is_primary_admin: true };
    mount();
    expect(screen.getByTestId('ollama-icon').outerHTML).not.toMatch(/@/);
  });
});
