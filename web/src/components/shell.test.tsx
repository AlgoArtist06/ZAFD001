import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { getFunctionName } from "convex/server";

import { Shell } from "@/components/shell";

const GROUNDED_STREAM = {
  _id: "stream-1",
  done: true,
  state: "normal",
  explanation: "The law says X.",
  citations: [{
    reference: "Bharatiya Nyaya Sanhita (2023), Section 303",
    verbatim: "Whoever commits theft shall be punished.",
    url: "https://example.gov.in/bns/303",
  }],
  disclaimer: "This is legal information, not legal advice. Consult a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
};

const createConversation = vi.fn(async () => "conv-server-1");
const askQuestion = vi.fn(
  async (args: { query: string; context?: string[]; conversationId?: string }) =>
    args &&
    "stream-1",
);
const deleteConversation = vi.fn(async () => undefined);
let stream: Record<string, unknown> = GROUNDED_STREAM;

vi.mock("convex/react", () => ({
  useQuery: (query: object, args?: object | "skip") => {
    const name = getFunctionName(query as never);
    if (name === "chat:listConversations") return [];
    if (name === "chat:getConversationHistory") return args === "skip" ? undefined : [];
    if (name === "chat:getStream") return args === "skip" ? undefined : stream;
    return undefined;
  },
  useMutation: (mutation: object) => {
    const name = getFunctionName(mutation as never);
    if (name === "chat:createConversation") return createConversation;
    if (name === "chat:deleteConversation") return deleteConversation;
    if (name === "chat:ask") return askQuestion;
    return vi.fn();
  },
}));

beforeEach(() => {
  stream = GROUNDED_STREAM;
  createConversation.mockClear();
  askQuestion.mockClear();
  deleteConversation.mockClear();
});

afterEach(() => {
  document.documentElement.classList.remove("dark");
  window.localStorage.clear();
});

async function ask(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/your legal question/i), question);
  await user.click(screen.getByRole("button", { name: /^ask$|send/i }));
  return user;
}

describe("Shell", () => {
  it("toggles dark mode", async () => {
    const user = userEvent.setup();
    render(<Shell />);

    await user.click(screen.getByRole("button", { name: /use dark mode/i }));

    expect(document.documentElement).toHaveClass("dark");
  });

  it("keeps a pre-applied dark theme when it mounts (never resets to light)", async () => {
    // The root layout's inline script sets this before paint; entering /chat
    // must not strip it. The old hook cleared the class on mount from its
    // initial light state - this pins that it no longer does.
    document.documentElement.classList.add("dark");
    window.localStorage.setItem("theme", "dark");

    render(<Shell />);
    // Let mount effects run.
    await screen.findByRole("button", { name: /use light mode/i });

    expect(document.documentElement).toHaveClass("dark");
    expect(window.localStorage.getItem("theme")).toBe("dark");
  });

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
    stream = { ...GROUNDED_STREAM, state: "refusal", explanation: "I do not have a sourced answer for that", citations: [] };
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
    stream = { ...GROUNDED_STREAM, state: "emergency", highStakesNotice: "If you are in immediate danger, get help first:\n- Emergency: 112\n- Women's helpline: 181" };
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

  it("deletes a Conversation through the server and removes it from the sidebar", async () => {
    render(<Shell />);
    const user = await ask("Tell me about theft");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.click(
      screen.getByRole("button", { name: /delete conversation tell me about theft/i }),
    );

    expect(deleteConversation).toHaveBeenCalledWith({ conversationId: "conv-server-1" });
    expect(askQuestion).toHaveBeenCalledWith(expect.objectContaining({ conversationId: "conv-server-1" }));
    expect(
      within(screen.getByRole("complementary")).queryByText("Tell me about theft"),
    ).not.toBeInTheDocument();
  });

  it("signs out from the sidebar without touching the account", async () => {
    const signOut = vi.fn(async () => undefined);
    const user = userEvent.setup();
    render(<Shell signOut={signOut} />);

    await user.click(screen.getByRole("button", { name: /sign out/i }));

    expect(signOut).toHaveBeenCalledOnce();
    expect(deleteConversation).not.toHaveBeenCalled();
  });

  it("sends prior turns as context so a follow-up builds on the Conversation", async () => {
    render(<Shell />);
    const user = await ask("Someone cheated me by fraud");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.type(screen.getByLabelText(/your legal question/i), "What is the punishment for it?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(askQuestion.mock.calls[1]?.[0]).toMatchObject({ context: ["Someone cheated me by fraud"] });
  });

  it("sends questions through the authenticated Convex mutation", async () => {
    render(<Shell />);
    await ask("What is the punishment for theft?");
    expect(askQuestion).toHaveBeenCalledWith(expect.objectContaining({ query: "What is the punishment for theft?" }));
  });

  it("does not carry memory across when a new Conversation is started", async () => {
    render(<Shell />);
    const user = await ask("Someone cheated me by fraud");
    await within(screen.getByRole("log")).findByText(/The law says X\./);

    await user.click(screen.getByRole("button", { name: /new chat/i }));
    await user.type(screen.getByLabelText(/your legal question/i), "What is the punishment for it?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(askQuestion.mock.calls.at(-1)?.[0]).toMatchObject({ context: [] });
  });
});
