import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Shell } from "@/components/shell";

// A fetch double whose response body streams the given chunks back, so the
// shell can be exercised against a streaming answer without a live backend.
function streamingResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return { ok: true, body } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () =>
    streamingResponse(["The law says X.\n\n", "Legal basis: Section 303."]),
  );
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
    expect(within(thread).getByText(/Legal basis: Section 303\./)).toBeInTheDocument();
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
