# ChatGPT-style shell layout: sidebar, central chat, new chat

Status: ready-for-agent

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
