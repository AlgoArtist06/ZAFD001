# Multilingual Legal Awareness Assistant

The domain language for a tool that helps Indian citizens understand their legal rights, regulations, consumer protections, and basic procedures in their own language.
This glossary fixes the vocabulary so that every part of the project means the same thing by the same word.

## Language

### Product boundary

**Legal Information**:
General, source-backed explanation of what the law says and what the standard procedure is.
This is the only kind of output the product produces.
_Avoid_: advice, guidance, recommendation, opinion

**Legal Advice**:
A personalised recommendation about a specific person's situation (what to do, whether to sue, predicted outcome).
The product never produces this; the term exists only to name the line that must not be crossed.
_Avoid_: counsel, recommendation

**Refusal**:
A deliberate non-answer the product gives when a request is out of scope, unsupported by a source, or would require Legal Advice.
A Refusal redirects (to a lawyer, legal aid, or emergency contact) rather than guessing.
_Avoid_: rejection, error, fallback

**Disclaimer**:
The persistent, useful pointer to a lawyer or legal aid attached to every answer.
_Avoid_: fine print, footer

**Legal-Aid Pointer**:
A concrete reference to real help (for example NALSA/DLSA, or an emergency helpline) included in a Disclaimer or a High-Stakes response.
_Avoid_: help link

**High-Stakes Routing**:
The behavior of leading with emergency or helpline contacts before the legal explanation when a query touches safety, arrest-in-progress, or active deadlines.
_Avoid_: emergency mode, escalation

### Legal content

**Source of Truth**:
The single authoritative body of statutory text the product retrieves from and quotes.
For criminal law this is the current BNS/BNSS/BSA codes, never the repealed IPC/CrPC/Evidence Act.
_Avoid_: dataset, knowledge base, corpus (when you mean the authoritative one specifically)

**Provenance Record**:
The mandatory metadata attached to every unit of legal text that makes a Citation traceable to a government source citable in court.
Includes act, year, section, source URL, document hash, retrieval date, and the Verbatim Text.
_Avoid_: metadata, source info, reference data

**Citation**:
A precise pointer to the exact statutory basis of a claim (act, year, section, sub-section).
A claim without a backing Provenance Record cannot carry a Citation, and so cannot be answered.
_Avoid_: reference, source link

**Verbatim Text**:
The exact statutory language as published by the government, stored separately from any paraphrase.
Quoted Citations always use Verbatim Text.
_Avoid_: original text, raw text

**Citation Anchor**:
The Verbatim Text and Citation kept in their original authoritative English even when the surrounding explanation is in another language.
_Avoid_: source block, English citation

**IPC-to-BNS Mapping**:
A structured lookup that relates a repealed IPC section number to its current BNS equivalent.
Used only to recognise old numbers on input and to annotate answers; never a Source of Truth.
_Avoid_: legacy map, conversion table

**Amendment History**:
The record of how a section has been amended over time, captured alongside its Provenance Record.
_Avoid_: change log, version history

**Landmark Judgment**:
A well-known, hand-verified court precedent held in a curated file with a full official citation.
The product may cite a Landmark Judgment but may never invent or generalise case law.
_Avoid_: precedent, case, ruling (when referring to the curated, citable ones)

**Covered Domain**:
One of the legal areas the product handles: intellectual property rights, consumer rights, fundamental rights (Part III only), criminal law and interactions, flagship government schemes, cyber law (IT Act), motor vehicle and traffic law, the right to information, and protection from domestic violence and workplace harassment.
Each Covered Domain maps to an `ActType` and is routed by trigger words before retrieval.
_Avoid_: category, topic, area

**Coverage**:
The proportion of an in-scope act's sections that have been brought into the Source of Truth.
Anything outside current Coverage is handled by a Refusal, never a guess.
_Avoid_: completeness, ingestion percentage

### Answering behavior

**Grounded Answer**:
An answer derived only from retrieved Source of Truth text, with every claim carrying a Citation.
_Avoid_: response, generated answer

A single answering profile serves every user: complaints are interpreted into legal concepts, and answers are plain, step-by-step, and heavily disclaimed.

**Confirmation Step**:
The clarifying check ("did you mean...?") used before answering an ambiguous query.
_Avoid_: prompt, clarification

### Language and translation

**Bilingual Legal Glossary**:
The curated, hand-verified table of critical legal terms and their correct equivalents across the supported languages.
It is the deterministic backbone that keeps terminology (for example bailable versus non-bailable) from drifting in translation.
_Avoid_: dictionary, glossary (unqualified, since that collides with this CONTEXT file)

**Supported Language**:
One of the four languages the product serves: English, Hindi, Tamil, Gujarati.
_Avoid_: locale, language pack

### Actors and conversations

**Citizen**:
A member of the public seeking to understand their rights; the primary user and the default audience.
_Avoid_: user, customer, client, end user

**Conversation**:
A single multi-turn chat with its own isolated context and a fixed Mode.
Context is remembered within a Conversation but never carried across Conversations.
_Avoid_: session, thread, chat history
