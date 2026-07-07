// Bare-act parser, ported from ingestion/parser.py, tuned to the v1 in-scope
// acts. The input is a lightly-structured bare-act text file: a header block
// carries act-level provenance; the body is a sequence of "Section N.
// Heading." (or "Article N.") blocks, each optionally split into "(n)"
// sub-sections and annotated with "@AMENDMENT year: ..." lines.
//
// Lives outside convex/ because parsing is ingest-time only (Node): the
// Convex runtime never parses acts, and this file may use node builtins.
import { createHash } from "node:crypto";

import { type ActType, type AmendmentEntry } from "../../convex/lib/models";

const SECTION_RE = /^(?:Section|Article)\s+([0-9A-Za-z]+)\.\s*(.*)$/;
const SUBSECTION_RE = /^\((\w+)\)\s*(.*)$/;
const AMENDMENT_RE = /^@AMENDMENT\s+(\d{4}):\s*(.*)$/;

export type SubSection = {
  label: string;
  text: string;
};

export type Section = {
  sectionNumber: string;
  heading: string;
  fullText: string;
  subSections: SubSection[];
  amendments: AmendmentEntry[];
  isDefinition: boolean;
};

export type ParsedAct = {
  actId: string;
  actName: string;
  actYear: number;
  actType: ActType;
  sourceUrl: string;
  retrievalDate: string;
  sourceHash: string;
  sections: Section[];
};

function splitHeader(text: string): [Record<string, string>, string] {
  const marker = text.indexOf("===");
  const headerRaw = marker >= 0 ? text.slice(0, marker) : text;
  const body = marker >= 0 ? text.slice(marker + "===".length) : "";
  const header: Record<string, string> = {};
  for (const line of headerRaw.split("\n")) {
    const colon = line.indexOf(":");
    if (colon >= 0) {
      header[line.slice(0, colon).trim().toUpperCase()] = line
        .slice(colon + 1)
        .trim();
    }
  }
  return [header, body];
}

// Turn a block of body lines into sub-sections, if any "(n)" markers.
function flushSubsections(bufferLines: string[]): SubSection[] {
  const subs: SubSection[] = [];
  let current: SubSection | null = null;
  for (const line of bufferLines) {
    const match = SUBSECTION_RE.exec(line.trim());
    if (match) {
      current = { label: match[1], text: match[2].trim() };
      subs.push(current);
    } else if (current !== null) {
      current.text = `${current.text} ${line.trim()}`.trim();
    }
  }
  return subs;
}

export function parseAct(text: string): ParsedAct {
  const [header, body] = splitHeader(text);
  const act: ParsedAct = {
    actId: header["ACT_ID"],
    actName: header["ACT"],
    actYear: parseInt(header["YEAR"], 10),
    actType: header["TYPE"].toLowerCase() as ActType,
    sourceUrl: header["SOURCE_URL"],
    retrievalDate: header["RETRIEVAL_DATE"],
    // Same hash the Python parser recorded: sha256 of the whole source text.
    sourceHash: createHash("sha256").update(text, "utf8").digest("hex"),
    sections: [],
  };

  let section: Section | null = null;
  let bodyLines: string[] = [];

  const closeSection = () => {
    if (section === null) return;
    // Reflow soft source line-wraps into clean single-spaced verbatim text.
    section.fullText = bodyLines.join(" ").replace(/\s+/g, " ").trim();
    section.subSections = flushSubsections(bodyLines);
    act.sections.push(section);
  };

  for (const raw of body.split("\n")) {
    const line = raw.trimEnd();
    const headerMatch = SECTION_RE.exec(line.trim());
    const amendmentMatch = AMENDMENT_RE.exec(line.trim());
    if (headerMatch) {
      closeSection();
      const heading = headerMatch[2].trim();
      section = {
        sectionNumber: headerMatch[1],
        heading,
        fullText: "",
        subSections: [],
        amendments: [],
        isDefinition: heading.toLowerCase().includes("definition"),
      };
      bodyLines = [];
    } else if (amendmentMatch && section !== null) {
      section.amendments.push({
        year: parseInt(amendmentMatch[1], 10),
        description: amendmentMatch[2].trim(),
      });
    } else if (section !== null) {
      bodyLines.push(line);
    }
  }

  closeSection();
  return act;
}
