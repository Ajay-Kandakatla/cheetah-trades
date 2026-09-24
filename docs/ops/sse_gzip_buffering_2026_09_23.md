# The app was gzipping its own SSE (2026-09-23)

> "Sometimes I am getting this error"
>
> — Ajay, screenshot of a red **`network error`** on a Hermes Agent turn

## What he was actually seeing

`network error` is **not a string this app owns.** `grep -rn "network error"
frontend/src` returns two unrelated comments. It is the browser's own
`TypeError` for a response body that died mid-stream, printed verbatim by
[`OllamaChat.tsx:486`](../../frontend/src/pages/OllamaChat.tsx):

```ts
if (!aborted) patchLast(a => ({ ...a, error: String((e as Error)?.message || e) }));
```

So the turn did not fail — **the HTTP connection under it was cut.** Had Hermes
itself failed, the bubble would have carried our words (`Hermes closed the
connection mid-turn`, or the backend's `{"error": …}`).

## Root cause

`backend/main.py` adds, for the ~295 KB `/chart-maps` JSON payload (2026-08-16):

```python
app.add_middleware(GZipMiddleware, minimum_size=1024)
```

Starlette's `GZipResponder` has **no content-type exclusion**, so it also
compresses every `text/event-stream` response in the app. Two details make that
fatal rather than merely wasteful:

1. **`minimum_size` does not exempt a stream.** The guard is
   `len(body) < minimum_size and not more_body`. A streaming response always has
   `more_body=True`, so it falls through to the streaming branch no matter how
   small each chunk is.
2. **The streaming branch never flushes.** It does `self.gzip_file.write(body)`
   then reads the buffer, at `compresslevel=9`. zlib holds roughly 250 KB before
   it emits anything. No SSE turn on this app comes close.

### Measured on the live api container, `GET /events`

| `Accept-Encoding` | bytes in 32 s | when |
|---|---|---|
| `gzip` | **316** | all at t=0.0 s, then silence |
| `identity` | **14,807** | ~60 chunks, flowing the whole time |

The 316 bytes are the HTTP headers plus the 10-byte gzip header. The browser got
that and nothing else **for the entire turn** — not just while the model was
thinking, but while it was streaming tokens too.

Any idle timeout in the `Cloudflare → tunnel → nginx → oauth2-proxy → uvicorn`
path then cuts a connection that looks dead. Short turns finished and flushed
before anything gave up, which is exactly why it failed *sometimes*.

## The trap: a heartbeat does not fix this

`events/sse.py` **already** emitted `: ping` every 25 seconds for precisely this
purpose. gzip swallowed it whole. Every one of the six SSE endpoints also already
set `X-Accel-Buffering: no` and `Cache-Control: no-cache`, because their authors
knew about proxy buffering. None of it helps when the buffering happens *inside
our own middleware stack*, before the bytes reach any proxy.

The first diagnosis in this session was "the turn loop has no heartbeat, add
one". That would have emitted **zero bytes** and fixed nothing.

## The fix

`backend/events/sse_headers.py` (new) holds one constant, and all six SSE
endpoints use it:

```python
SSE_HEADERS = {
    "Content-Encoding": "identity",
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
}
```

Starlette 0.41.3 `GZipResponder.__call__` reads the outgoing headers once:

```python
self.content_encoding_set = "content-encoding" in headers
...
elif message_type == "http.response.body" and self.content_encoding_set:
    await self.send(message)        # straight through, untouched
```

So declaring `identity` turns gzip off **for SSE only**; the `/chart-maps` JSON
win is untouched. `identity` is the RFC 9110 token for "no transformation
applied" — a truthful declaration, not a trick.

`no-transform` came from `events/sse.py`, which was the only endpoint carrying
it. Taking the stronger of the two values is the point of having one constant.

### The six endpoints

| file | what streams there |
|---|---|
| `ollama_chat/hermes.py:417` | 🤖 Hermes Agent turns — **his symptom** |
| `ollama_chat/api.py:285` | the direct Ollama model chat |
| `events/sse.py:100` | the app-wide event bus |
| `main.py:1232` | the live tape |
| `main.py:1707` | `/sepa/scan/stream` — the Scan button |
| `main.py:4329` | the Mac push-alert stream |

## Tests

`backend/tests/test_sse_not_gzipped_2026_09_23.py` — 10, mutation-tested four
ways (drop the header / set it to `gzip` / revert one endpoint to an inline dict
/ drop `no-transform` — all four caught).

* **The timing proof runs over a real socket**, not `TestClient`: uvicorn on an
  ephemeral port, a slow generator standing in for a Hermes turn, and the raw
  socket read the same way the live container was measured. `TestClient` uses an
  in-memory transport and coalesces the body however it likes, so chunk COUNTS
  through it prove nothing — that limitation is written into the test that has
  it, so nobody re-adds a chunk-count assertion and trusts it.
* **The negative is the bug itself.** The identical app without the header must
  leak *no* readable payload before the response closes. If Starlette ever
  changes its pass-through rule, that test fails and tells us the fix became a
  no-op — it is not to be deleted.
* `minimum_size` is pinned as *not* a defence: a 1-byte chunk is still gzipped.
* The `: ping` case is pinned, so nobody "fixes" a future stall with heartbeats.
* A **source guard** walks the tree for `media_type="text/event-stream"`, asserts
  there are exactly six, and fails if any of them does not use `SSE_HEADERS`.

## What this does NOT fix, and is his call

The red bubble's wording. Six terminal states exist on that page and two of them
— **Stop** and **a stream that ended without a `done` event** — render
identically: partial text, no stats, no marker. He cannot tell a turn he stopped
from one that was truncated. Fixing that is two strings, but the obvious wording
("Hermes may still be finishing this turn") asserts the opposite of what
`hermes.py:333-339` does on disconnect, so it needs his call rather than a guess.

## Findings from the same sweep that were checked and are NOT causes

* **`ws_orphan_reap` in `serve.log` is normal.** All 22 were preceded in
  `agent.log` by `tui turn finished … status=complete` for the same runtime id.
  Zero followed a failed turn. The bridge opens one websocket per turn and closes
  it in `finally`; the session is reaped 20 s later by design.
* **The `Auxiliary title generation failed` lines are stale** — that file has not
  been written since **2026-09-14 19:48**, before that fix.
  `auxiliary.title_generation.enabled: false` still holds.
* **`streaming: enabled: false`** in `~/.hermes/config.yaml` governs progressive
  message edits on Telegram/Discord/Slack, not this path. Leave it alone.
* **The live tunnel config is `/etc/cloudflared/config.yml`**, run by a root
  LaunchDaemon (`com.cloudflare.cloudflared`, PID 409) — *not* the
  `~/.cloudflared/config.yml` that reads the same. `ps aux | grep` does not show
  it; use `pgrep -fl cloudflared`. Neither file sets `originRequest`, so
  cloudflared runs pure defaults.
* **`auxiliary.background_review` is ON by default** and replays the whole
  conversation through the same single-slot 27B, for tens of minutes
  (measured spans 32 and 94 minutes). It did **not** fire tonight, so it is not
  this symptom — but it is the same collision family as the title-generation bug
  and will intermittently make a turn start slow. Disabling it is his call: it
  ended `result=skill` in 3 of its 4 runs, so it is actively patching his skills.
