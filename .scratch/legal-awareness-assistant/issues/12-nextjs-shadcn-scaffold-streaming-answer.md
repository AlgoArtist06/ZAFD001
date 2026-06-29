# Next.js + shadcn scaffold with one streaming Grounded Answer

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Stand up the real frontend the PRD calls for and prove it end to end with the narrowest possible path.
Scaffold a Next.js application (App Router) with Tailwind and shadcn/ui in a top-level `web/` directory.
On the page, a single shadcn chat input takes one English question in Citizen mode, sends it to a streaming HTTP endpoint, and renders the Grounded Answer as it streams back, including the cited legal basis.

To feed the frontend, expose the existing `answer(query, mode, language)` seam through a thin FastAPI streaming endpoint (per the PRD technology stack), replacing the ad-hoc stdlib WSGI surface as the demo entry point.
The FastAPI layer is a wrapper only: all retrieval, grounding, citation verification, and guardrails stay in the existing `rag` seam and are not reimplemented.

No authentication, no sidebar, no persisted history, no language switcher, and no mode selector yet.
This slice is the tracer bullet: type a question in a shadcn UI, watch a sourced answer stream in.

## Acceptance criteria

- [ ] A Next.js (App Router) app with Tailwind and shadcn/ui is scaffolded under `web/` and builds cleanly
- [ ] At least one shadcn/ui component is used for the chat input/submit surface
- [ ] A FastAPI endpoint streams a Grounded Answer over the existing `answer()` seam (token/chunk streaming, not a single blob)
- [ ] The FastAPI layer adds no retrieval or grounding logic of its own; it only wraps the `rag` seam
- [ ] Asking an in-scope English question renders the streamed explanation and the verbatim cited legal basis
- [ ] An unsupported question still renders the "I do not have a sourced answer for that" refusal
- [ ] A short README documents how to run the FastAPI backend and the Next.js dev server together

## Blocked by

- None - can start immediately
