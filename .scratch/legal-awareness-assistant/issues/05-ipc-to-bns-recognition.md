# IPC-to-BNS recognition end-to-end

Status: ready-for-agent

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
