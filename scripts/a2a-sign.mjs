// Reference implementation of the a2a-sig-v1 signature scheme for Node.js (built-in `crypto`, no dependencies).
// Usage:  node a2a-sign.mjs --selftest
// This file holds no secrets: the test key is 32 bytes of 0x01, published on purpose.
import crypto from 'node:crypto';

const SPKI_PREFIX = Buffer.from('302a300506032b6570032100', 'hex');   // DER prefix of a raw Ed25519 public key
const PKCS8_PREFIX = Buffer.from('302e020100300506032b657004220420', 'hex'); // DER prefix of a raw Ed25519 seed
const MAX_SKEW = 300;

export const publicKeyFromRaw = (raw) =>
  crypto.createPublicKey({ key: Buffer.concat([SPKI_PREFIX, raw]), format: 'der', type: 'spki' });
export const privateKeyFromSeed = (seed) =>
  crypto.createPrivateKey({ key: Buffer.concat([PKCS8_PREFIX, seed]), format: 'der', type: 'pkcs8' });
export const rawPublic = (privateKey) =>
  crypto.createPublicKey(privateKey).export({ format: 'der', type: 'spki' }).subarray(12);
export const fingerprint = (rawPub) =>
  crypto.createHash('sha256').update(rawPub).digest().subarray(0, 16).toString('hex');

export function signingString(method, path, recipientFp, ts, nonce, body, requestNonce) {
  const lines = ['a2a-sig-v1', method, path, recipientFp, String(ts), nonce,
                 crypto.createHash('sha256').update(body).digest('hex')];
  if (method === 'RESPONSE') lines.push(requestNonce ?? '');
  return Buffer.from(lines.join('\n'), 'utf8');
}

export function signHeaders(privateKey, method, path, recipientFp, body, requestNonce, now, nonce) {
  const ts = Math.floor(now ?? Date.now() / 1000);
  nonce = nonce ?? crypto.randomBytes(18).toString('base64url');
  const sig = crypto.sign(null, signingString(method, path, recipientFp, ts, nonce, body, requestNonce), privateKey);
  return { 'A2A-Key-Id': fingerprint(rawPublic(privateKey)), 'A2A-Timestamp': String(ts),
           'A2A-Nonce': nonce, 'A2A-Signature': sig.toString('base64') };
}

// Signature + freshness only. ALSO check that the key id is an active peer and the nonce is unseen (persist nonces).
export function verify(headers, peerRawPub, method, path, ownFp, body, requestNonce, now) {
  const ts = Number(headers['A2A-Timestamp']);
  if (!Number.isFinite(ts) || Math.abs((now ?? Date.now() / 1000) - ts) > MAX_SKEW) return false;
  try {
    const data = signingString(method, path, ownFp, ts, headers['A2A-Nonce'], body, requestNonce);
    return crypto.verify(null, data, publicKeyFromRaw(peerRawPub), Buffer.from(headers['A2A-Signature'], 'base64'));
  } catch { return false; }
}

function selftest() {
  const key = privateKeyFromSeed(Buffer.alloc(32, 1));
  const pub = rawPublic(key);
  const recipient = '6a3803d5f059902a1c6dafbc9ba47292';
  const body = Buffer.from('{"jsonrpc":"2.0","id":"1","method":"GetTask","params":{"id":"0123456789abcdef"}}');
  const check = (ok, what) => { if (!ok) { console.error('FAIL:', what); process.exit(1); } };
  check(pub.toString('base64') === 'iojj3XQJ8ZX9UtstPLpdcspnCb8dlBIb83SIAbQPb1w=', 'public key');
  check(fingerprint(pub) === '34750f98bd59fcfc946da45aaabe933b', 'fingerprint');
  const h = signHeaders(key, 'POST', '/a2a', recipient, body, undefined, 1790000000, 'Zm9vYmFyYmF6cXV4MTIzNDU2');
  check(h['A2A-Signature'] === 'B20jjXSG2n2g/TNzBwwsoE/JHnVuMUn7eBzfM2Wk7l0wWK89K6aDG5Js2KT0WLHddFSgLqHpEcv1eQRwtZIvAw==', 'signature');
  check(verify(h, pub, 'POST', '/a2a', recipient, body, undefined, 1790000000), 'valid signature rejected');
  check(!verify(h, pub, 'POST', '/a2a', recipient, Buffer.concat([body, Buffer.from(' ')]), undefined, 1790000000), 'tampered body accepted');
  check(!verify(h, pub, 'POST', '/a2a', '0'.repeat(32), body, undefined, 1790000000), 'wrong recipient accepted');
  check(!verify(h, pub, 'POST', '/a2a', recipient, body, undefined, 1790000301), 'stale timestamp accepted');
  console.log('selftest OK: public key, fingerprint, signature and all rejection cases match');
}

if (process.argv.includes('--selftest')) selftest();
