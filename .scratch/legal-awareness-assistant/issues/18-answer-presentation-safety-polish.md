# Answer presentation and safety polish

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Render the Grounded Answer in the structured, safe, low-literacy-friendly form the PRD requires.
Every answer shows, in order: a plain-language explanation, the exact legal basis as a distinct verbatim-English Citation block, a practical next step, and a persistent disclaimer with a legal-aid pointer (consult a lawyer / nearest Legal Services Authority, NALSA/DLSA).
High-stakes or emergency-category answers lead with emergency and helpline contacts (for example 112, 181, NALSA/DLSA) before the law.
Out-of-scope and unsupported queries render a clear, graceful refusal rather than a guess.
The interface uses large, readable text and icon-led category tiles so a low-literacy user can navigate it.

This is presentation and routing in the UI over signals the answer seam already returns (high-stakes notice, citation, refusal flag, disclaimer); it does not change what the seam decides.

## Acceptance criteria

- [ ] Answers render the four structured parts: explanation, verbatim-English legal basis, next step, disclaimer + legal-aid pointer
- [ ] The Citation block is visually distinct and shows the statutory text in original English
- [ ] High-stakes/emergency answers lead with emergency and legal-aid contacts before the legal content
- [ ] Out-of-scope and unsupported queries show a clear graceful refusal, never a fabricated answer
- [ ] The disclaimer and legal-aid pointer appear on every answer
- [ ] The UI uses large readable text and icon-led category tiles for common topics
- [ ] Refusal, emergency, and normal-answer states are each visually distinguishable

## Blocked by

- `13-chatgpt-shell-layout-sidebar.md`

## Comments

Built test-first (red -> green -> refactor).

This slice is presentation and routing over the signals the answer seam already returns; it changes no decision the seam makes.

Wire format: `POST /api/answer` now streams the Grounded Answer as NDJSON frames (`application/x-ndjson`), one structured part per line, instead of a flat text blob.
A leading `meta` frame carries the answer's state (`normal` / `emergency` / `refusal`), followed by the optional high-stakes notice, the plain-language explanation, each Citation (reference + verbatim English text + source URL), an optional former-IPC note, the next step, and the disclaimer.
The frames are derived in `rag/fastapi_app.py` from the existing `GroundedAnswer` fields; retrieval, grounding, citation verification, and guardrails are untouched.
The legacy WSGI HTML demo (`rag/shell_app.py`) still uses the plain-text `stream_answer` and was left alone.

Frontend (`web/`): new `src/components/answer-view.tsx` renders the structured, low-literacy-friendly answer.
Every answer shows, in order: a plain-language explanation, a visually distinct Citation block with the statutory text quoted verbatim in original English (`<blockquote lang="en">`), a practical next step, and the disclaimer with its legal-aid pointer (NALSA / DLSA).
High-stakes/emergency answers lead with a `role="alert"` block of emergency and helpline contacts (112, 181, NALSA/DLSA) before any legal content.
Out-of-scope/unsupported queries render as a graceful refusal (no fabricated citation), and each state (`normal` / `emergency` / `refusal`) is tinted distinctly and carries a `data-answer-state` marker so the three are distinguishable.
`src/components/shell.tsx` parses the NDJSON stream line by line and folds each frame into the active assistant turn's structured answer as it arrives, then renders it through `AnswerView`; the empty state now offers icon-led category tiles (Consumer rights, Police & arrest, Fundamental rights, Criminal law, Government schemes) that prefill a starter question, and answer/question text was bumped to large readable sizes.

Verified: `web` vitest (23, incl. new `answer-view.test.tsx` and added shell cases for structured rendering, refusal, emergency ordering, and category tiles), `npm run lint`, and `tsc --noEmit` all clean; full Python suite green (215), including the updated `tests/test_fastapi_app.py` case pinning the structured NDJSON citation frame over HTTP.
