# Legal Awareness Assistant - web demo

A tracer-bullet frontend for the Multilingual Legal Awareness Assistant.
Type one English question in Citizen mode and watch a sourced Grounded Answer stream in, including the verbatim cited legal basis.

This slice has no authentication, sidebar, history, language switcher, or mode selector.
It is a Next.js (App Router) app with Tailwind and shadcn/ui that talks to a thin FastAPI streaming endpoint.
The FastAPI layer is a wrapper only: all retrieval, grounding, citation verification, and guardrails stay in the existing `rag` answer seam.

## Architecture

```
Next.js page (shadcn Textarea + Button)
        |  POST /api/answer  (streamed text/plain chunks)
        v
FastAPI  rag.fastapi_app  ->  rag.answer.answer(query, mode, language)
```

## Prerequisites

- Python with `fastapi` and `uvicorn` installed (for the backend).
- Node.js 20.9+ and npm (for the frontend).

## Run the FastAPI backend

From the repository root:

```bash
pip install fastapi uvicorn
uvicorn rag.fastapi_app:build_demo_app --factory --reload --port 8000
```

The backend loads the real Source of Truth corpus from `data/` and exposes a single streaming endpoint:

- `POST /api/answer` with body `{"query": "...", "mode": "citizen", "language": "en"}`
  streams the Grounded Answer back as `text/plain` chunks.

Quick check:

```bash
curl -N -X POST http://localhost:8000/api/answer \
  -H 'Content-Type: application/json' \
  -d '{"query": "what is the punishment for cheating"}'
```

## Run the Next.js dev server

In a second terminal, from this `web/` directory:

```bash
npm install
npm run dev
```

Open http://localhost:3000 and ask a question.

The frontend posts to `http://localhost:8000/api/answer` by default.
Point it elsewhere with `NEXT_PUBLIC_API_URL`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/answer npm run dev
```

## Try it

- In scope: "What does the law say about theft of property?" streams the plain-language explanation and the verbatim BNS section it is grounded in.
- Out of scope: "best recipe for biryani" streams the refusal, "I do not have a sourced answer for that".
