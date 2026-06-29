# Low-literacy UI polish and final eval pass

Status: done

## Parent

PRD: `.scratch/legal-awareness-assistant/PRD.md`

## What to build

Apply the low-literacy-friendly polish and run the final evaluation pass.
Make the interface approachable: plain language, large readable type, and icon-led category tiles.
Add clear error and empty states.
Ensure the Disclaimer and Legal-Aid Pointer footers are consistent across the UI.
Run the final per-language gold eval pass across all four Supported Languages.

## Acceptance criteria

- [ ] UI uses plain language, large readable type, and icon-led category tiles
- [ ] Error and empty states are clear and handled
- [ ] Disclaimer and Legal-Aid Pointer footers are consistent across the UI
- [ ] Final per-language gold eval pass runs across English, Hindi, Tamil, and Gujarati
- [ ] Results meet the accuracy bar for each language

## Blocked by

- `07-multilingual-tamil-gujarati.md`
- `09-accounts-auth-chat-shell.md`

## Comments

Built test-first (red -> green -> refactor).

Final eval pass (`rag/eval.py`):
Added `run_final_eval`, which runs the curated gold subset for every Supported Language
(`SUPPORTED_LANGUAGES = en, hi, ta, gu`) through the real answer seam and checks each
against an accuracy bar (`ACCURACY_BAR = 1.0`).
`LanguageEvalResult` exposes per-language `accuracy` and `meets_bar`; `FinalEvalReport.passed`
holds only when every language clears its bar.
Tests cover full-language coverage, the accuracy bar per language, and a deliberate
wrong-section case proving the pass can fail.

Low-literacy UI polish (`rag/static/shell.html`):
Larger, more readable base type; an icon-led category tile for each Covered Domain in the
empty state (clicking a tile sends a plain-language starter question); a clear, dismissible
error banner replacing the silent in-bubble failure; and a persistent Disclaimer footer that
reuses the same Legal-Aid Pointer wording (NALSA / DLSA) as the grounded answers, kept
consistent with `rag.guardrails.LEGAL_AID_POINTER`.

All project tests pass (`python3.11 -m pytest`).
mypy on the changed `rag/eval.py` is clean (the 3 pre-existing errors in `rag/expansion.py`
are unrelated); no separate linter is configured.
