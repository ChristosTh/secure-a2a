# secure-a2a

A skill for Claude (and a plain guide for humans) on building **secure agent-to-agent communication between personal
AI assistants** owned by different people — for example, a friend's assistant asking yours when you're free, or
passing a message that you answer with one tap.

It is distilled from a working implementation between two self-hosted assistants, including the problems found in its
security reviews.

## What it covers

- The [A2A protocol](https://a2a-protocol.org) (v1.0, with 0.3 fallback) — a small subset, no SDK needed
- **Ed25519 signatures on every request and response** instead of bearer tokens, with replay protection
- Pairing by comparing fingerprints out-of-band, and an owner-only address book
- **Human approval** for every answer and every outbound message
- Containing prompt injection: other agents' text is always untrusted data
- Instant delivery of answers (push to the address-book URL only) with polling as fallback
- AI-suggested replies through an isolated, tool-less drafter with a private-memory filter
- A full threat model and a go-live checklist

## Layout

```
SKILL.md                         the skill: design, rules and why
references/signature-scheme.md   exact signing spec + test vector
references/protocol.md           message shapes, versions, push/polling, limits
references/threat-model.md       every risk and its control
references/ai-in-the-loop.md     suggested replies and context, safely
scripts/a2a_sign.py              reference signer/verifier (Python, `cryptography`)
scripts/a2a-sign.mjs             reference signer/verifier (Node.js, built-in crypto)
```

## Use it

**As a Claude skill:** copy this folder into your skills directory (e.g. `~/.claude/skills/secure-a2a/`).
Claude will use it when you ask to connect your agent with someone else's.

**Check interoperability:** both sides should pass the same test vector:

```
python scripts/a2a_sign.py --selftest      # pip install cryptography
node scripts/a2a-sign.mjs --selftest
```

## Safety notes

- This repository contains **no secrets**. The only key in it is a public test key (32 bytes of `0x01`) used for the
  test vector. Never use it for a real agent; generate your own (`python scripts/a2a_sign.py --keygen`) and keep the
  private key off GitHub.
- The guidance reduces risk; it does not remove it. The human approval step is the last line of defence, and whatever
  you send to another agent is then governed by *their* security.
- Review the threat model against your own setup before going live.

## License

MIT — see `LICENSE`.
