---
name: secure-a2a
description: Design and build secure agent-to-agent (A2A) communication between personal AI assistants owned by different people — e.g. a friend's assistant asking yours for free/busy times or sending a message, with every answer approved by the human owner. Covers the A2A protocol (v1.0 with 0.3 fallback), Ed25519 request/response signing instead of bearer tokens, replay protection, an owner-managed address book with fingerprint pairing, human-in-the-loop approval, prompt-injection containment, instant delivery of answers, AI-suggested replies done safely, and a full threat model. Use this skill whenever someone wants their agent, bot or assistant to talk to another person's agent, add an A2A endpoint, connect two self-hosted assistants, let agents exchange messages or calendar availability, or asks how to make agent-to-agent communication safe — even if they don't say "A2A".
---

# Safe agent-to-agent communication

This skill helps you build a channel where **one person's AI assistant talks directly to another person's assistant** — and stays safe while doing it. It comes from a working implementation between two self-hosted personal assistants, and from the mistakes found while reviewing it.

The core problem: an agent-to-agent channel is a door that lets *another AI* put text in front of *your* AI, which has access to your email, calendar and memory. Everything below exists to make that door useful without letting it become a prompt-injection, impersonation or data-leak route.

## The design in one picture

```
Their agent ──HTTPS (signed)──▶ reverse proxy (only 2 paths) ──▶ your A2A server
                                                                   │ 1. known key? valid signature? fresh? not replayed?
                                                                   │    (fail → 401, no AI call, no notification)
                                                                   │ 2. allowed skill? within limits?
                                                                   │ 3. CODE handles it (no AI with tools ever reads it)
                                                                   ▼
                                                        owner gets a notification:
                                                        Allow / Decline   or   Send / Write my own / Ignore
                                                                   │ (nothing leaves without the owner's tap)
                                                                   ▼
                                     answer pushed back, signed, to the ADDRESS-BOOK URL (polling as fallback)
```

Read the parts you need:

| Topic | File |
|---|---|
| Exact signature scheme, test vector, Python/Node code | `references/signature-scheme.md`, `scripts/a2a_sign.py`, `scripts/a2a-sign.mjs` |
| Protocol shapes (A2A v1.0 + 0.3), tasks, polling, instant delivery | `references/protocol.md` |
| Every risk found and how it is handled | `references/threat-model.md` |
| Letting AI help (suggested replies, context) without opening a hole | `references/ai-in-the-loop.md` |
| Tests to write, one or more per protection | `references/test-checklist.md` |

## How to work with the user

1. **Find out who is on the other side** before writing code. A connection needs a partner speaking the same protocol. Ask what the other agent runs on, where it is hosted (own server vs. a platform/tunnel that can read traffic), whether it can receive HTTPS, and which AI provider reads its messages. If the other side is a consumer chatbot with no API, agent-to-agent is not possible — say so.
2. **Agree on one small first skill**, e.g. "find a time we're both free" or "deliver a short message". Structured requests that code can answer are far safer than free-form chat.
3. **Build in this order**: identity + signatures → address book + pairing → server with checks → owner approval flow → outbound client → instant delivery → (optional) AI-suggested replies. Test each layer before the next; the signature test vector lets both sides check interoperability before they ever connect.
4. **Review with the threat model** (`references/threat-model.md`) before going live, and again after any change that lets more data in or out.

## The rules that matter most (and why)

