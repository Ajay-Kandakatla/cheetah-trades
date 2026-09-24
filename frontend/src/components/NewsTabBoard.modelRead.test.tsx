import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NewsTabBoard from './NewsTabBoard';
import { MODEL_WRITING, ageLabel, nameList } from '../lib/newsTab';

/* 🧠 Model read on the 📰 News tab (2026-09-24). Ajay: "You can use the
 * abliterated model we have via hermes. For this tab". The server
 * (backend/chart_maps/news_model_read.py) stores the local model's bull AND
 * bear case; this card prints it UNDER the gauge's own word, never in place
 * of it, and every other block still draws when it is missing. */

const NOTE = "Written by the local model from this tab's own facts — its opinion of the headlines against "
  + "the Market Gauge. UNMEASURED, not a forecast; gates nothing. The market word above is the gauge's, "
  + 'not the model\'s.';

const READ = {
  lean: 'bearish',
  bull: 'Oil strength is lifting energy while the weekly gauge stays constructive for the broad tape.',
  bear: 'Rising yields weigh on the index and technology is lagging the equal-weight benchmark today.',
  sectors_bullish: ['Energy'], sectors_bearish: ['Technology'], watch: ['Core PCE', 'Jobless claims'],
  model: 'huihui_ai/Qwen3.8-abliterated:27b', provider: 'local', generated_at_iso: '2026-09-24T19:00:00Z',
};

function payload(model_read: any) {
  return {
    verdict: { ok: true, daily: { score: 60, state_label: 'Caution', word: 'mixed' },
               weekly: { score: 84, state_label: 'Constructive', word: 'bullish' } },
    macro: { ok: true, days: 14, events: [] },
    sectors: { ok: true, benchmark: { symbol: 'RSP' }, d1: { live: true }, rows: [] },
    headlines: { ok: true, items: [], window_hours: 36 },
    model_read, note: 'Not advice.', measured: false,
  };
}

async function mount(model_read: any) {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => payload(model_read) })));
  render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
  await screen.findByTestId('news-tab-board');
}

