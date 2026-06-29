# Answer presentation and safety polish

Status: ready-for-agent

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
