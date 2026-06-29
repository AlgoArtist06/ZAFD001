# Privacy and data control

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Make privacy a first-class, DPDP-aligned feature on top of accounts.
At signup, require explicit consent and show a clear privacy notice that states what is stored, why, and that queries are sent to a third-party LLM with the associated trade-off.
Let a user delete a single Conversation.
Let a user delete their entire account along with all stored data, exercising the right to erasure.
Encrypt Conversation data at rest and keep sensitive content out of plaintext logs.

## Acceptance criteria

- [ ] Explicit consent plus a clear privacy notice is presented at signup and recorded
- [ ] The privacy notice discloses third-party LLM usage and the trade-off
- [ ] A user can delete a single Conversation
- [ ] A user can delete their account and all stored data, with deletion actually purging the data
- [ ] Conversation data is encrypted at rest
- [ ] Sensitive content does not appear in plaintext logs

## Blocked by

- `09-accounts-auth-chat-shell.md`

## Comments

Made privacy a first-class, DPDP-aligned layer on top of the issue 09 accounts seam, following the codebase's "deterministic offline behind a narrow seam, production swaps the real service" pattern.

- `rag/privacy.py` - the new privacy primitives.
  `PRIVACY_NOTICE` (+ `NOTICE_VERSION`) is the clear notice shown at signup: it states what is stored and why, and discloses that query text is sent to a third-party LLM together with the trade-off that carries.
  `ConsentLedger` records explicit consent against a notice version and erases it on a right-to-erasure request.
  `Cipher` is the encryption-at-rest seam (offline: a deterministic, dependency-free reversible XOR whose stored form is plainly not the plaintext; production swaps AES-GCM via a KMS behind the same `encrypt`/`decrypt`).
  `redact` keeps sensitive content out of plaintext logs.
- `rag/store.py` - Conversation content is now encrypted at rest: turn fields pass through the `Cipher` before being persisted and are decrypted on read, so a Citizen's words never sit in storage in the clear. Added owner-scoped `delete` (one Conversation) and `delete_all_for` (purge every Conversation a user owns).
- `rag/shell.py` - `sign_up(accept_privacy_notice=...)` makes consent a precondition: no session is issued without it, and consent is recorded. `record_consent` is the HTTP-side counterpart (Clerk owns signup/login; the app records consent to the notice it presented). Added `delete_conversation`, `delete_account` (purges data + erases consent), and a redacted log line on the chat path so sensitive content never reaches a plaintext log.
- `rag/shell_app.py` - new routes: `GET /api/privacy-notice` (the one unauthenticated /api route, since the notice is shown before a session exists), `POST /api/account/consent` (403 without acceptance), `DELETE /api/conversations/<id>`, and `DELETE /api/account`.
- `rag/static/shell.html` - presents the privacy notice in a consent dialog at signup (blocks use until consent is given and posted), a per-Conversation delete control, and a "Delete account and all data" action.

Tests: `tests/test_privacy.py`, `tests/test_store_privacy.py`, `tests/test_shell_privacy.py`, `tests/test_shell_app_privacy.py` (22 new tests). Full suite green (188). The 3 mypy errors are pre-existing in `rag/expansion.py` (untouched); the changed modules typecheck clean. No lint tool is configured.
