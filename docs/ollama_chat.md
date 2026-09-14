# /ollama — private chat with the local model

> Ajay 2026-09-14: *"Can you build me a chat interface to talk to my Ollamma
> LLM the abliterated model. I wanna chat with it from this app but only
> available for me. Make sure the LLM is setup to start on computer start.
> Turn on the LLM. I can upload images and talk to it."*

**Where:** avatar menu → *Ollama (local LLM)* → https://pounce.ajaykandakatla.dev/ollama

**Not a trading surface.** Nothing on this page reads the portfolio, the scans
or the zones. It is a plain chat with the model on this Mac.

## What was already true (nothing here re-does it)

| Ask | State when I looked | What I did |
|---|---|---|
| start on computer start | Homebrew service `sh.brew.ollama` — LaunchAgent with `RunAtLoad` + `KeepAlive`, `LoginWindow` session type | nothing; brew rewrites the plist on upgrade, a hand edit would be lost |
| turn on the LLM | not resident | one warm request with `keep_alive: -1` → `ollama ps`: 20 GB, 100 % GPU, **UNTIL Forever** |
| the abliterated model | `huihui_ai/Qwen3.8-abliterated:27b` (his Hermes terminal showed it) — qwen35, 27.3 B, Q4_K_M, ctx 262 144, capabilities **completion · vision · tools · thinking**, 460 M CLIP projector | default `OLLAMA_CHAT_MODEL` |
| images | native vision | pass `messages[].images` straight through |

"At login" is what a LaunchAgent gives; the Mac still needs to reach the
desktop once after a reboot. A LaunchDaemon would run before login but brew
does not manage one and Ollama would then run as root with a different model
directory — not worth it for a machine that auto-logs-in.

## Who can see it — and why it is not `is_admin`

`auth.is_admin_email()` is **true for every house owner** — Vineetha
included, by design, so household data is jointly managed. "Only available
for me" therefore cannot ride on that flag.

| Layer | Gate | On failure |
|---|---|---|
| `backend/ollama_chat/api.py` | `PRIMARY_ADMIN_EMAIL` — one address, local constant | **404** (stealth), raised in a **dependency** so it beats body validation (a stranger posting garbage gets 404, not a 422 that lists our field names) |
| `/auth/me` | new boolean `is_primary_admin` | — |
| `App.tsx` `PrimaryAdminRoute` | `user.is_primary_admin` | renders the stealth `NotFound`, does not redirect |
| the page | `GET /ollama/me` on mount | 404 → stealth 404 (a bookmarked URL says nothing) |
| avatar menu | `access/store.py` `_ADMIN_MENU_ITEMS` — `build_menu` already compares the strict address | item absent |

The constant is deliberately **not imported** from `access/api.py`
(same reasoning as that module's own note: a refactor of one gate must not
quietly relax the other). `tests/test_ollama_chat.py::test_gate_constant_matches_access_api_admin`
pins the two equal. The address never reaches the JS bundle —
`test_admin_email_never_reaches_the_frontend_sources` and the page's own
source-guard test check.

## Endpoints

| Route | Purpose |
|---|---|
| `GET /ollama/me` | gate probe + status: `model`, `reachable`, `resident`, `version`, `capabilities`, `context_length` |
| `POST /ollama/warm` | `/api/generate` with empty prompt and `keep_alive: -1` — the page calls it on open if the model is not resident |
| `POST /ollama/chat` | body `{messages:[{role, content, images?}], model?, think?, options?}` → SSE |

SSE events, one JSON object per `data:` line:

```
{"delta": "text"}        answer slice
{"thinking": "text"}     reasoning slice (Qwen3.8 emits it separately; shown folded)
{"done": true, "model", "eval_count", "prompt_eval_count", "total_duration"}
{"error": "message"}     then the stream ends
```

Every request carries `keep_alive: -1`. The relay stops reading when the
browser disconnects (Stop button / closed tab) so the GPU is not left
finishing an answer nobody will read.

Errors from Ollama ride **inside** the stream as `{"error"}` — the HTTP
status is 200 once the SSE channel opens.

## Images

* Ollama wants **bare base64**; browsers produce `data:image/…;base64,` URLs.
  The page strips the prefix; the backend **refuses** anything still carrying
  one (400) rather than let the model silently fail to decode it.
* Client-side downscale to 1600 px JPEG q0.88 before sending — a 12 MB
  phone photo becomes ~300 KB. The model's projector resizes to its own grid
  anyway. A 4 s load guard means a broken image never hangs the composer.
* Limits: 6 images per message (400), 12 MB base64 each (413), 200 messages.
* nginx `/api/` block: `client_max_body_size 40m;` in **both** confs — the
  1 MB default rejected one photo. Guarded by test, inside the location only.

## Container ↔ host

The api container reaches Ollama at `http://host.docker.internal:11434`
(verified from inside the container; `172.17.0.1` does not work on Docker
Desktop for Mac). Ollama binds `127.0.0.1:11434` on the host — it is not on
the LAN.

`backend/.env`:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_CHAT_MODEL=huihui_ai/Qwen3.8-abliterated:27b
```

## Frontend

* `frontend/src/pages/OllamaChat.tsx` — fetch + `getReader()` streaming,
  AbortController on Stop, paste/drop/attach images, thinking folded in
  `<details>`, think toggle (remembered), localStorage history **text only**
  (images live for the session and show as `📷 n` after a reload).
* `frontend/src/lib/markdownLite.tsx` — the renderer extracted from
  `ChatWidget` so both chats share one copy; no markdown dependency.
* Styles: `.ol-*` block at the end of `styles.css`.

## Tests

* BE `backend/tests/test_ollama_chat.py` — gate (stranger 404, house owner
  with `is_admin` 404, 404 before 422), stream relay (thinking/delta/done,
  after-done lines dropped, error line, upstream 500, junk lines), input
  guards (empty, no user turn, data-URL image, 7 images, 201 messages, bad
  role, oversize 413), source guards (router mounted, `is_primary_admin`
  on `/auth/me`, menu item, nginx body size in both confs inside `/api/`,
  no admin email in FE sources, env keys).
* FE `frontend/src/pages/OllamaChat.test.tsx` — stealth 404 renders no
  composer, status/warm, split-chunk stream reassembly, Shift+Enter, error
  event, mid-session 404, Stop aborts, Clear, think toggle, bare-base64
  image path, MAX_IMAGES cap, remove ×, restored `📷 n`, no `@gmail.com`
  in source.

## Not done / his call

* No server-side history — the thread lives in his browser.
* No model picker in the UI; `model` is accepted by the API for later.
* No system prompt. If he wants a persona, it is one field on `ChatBody`.
