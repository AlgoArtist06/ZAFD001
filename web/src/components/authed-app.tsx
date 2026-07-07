"use client";

import { RedirectToSignIn, useAuth } from "@clerk/nextjs";

import { ConsentGate } from "@/components/consent-gate";
import { Shell } from "@/components/shell";

// The signed-in surface. Only a Clerk-authenticated user reaches it; anyone else
// is redirected to sign-in. Clerk's session token is threaded into the consent
// gate and the shell so consent and every question are attributed to that user.
export function AuthedApp() {
  const { isLoaded, isSignedIn, signOut } = useAuth();

  if (!isLoaded) return null;
  if (!isSignedIn) return <RedirectToSignIn />;

  return (
    <ConsentGate>
      <Shell signOut={() => signOut()} />
    </ConsentGate>
  );
}
