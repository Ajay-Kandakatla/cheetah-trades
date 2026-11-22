// Review 2026-11-22 finding 1: the backend's setup_block served {setup, label, state_label, source} with no `text`, so
// parseSetupTag returned null and the 🎾 chip never drew. The golden below is written by the backend and pinned
// field-for-field by backend/tests/test_gajjala_watch_sections_2026_11_22.py::test_setup_block_matches_the_fe_golden —
// both sides read the SAME file.
import { describe, expect, it } from 'vitest';
import golden from './__fixtures__/ggwSetupBlock.golden.json';
import { parseRowOrg } from './gajjalaWatch';

describe('the served setup block parses into a chip', () => {
  it('the backend golden renders the 🎾 chip text and the state on hover', () => {
    const org = parseRowOrg({ group: 'auto', setup: golden });
    expect(org?.setup).toEqual({ text: golden.text, title: golden.title });
    expect(org?.setup?.text).toContain('🎾');
  });

  it('NEGATIVE: the pre-fix shape (no text) still draws nothing', () => {
    const { text: _t, title: _ti, ...old } = golden;
    expect(parseRowOrg({ group: 'auto', setup: old })?.setup).toBeNull();
  });
});
