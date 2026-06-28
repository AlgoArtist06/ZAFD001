# Privacy and data control

Status: ready-for-agent

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
