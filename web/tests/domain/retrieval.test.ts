// Ports tests/test_retrieval.py and test_expansion.py: domain routing,
// hybrid keyword+vector ranking, and parent/sibling expansion.
import { beforeAll, describe, expect, it } from "vitest";

import {
  expand,
  inMemorySectionMembers,
  sectionVerbatimText,
} from "../../convex/lib/expansion";
import { expandQuery } from "../../convex/lib/hybrid";
import { type Chunk } from "../../convex/lib/models";
import { routeDomains } from "../../convex/lib/routing";
import { buildCorpus } from "../helpers/corpus";
import { inMemoryRetriever } from "../helpers/doubles";

let corpus: Chunk[];
beforeAll(() => {
  corpus = buildCorpus();
});

describe("domain routing", () => {
  it("routes a consumer query to the consumer domain only", () => {
    const domains = routeDomains("I want a refund for a defective product");
    expect(domains).toEqual(["consumer"]);
  });

  it("returns every domain when nothing matches", () => {
    expect(routeDomains("hello there").length).toBe(9);
  });

  it("filters criminal sections out of a consumer query", async () => {
    const retrieve = inMemoryRetriever(corpus);
    const hits = await retrieve(
      "How do I file a complaint about a defective product?",
      routeDomains("How do I file a complaint about a defective product?"),
    );
    expect(hits.length).toBeGreaterThan(0);
    for (const hit of hits) {
      expect(hit.chunk.provenance.actType).toBe("consumer");
    }
  });
});

describe("hybrid ranking", () => {
  it("uses both keyword and vector signal", async () => {
    const retrieve = inMemoryRetriever(corpus);
    const hits = await retrieve("theft of movable property", ["criminal"]);
    expect(hits.length).toBeGreaterThan(0);
    const top = hits[0];
    expect(top.keywordScore).toBeGreaterThan(0);
    expect(top.vectorScore).toBeGreaterThan(0);
    expect(top.chunk.sectionNumber).toBe("303");
    // Scores are the normalized combination, monotonically ordered.
    for (let i = 1; i < hits.length; i++) {
      expect(hits[i - 1].score).toBeGreaterThanOrEqual(hits[i].score);
    }
  });

  it("expands lay complaint words toward legal concepts", () => {
    expect(expandQuery("I got scammed online")).toContain("cheating fraud");
    expect(expandQuery("what is theft")).toBe("what is theft");
  });
});

describe("parent/sibling expansion", () => {
  it("expands a matched child to its whole parent section", async () => {
    // CPA Section 35 chunks into two sub-section children at threshold 30.
    const child = corpus.find(
      (c) => c.actId === "cpa" && c.sectionNumber === "35" && c.subSection === "1",
    );
    expect(child).toBeDefined();
    const sections = await expand(
      [{ chunk: child!, score: 1, keywordScore: 1, vectorScore: 1 }],
      inMemorySectionMembers(corpus),
    );
    expect(sections).toHaveLength(1);
    expect(sections[0].chunks.length).toBeGreaterThan(1);
    const verbatim = sectionVerbatimText(sections[0]);
    expect(verbatim).toContain("District Commission");
    expect(verbatim).toContain("fee");
  });

  it("expands a whole-section hit to itself", async () => {
    const whole = corpus.find(
      (c) => c.actId === "bns" && c.sectionNumber === "303",
    );
    const sections = await expand(
      [{ chunk: whole!, score: 1, keywordScore: 1, vectorScore: 1 }],
      inMemorySectionMembers(corpus),
    );
    expect(sections).toHaveLength(1);
    expect(sections[0].chunks).toHaveLength(1);
  });
});
