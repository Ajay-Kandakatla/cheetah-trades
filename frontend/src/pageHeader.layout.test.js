import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

/* Bug 1 (2026-06-23): the shared `.sepa-page__title` header block is a flex
   row (text wrapper + optional action buttons). On phones the buttons
   (Rescan / Refresh / Update) shared the row and starved the flex-basis:0 text
   wrapper down to ~60px, so the `.lede` description broke one-word-per-line on
   Patterns, Breakouts, and the ~20 other pages that use this class.

   jsdom doesn't compute layout or apply @media, and vitest stubs CSS imports
   to empty — so this is a source-guard (the style Ajay uses for contracts
   tests): read styles.css from disk and assert the mobile breakpoint stacks
   the title block to a column so the text wrapper gets full width.

   This is a .js test on purpose: it uses node's fs, and the production build's
   `tsc -b` (allowJs:false) skips .js, so it can't drag @types/node into the
   build. Vitest still runs it. */

// Vitest runs with cwd = the frontend package root.
const css = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8');

describe('page-header description — mobile layout', () => {
  it('base .sepa-page__title is a flex row (the thing that collapses)', () => {
    const base = css.match(/\.sepa-page__title\s*\{[^}]*\}/);
    expect(base).not.toBeNull();
    expect(base[0]).toMatch(/display:\s*flex/);
  });

  it('REGRESSION: the 720px breakpoint stacks the title block to a column', () => {
    // Grab every @media (max-width: 720px) block up to & including the title rule.
    const mobile = css.match(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\.sepa-page__title\s*\{[^}]*\}/g,
    );
    expect(mobile).not.toBeNull();
    const stacks = mobile.some(
      (block) =>
        /\.sepa-page__title\s*\{[^}]*flex-direction:\s*column[^}]*\}/.test(block) &&
        /\.sepa-page__title\s*\{[^}]*align-items:\s*stretch[^}]*\}/.test(block),
    );
    expect(stacks).toBe(true);
  });
});
