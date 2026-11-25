# Protocol: a small, safe subset of A2A

[A2A (Agent2Agent)](https://a2a-protocol.org) is an open standard (Linux Foundation) for agents built by different
people to talk. You don't need an SDK for a narrow use: JSON-RPC 2.0 over HTTPS plus the signature scheme is enough,
and less third-party code runs next to personal data.

## Endpoints

| Method and path | Purpose |
|---|---|
| `POST /a2a` | JSON-RPC 2.0, `Content-Type: application/json`, body ≤ 16 KB |
| `GET /.well-known/agent-card.json` | Agent card — serve it **only** to a validly signed GET from a known peer (404 otherwise), listing only the skills that peer may use |

Everything else: 404. Paused: 503. Put the server behind a reverse proxy that forwards only these two paths, caps the
body and keeps no access log.

## Versions

- **v1.0**: header `A2A-Version: 1.0`; methods `SendMessage`, `GetTask`; `role` is `ROLE_USER`/`ROLE_AGENT`; parts
  have no `kind` (`{"text": …}`, `{"data": …}`); states `TASK_STATE_SUBMITTED|WORKING|INPUT_REQUIRED|COMPLETED|FAILED|CANCELED|REJECTED`;
  results wrapped as `{"task": {…}}`.
- **0.3** (no header): `message/send`, `tasks/get`; `kind` on messages/parts/tasks; lowercase states (`input-required`);
  the task itself is the result.
- Missing header = 0.3. Unknown version → JSON-RPC error with `data.supportedVersions`. Keep one internal shape and
  convert at the edges. A client can speak 1.0 and retry once with 0.3 on "method not found" or the version error.

## A request that waits for a human

```json
{"jsonrpc":"2.0","id":"1","method":"SendMessage","params":{"message":{
  "messageId":"unique-id-1","role":"ROLE_USER",
  "parts":[{"data":{"start":"2026-12-01T00:00:00+01:00","end":"2026-12-05T00:00:00+01:00"}}],
  "metadata":{"skill":"free_busy"}}}}
```

Validate strictly in code (ISO 8601 with offset, end after start, ≤ 14 days, within the next 60 days). Deduplicate by
`messageId` so a retry doesn't ask the owner twice. Answer immediately with a task in `TASK_STATE_INPUT_REQUIRED`;
the owner decides later.

Completed free/busy task (code-built, busy ranges only, merged, UTC, clipped to the range):

```json
{"task":{"id":"9f3c0a51d27e4b86","status":{"state":"TASK_STATE_COMPLETED","timestamp":"…"},
 "artifacts":[{"artifactId":"busy","parts":[{"data":{"start":"…","end":"…",
   "busy":[{"start":"2026-12-02T08:00:00+00:00","end":"2026-12-02T10:30:00+00:00"}]}}]}]}}
```

A `message` skill carries one text part (≤ 1000 chars, control characters removed). The reply becomes a text artifact.

## Getting the answer: push first, polling as fallback

1. **Push**: the moment the owner answers (send, ignore, allow, decline) or it fails, POST one signed `SendMessage`
   to the peer's **address-book URL** + `/a2a`:
   ```json
   {"messageId":"…","role":"ROLE_USER","referenceTaskIds":["<task id>"],
    "parts":[{"text":"Sure, 15:00 works."}],
    "metadata":{"skill":"task_update","taskId":"<task id>","state":"TASK_STATE_COMPLETED"}}
   ```
   Any validly signed, non-error result = delivered. Otherwise retry at most twice, ~60 s apart, then stop.
2. **Polling**: `GetTask` (≤ once per 20 s per task) always keeps working, and only returns tasks of the requesting peer.

Receiving a `task_update`: accept it only for an **open task you sent to that same peer** (else "task not found"),
process it exactly like a polled result (strict parsing, escaping), and make it idempotent so a later poll can't notify
the owner twice. Never adopt a callback URL supplied by the peer.

## Limits worth copying

| What | Value |
|---|---|
| Body | 16 KB in, 64 KB for answers you receive |
| Per peer | 30 requests/hour; 5 unanswered requests at a time |
| Global | separate budgets before and after authentication |
| Polling | once per 20 s per task |
| Expiry | unanswered tasks canceled after 24 h; payloads deleted 48 h after the end |
| Client | 15 s timeout, no redirects, SSRF check on every call |
