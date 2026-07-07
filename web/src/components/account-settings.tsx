"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, LogOut, ShieldAlert, Trash2 } from "lucide-react";
import { useAction } from "convex/react";

import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// How the settings screen obtains the signed-in user's identity and session. The
// authenticated page passes Clerk's values and its profile editor; the component
// itself stays prop-driven so it renders and tests in isolation, exactly as the
// chat Shell does.
type AccountSettingsProps = {
  email?: string | null;
  memberSince?: string | null;
  onSignOut: () => Promise<void>;
  // Where to go once the account is gone: the caller navigates to a public
  // page before the session is cleared, so the erased user is not bounced back
  // to sign-in from this protected route.
  onDeleted: () => void;
  // Clerk's self-service profile editor (change name, email, password); slotted
  // in by the authenticated page so this component needs no Clerk dependency.
  profile?: React.ReactNode;
};

// The dedicated account-settings screen: manage the profile, switch appearance,
// and - guarded behind an explicit confirmation - permanently erase the account
// and every piece of stored data. Every destructive account action lives here,
// so the chat sidebar only links to it.
export function AccountSettings({
  email,
  memberSince,
  onSignOut,
  onDeleted,
  profile,
}: AccountSettingsProps) {
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const deleteAccount = useAction(api.chat.deleteAccount);

  async function confirmDelete() {
    setError(null);
    setDeleting(true);
    try {
      await deleteAccount({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setDeleting(false);
      return;
    }
    // Leave this protected route for the public landing page first, then clear
    // the session; the order keeps the erased user from a sign-in bounce.
    onDeleted();
    await onSignOut();
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back to chat">
            <Link href="/chat">
              <ArrowLeft aria-hidden />
            </Link>
          </Button>
          <div>
            <h1 className="font-heading text-xl font-semibold tracking-tight">
              Account settings
            </h1>
            {email && (
              <p className="text-muted-foreground text-sm">
                {email}
                {memberSince ? ` · member since ${memberSince}` : ""}
              </p>
            )}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          onClick={() => void onSignOut()}
          className="text-muted-foreground min-h-11"
        >
          <LogOut aria-hidden />
          Sign out
        </Button>
      </header>

      {/* Profile and security: Clerk owns the identity itself (name, email,
          password), so changing it happens in its self-service editor. */}
      {profile && <section aria-label="Profile and security">{profile}</section>}

      {/* Danger zone: the one place a permanent, irreversible erasure lives. */}
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2 text-base">
            <ShieldAlert className="size-5 shrink-0" aria-hidden />
            Delete account permanently
          </CardTitle>
          <CardDescription>
            This erases your account and every stored Conversation, and revokes
            your recorded consent. It is immediate and cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {error && (
            <p role="alert" className="text-destructive text-sm leading-5">
              {error}
            </p>
          )}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                type="button"
                variant="destructive"
                disabled={deleting}
                className="min-h-11 w-fit"
              >
                <Trash2 aria-hidden />
                {deleting ? "Deleting…" : "Delete my account"}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete your account?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently erases your account and every stored
                  Conversation. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Keep my account</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => void confirmDelete()}
                  className="bg-destructive text-white hover:bg-destructive/90"
                >
                  Delete account
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  );
}
