# Clerk authentication and consent at signup

Status: done

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

## Comments

Built test-first (red -> green -> refactor) on the existing seams; the backend
auth/consent/notice contract in `rag/fastapi_app.py` was already in place and
tested, so this slice is the Next.js wiring that puts real accounts in front of
it.

- `ClerkProvider` wraps the app in `layout.tsx`, and a Next.js 16 `proxy.ts`
  (Clerk middleware) protects every route except the Clerk-hosted `/sign-in`
  and `/sign-up` pages, so an unauthenticated visitor never reaches the shell.
- `page.tsx` now renders `AuthedApp`, a client gate that redirects an
  unauthenticated user to sign-in and otherwise threads Clerk's `getToken` into
  the consent gate and the shell.
- `ConsentGate` fetches the DPDP privacy notice from `/api/privacy-notice`
  (third-party-LLM disclosure and trade-off), blocks the shell until the user
  explicitly opts in, then records consent server-side via
  `POST /api/consent` carrying the user's `Authorization: Bearer` token.
- `Shell` attaches the signed-in user's Clerk token on every `POST /api/answer`,
  so the existing accounts seam verifies the session and attributes the request
  to that user - no cross-user leakage. A new `lib/api.ts` centralises the
  backend base URL the shell, notice, and consent calls share.
- Clerk config keys are already present as placeholders in the repo-root
  `.env.example`; no new real secret was committed. `.venv/` was added to
  `.gitignore` (used only to run the backend suite locally).

Verified: web `vitest` (7 passing, incl. new auth-token and consent-gate tests),
`eslint` clean, `tsc --noEmit` clean, `next build` succeeds with the proxy and
Clerk routes, and the full backend `pytest` suite stays green.
