# Next.js + shadcn scaffold with one streaming Grounded Answer

Status: done

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

## Comments

Built the tracer-bullet slice end to end, TDD on the backend.

Backend (`rag/fastapi_app.py`): a thin FastAPI app exposing `POST /api/answer` that streams a Grounded Answer back chunk by chunk via `StreamingResponse` (no fixed `Content-Length` - chunked, not a blob).
It is a wrapper only: it reuses the shared `stream_answer` helper over the existing `answer()` seam and adds no retrieval or grounding of its own.
`build_demo_app()` (a uvicorn `--factory`) loads the real `data/` Source of Truth corpus; `create_app(assistant)` keeps the assistant injectable for tests.
Replaced the ad-hoc stdlib WSGI demo as the entry point: removed `build_app`/`_read_index` and the orphaned `rag/static/index.html`, leaving `rag/api.py` as just the shared `stream_answer`/`_answer_parts` streaming helper (still used by `rag/shell_app.py`).

Tests (`tests/test_fastapi_app.py`): in-scope query streams the explanation plus the verbatim cited legal basis; response is chunk-encoded (no `Content-Length`); unsupported query streams the "I do not have a sourced answer for that" refusal. Trimmed `tests/test_api.py` to the streaming-helper test. Full suite green.

Frontend (`web/`): Next.js 16 (App Router) + Tailwind v4 + shadcn/ui (radix/nova). The page is a client component using the shadcn `Textarea` and `Button` for the chat surface; it POSTs one English Citizen-mode question and renders the streamed answer as it arrives by reading the response body reader. `next build`, `eslint`, and `tsc --noEmit` all pass. `NEXT_PUBLIC_API_URL` overrides the default `http://localhost:8000/api/answer`.

Verified end to end with uvicorn + curl: in-scope question streams a real BNS-grounded answer, out-of-scope streams the refusal, and the CORS preflight succeeds. `web/README.md` documents running both servers together.
