# Language switcher (English, Hindi, Tamil, Gujarati)

Status: ready-for-agent

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
