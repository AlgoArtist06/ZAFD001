import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { getFunctionName } from "convex/server";

import { ConsentGate } from "@/components/consent-gate";

const NOTICE =
  "Privacy notice\n\nThird-party LLM: the text of your query is sent to a " +
  "third-party large language model (LLM) provider.";
const recordConsent = vi.fn(async () => ({}));
let consented = false;

vi.mock("convex/react", () => ({
  useQuery: (query: object) => {
    const name = getFunctionName(query as never);
    if (name === "chat:privacyNotice") return { notice: NOTICE, version: "2026-06-29" };
    if (name === "chat:consentStatus") return { consented };
    return undefined;
  },
  useMutation: () => recordConsent,
}));

beforeEach(() => {
  consented = false;
  recordConsent.mockClear();
});

describe("ConsentGate", () => {
  it("skips the gate when consent is already recorded", () => {
    consented = true;
    render(<ConsentGate><p>chat shell</p></ConsentGate>);
    expect(screen.getByText("chat shell")).toBeInTheDocument();
  });

  it("shows the notice and records consent through Convex", async () => {
    const user = userEvent.setup();
    render(<ConsentGate><p>chat shell</p></ConsentGate>);

    expect(screen.getByText(/third-party large language model/i)).toBeInTheDocument();
    expect(screen.queryByText("chat shell")).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /agree|continue|accept/i }));

    await waitFor(() => expect(recordConsent).toHaveBeenCalledWith({}));
    expect(screen.getByText("chat shell")).toBeInTheDocument();
  });
});
