// Ports tests/test_verifier.py, test_recognition.py, and test_mapping.py:
// citation verification strips anything not retrieved; IPC recognition
// rewrites toward BNS only when "IPC" is present; the mapping reproduces the
// official correspondence chart.
import { readFileSync } from "node:fs";
import { beforeAll, describe, expect, it } from "vitest";

import { verifyCitations, type Citation } from "../../convex/citations";
import { expand, inMemorySectionMembers } from "../../convex/lib/expansion";
import { loadIpcBnsMapping } from "../../convex/lib/mapping";
import { type Chunk } from "../../convex/lib/models";
import { formerIpcNote, recognizeIpc } from "../../convex/lib/recognition";
import { dataPath } from "../../scripts/lib/repo";
import { buildCorpus } from "../helpers/corpus";

let corpus: Chunk[];
const mapping = loadIpcBnsMapping();

beforeAll(() => {
  corpus = buildCorpus();
});

async function retrievedTheftSection() {
  const chunk = corpus.find((c) => c.actId === "bns" && c.sectionNumber === "303")!;
  return expand(
    [{ chunk, score: 1, keywordScore: 1, vectorScore: 1 }],
    inMemorySectionMembers(corpus),
  );
}

describe("citation verification", () => {
  it("keeps a citation whose section was retrieved", async () => {
    const sections = await retrievedTheftSection();
    const genuine: Citation = {
      actId: "bns",
      actName: "Bharatiya Nyaya Sanhita",
      actYear: 2023,
      sectionNumber: "303",
      verbatimText: "…",
      sourceUrl: "https://www.indiacode.nic.in/bns",
    };
    expect(verifyCitations([genuine], sections)).toEqual([genuine]);
  });

  it("strips a fabricated section", async () => {
    const sections = await retrievedTheftSection();
    const fabricated: Citation = {
      actId: "bns",
      actName: "Bharatiya Nyaya Sanhita",
      actYear: 2023,
      sectionNumber: "999",
      verbatimText: "made up",
      sourceUrl: "https://www.indiacode.nic.in/bns",
    };
    expect(verifyCitations([fabricated], sections)).toEqual([]);
  });
});

describe("IPC recognition", () => {
  it("recognises an old IPC number and normalises toward BNS", () => {
    const recognized = recognizeIpc("What is IPC 420?", mapping);
    expect(recognized.references).toHaveLength(1);
    expect(recognized.references[0].bns).toBe("318");
    expect(recognized.query).toContain("318");
  });

  it("leaves a query without an IPC reference unchanged", () => {
    const recognized = recognizeIpc("What is the punishment for theft?", mapping);
    expect(recognized.query).toBe("What is the punishment for theft?");
    expect(recognized.references).toEqual([]);
  });

  it("does not treat a bare number as an IPC reference", () => {
    const recognized = recognizeIpc("What is Section 318?", mapping);
    expect(recognized.query).toBe("What is Section 318?");
    expect(recognized.references).toEqual([]);
  });

  it("renders the courtesy annotation for recognised numbers", () => {
    const { references } = recognizeIpc("IPC 420?", mapping);
    const note = formerIpcNote(references);
    expect(note).toContain("formerly IPC 420");
    expect(note).toContain("not itself a source");
  });
});

describe("the IPC-to-BNS mapping", () => {
  it("returns the current BNS section for an old IPC number", () => {
    expect(mapping.lookup("420")?.bns).toBe("318");
    expect(mapping.lookup(" 302 ")?.bns).toBeTruthy();
  });

  it("returns null for an unknown IPC number", () => {
    expect(mapping.lookup("9999")).toBeNull();
  });

  it("matches the official correspondence chart", () => {
    const chartPath = dataPath("ground_truth", "ipc_bns_correspondence.json");
    const chart = JSON.parse(readFileSync(chartPath, "utf8")) as {
      pairs: Record<string, string>;
    };
    expect(mapping.verify(chart.pairs)).toBe(true);
  });

  it("fails verification against a tampered chart", () => {
    expect(mapping.verify({ "420": "999" })).toBe(false);
  });
});
