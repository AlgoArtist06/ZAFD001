# PRD: Multilingual Legal Awareness Assistant (ZABR-008)

Status: ready-for-agent

## Problem Statement

Legal information in India is hard for ordinary citizens to understand and act on.
It is written in dense statutory English, scattered across many sources, and locked behind both language and literacy barriers.
A citizen who has been cheated by a shopkeeper, is unsure of their rights during a police interaction, wants to file an RTI, or needs to know if a government scheme applies to them, has no easy, trustworthy way to get plain-language answers in their own language.
The stakes are high: wrong or invented legal information actively harms a vulnerable person, so any tool serving this need must be accurate and traceable to a real legal source, not merely fluent.

## Solution

A retrieval-grounded legal information assistant where every answer is traceable to a cited government source.
It is delivered as a ChatGPT-style web application: a central chat box, a left sidebar of the user's past conversations, multilingual support (English, Hindi, Tamil, Gujarati), and two answer modes (Citizen and Professional).
It explains the law in plain language and shows the exact statutory citation alongside, but it never gives personalised legal advice.
The product priority order, fixed for all design decisions, is: Accuracy and sourcing first, then trust and safety guardrails, then multilingual access, then conversational UX, then the dashboard shell.

The system is built on a single authoritative legal corpus ingested only from government sources, retrieved through a disciplined RAG pipeline with citation verification, rendered through a glossary-grounded translation layer, and fenced by guardrails that keep it firmly on the "legal information, not legal advice" side of the line.

## User Stories

1. As a citizen, I want to ask a legal question in plain everyday language, so that I can understand my rights without knowing legal terminology.
2. As a citizen, I want to ask my question in Hindi, Tamil, or Gujarati, so that I am not blocked by an English-only interface.
3. As a citizen, I want the answer written in simple language in my own language, so that I can actually understand it.
4. As a citizen, I want to see the exact law and section the answer is based on, so that I can trust it and show it to a lawyer if needed.
5. As a citizen, I want the legal citation shown in its original English form even when the explanation is in my language, so that the reference stays accurate and court-traceable.
6. As a citizen, I want critical legal terms shown with their English term in brackets, so that a mistranslation cannot flip the meaning (for example bailable versus non-bailable).
7. As a citizen who has been cheated while shopping, I want to know what consumer protection law applies and how to complain, so that I can seek redress.
8. As a citizen, I want to understand my fundamental rights, so that I know what protections I have.
9. As a citizen, I want to understand my rights during a police interaction or arrest, so that I am not taken advantage of.
10. As a citizen, I want to understand intellectual property rights at a basic level, so that I know how my creative or inventive work is protected.
11. As a citizen, I want guidance on flagship government schemes (eligibility, documents, how to apply, official link), so that I can access benefits I am entitled to.
12. As a citizen who only knows old section numbers (for example IPC 420), I want the assistant to recognise them and answer with the current law, so that outdated knowledge does not block me.
13. As a citizen, I want a clear pointer to a lawyer or legal aid on every answer, so that I know where to go for actual representation.
14. As a citizen facing an emergency or safety-critical situation, I want to be shown emergency and helpline contacts first (for example 112, 181, NALSA/DLSA legal aid), so that I get urgent help before reading the law.
15. As a citizen, I want the assistant to refuse to predict my case outcome or tell me what to specifically do, so that I am not misled by advice it is not qualified to give.
16. As a citizen, I want to ask follow-up questions that build on my previous question in the same chat, so that I do not have to repeat context.
17. As a citizen, I want each new conversation to start fresh without remembering my past chats, so that my sensitive history is not carried across conversations.
18. As a legal professional or para-legal, I want a Professional mode that answers tersely with dense citations in statutory language, so that I can work efficiently.
19. As a legal professional, I want to query precise sections and ingredients directly, so that exact keyword matching returns the right provision.
20. As a registered user, I want to log in and see my past conversations in a sidebar across devices, so that I can return to earlier questions.
21. As a registered user, I want to start a new chat and pick Citizen or Professional mode for it, so that the answer style fits my need.
22. As a registered user, I want to delete a single conversation, so that I control my own data.
23. As a registered user, I want to delete my entire account and all stored data, so that I can exercise my right to erasure.
24. As a registered user, I want explicit consent and a clear privacy notice at signup, so that I understand what is stored, why, and that my queries are sent to a third-party LLM.
25. As a citizen, I want my stored legal questions protected, so that my legal vulnerabilities are not exposed.
26. As a low-literacy user, I want plain language, large readable text, and icon-led category tiles, so that the interface is approachable.
27. As a citizen, I want a clear "I do not have a sourced answer for that" response when the system lacks coverage, so that I am never given a confident wrong answer.
28. As a citizen, I want out-of-scope questions handled gracefully with a pointer to where to go, so that I am not given a fabricated answer.
29. As the product owner, I want every retrievable fact to be backed by a government source with complete provenance, so that the product is legally defensible.
30. As the product owner, I want the criminal-law answers grounded in the current BNS/BNSS/BSA codes, so that the tool never cites repealed statutes as current law.
31. As the product owner, I want landmark court judgments available as citations where relevant, so that answers can reference authoritative precedent without the system inventing case law.
32. As the product owner, I want measured accuracy per language via a gold evaluation set, so that I can vouch for the tool rather than merely claim it works.
33. As the product owner, I want the data layer verified before anything is built on top of it, so that downstream work does not inherit bad data.

