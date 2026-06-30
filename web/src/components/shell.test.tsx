import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Shell } from "@/components/shell";

// A fetch double whose response body streams the given structured frames back as
// NDJSON, so the shell can be exercised against the answer seam's signals
// (explanation, citation, disclaimer, refusal, high-stakes) without a backend.
function streamingResponse(frames: object[]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(JSON.stringify(frame) + "\n"));
      }
      controller.close();
    },
  });
  return { ok: true, body } as unknown as Response;
}

// The frames a normal grounded answer streams: a plain-language explanation, a
// verbatim-English citation, and the disclaimer with its legal-aid pointer.
const GROUNDED_FRAMES = [
  { kind: "meta", state: "normal" },
  { kind: "explanation", text: "The law says X." },
  {
    kind: "citation",
    reference: "Bharatiya Nyaya Sanhita (2023), Section 303",
    verbatim: "Whoever commits theft shall be punished.",
    url: "https://example.gov.in/bns/303",
  },
  {
    kind: "disclaimer",
    text: "This is legal information, not legal advice. Consult a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
  },
];

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => streamingResponse(GROUNDED_FRAMES));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function ask(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/your legal question/i), question);
  await user.click(screen.getByRole("button", { name: /^ask$|send/i }));
  return user;
}

describe("Shell", () => {
  it("renders the asked question and streams the assistant answer into the thread", async () => {
    render(<Shell />);
    await ask("What is the punishment for theft?");

    const thread = screen.getByRole("log");
    expect(within(thread).getByText("What is the punishment for theft?")).toBeInTheDocument();
    expect(await within(thread).findByText(/The law says X\./)).toBeInTheDocument();
    // The cited statutory text arrives in its own distinct, verbatim-English block.
    const basis = within(thread).getByRole("region", { name: /legal basis/i });
    expect(within(basis).getByText(/Whoever commits theft/)).toBeInTheDocument();
  });

  it("renders an out-of-scope query as a graceful refusal, never a fabricated citation", async () => {
    fetchMock.mockResolvedValueOnce(
      streamingResponse([
        { kind: "meta", state: "refusal" },
        { kind: "explanation", text: "I do not have a sourced answer for that" },
        {
          kind: "disclaimer",
          text: "This is legal information, not legal advice. Consult a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
        },
      ]),
    );
    render(<Shell />);
    await ask("best recipe for biryani");

    const thread = screen.getByRole("log");
    expect(
      await within(thread).findByText(/I do not have a sourced answer for that/),
    ).toBeInTheDocument();
    expect(
      within(thread).queryByRole("region", { name: /legal basis/i }),
    ).not.toBeInTheDocument();
  });

  it("leads a high-stakes answer with emergency contacts before the legal content", async () => {
    fetchMock.mockResolvedValueOnce(
      streamingResponse([
        { kind: "meta", state: "emergency" },
        {
          kind: "highStakesNotice",
          text: "If you are in immediate danger, get help first:\n- Emergency: 112\n- Women's helpline: 181",
        },
        { kind: "explanation", text: "The law says X." },
        {
          kind: "citation",
          reference: "Bharatiya Nyaya Sanhita (2023), Section 303",
          verbatim: "Whoever commits theft shall be punished.",
          url: "https://example.gov.in/bns/303",
        },
      ]),
    );
    render(<Shell />);
    await ask("I was just arrested, what are my rights?");

    const thread = screen.getByRole("log");
    const emergency = await within(thread).findByRole("alert");
    expect(within(emergency).getByText(/112/)).toBeInTheDocument();
    const basis = within(thread).getByRole("region", { name: /legal basis/i });
    expect(
      emergency.compareDocumentPosition(basis) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("offers icon-led category tiles for common topics that prefill a question", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    const tiles = screen.getByRole("group", { name: /common topics/i });
    expect(within(tiles).getByRole("button", { name: /consumer/i })).toBeInTheDocument();
    expect(within(tiles).getByRole("button", { name: /police|arrest/i })).toBeInTheDocument();

    await user.click(within(tiles).getByRole("button", { name: /consumer/i }));
    const input = screen.getByLabelText(/your legal question/i) as HTMLTextAreaElement;
    expect(input.value).toMatch(/consumer/i);
  });

  it("starts a fresh, empty conversation when the new-chat action is used", async () => {
    render(<Shell />);
    const user = await ask("Tell me about theft");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.click(screen.getByRole("button", { name: /new chat/i }));

    // The central thread is now empty for the new Conversation...
    const thread = screen.getByRole("log");
    expect(within(thread).queryByText("Tell me about theft")).not.toBeInTheDocument();
    // ...but the previous Conversation is still listed in the sidebar.
    const sidebar = screen.getByRole("complementary");
    expect(within(sidebar).getByText(/Tell me about theft/)).toBeInTheDocument();
  });

  it("sends prior turns as context so a follow-up builds on the Conversation", async () => {
    render(<Shell />);
    const user = await ask("Someone cheated me by fraud");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.type(screen.getByLabelText(/your legal question/i), "What is the punishment for it?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    const followupBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(followupBody.context).toEqual(["Someone cheated me by fraud"]);
  });

  it("attributes the request to the signed-in user by sending their Bearer token", async () => {
    render(<Shell getToken={async () => "sess_asha"} />);
    await ask("What is the punishment for theft?");

    const headers = fetchMock.mock.calls[0][1].headers;
    expect(headers.Authorization).toBe("Bearer sess_asha");
  });

  it("routes a new Conversation through the dual-mode seam in Citizen mode by default", async () => {
    render(<Shell />);
    await ask("What is the punishment for theft?");

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.mode).toBe("citizen");
  });

  it("routes through Professional mode when it is chosen for a new Conversation", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    await user.click(screen.getByRole("radio", { name: /professional/i }));
    await user.type(screen.getByLabelText(/your legal question/i), "Define abetment");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.mode).toBe("professional");
  });

  it("shows each Conversation's mode as a badge in the sidebar", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    await user.click(screen.getByRole("radio", { name: /professional/i }));
    await ask("Define abetment");

    const sidebar = screen.getByRole("complementary");
    expect(within(sidebar).getByText(/professional/i)).toBeInTheDocument();
  });

  it("locks the mode once the Conversation has a message", async () => {
    render(<Shell />);
    await ask("What is the punishment for theft?");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    // The selector is gone, so the chosen mode cannot be changed mid-Conversation.
    expect(screen.queryByRole("radiogroup", { name: /answer mode/i })).not.toBeInTheDocument();
  });

  it("routes a question through the multilingual seam in English by default", async () => {
    render(<Shell />);
    await ask("What is the punishment for theft?");

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.language).toBe("en");
  });

  it("offers exactly English, Hindi, Tamil, and Gujarati as answer languages", () => {
    render(<Shell />);

    const selector = screen.getByRole("combobox", { name: /answer language/i });
    const options = within(selector)
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual(["English", "हिन्दी", "தமிழ்", "ગુજરાતી"]);
  });

  it("passes the chosen language through to the multilingual seam", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    await user.selectOptions(
      screen.getByRole("combobox", { name: /answer language/i }),
      "hi",
    );
    await ask("What is the punishment for theft?");

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.language).toBe("hi");
  });

  it("does not carry memory across when a new Conversation is started", async () => {
    render(<Shell />);
    const user = await ask("Someone cheated me by fraud");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.click(screen.getByRole("button", { name: /new chat/i }));
    await user.type(screen.getByLabelText(/your legal question/i), "What is the punishment for it?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    const freshBody = JSON.parse(fetchMock.mock.calls.at(-1)![1].body);
    expect(freshBody.context).toEqual([]);
  });
});
