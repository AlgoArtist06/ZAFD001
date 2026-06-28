# Multilingual layer: Hindi

Status: ready-for-agent

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Build the multilingual answering layer, proving it out with Hindi first.
Detect the user's language and use LLM-based intent extraction to normalize the query to English with legal terms preserved (handling code-mixing such as Hinglish).
Retrieve and reason over the English Source of Truth, then generate the answer in Hindi.
The Bilingual Legal Glossary (Hindi rows) constrains terminology in the output so critical terms cannot flip meaning.
The Citation Anchor stays verbatim in English, and critical legal terms are rendered in Hindi with the English term inline in brackets.
Citizen Mode includes a Confirmation Step for ambiguous queries before answering.

## Acceptance criteria

- [ ] Language detection plus intent extraction normalizes a Hindi (or Hinglish) query to English with legal terms preserved
- [ ] Retrieval and reasoning run over the English corpus; the answer is generated in Hindi
- [ ] The Bilingual Legal Glossary constrains Hindi terminology in the output
- [ ] The Citation Anchor remains verbatim English
- [ ] Critical terms appear in Hindi with the English term inline in brackets
- [ ] Confirmation Step fires for ambiguous Citizen-mode queries
- [ ] The gold eval set runs for Hindi

## Blocked by

- `02-grounded-answer-english-citizen.md`
- `03-guardrails-information-not-advice.md`
