"use client";

import { type ReactNode } from "react";
import { useAuth } from "@clerk/nextjs";
import { ConvexReactClient } from "convex/react";
import { ConvexProviderWithClerk } from "convex/react-clerk";

// Clerk stays the identity provider; Convex verifies the Clerk JWT ("convex"
// template) deployment-side, so every Convex function sees the same signed-in
// user the rest of the app does.
//
// Without NEXT_PUBLIC_CONVEX_URL (an unconfigured checkout) this renders
// children unchanged so the public pages still work; the chat surface then
// reports its queries as unavailable rather than crashing at import time.
const convexUrl = process.env.NEXT_PUBLIC_CONVEX_URL;
const convex = convexUrl ? new ConvexReactClient(convexUrl) : null;

export function ConvexClientProvider({ children }: { children: ReactNode }) {
  if (!convex) return children;
  return (
    <ConvexProviderWithClerk client={convex} useAuth={useAuth}>
      {children}
    </ConvexProviderWithClerk>
  );
}
