import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AccountSettings } from "@/components/account-settings";

const deleteAccount = vi.fn(async () => undefined);
vi.mock("convex/react", () => ({ useAction: () => deleteAccount }));

beforeEach(() => deleteAccount.mockReset().mockResolvedValue(undefined));

function renderSettings() {
  const props = {
    email: "asha@example.in",
    memberSince: "1 Jan 2026",
    onSignOut: vi.fn(async () => undefined),
    onDeleted: vi.fn(),
  };
  render(<AccountSettings {...props} />);
  return props;
}

describe("AccountSettings", () => {
  it("shows the signed-in identity", () => {
    renderSettings();
    expect(screen.getByText(/asha@example.in/)).toBeInTheDocument();
  });

  it("deletes through Convex only after confirmation, then leaves and signs out", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /delete my account/i }));
    expect(deleteAccount).not.toHaveBeenCalled();
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: /^delete account$/i }));

    await vi.waitFor(() => expect(deleteAccount).toHaveBeenCalledWith({}));
    expect(props.onDeleted).toHaveBeenCalledOnce();
    expect(props.onSignOut).toHaveBeenCalledOnce();
  });

  it("surfaces a failed deletion and stays signed in", async () => {
    deleteAccount.mockRejectedValueOnce(new Error("deployment unavailable"));
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /delete my account/i }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: /^delete account$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/deployment unavailable/i);
    expect(props.onDeleted).not.toHaveBeenCalled();
    expect(props.onSignOut).not.toHaveBeenCalled();
  });
});
