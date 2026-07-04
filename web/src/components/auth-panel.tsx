import Link from "next/link";
import { Scale } from "lucide-react";

// The branded frame around Clerk's hosted auth cards: the product identity and
// its trust commitments on one side, the auth form on the other. Clerk owns
// the form itself; the product never sees a password.
export function AuthPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="bg-primary text-primary-foreground hidden flex-col justify-between p-10 lg:flex">
        <Link href="/" className="flex w-fit items-center gap-3">
          <span className="bg-primary-foreground/10 grid size-10 place-items-center rounded-lg">
            <Scale className="size-5" aria-hidden />
          </span>
          <span className="font-heading text-lg font-semibold tracking-tight">
            Legal Saathi
          </span>
        </Link>
        <div className="max-w-md space-y-4">
          <h1 className="font-heading text-3xl leading-snug font-semibold text-balance">
            Clear answers about Indian law, quoted from the law itself.
          </h1>
          <p className="text-primary-foreground/80 leading-7">
            Every answer cites its exact section. When the sources cannot
            answer, it says so and points you to real help - never a guess.
          </p>
          <p className="text-primary-foreground/70 text-sm">
            English · हिन्दी · தமிழ் · ગુજરાતી
          </p>
        </div>
        <p className="text-primary-foreground/60 text-xs leading-5">
          Legal information, not legal advice. Free legal aid: NALSA / DLSA.
        </p>
      </aside>
      <main className="flex flex-col items-center justify-center gap-4 p-6">
        <Link href="/" className="flex items-center gap-2 lg:hidden">
          <span className="bg-primary text-primary-foreground grid size-9 place-items-center rounded-lg">
            <Scale className="size-4" aria-hidden />
          </span>
          <span className="font-heading font-semibold">Legal Saathi</span>
        </Link>
        {children}
      </main>
    </div>
  );
}