## Implementation Decisions

### Scope of legal domains (v1)

- Covered domains: intellectual property rights, consumer rights, fundamental rights (Part III of the Constitution only), criminal law and interactions, and flagship government schemes.
- Explicitly excluded as sources: the Preamble and the Directive Principles of State Policy, because they are non-justiciable and carry no direct legal enforceability.
- Anything outside the covered domains is handled by a graceful out-of-scope refusal, never a guess.

### Source of truth and the IPC mapping layer

- Criminal law is grounded in the current codes: Bharatiya Nyaya Sanhita (BNS), Bharatiya Nagarik Suraksha Sanhita (BNSS), and Bharatiya Sakshya Adhiniyam (BSA), which replaced the IPC, CrPC, and Indian Evidence Act respectively from 1 July 2024.
- The BNS/BNSS/BSA corpus is the only substantive legal source the model retrieves from and quotes.
- An IPC to BNS mapping exists as a separate, structured lookup table (section-number pairs plus a short label), sourced from the official correspondence chart, never LLM-generated.
- The mapping is used only for input normalization (old number translated to current section before retrieval) and output annotation (answer cites the current section and notes the former IPC number as a courtesy). It is never a retrieval source, so it adds zero risk to BNS accuracy.

### Authoritative corpus and provenance

- All legal text is sourced strictly from government sources: the India Code portal for statutes, official ministry/aggregator sources for scheme information, and the relevant consumer and IP acts.
- No blogs, Wikipedia, or LLM-generated summaries are ever used as a primary source. Everything retrievable must be government-backed and traceable to a source citable in a court of justice.
- Every chunk carries a mandatory provenance record: act name, act year, section number (plus sub-section/clause where present), act type (criminal/consumer/IP/constitutional/scheme), source URL, source document hash, retrieval date, and the verbatim statutory text stored separately from any paraphrase. Scheme entries carry governing authority and official scheme URL in place of a section number.
- Each chunk also carries amendment history captured during ingestion.
- Hard rule: no provenance, no answer. The generator may only present claims backed by a chunk with complete provenance; anything else is refused or flagged "not in source."

### Landmark judgments

- Court precedents are not part of the bulk pipeline (case law is not cleanly available from government sources at scale, and free-form precedent generation is the highest hallucination risk).
- Instead, a single curated landmark-judgments source file holds well-known judgments with full citations (case name, citation number, year, court, official judgment URL), hand-verified.
- Strict rule: the model may cite a precedent only from this curated file, and may never generate one.

### Retrieval and answer architecture

