// @vitest-environment node
/* 📬 Delivery receipts — the REAL service worker (frontend/public/sw.js), evaluated in a
 * sandbox with a fake `self` (2026-10-21).
 *
 * Ajay 2026-10-21, on a 🚩 A+ push the server recorded as sent 3 / failed 0: "Oh man I did
 * not get an A+ alert for it then today" — "Yes POLA reached and SAIQ too". `sent` is the
 * push service accepting the message; the receipt is the device's screen. The worker is
 * plain JS with no module boundary, so the test runs the file itself (node:vm) and fires a
 * push event at the handler it registered — the receipt body builder and the ordering
 * (receipt AFTER showNotification) are what is pinned.
 */
import { describe, expect, it, vi } from 'vitest';

/* The tsconfig carries no node types (the app is browser code); the node modules are
 * reached the way Alerts.tape_control_live.test.tsx reaches fs. */
async function nodeMod(name: string): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + name));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
const fs: any = await nodeMod('fs');
const vm: any = await nodeMod('vm');
const SW_SRC: string = fs.readFileSync(`${root}/public/sw.js`, 'utf8');
const ENDPOINT = 'https://web.push.apple.com/QAbcdef0123456789';

type Harness = {
  fire: (payload: unknown) => Promise<void>;
  fetch: ReturnType<typeof vi.fn>;
  show: ReturnType<typeof vi.fn>;
  calls: string[];
  sandbox: any;
  listeners: Record<string, (ev: any) => void>;   // 2026-11-17: the click test fires notificationclick
};

/** Evaluate sw.js with a fake worker global; `config` is what the Cache API hands back
 *  (null = nothing cached → the worker's own default API base). */
function boot(opts: { config?: { api: string } | null; endpoint?: string | null; fetchImpl?: any } = {}): Harness {
  const listeners: Record<string, (ev: any) => void> = {};
  const calls: string[] = [];
  const fetch = vi.fn(opts.fetchImpl ?? (async () => { calls.push('fetch'); return { ok: true }; }));
  const show = vi.fn(async () => { calls.push('show'); });
  const sub = opts.endpoint === null ? null : { endpoint: opts.endpoint ?? ENDPOINT };
  const config = opts.config === undefined ? { api: '/api' } : opts.config;
  const sandbox: any = {
    console: { warn: () => {}, log: () => {}, error: () => {} },
    fetch,
    caches: { open: async () => ({ match: async () => (config ? { json: async () => config } : undefined), put: async () => {} }) },
    addEventListener: (type: string, fn: (ev: any) => void) => { listeners[type] = fn; },
    skipWaiting: () => {},
    clients: { claim: async () => {}, matchAll: async () => [] },
    location: { hostname: 'pounce.example', protocol: 'https:' },
    registration: { showNotification: show, pushManager: { getSubscription: async () => sub } },
    Date,
  };
  sandbox.self = sandbox;
  vm.runInNewContext(SW_SRC, sandbox, { filename: 'sw.js' });
  const fire = async (payload: unknown) => {
    const pending: Promise<unknown>[] = [];
    listeners.push({
      data: { json: () => payload, text: () => JSON.stringify(payload) },
      waitUntil: (p: Promise<unknown>) => { pending.push(p); },
    });
    await Promise.all(pending);
  };
  return { fire, fetch, show, calls, sandbox, listeners };
}

const PUSH = { title: '🚩 NIXX A+', body: 'his setup, not a buy signal', kind: 'gajjala_setup',
  tag: 'gajjala_setup-NIXX', url: '/chart-maps?tab=gajjala', push_id: 'a3f1c2e4d5b6978012345678abcdef01' };

