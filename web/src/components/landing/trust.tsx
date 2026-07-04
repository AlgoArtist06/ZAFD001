import { HandHelping, Lock, PhoneCall, Scale } from "lucide-react";

// The boundary and safety commitments, stated plainly. Naming what the product
// will NOT do (advice, guessing) is what makes the rest believable.
const COMMITMENTS: {
  icon: typeof Scale;
  title: string;
  body: string;
}[] = [
  {
    icon: Scale,
    title: "Information, never advice",
    body:
      "You get a clear explanation of what the law says and the standard procedure - never a prediction about your case or a recommendation to sue. For decisions about your specific situation, it points you to a lawyer or legal aid.",
  },
  {
    icon: PhoneCall,
    title: "Urgent help comes first",
    body:
      "If a question touches safety, an arrest in progress, or an active deadline, emergency and helpline contacts (112, 181) lead the answer, before any legal explanation.",
  },
  {
    icon: HandHelping,
    title: "Real help, named",
    body:
      "Every answer carries a pointer to free legal aid: your nearest Legal Services Authority (NALSA / DLSA). When the sources cannot answer, the assistant refuses and redirects instead of guessing.",
  },
  {
    icon: Lock,
    title: "Your data, your control",
    body:
      "Conversations are encrypted at rest and only stored with your explicit consent. You can delete any conversation, or your whole account and every trace of it, at any time.",
  },
];

export function Trust() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 py-16">
      <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
        Built to be trusted
      </h2>
      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {COMMITMENTS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="bg-card rounded-xl border p-6">
            <span className="bg-primary/10 text-primary grid size-10 place-items-center rounded-lg">
              <Icon className="size-5" aria-hidden />
            </span>
            <h3 className="text-foreground mt-4 text-lg font-semibold">
              {title}
            </h3>
            <p className="text-muted-foreground mt-2 leading-7">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
