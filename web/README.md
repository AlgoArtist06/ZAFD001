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
                                          |  POST /api/answer  (NDJSON frames)
                                          v
             FastAPI  rag.api.app (wired by rag.composition) -> rag.domain
```

Route protection happens at the edge in `src/proxy.ts` (Clerk middleware); `/`, `/sign-in`, and `/sign-up` are the only public routes.
All state lives in two hooks: `src/hooks/use-chat.ts` (conversations, streaming, deletion) and `src/hooks/use-theme.ts` (dark mode).
The components under `src/components/chat/` and `src/components/landing/` are presentation only.
The NDJSON folding logic is pure and unit-tested in `src/lib/answer-stream.ts`.

## The answer stream contract

`POST /api/answer` streams NDJSON frames, one JSON object per line.
Frames replace their field on the accumulating answer, except `citation`, which appends.

| Frame kind | Payload | Semantics |
|---|---|---|
| `meta` | `state` (`normal` / `emergency` / `refusal`), `language` | Leads the stream; may repeat later as a correction (late refusal) |
| `highStakesNotice` | `text` | Emergency contacts, always before legal content |
| `explanation` | `text` | Cumulative: each frame carries the full text so far |
| `citation` | `reference`, `verbatim`, `url` | One per verified Citation, appended |
| `note` | `text` | Former-IPC recognition note |
| `nextStep` | `text` | Practical next step |
| `disclaimer` | `text` | The persistent legal-aid pointer |

## Backend endpoints used

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/privacy-notice` | Notice text for the consent gate |
| GET | `/api/consent` | Whether this user already consented (skips the gate) |
| POST | `/api/consent` | Record consent |
| GET | `/api/conversations` | Hydrate the sidebar after a reload |
| POST | `/api/conversations` | Create a persisted Conversation |
| GET | `/api/conversations/{id}` | Load a Conversation's turns on selection |
| DELETE | `/api/conversations/{id}` | Delete one Conversation |
| POST | `/api/answer` | Ask; streams NDJSON frames |
| DELETE | `/api/account` | Erase the account and all data |

Every mutating call carries the Clerk session token as `Authorization: Bearer <token>`.

## Run it

Backend, from the repository root (see the root `.env.example` for all settings):

```bash
pip install -e . && pip install fastapi uvicorn "pyjwt[crypto]" httpx
set -a; source .env; set +a
uvicorn rag.composition:build_demo_app --factory --reload --port 8000
```

Frontend, from this `web/` directory (Node 20.9+):

```bash
npm install
npm run dev
```

Open http://localhost:3000.
The frontend targets `http://localhost:8000` by default; point it elsewhere with `NEXT_PUBLIC_API_URL`.
Clerk keys must be present in `web/.env.local` (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`) and exported to the backend so it verifies the same instance's session tokens.

## Develop

```bash
npm run test    # vitest + testing-library (shell, answer view, consent gate, stream folding)
npm run lint    # eslint
npm run build   # production build
```

Design tokens (authority-navy palette, Noto Sans/Serif with Devanagari, Tamil, and Gujarati companions) live in `src/app/globals.css`; shadcn/ui primitives are vendored under `src/components/ui/`.
Note: this Next.js version differs from most training data - read `node_modules/next/dist/docs/` before changing routing, fonts, or middleware (see `AGENTS.md`).
