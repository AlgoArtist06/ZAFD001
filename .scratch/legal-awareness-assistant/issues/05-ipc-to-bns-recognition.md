# IPC-to-BNS recognition end-to-end

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Let a user who only knows old IPC section numbers still get a correct, current answer.
When input references a repealed IPC number, the IPC-to-BNS Mapping normalizes it to the current section before retrieval.
The answer is grounded in the current BNS section and annotates the former IPC number as a courtesy.
The mapping is used only for input normalization and output annotation and is never treated as a Source of Truth.

## Acceptance criteria

- [ ] Input referencing an old IPC number is recognized and normalized before retrieval
- [ ] The answer is grounded in the current BNS section
- [ ] The answer annotates the former IPC number (for example "formerly IPC 420") without citing it as a source
- [ ] The IPC-to-BNS Mapping is never used as a retrieval source
- [ ] A gold eval case covering an old-number query passes

## Blocked by

- `02-grounded-answer-english-citizen.md`

## Comments

Built an IPC-number recognition step that normalizes repealed IPC references to the current BNS section before retrieval, end to end through the existing `answer(query, mode, language)` seam.

- New `rag/recognition.py`: `recognize_ipc(query, mapping)` is gated on the literal "IPC" token (so a bare "Section 318" is not mistaken for an IPC reference), looks each section number up in the IPC-to-BNS Mapping, and returns a `RecognizedQuery` whose query has the current BNS section number + label appended for retrieval, plus the matched mapping entries for annotation.
- `rag/answer.py`: `LegalAssistant` now holds an `IpcBnsMapping` (defaulting to the committed `data/ipc_bns_mapping.json`) and runs recognition before `expand_query`/retrieval. A `former_ipc_note` ("formerly IPC 420 (...)") is added to `GroundedAnswer` and rendered after the legal basis. The mapping only rewrites the query string and annotates output - it is never chunked, embedded, or cited; citations stay BNS-only (e.g. IPC 420 resolves to a citation of BNS Section 318).
- Added a gold eval case `ipc-420-to-bns-318-en` and tests in `tests/test_recognition.py`, `tests/test_answer.py`, and `tests/test_eval.py`.

Followed red -> green -> refactor. Full suite (112 tests) passes; mypy reports only 4 pre-existing errors in the unrelated `rag/expansion.py` (present on HEAD), and the new files are clean. No lint tool is configured.
