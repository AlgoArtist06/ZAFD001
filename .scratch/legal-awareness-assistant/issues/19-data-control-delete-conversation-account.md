# Data-control UI: delete a Conversation, delete account

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Give the user control over their stored data, exercising the right to erasure the PRD requires.
From the UI, a user can delete a single Conversation, which removes it and its turns from the sidebar and from Postgres.
A user can also delete their entire account and all stored data, after a clear confirmation, which removes their Conversations and account record and signs them out.
Both actions route through the existing privacy/deletion seam so deletion is enforced server-side, not just hidden in the UI.

## Acceptance criteria

- [ ] A user can delete a single Conversation from the UI; it disappears from the sidebar and from storage
- [ ] A user can delete their entire account and all associated data after an explicit confirmation
- [ ] Account deletion removes the user's Conversations and account record, then signs the user out
- [ ] Both deletions are enforced server-side through the existing privacy/deletion seam
- [ ] A deleted Conversation cannot be reloaded afterward, including on another device
- [ ] Deletion actions are scoped to the authenticated user and cannot affect another user's data

## Blocked by

- `15-postgres-conversation-history.md`