**1. Authenticate every message with signatures, not bearer tokens.**
A bearer token is a shared password: if it leaks (a screenshot, a log, a chat), anyone can pose as that agent until it is rotated, and it proves nothing about the content. Instead each agent has an Ed25519 key pair; only *public* keys are exchanged. Sign every request **and every response** over method, path, recipient fingerprint, timestamp, nonce and a hash of the body; responses also include the request's nonce so an old answer can't be replayed onto a new question. Reject timestamps more than ~300 s off and remember nonces (persisted, so a restart doesn't reopen a replay window). A2A itself leaves authentication open, so this is an application-level scheme both sides implement — see `references/signature-scheme.md`.

**2. Pair out-of-band, and let only the owner manage the address book.**
Keys travel over ordinary chat, so they can be swapped in transit. Both owners read their fingerprints aloud (in person or on a call) and compare. The address book (name, https URL, public key, allowed skills, expiry ~90 days) is editable only by the human through an authenticated UI — never by the AI, never by a message. Unknown, revoked or expired keys get a generic 401 with no notification and no AI call, so strangers cost nothing and learn nothing.

**3. Another agent's text is untrusted data — it never drives actions.**
Treat it exactly like email or web content: wrap it, mark it, neutralise anything that could close the wrapper (angle brackets, control and bidi/zero-width characters), cap its length. It may never on its own trigger an outbound message, a calendar change, a memory write or a settings change. If your main assistant is allowed to *see* it (so the owner can ask "what did they want?"), mark it clearly as untrusted in the context and add an explicit rule that it is data, not instruction.

**4. The human approves every answer and every outbound message.**
Every incoming request produces a notification with buttons (Allow/Decline, or Send/Write my own/Ignore). Outbound messages are proposals showing the *exact* text before sending. Buttons are single-use (atomic state change) and checked against the owner's identity. This is the control that makes the remaining risk acceptable: the AI can propose something too revealing, but it cannot send it.

**5. Answer structured requests with code, not AI.**
"When is the owner busy between A and B?" is answered by code from the calendar's free/busy API: merged busy ranges only — no titles, places or attendees. No language model reads the request, so there is nothing to inject into. Parse the other side's structured answers strictly (validated ISO times only) and compute results (e.g. common free slots) in code.

**6. Only ever send to the address book.**
When delivering answers instantly ("push"), send a signed message to the peer's **address-book URL**, never to a URL the peer supplies (standard push-notification/webhook configs let a hostile agent point you at internal services). Run an SSRF check on every outbound call, follow no redirects, cap response size and time, and verify the response signature. Keep polling (`GetTask`) as a fallback and retry pushes a bounded number of times.

**7. Limit everything.**
Body size (~16 KB), requests per peer per hour, pending requests per peer, polling frequency, a separate pre-authentication limit so junk floods can't lock out real peers, deeply nested JSON handled as a clean parse error, task expiry (~24 h unanswered) and payload deletion (~48 h after the end). Provide a kill switch (pause everything) and one-tap revoke.

**8. Log metadata, never content.**
Audit rows hold peer id, skill, outcome, cost — never message text, times, keys or URLs. Rate-limit the audit of rejected requests so a flood can't fill the log.

## When AI should help

Owners usually want help: a suggested reply, or the ability to ask their assistant about a message. Both are possible without breaking rule 3 — through an **isolated, tool-less drafter** and **marked, untrusted context**. The details, including which personal memories may and may not reach the drafter, are in `references/ai-in-the-loop.md`. Read it before adding any AI to the inbound path.

## Before going live — checklist

- [ ] Signature test vector passes on both sides (`python scripts/a2a_sign.py --selftest`).
- [ ] Unsigned, wrongly signed, stale and replayed requests all get the same generic 401; no notification fires.
- [ ] The agent card / discovery document is only served to signed requests from known peers.
- [ ] Reverse proxy exposes only the A2A paths, with a body cap and no access log.
- [ ] Every inbound request needs an owner tap; every outbound message shows exact text before sending.
- [ ] Inbound text is wrapped, neutralised and capped wherever it is shown or stored; it can't trigger actions.
- [ ] Pushes go only to the address-book URL; SSRF check, no redirects, response signature verified.
- [ ] Private key file is 0600, never logged, and only backed up encrypted (it *is* the agent's identity).
- [ ] Audit log holds no content; rejected-request audit is rate-limited.
- [ ] Both owners protect the accounts that control their domain names (2FA, CAA record): whoever controls DNS can obtain a certificate for your agent's name.

## Adapting this to a codebase

Keep the layers separate so each can be tested alone: a pure module for identity/signing/validation (no I/O), a server/client module, and the owner-facing notification flow. Put protocol-version conversion (v1.0 ↔ 0.3) at the edges and keep one internal shape. Write the tests in `references/test-checklist.md` — a fake peer with its own key pair, running in-process, makes end-to-end tests easy.
