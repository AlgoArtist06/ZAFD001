# Legal Saathi - web frontend

The Next.js frontend of the Multilingual Legal Awareness Assistant.
A public landing page introduces the product; the chat itself lives at `/chat` behind Clerk authentication and an explicit privacy-consent gate.
Signed-in users ask legal questions in English, Hindi, Tamil, or Gujarati and receive Grounded Answers streamed token by token, each citing the verbatim statutory text it comes from.

## Architecture

```
/            static landing page (public)
/sign-in     Clerk-hosted auth in a branded panel (public)
/sign-up     Clerk-hosted auth in a branded panel (public)
/chat        AuthedApp -> ConsentGate -> Shell
                                          |  Convex mutations + reactive query
                                          v
             Convex answer pipeline -> Convex DB + vector search
```

Route protection happens at the edge in `src/proxy.ts` (Clerk middleware); `/`, `/sign-in`, and `/sign-up` are the only public routes.
All state lives in two hooks: `src/hooks/use-chat.ts` (conversations, streaming, deletion) and `src/hooks/use-theme.ts` (dark mode).
The components under `src/components/chat/` and `src/components/landing/` are presentation only.
Convex stores the growing structured answer in a stream document; `useQuery`
reactively updates the existing answer UI.

## The answer document contract

`chat.ask` returns a stream-document id. `chat.getStream` exposes its current
state until `done` becomes true.

| Field | Semantics |
|---|---|
| `state`, `language` | Normal, emergency, refusal, or error presentation |
| `highStakesNotice` | Emergency contacts before legal content |
| `explanation` | Cumulative generated explanation |
| `citations` | Verified references with verbatim statutory text |
| `note`, `nextStep`, `disclaimer` | Recognition note, practical step, legal boundary |

## Convex functions used

| Type | Function | Purpose |
|---|---|---|
| Query | `privacyNotice`, `consentStatus` | Consent gate |
| Mutation | `recordConsent` | Record consent |
| Query | `listConversations`, `getConversationHistory` | Restore history |
| Mutation | `createConversation`, `deleteConversation`, `ask` | Chat lifecycle |
| Query | `getStream` | Reactive answer updates |
| Action | `deleteAccount` | Erase Clerk and Convex data |

Clerk supplies the Convex JWT; application code never handles bearer tokens.

## Run it

Convex backend, from this `web/` directory:

```bash
npx convex dev
```

Frontend, from this `web/` directory (Node 20.9+):

```bash
npm install
npm run dev
```

Open http://localhost:3000.
Set `NEXT_PUBLIC_CONVEX_URL` and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in `web/.env.local`. Set `CLERK_JWT_ISSUER_DOMAIN`, `LLM_API_KEY`, and `LLM_MODEL` on the Convex deployment.

## Develop

```bash
npm run test    # vitest + testing-library
npm run lint    # eslint
npm run build   # production build
```

Design tokens (authority-navy palette, Noto Sans/Serif with Devanagari, Tamil, and Gujarati companions) live in `src/app/globals.css`; shadcn/ui primitives are vendored under `src/components/ui/`.
Note: this Next.js version differs from most training data - read `node_modules/next/dist/docs/` before changing routing, fonts, or middleware (see `AGENTS.md`).
