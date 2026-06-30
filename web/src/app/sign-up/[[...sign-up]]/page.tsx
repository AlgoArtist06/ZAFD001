import { SignUp } from "@clerk/nextjs";

// Clerk owns signup. Explicit consent to the privacy notice - including the
// third-party-LLM disclosure - is collected by the ConsentGate immediately
// after the account is created, before the chat shell is reachable.
export default function SignUpPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
      <SignUp />
      <p className="text-muted-foreground max-w-sm text-center text-sm">
        After creating your account you will be shown a privacy notice and asked
        to consent before using the assistant.
      </p>
    </div>
  );
}
