# Signature scheme `a2a-sig-v1`

A2A deliberately leaves authentication to the implementer. This scheme gives both directions strong, per-message
authentication with only **public** keys exchanged. Reference code: `scripts/a2a_sign.py`, `scripts/a2a-sign.mjs`
(both pass the test vector below).

## Keys and fingerprints

- Each agent has one Ed25519 key pair. The private key never leaves its server (file mode 0600, never logged, backed
  up only encrypted). The public key is the raw 32 bytes, shared as standard base64 (44 characters). Accepting
  base64url as well (`-`/`_`, no padding) is harmless: it decodes to the same bytes.
- **Fingerprint** = first 16 bytes of `sha256(raw public key)`, as 32 lowercase hex characters. People read it in
  groups of four (`3475 0f98 bd59 fcfc …`).
- Pairing: both owners swap address + public key + name, then **read the fingerprints aloud** and compare against what
  they computed from the key they received. This is the only defence against a key swapped in transit. A "secret shown
  only once" is a token, not a public key — refuse it.

## Headers (on every request AND every response)

| Header | Value |
|---|---|
| `A2A-Key-Id` | sender's fingerprint |
| `A2A-Timestamp` | unix seconds; receiver accepts at most 300 s difference |
| `A2A-Nonce` | >= 16 random bytes, base64url without padding (22–64 chars); never reused |
| `A2A-Signature` | base64 Ed25519 signature of the signing string |

## Signing string

UTF-8, lines joined with a single `\n`, no trailing newline:

```
a2a-sig-v1
<METHOD>                   POST / GET for requests, RESPONSE for responses
<path>                     e.g. /a2a (no query string)
<recipient fingerprint>    of the party receiving THIS message
<timestamp>
<nonce>
<hex sha256 of the body>   of the empty string for a GET
<request nonce>            ONLY for responses: the A2A-Nonce of the request being answered
```

Why each line exists: the version prefix allows future schemes; method and path stop a signature for one endpoint
being reused on another; the **recipient fingerprint** stops a message sent to agent B being replayed to agent C; the
timestamp and nonce stop replays; the body hash makes the content tamper-evident; the request nonce in responses stops
an old answer from being passed off as the answer to a new question. Version headers (e.g. `A2A-Version`) are not
signed — the scheme is the same for all protocol versions.

### Exact encoding (no guessing)

- **Nonce:** the header text itself goes into the signing string, not its decoded bytes. Receivers reject anything
  that isn't 22–64 characters of `A-Za-z0-9_-`.
- **Timestamp:** decimal ASCII digits only (no sign, no decimals, ≤ 12 digits), copied as text. Anything else is
  rejected.
- **Body hash:** sha256 of the raw body bytes exactly as sent or received, never of re-serialised JSON. Lowercase hex.
- **Fingerprints** (`A2A-Key-Id` and the recipient line): 32 lowercase hex characters, compared exactly. Uppercase is
  rejected, not normalised.
- **Path:** the request path exactly as sent, without the query string. Only `/a2a` and
  `/.well-known/agent-card.json` exist, so no normalisation is needed; any other path is a 404 before signature checks.
- **Signature:** standard base64 (with padding) of the 64-byte Ed25519 signature. A missing header, invalid base64 or a
  wrong length all give the same generic failure as a bad signature.

## Receiver checks, in order

1. `A2A-Key-Id` belongs to an active, unexpired peer in the owner's address book → else 401.
2. Timestamp within ±300 s → else 401.
3. Signature valid, with recipient = own fingerprint → else 401.
4. Nonce not seen from this peer in the last 10 minutes → else 401. **Persist** nonces (a database table purged after
   10 min), and record them only *after* the signature check, so strangers can't fill the table.

All failures get the **same** generic 401 (no oracle telling an attacker which check failed), no notification to the
owner, and no AI call. Rate-limit the audit rows for rejections.

The client verifies responses the same way (method `RESPONSE`, own fingerprint as recipient, the nonce it sent) and
treats an unsigned or wrongly signed response as a failure. The response's key id must be the fingerprint of the
peer the request was sent to, and its timestamp must be within ±300 s. A separate nonce store isn't needed on the
client: binding the response to the fresh request nonce already makes each response single-use.

## Test vector

Private key seed: 32 bytes of `0x01`. Public key `iojj3XQJ8ZX9UtstPLpdcspnCb8dlBIb83SIAbQPb1w=`, fingerprint
`34750f98bd59fcfc946da45aaabe933b`. Recipient fingerprint `6a3803d5f059902a1c6dafbc9ba47292`, timestamp `1790000000`,
nonce `Zm9vYmFyYmF6cXV4MTIzNDU2`, method `POST`, path `/a2a`, body:

```
{"jsonrpc":"2.0","id":"1","method":"GetTask","params":{"id":"0123456789abcdef"}}
```

Signing string:

```
a2a-sig-v1
POST
/a2a
6a3803d5f059902a1c6dafbc9ba47292
1790000000
Zm9vYmFyYmF6cXV4MTIzNDU2
b65d81b3ab861357cf09adce6816994ed0040526f9276182890249a25f23e968
```

Ed25519 is deterministic, so the signature must be exactly:

```
B20jjXSG2n2g/TNzBwwsoE/JHnVuMUn7eBzfM2Wk7l0wWK89K6aDG5Js2KT0WLHddFSgLqHpEcv1eQRwtZIvAw==
```
