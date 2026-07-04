"use client";

import { RedirectToSignIn, UserProfile, useAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

import { AccountSettings } from "@/components/account-settings";
import { clerkAppearance } from "@/lib/clerk-theme";

// The dedicated account-settings route, behind authentication. A signed-in user
// manages their profile and, from the danger zone, permanently deletes their
// account and all stored data; anyone else is redirected to sign-in. Clerk's
// session is threaded down so the deletion is attributed to that user.
export default function SettingsPage() {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  const router = useRouter();

  if (!isLoaded) return null;
  if (!isSignedIn) return <RedirectToSignIn />;

  return (
    <AccountSettings
      email={user?.primaryEmailAddress?.emailAddress}
      memberSince={
        user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : null
      }
      getToken={() => getToken()}
      onSignOut={() => signOut()}
      onDeleted={() => router.replace("/")}
      profile={<UserProfile appearance={clerkAppearance} routing="hash" />}
    />
  );
}
