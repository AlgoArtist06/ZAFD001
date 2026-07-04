import Link from "next/link";
import { Scale } from "lucide-react";

import { Hero } from "@/components/landing/hero";
import { Sources } from "@/components/landing/sources";
import { Trust } from "@/components/landing/trust";
import { Button } from "@/components/ui/button";

// The public face: a static page that establishes what the product is, what it
// draws on, and where its boundary lies - before anyone signs in. The chat
// itself lives at /chat behind authentication and consent.
export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-5">
        <div className="flex items-center gap-3">
          <span className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg shadow-xs">
            <Scale className="size-5" aria-hidden />
          </span>
          <div>
            <p className="font-heading text-lg font-semibold tracking-tight">
              Legal Saathi
            </p>
            <p className="text-muted-foreground text-xs">
              Rights, made understandable
            </p>
          </div>
        </div>
        <nav className="flex items-center gap-2">
          <Button asChild variant="ghost" className="min-h-11">
            <Link href="/sign-in">Sign in</Link>
          </Button>
          <Button asChild className="min-h-11 rounded-lg">
            <Link href="/chat">Get started</Link>
          </Button>
        </nav>
      </header>

      <main className="flex-1">
        <Hero />
        <Sources />
        <Trust />
      </main>

      <footer className="border-t">
        <div className="text-muted-foreground mx-auto w-full max-w-6xl space-y-2 px-6 py-8 text-sm leading-6">
          <p>
            Legal Saathi provides legal information, not legal advice. For help
            with your specific situation, consult a lawyer or your nearest Legal
            Services Authority (NALSA / DLSA).
          </p>
          <p>English · हिन्दी · தமிழ் · ગુજરાતી</p>
        </div>
      </footer>
    </div>
  );
}
