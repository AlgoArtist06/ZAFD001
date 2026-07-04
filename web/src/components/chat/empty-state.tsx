import { TOPIC_TILES } from "@/lib/topics";

// The first screen of a fresh Conversation: what this product is, in one
// breath, and the Covered Domains as tappable starter questions.
export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="text-muted-foreground mx-auto mt-[3vh] w-full text-left">
      <span className="border-highlight/40 bg-highlight/10 text-highlight inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-wide uppercase">
        Source-backed legal information
      </span>
      <h1 className="text-foreground mt-5 max-w-3xl text-3xl font-semibold tracking-tight sm:text-5xl sm:leading-[1.08]">
        Understand your rights.
        <span className="text-primary"> Know your next step.</span>
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-7">
        Ask in everyday language and get a clear answer grounded in official
        Indian legal sources - in English, हिन्दी, தமிழ், or ગુજરાતી.
      </p>
      <div
        role="group"
        aria-label="Common topics"
        className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        {TOPIC_TILES.map(({ icon: Icon, label, prompt }) => (
          <button
            key={label}
            type="button"
            onClick={() => onPick(prompt)}
            className="group bg-card hover:border-primary/40 flex min-h-28 cursor-pointer flex-col items-start justify-between rounded-xl border p-4 text-left shadow-xs transition-all hover:-translate-y-0.5 hover:shadow-md"
          >
            <span className="bg-primary/10 text-primary grid size-10 place-items-center rounded-lg transition-transform group-hover:scale-105">
              <Icon className="size-5" aria-hidden />
            </span>
            <span className="text-foreground text-sm leading-5 font-semibold">
              {label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
