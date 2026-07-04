import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AccountSettings } from "@/components/account-settings";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => ({ ok: true }) as Response);
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
});

function renderSettings(overrides: Partial<Parameters<typeof AccountSettings>[0]> = {}) {
  const props = {
    email: "asha@example.in",
    memberSince: "1 Jan 2026",
    getToken: async () => "sess_asha",
    onSignOut: vi.fn(async () => undefined),
    onDeleted: vi.fn(),
    ...overrides,
  };
  render(<AccountSettings {...props} />);
  return props;
}

describe("AccountSettings", () => {
  it("shows the signed-in identity", () => {
    renderSettings();
    expect(screen.getByText(/asha@example.in/)).toBeInTheDocument();
    expect(screen.getByText(/member since 1 Jan 2026/)).toBeInTheDocument();
  });

  it("permanently deletes only after confirmation, then signs out and leaves", async () => {
    const user = userEvent.setup();
    const props = renderSettings();

    await user.click(screen.getByRole("button", { name: /delete my account/i }));

    // Nothing is erased until the confirmation dialog's destructive action.
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: /^delete account$/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/account$/),
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ Authorization: "Bearer sess_asha" }),
      }),
    );
    // On success the user is taken to the public landing before the session is
    // cleared, so an erased user is never bounced to sign-in from this route.
    await vi.waitFor(() => expect(props.onSignOut).toHaveBeenCalledOnce());
    expect(props.onDeleted).toHaveBeenCalledOnce();
  });

  it("surfaces a failed deletion and stays signed in", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500 } as Response);
    const user = userEvent.setup();
    const props = renderSettings();

    await user.click(screen.getByRole("button", { name: /delete my account/i }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: /^delete account$/i,
      }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/deletion failed \(500\)/i);
    expect(alert).toHaveTextContent(/still exists/i);
    expect(props.onSignOut).not.toHaveBeenCalled();
  });

  it("keeps the account when the confirmation is cancelled", async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.click(screen.getByRole("button", { name: /delete my account/i }));
    await user.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: /keep my account/i,
      }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
