# Multilingual layer: Tamil and Gujarati

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Extend the multilingual layer built for Hindi to Tamil and Gujarati.
Add hand-verified Tamil and Gujarati rows to the Bilingual Legal Glossary, noting the known soft spot that official central-act translations may be unavailable for verification of these languages.
Generate answers in Tamil and Gujarati with the same rules: English Citation Anchor, critical terms with the English term inline in brackets, and the Confirmation Step in Citizen Mode.
Give these lower-resource languages extra evaluation attention.

## Acceptance criteria

- [ ] Tamil and Gujarati queries are normalized to English and answered in the user's language
- [ ] The Bilingual Legal Glossary is extended with hand-verified Tamil and Gujarati rows
- [ ] The Citation Anchor remains verbatim English; critical terms show the English term inline
- [ ] The gold eval set runs per language with extra attention to Tamil and Gujarati
- [ ] Any glossary terms lacking an official translation source are flagged

## Blocked by

- `06-multilingual-hindi.md`
