# ChatGPT-style shell layout: sidebar, central chat, new chat

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Grow the single-input page into the ChatGPT-style shell layout the PRD describes, built with shadcn/ui.
A left sidebar lists the current session's Conversations and carries a clear new-chat action.
The central column is a chat thread of message bubbles (user turns and assistant Grounded Answers) that streams each new answer in place.
Follow-up questions within a Conversation build on prior turns by routing through the existing multi-turn memory seam, so the user does not repeat context.

Persistence in this slice stays in-memory/client-side; durable cross-device history arrives in a later slice.
The focus here is the layout, the conversation thread, the new-chat flow, and multi-turn continuity within one Conversation.

## Acceptance criteria

- [ ] A shadcn/ui shell renders a left sidebar (Conversation list + new-chat action) and a central chat thread
- [ ] User and assistant turns render as a scrollable thread, with the latest answer streaming in place
- [ ] The new-chat action starts a fresh, empty Conversation that becomes the active one
- [ ] A follow-up question in the same Conversation is answered using prior turns via the existing memory seam
- [ ] Starting a new Conversation does not carry memory across from a previous one
- [ ] The layout is responsive and the central thread remains readable on a narrow viewport

## Blocked by

- `12-nextjs-shadcn-scaffold-streaming-answer.md`

## Comments

Built test-first (red -> green -> refactor).

Frontend (`web/`): grew the single-input page into a ChatGPT-style shell in `src/components/shell.tsx`, rendered by `src/app/page.tsx`.
A shadcn/ui sidebar (`aside`) carries the brand, a clear `+ New chat` action, and the session's Conversation list; the central column is a scrollable thread of user/assistant bubbles that streams each Grounded Answer in place via the existing chunk-by-chunk fetch reader.
Conversations live in client-side React state for this slice (in-memory, as the issue scopes).
New chat opens a fresh empty Conversation and makes it active; selecting a Conversation switches the thread.
The layout stacks the sidebar above the thread on narrow viewports and sits it left on wider ones, with the thread centered (`max-w-2xl`) so it stays readable.

Multi-turn memory: each turn sends the active Conversation's prior user turns as `context`; the FastAPI `/api/answer` endpoint now routes that through the existing `rewrite_followup` seam (bounded to the last 4 turns, mirroring `Conversation._CONTEXT_TURNS`) before retrieval.
A fresh Conversation sends empty context, so memory never carries across Conversations.

Tooling: added Vitest + Testing Library to `web/` (no `@vitejs/plugin-react` - it conflicts with shadcn's Babel 7; Vitest's oxc transform handles JSX).
Tests cover streaming a turn into the thread, the new-chat flow, follow-up context, and no cross-Conversation memory.

Verified: `web` vitest (4), `npm run lint`, `tsc --noEmit`, `next build` all clean; full Python suite green, including two new `tests/test_fastapi_app.py` cases pinning the context-aware follow-up over HTTP.
