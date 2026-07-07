# Convex Frontend Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser FastAPI/NDJSON traffic with authenticated Convex hooks while preserving the existing UI and structured-answer behavior.

**Architecture:** Keep presentation components unchanged. `useChat` owns local UI state and calls generated Convex functions; `useQuery(chat.getStream)` supplies reactive stream snapshots. Consent and account deletion call their existing Convex functions directly.

**Tech Stack:** Next.js 16 client components, React 19, Clerk 7, Convex 1.42, Vitest 4.

## Global Constraints

- Keep Clerk as identity provider through `ConvexProviderWithClerk`.
- Remove `NEXT_PUBLIC_API_URL` from browser runtime.
- Do not delete Python until live Convex gold evaluation passes.
- Preserve normal, emergency, refusal, and error answer states and verified citations.
- Production answers require `LLM_API_KEY` and `LLM_MODEL`; no fallback answers.

---

### Task 1: Consent transport

**Files:**
- Modify: `web/src/components/consent-gate.test.tsx`
- Modify: `web/src/components/consent-gate.tsx`

**Interfaces:**
- Consumes: `api.chat.privacyNotice`, `api.chat.consentStatus`, `api.chat.recordConsent`
- Produces: unchanged `ConsentGate({ children })` rendering contract

- [ ] Write a test mocking `convex/react` which supplies notice/status and asserts `recordConsent({})` after checkbox acceptance.
- [ ] Run `npm test -- src/components/consent-gate.test.tsx`; expect failure because the component still calls `fetch`.
- [ ] Replace effects/fetch/token plumbing with `useQuery` and `useMutation`; retain loading and submission UI.
- [ ] Run the focused test; expect pass.

### Task 2: Account deletion transport

**Files:**
- Modify: `web/src/components/account-settings.test.tsx`
- Modify: `web/src/components/account-settings.tsx`
- Modify: `web/src/app/settings/page.tsx`
- Delete: `web/src/lib/account.ts`

**Interfaces:**
- Consumes: `api.chat.deleteAccount` action
- Produces: existing confirmation, error, navigation, and sign-out behavior

- [ ] Write a test mocking `useAction` and asserting the Convex action runs before navigation/sign-out.
- [ ] Run focused test; expect failure because deletion still uses REST.
- [ ] Call `useAction(api.chat.deleteAccount)` directly; remove `getToken` prop and REST helper.
- [ ] Run focused test; expect pass.

### Task 3: Chat history and mutations

**Files:**
- Modify: `web/src/components/shell.test.tsx`
- Modify: `web/src/components/shell.tsx`
- Modify: `web/src/components/authed-app.tsx`
- Modify: `web/src/hooks/use-chat.ts`

**Interfaces:**
- Consumes: `listConversations`, `getConversationHistory`, `createConversation`, `deleteConversation`, `ask`, `getStream`
- Produces: unchanged `Conversation`, `Turn`, and Shell presentation props

- [ ] Add hook-level/component tests whose mocked Convex functions prove history hydration, creation, deletion, ask, and reactive stream completion without `fetch`.
- [ ] Run focused tests; expect failure on current REST implementation.
- [ ] Replace REST calls and NDJSON frame application with Convex hooks. Subscribe with `useQuery(api.chat.getStream, streamId ? { streamId } : "skip")`; map each snapshot to `StructuredAnswer`; clear `streaming` only when `done`.
- [ ] Run focused tests; expect pass.

### Task 4: Remove REST frontend artifacts and verify

**Files:**
- Delete: `web/src/lib/api.ts`
- Delete: `web/src/lib/answer-stream.ts`
- Delete: `web/src/lib/answer-stream.test.ts`
- Modify: `web/src/components/answer-view.tsx`
- Modify: `web/README.md`
- Modify: `.env.example`

**Interfaces:**
- Produces: no `NEXT_PUBLIC_API_URL`, `/api/answer`, or NDJSON reader references under `web/src`

- [ ] Move shared answer types/default factory into `answer-view.tsx` or a minimal transport-neutral module only if imports require it.
- [ ] Remove obsolete REST files and documentation/env entries.
- [ ] Run `rg -n 'NEXT_PUBLIC_API_URL|/api/answer|readNdjson|apiUrl' web/src web/README.md .env.example`; expect no matches.
- [ ] Run `npm test`, `npm run lint`, and `npm run build`; expect all pass.