- Hybrid retrieval combines keyword/BM25 (for exact section references, article numbers, act names) with vector search (for natural-language complaints).
- Retrieval is metadata-filtered and routed by domain first, so a consumer query does not pull criminal sections.
- Grounded generation operates under a hard contract: answer only from retrieved chunks, cite the provenance of each claim, and say "I do not have a sourced answer for this" rather than guess.
- A citation verification step programmatically checks that every section the model cited actually exists in the retrieved chunks; anything not retrieved is treated as hallucination and rejected or stripped.
- Structured answer format: plain-language explanation, then exact legal basis (cited), then practical next step, then the consult-a-lawyer/legal-aid disclaimer.

### Dual-mode over a single corpus

- Two modes share one corpus, one provenance layer, one retrieval index, and one citation verifier (single source of truth, never two copies of the law).
- Citizen mode: adds a complaint-to-legal-concept normalization step before retrieval, leans on semantic search, expands lay phrasing, answers in plain step-by-step language with stronger disclaimers.
- Professional mode: assumes legal terms and section numbers, leans on exact keyword/BM25 matching with no query expansion, answers tersely with dense citations.
- Mode is chosen when a conversation starts and is locked for that conversation's lifetime; switching means starting a new chat. Default mode for new users is Citizen.

### Chunking

- Adaptive hierarchical chunking. Sections under a token threshold are stored as one whole chunk; sections over the threshold are split into per-sub-section child chunks.
- The embedding/retrieval unit is the small (sub-section) unit, producing sharper embeddings and better retrieval on large sections.
- Each child carries a parent_section_id and full provenance. At query time, retrieved children are expanded up to the parent section and sibling sub-sections before generation, so the model always sees complete legal context (including provisos and exceptions) while citations remain at section level.
- Sub-section text is stored once, never duplicated per child; parent expansion is a query-time lookup, so storage stays compact.
- Definitions sections are chunked and tagged specially for citizen-mode concept matching.

### Multilingual layer

- Supported languages for v1: English, Hindi, Tamil, Gujarati. No other languages in v1.
- Flow: detect language, extract intent and normalize the query to English (legal terms preserved), retrieve and reason over the English corpus, generate the answer in the user's language.
- Query understanding uses LLM-based intent extraction (not a generic machine-translation API), which handles code-mixing (for example Hinglish) and maps colloquial complaints to legal concepts.
- The explanation is translated for comprehension, but the statutory citation and verbatim quoted text always remain in the original authoritative English.
- Critical legal terms are rendered in the user's language with the English term inline in brackets.
- Citizen mode includes a confirmation step for ambiguous queries (for example "did you mean...?") before answering.
- Known soft spot: Tamil and Gujarati are lower-resource, so they need the most glossary coverage and the most evaluation attention; official central-act translations may be unavailable for Tamil/Gujarati glossary verification.

### Glossary-grounded translation module

- The translation work is a separate lightweight module, not a second RAG pipeline.
- It uses a curated bilingual legal glossary (roughly 100 to 200 critical terms across the four languages, hand-verified) as a keyed lookup table.
- Relevant glossary terms are injected into the translation prompt as hard constraints, so the LLM produces fluent prose while the glossary nails the legal terms.
- This makes terminology deterministic, auditable, and faster than a vector-based approach, and more accurate for terminology than vector retrieval would be.

### Guardrails: information, not advice

- The system provides general legal information grounded in cited statute; it is explicitly not a legal advice tool, because the operator is not authorized to give legal advice and doing so would be unlawful. This boundary is made clear to users and enforced in the system.
- Layered enforcement: a scope contract in the system prompt, input-side classification (general law and procedure answered, case-outcome prediction and personalised "what should I do" refused and redirected), mandatory safety routing for high-stakes categories (lead with emergency and legal-aid contacts such as 112, 181, NALSA/DLSA), a persistent and useful disclaimer plus legal-aid pointer on every answer, an output-side refusal check that softens any answer that slipped into "you should sue / you will win / do X" language, and a hard out-of-scope refusal.
- Principle: the system may say "the law says X and the general process is Y"; it may never say "therefore in your case do Z and you will win."