describe('sw.js — the delivery receipt (2026-10-21)', () => {
  it('after showNotification resolves, POSTs {push_id, endpoint, shown_at} to <api>/push/receipt and nothing else', async () => {
    const h = boot();
    await h.fire(PUSH);
    expect(h.show).toHaveBeenCalledTimes(1);
    expect(h.calls).toEqual(['show', 'fetch']);                       // the receipt follows the screen
    expect(h.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = h.fetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/push/receipt');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect((init.headers as any)['Content-Type']).toBe('application/json');
    const body = JSON.parse(String(init.body));
    expect(Object.keys(body).sort()).toEqual(['endpoint', 'push_id', 'shown_at']);
    expect(body.push_id).toBe(PUSH.push_id);
    expect(body.endpoint).toBe(ENDPOINT);
    expect(typeof body.shown_at).toBe('number');
    expect(body.shown_at).toBeGreaterThan(1_700_000_000_000);         // Date.now() ms
    // NEGATIVE: no content and no key ride on a receipt
    expect(String(init.body)).not.toMatch(/title|body|p256dh|auth|keys/);
  });

  it('the notification itself is unchanged: title, body, tag, url and the payload in data', async () => {
    const h = boot();
    await h.fire(PUSH);
    const [title, options] = h.show.mock.calls[0] as [string, any];
    expect(title).toBe('🚩 NIXX A+');
    expect(options.body).toBe('his setup, not a buy signal');
    expect(options.tag).toBe('gajjala_setup-NIXX');
    expect(options.data.url).toBe('/chart-maps?tab=gajjala');
    expect(options.data.push_id).toBe(PUSH.push_id);
  });

  it('receiptBody is pure: the three keys, and null without a push_id or an endpoint', () => {
    const { sandbox } = boot();
    const b = sandbox.receiptBody(PUSH, ENDPOINT);
    expect(Object.keys(b).sort()).toEqual(['endpoint', 'push_id', 'shown_at']);
    expect(sandbox.receiptBody({ ...PUSH, push_id: undefined }, ENDPOINT)).toBeNull();
    expect(sandbox.receiptBody({ ...PUSH, push_id: '' }, ENDPOINT)).toBeNull();
    expect(sandbox.receiptBody({ ...PUSH, push_id: 42 }, ENDPOINT)).toBeNull();
    expect(sandbox.receiptBody(PUSH, '')).toBeNull();
    expect(sandbox.receiptBody(PUSH, undefined)).toBeNull();
    expect(sandbox.receiptBody(null, ENDPOINT)).toBeNull();
  });

  it('NEGATIVE: a payload without push_id (an older sender, the Settings test ping) shows and posts nothing', async () => {
    const h = boot();
    await h.fire({ title: 'Pounce test ✓', body: 'Push notifications are working', tag: 'test', url: '/notifications' });
    expect(h.show).toHaveBeenCalledTimes(1);
    expect(h.fetch).not.toHaveBeenCalled();
  });

  it('NEGATIVE: no subscription on this device → no receipt (never a POST without the credential)', async () => {
    const h = boot({ endpoint: null });
    await h.fire(PUSH);
    expect(h.show).toHaveBeenCalledTimes(1);
    expect(h.fetch).not.toHaveBeenCalled();
  });

  it('NEGATIVE: a receipt that fails never rejects the push event (the notification already showed)', async () => {
    const h = boot({ fetchImpl: async () => { throw new Error('offline'); } });
    await expect(h.fire(PUSH)).resolves.toBeUndefined();
    expect(h.show).toHaveBeenCalledTimes(1);
    expect(h.fetch).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a failed showNotification posts no receipt', async () => {
    const h = boot();
    h.show.mockImplementationOnce(async () => { throw new Error('denied'); });
    await expect(h.fire(PUSH)).rejects.toThrow('denied');
    expect(h.fetch).not.toHaveBeenCalled();
  });

  it('with no cached config the worker falls back to its own API base (host:8000), like resubscribe does', async () => {
    const h = boot({ config: null });
    await h.fire(PUSH);
    expect(h.fetch.mock.calls[0][0]).toBe('https://pounce.example:8000/push/receipt');
  });
});

/* 🎯 2026-11-17 — Ajay: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and
 * GP". The two 🚩 A+ entry kinds join STICKY_KINDS (requireInteraction): on Mac Chrome the notification stays until
 * he acts. iOS Safari IGNORES requireInteraction — on his iPhone only the 🎯 A+ title lead helps. The tap opens the
 * payload's own url (the 👀 Watch, alerts.compose ENTRY_URL). */
describe('sw.js — the A+ push stays on screen on desktop (2026-11-17)', () => {
  const sticky = async (kind?: string) => {
    const h = boot();
    await h.fire(kind === undefined ? { title: 'x' } : { title: 'x', kind });
    const [, options] = h.show.mock.calls[0] as unknown as [string, NotificationOptions];
    return options.requireInteraction;
  };

  it('gajjala_setup and gajjala_1m_setup are sticky', async () => {
    expect(await sticky('gajjala_setup')).toBe(true);
    expect(await sticky('gajjala_1m_setup')).toBe(true);
  });

  it('volume_breakout and rising_momentum stay sticky', async () => {
    expect(await sticky('volume_breakout')).toBe(true);
    expect(await sticky('rising_momentum')).toBe(true);
  });

  /* WIDENED 2026-11-23 (high-SI spec §3.9): 🩳 gajjala_si_cross is NOT sticky (sw.js untouched; sticky = A+ only). */
  /* WIDENED 2026-11-24 (voldry spec §3.9): 💧 gajjala_vol_dried is NOT sticky (sw.js untouched; sticky = A+ only). */
  it('NEGATIVE: potentials, Luk, long_term, the 🩳 High SI cross, 💧 Volume dried and a kind-less ping are not sticky', async () => {
    for (const k of ['gajjala_potential', 'gajjala_1m_potential', 'luk_setup', 'long_term', 'gajjala_si_cross', 'gajjala_vol_dried', 'gajjala_setupX']) {
      expect(await sticky(k)).toBe(false);
    }
    expect(await sticky(undefined)).toBe(false);
  });

  it('the title and url ride through untouched', async () => {
    const h = boot();
    const url = '/chart-maps?tab=gajjala_watch&focus=AKAN';
    await h.fire({ title: '🎯 A+ · AKAN · 🎾 Reversal Squeeze', kind: 'gajjala_1m_setup', url });
    const [title, options] = h.show.mock.calls[0] as unknown as [string, NotificationOptions & { data: any }];
    expect(title).toBe('🎯 A+ · AKAN · 🎾 Reversal Squeeze');
    expect(options.data.url).toBe(url);
  });

  const click = async (h: Harness, url: string) => {
    const pending: Promise<unknown>[] = [];
    const close = vi.fn();
    h.listeners.notificationclick({
      notification: { close, data: { url } },
      waitUntil: (p: Promise<unknown>) => { pending.push(p); },
    });
    await Promise.all(pending);
    return close;
  };

  it('a tap with no open window opens the Watch url', async () => {
    const h = boot();
    const openWindow = vi.fn(async () => null);
    h.sandbox.clients.openWindow = openWindow;
    const url = '/chart-maps?tab=gajjala_watch&focus=AKAN';
    const close = await click(h, url);
    expect(close).toHaveBeenCalledTimes(1);
    expect(openWindow).toHaveBeenCalledWith(url);
  });

  it('a tap with the app open focuses it and navigates to the Watch url (no new window)', async () => {
    const h = boot();
    const navigate = vi.fn();
    const focus = vi.fn();
    const openWindow = vi.fn(async () => null);
    h.sandbox.clients.matchAll = async () => [{ focus, navigate }];
    h.sandbox.clients.openWindow = openWindow;
    const url = '/chart-maps?tab=gajjala_watch&focus=GP';
    await click(h, url);
    expect(focus).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(url);
    expect(openWindow).not.toHaveBeenCalled();
  });
});
