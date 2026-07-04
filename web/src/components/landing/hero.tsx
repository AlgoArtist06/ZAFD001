import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";

import { Button } from "@/components/ui/button";

// The first screen a visitor sees: what this product is, its promise, and the
// two facts that build trust fastest - every answer is cited, and it speaks
// the reader's language.
export function Hero() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 pt-16 pb-20 sm:pt-24">
      <span className="border-highlight/40 bg-highlight/10 text-highlight inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-wide uppercase">
        Source-backed legal information
      </span>
      <h1 className="text-foreground mt-6 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-6xl sm:leading-[1.05]">
        Understand your rights.
        <span className="text-primary"> Know your next step.</span>
      </h1>
      <p className="text-muted-foreground mt-6 max-w-2xl text-lg leading-8">
        Ask about consumer complaints, police interactions, fundamental rights,
        criminal law, or government schemes in everyday language. Every answer
        quotes the exact section of current Indian law it comes from.
      </p>
      <p className="text-muted-foreground mt-3 text-base">
        English · हिन्दी · தமிழ் · ગુજરાતી
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button asChild size="lg" className="min-h-12 rounded-lg px-6 text-base">
          <Link href="/chat">
            Ask your first question
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Button>
        <Button
          asChild
          size="lg"
          variant="outline"
          className="min-h-12 rounded-lg px-6 text-base"
        >
          <a href="#sources">
            <BookOpen className="size-4" aria-hidden />
            See the sources
          </a>
        </Button>
      </div>
    </section>
  );
}
