# Tests to write

One or more tests per protection. A protection without a test tends to break quietly the next time someone refactors.
This list comes from the test suite of a live implementation, and every item maps to a row in `threat-model.md`.

**Setup that makes this easy:** a fake peer with its own Ed25519 key pair, running in-process (a local HTTP server or
your framework's test client). Use a fixed clock so you can test timestamp edges, a temporary database so you can
test restarts, and a fake notifier that records what the owner would see. Also fake the AI calls and assert on what
they *receive*, not only on what they return.

## Identity and signatures

- [ ] The test vector from `signature-scheme.md` matches exactly: public key, fingerprint, signing string and signature.
- [ ] Sign → verify round-trip passes. Each of these fails: one changed body byte, a different recipient fingerprint,
      a different path, a different method.
- [ ] Timestamp exactly 300 s off is accepted; 301 s off is rejected.
- [ ] The same nonce is rejected the second time, **including after a restart** (the nonce store is persisted).
- [ ] An unknown key id gets 401, with **no** owner notification and **no** AI call.
- [ ] Missing headers, malformed base64, a wrong signature length or an uppercase fingerprint all get the same
      generic 401.
- [ ] The identity key file is created with owner-only permissions, and the same key loads on restart.
- [ ] Client side: an unsigned response, a wrongly signed one, or one bound to a different request nonce counts as a
      failure, never as an answer.

## Address book and pairing

- [ ] A peer can only be added through the owner's own interface, and only after the "I compared the fingerprint" step.
- [ ] Invalid entries are refused: non-https URL, bad public key, duplicate key, too many peers.
- [ ] Revoked and expired peers are refused everywhere: inbound requests, outbound messages, push and polling.
- [ ] The global pause makes the server answer 503 and stops all outbound traffic.
- [ ] The AI has no tool or command that can add, change or enable a peer.

## Server input

- [ ] The agent card is served only to a signed request from a known peer (404 otherwise), and lists only that peer's
      skills.
- [ ] A skill the peer isn't allowed to use is refused.
- [ ] A body over the cap, a wrong content type, an unknown method or an unsupported protocol version each get a clean
      error.
- [ ] Deeply nested JSON gives a clean parse error, not a crash or a 500.
- [ ] Free/busy input is validated: ISO 8601 with offset, end after start, ≤ 14 days, within the next 60 days.
- [ ] Message text has control, bidi and zero-width characters stripped and is capped in length. Empty text is refused.
- [ ] The same `messageId` sent twice asks the owner only once.

## Limits

- [ ] The per-peer hourly limit and the pending-request cap both work.
- [ ] Polling the same task faster than allowed is refused.
- [ ] **A flood of junk from strangers does not lock out a real peer** (the pre-auth and post-auth budgets are
      separate).
- [ ] Audit rows for rejected requests are capped per hour.
- [ ] An unanswered inbound task expires after 24 h, and its payload is deleted later.

## Owner approval

- [ ] An inbound request always reaches the owner first. Nothing is answered without a tap.
- [ ] Allow on free/busy returns **busy ranges only**: merged, clipped to the range, no titles or locations.
- [ ] Decline, and "calendar unavailable", give a clean task state, not an error.
- [ ] Every approval button works only once (a double tap can't answer twice).
- [ ] The owner's typed reply goes straight to the peer: it never reaches the main AI and is never logged.
- [ ] Outbound messages are refused when the turn was not the owner's own. That covers text from email, the web,
      another agent or a scheduled job.
- [ ] The approval preview shows the peer's name, domain and the **exact** text that will be sent.

## Outbound client and delivery

- [ ] The full round-trip works: send a request, the fake peer answers, the owner is notified once.
- [ ] Answers received from the peer are escaped before display and parsed strictly.
- [ ] A URL that points at a private or internal address is refused (SSRF check), and redirects are not followed.
- [ ] Protocol fallback: a v1.0 client talks to a v1.0-only peer, and falls back to 0.3 exactly once on
      "method not found".
- [ ] Push goes only to the **address-book URL**, never to a URL found in the peer's message.
- [ ] A failed push is retried at most twice, then stops. No push happens while paused or when the peer is revoked.
- [ ] A pushed update and a later poll for the same task notify the owner only **once**.
- [ ] A `task_update` for a task you never sent to that peer is refused.

## AI in the loop (if you add suggested replies or follow-up questions)

- [ ] The drafter receives **only** the listed inputs. Assert on the exact prompt: wrapped agent text, peer name,
      busy times, date and time, filtered memories, and no tools.
- [ ] Agent text containing a closing tag (e.g. `</untrusted_agent_message>`) can't break out of its wrapper.
- [ ] The memory filter drops private topics in **every language you support**, and keeps harmless near-misses
      (e.g. "fine with that" vs. a parking fine).
- [ ] A draft that touches a private topic is still shown, with a warning.
- [ ] A failed or slow draft (> ~30 s) falls back to plain Reply/Ignore.
- [ ] A saved draft survives a restart, and is never visible to the peer unless it is sent.
- [ ] With drafts switched off, or with no AI configured, no AI call is made.
- [ ] In the main assistant's context, agent text is quoted, neutralised and marked untrusted, and the owner's outcome
      ("you replied …") is appended.
- [ ] Text from public web forms (sign-ups and the like) never reaches the AI at all.

## Logs and privacy

- [ ] Audit rows hold ids, outcomes, counts and costs only. Assert that no message text, times, keys or URLs appear
      in them.
- [ ] Whatever the AI sees about peers is limited to name and domain.
