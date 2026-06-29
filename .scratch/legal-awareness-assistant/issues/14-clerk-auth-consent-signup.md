# Clerk authentication and consent at signup

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Put real accounts in front of the shell using Clerk in the Next.js app, replacing the offline session stub.
Signup and login go through Clerk; the app is gated so only a signed-in user reaches the chat shell.
At signup the user must give explicit consent and is shown a clear privacy notice, including the disclosure that queries are sent to a third-party LLM and what that trade-off means, aligned with the DPDP framing already in the privacy seam.
The authenticated user's identity flows to the backend so Conversations are scoped to that user through the existing accounts seam (no cross-user leakage).

Durable storage of those Conversations is the next slice; here the requirement is that the session is real and every request is attributed to the signed-in user.

## Acceptance criteria

- [ ] Clerk powers signup and login in the Next.js app; unauthenticated users cannot reach the chat shell
- [ ] The signed-in user's session is verified on the backend through the existing accounts seam before any answer is served
- [ ] Conversations and requests are attributed to the authenticated user, never shared across users
- [ ] Signup requires explicit consent and shows a privacy notice that discloses third-party-LLM processing
- [ ] Consent is recorded server-side at the time it is given
- [ ] Required Clerk configuration keys are present as placeholders in `.env.example`, with no real secret committed

## Blocked by

- `13-chatgpt-shell-layout-sidebar.md`
