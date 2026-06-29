# Mode selection (Citizen / Professional) in the UI

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Surface the dual-mode behavior in the frontend.
When the user starts a new Conversation, they pick Citizen or Professional mode; the choice is locked for that Conversation's lifetime, and switching means starting a new chat.
The selected mode is shown per Conversation as a badge in the sidebar, and every message in that Conversation routes through the existing dual-mode seam with the locked mode.
The default mode for a new Conversation is Citizen.

This slice wires the UI to the dual-mode seam that already exists; it does not change retrieval or generation behavior, only how mode is chosen, displayed, and carried.

## Acceptance criteria

- [ ] Starting a new Conversation offers a Citizen/Professional choice, defaulting to Citizen
- [ ] The chosen mode is locked for that Conversation and cannot be changed mid-Conversation
- [ ] Each Conversation shows its mode as a badge in the sidebar
- [ ] Messages route through the existing dual-mode seam using the Conversation's locked mode
- [ ] A Professional-mode Conversation returns the terser, citation-dense answer style; Citizen returns the plain-language style
- [ ] The locked mode is preserved with the Conversation across reload (once persistence exists)

## Blocked by

- `13-chatgpt-shell-layout-sidebar.md`
