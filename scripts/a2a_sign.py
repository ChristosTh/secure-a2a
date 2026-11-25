"""Reference implementation of the a2a-sig-v1 signature scheme (Ed25519), for testing interoperability.

Usage:
    python a2a_sign.py --selftest      # checks this code against the published test vector
    python a2a_sign.py --keygen        # prints a new key pair (private key stays on YOUR server only)

Requires: pip install cryptography
This file holds no secrets: the test key below is 32 bytes of 0x01, published on purpose.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SIG_VERSION = "a2a-sig-v1"
MAX_SKEW = 300  # seconds


def raw_public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def fingerprint(raw_pub: bytes) -> str:
    """First 16 bytes of sha256(raw 32-byte public key), as 32 lowercase hex characters."""
    return hashlib.sha256(raw_pub).digest()[:16].hex()


def signing_string(method: str, path: str, recipient_fp: str, ts: int, nonce: str, body: bytes,
                   request_nonce: str | None = None) -> bytes:
    """Lines joined by a single \\n, no trailing newline. `method` is POST/GET for requests, RESPONSE for responses;
    responses add the request's nonce as an extra line (binds the answer to the question)."""
    lines = [SIG_VERSION, method, path, recipient_fp, str(ts), nonce, hashlib.sha256(body).hexdigest()]
    if method == "RESPONSE":
        lines.append(request_nonce or "")
    return "\n".join(lines).encode("utf-8")


def sign_headers(private: Ed25519PrivateKey, method: str, path: str, recipient_fp: str, body: bytes,
                 request_nonce: str | None = None, now: float | None = None, nonce: str | None = None) -> dict:
    ts = int(now if now is not None else time.time())
    nonce = nonce or base64.urlsafe_b64encode(secrets.token_bytes(18)).decode().rstrip("=")
    sig = private.sign(signing_string(method, path, recipient_fp, ts, nonce, body, request_nonce))
    return {"A2A-Key-Id": fingerprint(raw_public(private)), "A2A-Timestamp": str(ts),
            "A2A-Nonce": nonce, "A2A-Signature": base64.b64encode(sig).decode()}


def verify(headers: dict, peer_raw_pub: bytes, method: str, path: str, own_fp: str, body: bytes,
           request_nonce: str | None = None, now: float | None = None) -> bool:
    """Signature + freshness only. The caller must ALSO check that the key id belongs to an active peer and that
    the nonce was not seen from that peer in the last 10 minutes (store nonces persistently)."""
    try:
        ts = int(headers["A2A-Timestamp"])
        if abs((now if now is not None else time.time()) - ts) > MAX_SKEW:
            return False
        data = signing_string(method, path, own_fp, ts, headers["A2A-Nonce"], body, request_nonce)
        Ed25519PublicKey.from_public_bytes(peer_raw_pub).verify(base64.b64decode(headers["A2A-Signature"]), data)
        return True
    except (KeyError, ValueError, InvalidSignature):
        return False


# Published test vector (see references/signature-scheme.md)
TV_PRIVATE_SEED = bytes([1]) * 32
TV_PUBLIC_B64 = "iojj3XQJ8ZX9UtstPLpdcspnCb8dlBIb83SIAbQPb1w="
TV_FINGERPRINT = "34750f98bd59fcfc946da45aaabe933b"
TV_RECIPIENT = "6a3803d5f059902a1c6dafbc9ba47292"
TV_TS = 1790000000
TV_NONCE = "Zm9vYmFyYmF6cXV4MTIzNDU2"
TV_BODY = b'{"jsonrpc":"2.0","id":"1","method":"GetTask","params":{"id":"0123456789abcdef"}}'
TV_SIGNATURE = "B20jjXSG2n2g/TNzBwwsoE/JHnVuMUn7eBzfM2Wk7l0wWK89K6aDG5Js2KT0WLHddFSgLqHpEcv1eQRwtZIvAw=="


def selftest() -> None:
    key = Ed25519PrivateKey.from_private_bytes(TV_PRIVATE_SEED)
    pub = raw_public(key)
    assert base64.b64encode(pub).decode() == TV_PUBLIC_B64, "public key mismatch"
    assert fingerprint(pub) == TV_FINGERPRINT, "fingerprint mismatch"
    h = sign_headers(key, "POST", "/a2a", TV_RECIPIENT, TV_BODY, now=TV_TS, nonce=TV_NONCE)
    assert h["A2A-Signature"] == TV_SIGNATURE, "signature mismatch"
    assert verify(h, pub, "POST", "/a2a", TV_RECIPIENT, TV_BODY, now=TV_TS)
    assert not verify(h, pub, "POST", "/a2a", TV_RECIPIENT, TV_BODY + b" ", now=TV_TS), "tampered body accepted"
    assert not verify(h, pub, "POST", "/other", TV_RECIPIENT, TV_BODY, now=TV_TS), "wrong path accepted"
    assert not verify(h, pub, "POST", "/a2a", "0" * 32, TV_BODY, now=TV_TS), "wrong recipient accepted"
    assert not verify(h, pub, "POST", "/a2a", TV_RECIPIENT, TV_BODY, now=TV_TS + 301), "stale timestamp accepted"
    print("selftest OK: public key, fingerprint, signature and all rejection cases match")


def keygen() -> None:
    key = Ed25519PrivateKey.generate()
    pub = raw_public(key)
    seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    print("PUBLIC key (share it):        ", base64.b64encode(pub).decode())
    print("Fingerprint (read it aloud):  ", " ".join(fingerprint(pub)[i:i + 4] for i in range(0, 32, 4)))
    print("PRIVATE key (keep on your server only, file mode 0600, never commit or log):")
    print("  ", base64.b64encode(seed).decode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--keygen", action="store_true")
    args = ap.parse_args()
    if args.keygen:
        keygen()
    else:
        selftest()
