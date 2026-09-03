/* ensurePushSubscription — the device-side self-heal (Ajay 2026-09-03:
   "my phone alerts are also not working"; his phone endpoint was purged on
   2026-09-02 after a 410 and nothing re-registered it). */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { ensurePushSubscription } from './pushSubscribe';

const KEY = 'BOa0iMEYgU6lKk8mObjdHXiGNVmvfbrEmxA3xQr7aDpwdZlwfHfIq0vNxcVYkI5BHwpv9pIOQHMlyi-9kUb4FIY';

function mockSub(endpoint: string) {
  return {
    endpoint,
    toJSON: () => ({ endpoint, keys: { p256dh: 'p', auth: 'a' } }),
    unsubscribe: vi.fn(async () => true),
    options: { applicationServerKey: new Uint8Array([1]) },
  };
}

function setup(opts: { permission?: NotificationPermission; local?: any; server?: string[] | null } = {}) {
  const local = opts.local === undefined ? null : opts.local;
  const subscribe = vi.fn(async () => mockSub('https://fcm.googleapis.com/fcm/send/NEW'));
  const reg = {
    active: { postMessage: vi.fn() },
    pushManager: { getSubscription: vi.fn(async () => local), subscribe },
  };
  vi.stubGlobal('navigator', { serviceWorker: { getRegistration: vi.fn(async () => reg), register: vi.fn() }, userAgent: 'TestPhone/1.0' });
  vi.stubGlobal('PushManager', function PushManager() {});
  vi.stubGlobal('Notification', { permission: opts.permission ?? 'granted', requestPermission: vi.fn() });
  const calls: { url: string; method: string; body?: any }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: any) => {
    calls.push({ url, method: init?.method || 'GET', body: init?.body ? JSON.parse(init.body) : undefined });
    if (url.endsWith('/push/public-key')) return { ok: true, json: async () => ({ public_key: KEY }) } as any;
    if (url.endsWith('/push/subscriptions')) {
      if (opts.server === null) return { ok: false, json: async () => ({}) } as any;
      // the real payload shape: {rows: [{kind, endpoint, ...}]} incl. mac rows without an endpoint
      return { ok: true, json: async () => ({ rows: [{ kind: 'mac', endpoint: null }, ...(opts.server || []).map((e) => ({ kind: 'web', endpoint: e }))] }) } as any;
    }
    return { ok: true, json: async () => ({ ok: true }) } as any;
  }));
  vi.stubGlobal('caches', { open: vi.fn(async () => ({ put: vi.fn(async () => undefined) })) });
  vi.stubGlobal('window', { ...(globalThis as any).window, caches: {}, localStorage: undefined });
  return { reg, subscribe, calls, local };
}

const mem = () => { const m = new Map<string, string>(); return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); }, removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(), key: () => null, length: 0 } as unknown as Storage; };

afterEach(() => { vi.unstubAllGlobals(); });

describe('ensurePushSubscription', () => {
  it('never prompts: without granted permission it does nothing', async () => {
    const s = setup({ permission: 'default' });
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r.action).toBe('no-permission');
    expect(s.subscribe).not.toHaveBeenCalled();
    expect(s.calls).toHaveLength(0);
  });

  it('subscribes and registers when the device has no subscription at all', async () => {
    const s = setup({ local: null, server: [] });
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r).toEqual({ ok: true, action: 'subscribed' });
    expect(s.subscribe).toHaveBeenCalledTimes(1);
    const post = s.calls.find((c) => c.url.endsWith('/push/subscribe') && c.method === 'POST')!;
    expect(post.body.subscription.endpoint).toContain('/NEW');
    expect(post.body.label).toContain('self-heal');
  });

  it('re-subscribes when the server no longer knows the local endpoint (the 410 purge)', async () => {
    const dead = mockSub('https://fcm.googleapis.com/fcm/send/DEAD');
    const s = setup({ local: dead, server: ['https://fcm.googleapis.com/fcm/send/OTHER-MAC'] });
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r).toEqual({ ok: true, action: 'resubscribed' });
    expect(dead.unsubscribe).toHaveBeenCalledTimes(1);
    expect(s.subscribe).toHaveBeenCalledTimes(1);
    expect(s.calls.some((c) => c.url.endsWith('/push/subscribe') && c.method === 'POST')).toBe(true);
  });

  it('keeps a subscription the server knows, and hands the API base to the worker', async () => {
    const live = mockSub('https://fcm.googleapis.com/fcm/send/LIVE');
    const s = setup({ local: live, server: ['https://fcm.googleapis.com/fcm/send/LIVE'] });
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r).toEqual({ ok: true, action: 'kept' });
    expect(live.unsubscribe).not.toHaveBeenCalled();
    expect(s.subscribe).not.toHaveBeenCalled();
    expect(s.reg.active.postMessage).toHaveBeenCalledWith(expect.objectContaining({ type: 'cheetah:config', api: expect.any(String) }));
  });

  it('when the server list cannot be read it keeps the local subscription rather than churning it', async () => {
    const live = mockSub('https://fcm.googleapis.com/fcm/send/LIVE');
    const s = setup({ local: live, server: null });
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r.action).toBe('kept');
    expect(live.unsubscribe).not.toHaveBeenCalled();
    expect(s.subscribe).not.toHaveBeenCalled();
  });

  it('throttles to once per 6 hours unless forced', async () => {
    const st = mem();
    setup({ local: null, server: [] });
    const t0 = 1_800_000_000_000;
    expect((await ensurePushSubscription({ storage: st, now: t0 })).action).toBe('subscribed');
    expect((await ensurePushSubscription({ storage: st, now: t0 + 60_000 })).action).toBe('skipped');
    expect((await ensurePushSubscription({ storage: st, now: t0 + 60_000, force: true })).action).toBe('subscribed');
    expect((await ensurePushSubscription({ storage: st, now: t0 + 7 * 3_600_000 })).action).toBe('subscribed');
  });

  it('swallows failures into an error result instead of throwing on app load', async () => {
    const s = setup({ local: null, server: [] });
    s.reg.pushManager.subscribe.mockRejectedValueOnce(new Error('boom'));
    const r = await ensurePushSubscription({ storage: mem() });
    expect(r.ok).toBe(false);
    expect(r.action).toBe('error');
    expect(r.reason).toContain('boom');
  });
});
