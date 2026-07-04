import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ConsentGate } from "@/components/consent-gate";

const NOTICE =
  "Privacy notice\n\nThird-party LLM: the text of your query is sent to a " +
  "third-party large language model (LLM) provider.";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/api/privacy-notice")) {
      return {
        ok: true,
        json: async () => ({ notice: NOTICE, version: "2026-06-29" }),
      } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConsentGate", () => {
  it("skips the gate for a returning user whose consent is already recorded", async () => {
    fetchMock.mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/api/consent") && options?.method !== "POST") {
        return {
          ok: true,
          json: async () => ({ consented: true, notice_version: "2026-06-29" }),
        } as unknown as Response;
      }
      return {
        ok: true,
        json: async () => ({ notice: NOTICE, version: "2026-06-29" }),
      } as unknown as Response;
    });

    render(
      <ConsentGate getToken={async () => "sess_asha"}>
        <p>chat shell</p>
      </ConsentGate>,
    );

    expect(await screen.findByText("chat shell")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("shows the privacy notice disclosing third-party-LLM processing and hides the app until consent", async () => {
    render(
      <ConsentGate getToken={async () => "sess_asha"}>
        <p>chat shell</p>
      </ConsentGate>,
    );

    expect(
      await screen.findByText(/third-party large language model/i),
    ).toBeInTheDocument();
    // The gated app is not reachable before consent is given.
    expect(screen.queryByText("chat shell")).not.toBeInTheDocument();
  });

  it("records consent server-side with the user's token, then reveals the app", async () => {
    const user = userEvent.setup();
    render(
      <ConsentGate getToken={async () => "sess_asha"}>
        <p>chat shell</p>
      </ConsentGate>,
    );

    // The user must explicitly opt in before continuing.
    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /agree|continue|accept/i }));

    await waitFor(() => {
      expect(screen.getByText("chat shell")).toBeInTheDocument();
    });

    const consentCall = fetchMock.mock.calls.find(
      (call) =>
        String(call[0]).endsWith("/api/consent") && call[1]?.method === "POST",
    );
    expect(consentCall).toBeTruthy();
    expect(consentCall![1].headers.Authorization).toBe("Bearer sess_asha");
  });
});
