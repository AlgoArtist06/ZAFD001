import { apiUrl } from "@/lib/api";

// The outcome of a permanent account deletion: either it succeeded, or it
// failed with a message the UI must surface - a failed erasure means the
// account still exists, which the user has to be told, never silently swallowed.
export type AccountDeletion = { ok: true } | { ok: false; message: string };

// Permanently erase the signed-in user's account and all stored data through the
// backend deletion seam (`DELETE /api/account`), which purges their persisted
// Conversations, erases their consent record, and deletes their Clerk identity.
// The session token attributes the request to that user so only their own data
// is erased.
export async function deleteAccount(
  getToken: () => Promise<string | null>,
): Promise<AccountDeletion> {
  try {
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(apiUrl("/api/account"), {
      method: "DELETE",
      headers,
    });
    if (!response.ok) {
      return {
        ok: false,
        message: `Account deletion failed (${response.status}). Your account still exists - please try again.`,
      };
    }
    return { ok: true };
  } catch {
    return {
      ok: false,
      message:
        "Account deletion failed: the backend could not be reached. Your account still exists.",
    };
  }
}