### Accounts, privacy, and data handling

- Real accounts with server-side per-user storage and cross-device conversation history.
- Privacy is first-class, aligned with India's DPDP Act 2023: encryption at rest, no plaintext sensitive content in logs, explicit consent and a clear privacy notice at signup (including disclosure that queries are sent to a third-party LLM and the associated trade-off), user-controlled deletion of a single conversation, and full account-plus-data deletion (right to erasure).
- Memory exists within a single conversation (multi-turn) but does not persist across conversations; each new conversation is an isolated context.
- Multi-turn handling rewrites each follow-up into a standalone query using the bounded recent conversation context before retrieval; every turn still passes through the full retrieval, grounding, citation-verification, and guardrail pipeline.

### Technology stack

- Generation: an OpenAI-API-compatible model behind a router/gateway (so the model is a swappable config value). v1 default is Google Gemini 2.5 Flash via its OpenAI-compatible endpoint, free tier, disclosed in the privacy notice. Cheaper/weaker models are a knob, not the baseline, and any model must be tested against the grounding and refusal contract before being trusted.
- Embeddings: local open model via FastEmbed (BAAI/bge-base-en-v1.5), running on CPU with no API key and no data leaving the machine. This is safe because retrieval runs on English (English corpus, English-normalized queries).
- Vector store: Qdrant, holding legal documents only, chosen for best-in-class metadata filtering (domain routing and provenance), hybrid sparse-plus-dense search, and trivial self-hosting that keeps data in-boundary.
- Application data: Postgres for users, auth/consent records, and conversations.
- Backend, API, and RAG orchestration: Python with FastAPI (ingestion pipeline, hybrid retrieval, parent expansion, glossary module, citation verifier, guardrails), exposing streaming chat endpoints.
- Frontend: Next.js with Tailwind and shadcn/ui, providing the ChatGPT-style shell (central chat, left sidebar history, streaming responses, mode selection, language switcher).
- Auth: Clerk.
- Configuration is arranged ahead of time in a committed .env.example (LLM key needed from Phase 1, embeddings local with no key, Qdrant local Docker, Postgres and Clerk from Phase 3).

### Build sequencing and the Phase 0 gate

- Phase 0 (the hard gate): the ingestion module is a standalone build, run once over today's applicable laws, but kept re-runnable for future amendments.
- Ingestion is scoped to the v1 acts (BNS, BNSS, BSA, Consumer Protection Act 2019, the IP acts, and Constitution Part III). A parser tuned to this known set is preferred over a generic one. Schemes are curated structured fact-cards rather than parsed.
- Ingestion is a re-runnable pipeline with a validation gate: download, extract, structure-detect, chunk, validate (every chunk has a section number and complete provenance; failures flagged), embed, load to Qdrant.
- Phase 0 definition of done: 80 to 90 percent coverage of in-scope acts with the uncovered remainder logged and known (partial coverage is safe because of the no-provenance-no-answer and graceful out-of-scope rules), 100 percent provenance completeness, structural integrity (no orphaned children, gaps flagged), spot-check accuracy on 30 to 50 hand-verified sections, IPC to BNS mapping loaded and verified, and a retrieval smoke test where known queries return the correct section as top hit.
- After Phase 0 there is exactly one human checkpoint: the user reviews a consolidated artifact (the 30 to 50 sample sections side-by-side with official source links, plus the coverage/structural test report) in a single sitting and approves before Phase 1 begins. There is no mid-build interference.
- Data-independent work (app-shell scaffolding, Clerk auth wiring, Postgres schema, UI components) may proceed in parallel while the Phase 0 checkpoint is in the user's court, so the user is never a bottleneck. Only the RAG core waits on approval.
- Subsequent phases, each gated on the previous: Phase 1 RAG core (retrieval, parent expansion, grounded generation, citation verifier, guardrails) validated against the gold eval set; Phase 2 multilingual layer validated per language; Phase 3 app shell (FastAPI streaming endpoints, Next.js UI, Clerk auth, Postgres conversations, sidebar history, mode selection, consent and deletion flows); Phase 4 polish (low-literacy UI touches, disclaimers and legal-aid footers, error/empty states, final eval pass).

