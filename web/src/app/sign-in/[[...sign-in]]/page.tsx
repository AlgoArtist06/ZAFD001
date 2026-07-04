import { SignIn } from "@clerk/nextjs";

import { AuthPanel } from "@/components/auth-panel";

// Clerk owns login; the product never handles a password itself.
export default function SignInPage() {
  return (
    <AuthPanel>
      <SignIn />
    </AuthPanel>
  );
}