describe('NewsTabBoard 🧠 model read', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints the lean, BOTH cases, who wrote it and how old it is', async () => {
    await mount({ ok: true, read: READ, age_sec: 720, refreshing: false, note: NOTE });
    expect(screen.getByTestId('nt-model-lean')).toHaveTextContent('lean: bearish');
    expect(screen.getByTestId('nt-model-lean').className).toContain('nt-word--down');
    expect(screen.getByTestId('nt-model-bull')).toHaveTextContent(READ.bull);
    expect(screen.getByTestId('nt-model-bear')).toHaveTextContent(READ.bear);
    expect(screen.getByTestId('nt-model-meta')).toHaveTextContent('read by huihui_ai/Qwen3.8-abliterated:27b · 12 min ago');
    expect(screen.getByTestId('nt-model-sectors')).toHaveTextContent('news-bullish Energy');
    expect(screen.getByTestId('nt-model-sectors')).toHaveTextContent('news-bearish Technology');
    expect(screen.getByTestId('nt-model-watch')).toHaveTextContent('watch: Core PCE · Jobless claims');
    expect(screen.getByTestId('nt-model-note')).toHaveTextContent('UNMEASURED, not a forecast');
  });

  it('sits UNDER the gauge word — the market read still says the gauge\'s words', async () => {
    await mount({ ok: true, read: READ, age_sec: 60, note: NOTE });
    const board = screen.getByTestId('news-tab-board');
    const sections = Array.from(board.querySelectorAll('section')).map((s) => s.getAttribute('data-testid'));
    expect(sections.indexOf('nt-section-verdict')).toBeLessThan(sections.indexOf('nt-section-model'));
    expect(screen.getByTestId('nt-card-daily')).toHaveTextContent('mixed');
    expect(screen.getByTestId('nt-card-weekly')).toHaveTextContent('bullish');
  });

  it('a stored read with a refresh running shows both the read and the writing line', async () => {
    await mount({ ok: true, read: READ, age_sec: 4000, refreshing: true, note: NOTE });
    expect(screen.getByTestId('nt-model-bull')).toBeInTheDocument();
    expect(screen.getByTestId('nt-model-writing')).toHaveTextContent(MODEL_WRITING);
    expect(screen.getByTestId('nt-model-meta')).toHaveTextContent('1 h ago');
  });

  it('NEGATIVE — no read yet, model writing: the reason and the writing line, nothing invented', async () => {
    await mount({ ok: false, read: null, refreshing: true, reason: 'no model read written yet', note: NOTE });
    expect(screen.getByTestId('nt-model-reason')).toHaveTextContent('no model read written yet');
    expect(screen.getByTestId('nt-model-writing')).toBeInTheDocument();
    expect(screen.queryByTestId('nt-model-lean')).toBeNull();
    expect(screen.queryByTestId('nt-model-bull')).toBeNull();
  });

  it('NEGATIVE — a refused last attempt is printed with its reason beside the older read', async () => {
    await mount({ ok: true, read: READ, age_sec: 7200, last_error: 'model wrote numbers not in its facts (5.2)', note: NOTE });
    expect(screen.getByTestId('nt-model-last-error')).toHaveTextContent('last attempt refused — model wrote numbers not in its facts (5.2)');
  });

  it('NEGATIVE — model_read missing entirely (older server) → one reason line, the other blocks draw', async () => {
    await mount(undefined);
    expect(screen.getByTestId('nt-model-reason')).toHaveTextContent('model read unavailable');
    expect(screen.getByTestId('nt-card-daily')).toBeInTheDocument();
    expect(screen.getByTestId('nt-section-sectors')).toBeInTheDocument();
  });

  it('NEGATIVE — ok:true but read null is treated as no read', async () => {
    await mount({ ok: true, read: null, reason: null });
    expect(screen.getByTestId('nt-model-reason')).toHaveTextContent('model read unavailable');
  });

  it('NEGATIVE — a timed-out leg prints the server reason in place', async () => {
    await mount({ ok: false, reason: 'still loading — timed out after 8s, refresh' });
    expect(screen.getByTestId('nt-model-reason')).toHaveTextContent('timed out after 8s');
    expect(screen.queryByTestId('nt-model-writing')).toBeNull();
  });

  it('NEGATIVE — junk in the lists and lean never renders as an object, NaN or undefined', async () => {
    await mount({ ok: true, read: { ...READ, lean: '', sectors_bullish: [{ x: 1 }, 5, '', 'Energy', 'Energy'],
                                     sectors_bearish: 'Technology', watch: null, model: null },
                  age_sec: Number.NaN, refreshing: 'yes' });
    const text = document.body.textContent || '';
    expect(text).not.toMatch(/\[object Object\]|NaN|undefined/);
    expect(screen.getByTestId('nt-model-lean')).toHaveTextContent('lean: unknown');
    expect(screen.getByTestId('nt-model-sectors')).toHaveTextContent('news-bullish Energy');
    expect(screen.getByTestId('nt-model-sectors')).not.toHaveTextContent('news-bearish');
    expect(screen.queryByTestId('nt-model-watch')).toBeNull();
    expect(screen.queryByTestId('nt-model-writing')).toBeNull();          // "yes" is not true
    expect(screen.getByTestId('nt-model-meta')).not.toHaveTextContent('read by');
  });

  it('NEGATIVE — no sectors and no watch → neither line renders', async () => {
    await mount({ ok: true, read: { ...READ, sectors_bullish: [], sectors_bearish: [], watch: [] }, age_sec: 30 });
    expect(screen.queryByTestId('nt-model-sectors')).toBeNull();
    expect(screen.queryByTestId('nt-model-watch')).toBeNull();
    expect(screen.getByTestId('nt-model-meta')).toHaveTextContent('just now');
  });

  it('NEGATIVE — "bounce" is nowhere on the card', async () => {
    await mount({ ok: true, read: READ, age_sec: 60, note: NOTE });
    expect(screen.getByTestId('nt-section-model').textContent || '').not.toMatch(/\bbounce\b/i);
  });
});

describe('ageLabel / nameList', () => {
  it.each([
    [0, 'just now'], [59, 'just now'], [60, '1 min ago'], [3599, '59 min ago'],
    [3600, '1 h ago'], [86399, '23 h ago'], [86400, '1 d ago'],
  ])('%s s → %s', (sec, want) => { expect(ageLabel(sec)).toBe(want); });

  it.each([[null], [undefined], [Number.NaN], [Infinity], [-5]])('NEGATIVE — %s → empty', (v) => {
    expect(ageLabel(v as any)).toBe('');
  });

  it('nameList keeps served strings once, trimmed, and drops junk', () => {
    expect(nameList([' Energy ', 'Energy', '', 3, null, { a: 1 }, 'Utilities'])).toEqual(['Energy', 'Utilities']);
    expect(nameList('Energy')).toEqual([]);
    expect(nameList(undefined)).toEqual([]);
  });
});
