import { AuthedApp } from "@/components/authed-app";

// The chat shell lives behind authentication: a signed-in, consented user gets
// the sidebar-and-thread shell; everyone else is sent to sign-in first.
export default function ChatPage() {
  return <AuthedApp />;
}
