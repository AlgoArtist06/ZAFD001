import { BookOpen } from "lucide-react";

// The Source of Truth, named in full. Listing the exact statutes - and that
// answers quote them verbatim - is the strongest trust signal this product
// can give. Keep this list in step with the ingested corpus.
const SOURCES: { name: string; detail: string }[] = [
  {
    name: "Bharatiya Nyaya Sanhita, 2023",
    detail: "The current criminal code - offences and punishments.",
  },
  {
    name: "Bharatiya Nagarik Suraksha Sanhita, 2023",
    detail: "Criminal procedure - arrest, bail, FIR, and investigation.",
  },
  {
    name: "Bharatiya Sakshya Adhiniyam, 2023",
    detail: "The law of evidence.",
  },
  {
    name: "Consumer Protection Act, 2019",
    detail: "Consumer rights, defective goods, and complaint forums.",
  },
  {
    name: "Constitution of India, Part III",
    detail: "Your fundamental rights.",
  },
  {
    name: "Copyright, Trade Marks & Patents Acts",
    detail: "Intellectual property protection.",
  },
  {
    name: "Flagship welfare schemes",
    detail: "PMAY, Ayushman Bharat, and more - eligibility and how to apply.",
  },
];

export function Sources() {
  return (
    <section id="sources" className="border-y bg-card">
      <div className="mx-auto w-full max-w-6xl px-6 py-16">
        <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
          Grounded in the law itself
        </h2>
        <p className="text-muted-foreground mt-3 max-w-2xl leading-7">
          Answers are retrieved from the current statutes as published on India
          Code - never the repealed IPC, CrPC, or Evidence Act - and every claim
          carries a citation with the statutory text quoted verbatim in English.
          If the sources do not answer a question, the assistant says so instead
          of guessing.
        </p>
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map(({ name, detail }) => (
            <li
              key={name}
              className="bg-background flex items-start gap-3 rounded-xl border p-4"
            >
              <span className="bg-primary/10 text-primary mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg">
                <BookOpen className="size-4" aria-hidden />
              </span>
              <div>
                <p className="text-foreground font-semibold">{name}</p>
                <p className="text-muted-foreground mt-1 text-sm leading-6">
                  {detail}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
