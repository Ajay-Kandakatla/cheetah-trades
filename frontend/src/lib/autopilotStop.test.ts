import { describe, it, expect } from 'vitest';
import { stopStatusView } from './autopilotStop';

describe('stopStatusView — Auto-Pilot Stop-status badge', () => {
  it('working broker stop → green "Stop set"', () => {
    const v = stopStatusView({ stop_status: 'working', watchdog_stop: 93 });
    expect(v.kind).toBe('working');
    expect(v.label).toBe('✓ Stop set');
    expect(v.tone).toBe('good');
  });

  it('watchdog (Alpaca held-leg case) → amber, NOT "unprotected", names the enforced price', () => {
    const v = stopStatusView({ stop_status: 'watchdog', watchdog_stop: 157.25 });
    expect(v.kind).toBe('watchdog');
    expect(v.label).toContain('engine');
    expect(v.tone).toBe('warn');
    expect(v.tooltip).toContain('$157.25');
    // The whole point: a watchdog-covered position must NOT read as "No stop".
    expect(v.label).not.toBe('No stop');
  });

  it('none → red "No stop" (truly uncovered)', () => {
    const v = stopStatusView({ stop_status: 'none' });
    expect(v.kind).toBe('none');
    expect(v.label).toBe('No stop');
    expect(v.tone).toBe('bad');
  });

  it('no Flatten/UNPROTECTED/protected vocabulary leaks into any label', () => {
    for (const st of ['working', 'watchdog', 'none'] as const) {
      const { label } = stopStatusView({ stop_status: st });
      expect(label.toLowerCase()).not.toMatch(/flatten|unprotected|protected/);
    }
  });

  // ── negative / fallback ─────────────────────────────────────────────────────
  it('falls back to the legacy protected boolean when stop_status is absent', () => {
    expect(stopStatusView({ protected: true }).kind).toBe('working');
    expect(stopStatusView({ protected: false }).kind).toBe('none');
  });

  it('watchdog with no price still renders without crashing', () => {
    const v = stopStatusView({ stop_status: 'watchdog', watchdog_stop: null });
    expect(v.kind).toBe('watchdog');
    expect(v.tooltip).toContain('the stop');
  });
});
