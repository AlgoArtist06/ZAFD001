# Language switcher (English, Hindi, Tamil, Gujarati)

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Let the user ask and read in their own language from the UI.
Add a language selector offering English, Hindi, Tamil, and Gujarati; the chosen language is passed as the `language` parameter into the existing multilingual answer seam.
The explanation comes back in the user's language, while the statutory Citation and verbatim quoted text stay in their original authoritative English, and critical legal terms are shown in the user's language with the English term inline in brackets.

This slice exposes the multilingual seam that already exists end to end through the UI; it does not add a new translation pipeline.

## Acceptance criteria

- [ ] A language selector offers exactly English, Hindi, Tamil, and Gujarati
- [ ] The selected language is passed through to the existing multilingual answer seam
- [ ] The plain-language explanation renders in the selected language
- [ ] The Citation and verbatim statutory text remain in original English regardless of selected language
- [ ] Critical legal terms render in the user's language with the English term inline in brackets
- [ ] Selecting a non-English language and asking an in-scope question renders a correctly localized, still-sourced answer

## Blocked by

- `12-nextjs-shadcn-scaffold-streaming-answer.md`

## Comments

Exposed the existing multilingual answer seam through the chat shell UI.

- Added an "Answer language" selector to `web/src/components/shell.tsx` offering exactly English, Hindi (हिन्दी), Tamil (தமிழ்), and Gujarati (ગુજરાતી), each labelled by its own endonym/script. The selected language code drives the `language` parameter sent in the `/api/answer` request body (defaulting to `en`).
- The localized rendering (plain-language explanation in the user's language, Citation and verbatim statutory text staying in authoritative English, and critical legal terms rendered with the English term inline in brackets) is already implemented and tested in the `rag.multilingual` seam that `/api/answer` streams through; this slice is UI-only and adds no new translation pipeline.
- TDD: three new Shell tests cover defaulting to English, offering exactly the four languages, and passing the chosen language through to the seam. Full web suite (14 tests), eslint, `tsc --noEmit`, and the backend pytest suite all pass.