## Testing Decisions

A good test here asserts external, observable behavior, not implementation details: given an input, the right law is cited, refusals fire when they should, and language output holds up. Tests are pinned to ground truth the agent did not itself generate wherever content fidelity is at stake.

### Seam 1 - Ingestion output (the Phase 0 gate)

- Tested at the point where the pipeline produces validated chunk records, around the Qdrant load, independent of the RAG layer.
- Claude authors and runs these unit tests and iterates the parser until all pass; the Phase 0 gate stays closed until green.
- Structural-invariant tests are self-verifying and run fully autonomously: complete provenance on every chunk, no orphaned children, every parent link resolves, valid schema, IPC to BNS table loaded.
- Content-accuracy tests are pinned to source-of-truth values the agent did not generate (the real bare-act text and the user's spot-check), so the loop never grades its own homework. These cover text fidelity to the official source and section counts versus the actual act.
- The agent-autonomous build is followed by the single human checkpoint described above before Phase 1.

### Seam 2 - The RAG answer function (the core product)

- A single orchestration entry of the shape answer(query, mode, language) returning the answer, its citations, and a refused flag.
- Everything funnels through this seam: query rewriting, hybrid retrieval, parent expansion, grounded generation, citation verification, guardrails, and the multilingual layer via the language parameter.
- The gold evaluation set is the test suite at this seam. Each gold case asserts the correct section is cited, refusal fires for out-of-scope or advice-seeking inputs, and Hindi/Tamil/Gujarati outputs hold up. The eval set is hand-verified by the user against the bare-act text and is a v1 must-have (reducible in size if time is tight, never dropped).
- The eval set is re-run whenever the model, prompts, or chunking change, and re-run per language after the multilingual layer is added.
- The FastAPI route and the React UI sit above this seam as thin wrappers, so the core logic is tested without touching HTTP or the frontend.

### Prior art

- This is a greenfield repository, so there is no in-repo prior art yet. These two seams establish the testing conventions for the project.

## Out of Scope

- Voice input (ASR) and voice output (TTS); v1 is text chat plus the dashboard shell only. Voice is the roadmap answer to full literacy inclusion.
- Languages beyond English, Hindi, Tamil, and Gujarati.
- Legal domains beyond the five covered; out-of-scope queries are refused gracefully.
- Personalised legal advice, case-outcome prediction, and litigation strategy; the product is strictly an information tool.
- A broad case-law corpus; only the curated landmark-judgments file is in scope.
- Continuous or scheduled ingestion; v1 is a one-time run with a re-runnable pipeline.
- Self-hosted/on-premise LLM inference; v1 uses a third-party API (disclosed).
- An analytics/admin dashboard; the dashboard is the citizen-facing chat shell, not usage analytics.
- Cross-conversation memory and long-term user profiling.
- An incognito/do-not-save chat toggle (optional future enhancement).
- Ingesting the entire India Code corpus; only the v1 acts are ingested, with the pipeline built to extend later.

## Further Notes

- The single most important non-negotiable is that no answer is presented without complete provenance, and that the citation verifier rejects any cited section not actually retrieved.
- The curated multilingual legal glossary and the per-language gold evaluation set are both v1 must-haves; they convert "we are accurate" from a claim into a measurable fact.
- The criminal-law currency point (BNS/BNSS/BSA over the repealed IPC) is both the single most likely accuracy failure for naive tools and a genuine differentiator when handled correctly.
- Free-tier LLM usage may train on inputs; this is acceptable for v1 only because it is disclosed in the privacy notice, and the embedding half is fully private (local). A real deployment would move generation to a paid no-training tier.
- All keys are arranged ahead of time in .env.example; the real .env must be git-ignored and never committed, and .scratch/ should also be git-ignored when version control is set up.
