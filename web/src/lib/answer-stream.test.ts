import { describe, expect, it } from "vitest";

import {
  applyFrame,
  emptyAnswer,
  readNdjson,
  type StructuredAnswer,
} from "@/lib/answer-stream";

function fold(frames: (object | string)[]) {
  return frames.reduce<StructuredAnswer>(
    (answer, frame) =>
      applyFrame(
        answer,
        typeof frame === "string" ? frame : JSON.stringify(frame),
      ),
    emptyAnswer(),
  );
}

describe("applyFrame", () => {
  it("folds the structured frames of a grounded answer", () => {
    const answer = fold([
      { kind: "meta", state: "normal", language: "hi" },
      { kind: "explanation", text: "The law says X." },
      { kind: "citation", reference: "BNS 303", verbatim: "text", url: "u" },
      { kind: "nextStep", text: "Read it." },
      { kind: "disclaimer", text: "Not legal advice." },
    ]);
    expect(answer.state).toBe("normal");
    expect(answer.language).toBe("hi");
    expect(answer.explanation).toBe("The law says X.");
    expect(answer.citations).toEqual([
      { reference: "BNS 303", verbatim: "text", url: "u" },
    ]);
    expect(answer.nextStep).toBe("Read it.");
    expect(answer.disclaimer).toBe("Not legal advice.");
  });

  it("replaces the explanation on each frame, so cumulative streaming renders progressively", () => {
    const answer = fold([
      { kind: "explanation", text: "The law" },
      { kind: "explanation", text: "The law says X." },
    ]);
    expect(answer.explanation).toBe("The law says X.");
  });

  it("lets a late corrective meta flip the state to refusal", () => {
    const answer = fold([
      { kind: "meta", state: "normal" },
      { kind: "explanation", text: "Streamed text..." },
      { kind: "meta", state: "refusal" },
      { kind: "explanation", text: "I do not have a sourced answer for that" },
    ]);
    expect(answer.state).toBe("refusal");
    expect(answer.explanation).toBe("I do not have a sourced answer for that");
    expect(answer.citations).toEqual([]);
  });

  it("carries the refusal reason and the error detail from the meta frame", () => {
    const refusal = fold([{ kind: "meta", state: "refusal", reason: "no_match" }]);
    expect(refusal.reason).toBe("no_match");

    const error = fold([
      { kind: "meta", state: "normal" },
      { kind: "explanation", text: "Streamed text..." },
      { kind: "meta", state: "error", detail: "ReadError: connection lost" },
      { kind: "explanation", text: "The assistant could not reach its language model." },
    ]);
    expect(error.state).toBe("error");
    expect(error.detail).toBe("ReadError: connection lost");
  });

  it("ignores malformed and unknown frames without corrupting the answer", () => {
    const answer = fold([
      { kind: "explanation", text: "Kept." },
      "{not json",
      { kind: "someFutureFrame", text: "ignored" },
    ]);
    expect(answer.explanation).toBe("Kept.");
  });
});

describe("readNdjson", () => {
  function streamOf(chunks: string[]) {
    const encoder = new TextEncoder();
    return new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
  }

  it("delivers only newline-complete lines, even when frames split across chunks", async () => {
    const lines: string[] = [];
    await readNdjson(
      streamOf(['{"kind":"expl', 'anation","text":"X"}\n{"kind":"meta"', "}\n"]),
      (line) => lines.push(line),
    );
    expect(lines).toEqual(['{"kind":"explanation","text":"X"}', '{"kind":"meta"}']);
  });

  it("flushes a trailing unterminated line at the end of the stream", async () => {
    const lines: string[] = [];
    await readNdjson(streamOf(['{"kind":"meta"}']), (line) => lines.push(line));
    expect(lines).toEqual(['{"kind":"meta"}']);
  });
});
