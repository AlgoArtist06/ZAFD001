// IPC-number recognition, ported from rag/domain/recognition.py: input
// normalisation via the IPC-to-BNS Mapping. A user who only knows the
// repealed IPC section number still reaches the current BNS section; the
// former number is carried forward so the answer can annotate it.
import { type IpcBnsMapping, type MappingEntry } from "./mapping";

// Recognition is gated on the literal token "IPC": a bare number like
// "Section 318" is a current BNS reference, not a repealed IPC one, so it
// must not be rewritten. A section number may carry a letter suffix (304B).
const IPC_TOKEN_RE = /\bipc\b/i;
const SECTION_RE = /\b(\d{1,3}[A-Z]?)\b/g;

// A query after IPC normalisation, with any references it carried forward.
export type RecognizedQuery = {
  query: string;
  references: MappingEntry[];
};

// Recognise repealed IPC numbers and normalise the query toward BNS. Returns
// the original query untouched when no IPC reference is present; otherwise
// the current BNS section number and label are appended so keyword retrieval
// reaches the BNS section, and the matched entries return for annotation.
export function recognizeIpc(
  query: string,
  mapping: IpcBnsMapping,
): RecognizedQuery {
  if (!IPC_TOKEN_RE.test(query)) {
    return { query, references: [] };
  }
  const references: MappingEntry[] = [];
  const additions: string[] = [];
  for (const match of query.matchAll(SECTION_RE)) {
    const entry = mapping.lookup(match[1]);
    if (entry === null || references.some((r) => r.ipc === entry.ipc)) {
      continue;
    }
    references.push(entry);
    additions.push(`${entry.bns} ${entry.label}`);
  }
  if (references.length === 0) {
    return { query, references: [] };
  }
  return { query: `${query} ${additions.join(" ")}`, references };
}

// A courtesy annotation of the repealed IPC numbers a query referenced. The
// note names the former IPC number so a user who only knows the old number
// recognises the answer, while the answer itself stays grounded in - and
// cites only - the current BNS section. (From rag/domain/answer.py.)
export function formerIpcNote(references: MappingEntry[]): string {
  if (references.length === 0) return "";
  const parts = references.map((r) => `formerly IPC ${r.ipc} (${r.label})`);
  return (
    "Note: " +
    parts.join("; ") +
    ". This is now covered by the current " +
    "BNS section cited above; the former IPC number is given only for " +
    "recognition and is not itself a source."
  );
}
