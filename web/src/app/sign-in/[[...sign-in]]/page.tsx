import { SignIn } from "@clerk/nextjs";

// Clerk owns login; the product never handles a password itself.
export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <SignIn />
    </div>
  );
}
