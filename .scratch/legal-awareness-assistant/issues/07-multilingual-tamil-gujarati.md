# Multilingual layer: Tamil and Gujarati

Status: done

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

## Comments

Extended the multilingual seam from Hindi to Tamil and Gujarati by making the
layer data-driven by language code instead of branching on Hindi.

- `detect_language` now walks an ordered table of script ranges (Devanagari,
  Tamil, Gujarati), so detection - including code-mixed queries - covers all
  three languages and falls back to English.
- `BilingualGlossary` holds each entry's translations as a per-language map and
  builds one reverse map across every language for normalisation, so `to_english`
  maps any foreign legal term to English and drops the remaining foreign-script
  function words. `term_for(term, language)` and `render` replace the
  Hindi-specific accessors (`hindi_for` kept as a thin wrapper for back-compat).
- `data/glossary.json` gains hand-verified Tamil (`ta`) and Gujarati (`gu`)
  columns for every term and domain. Rows whose translation could not be checked
  against an official central-act source list those codes under `unverified`;
  `glossary.unverified_terms(language)` surfaces them, honouring the known soft
  spot that official translations are often unavailable for these languages.
- `DeterministicGenerator` replaces its single Hindi branch with a per-language
  copy table (`_COPY`), so the Citizen explanation, Legal-basis label, next step,
  Disclaimer, and Professional heading all render in the target language. The
  Citation Anchor stays verbatim English, and critical terms render as
  `<term> (english)` in every language.
- Refusal text and the legal-aid next step now have Tamil and Gujarati copy, and
  the Confirmation Step poses its clarifying question in all three languages.
- The gold eval set gains Tamil and Gujarati subsets (8 cases each: five cited
  Citizen answers across domains, a Professional-mode case, a Refusal, and a
  Confirmation) for the extra attention these lower-resource languages warrant;
  `load_gold_cases(language=...)` runs each subset and all cases hold.

Tests: new `tests/test_multilingual_tamil_gujarati.py` (14 cases) built
red-green-refactor; full suite green. mypy clean on changed files (the 3
pre-existing `rag/expansion.py` errors are unrelated).
