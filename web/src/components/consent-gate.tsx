"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiUrl } from "@/lib/api";

// How the gate obtains the signed-in user's session token, so the consent it
// records server-side is attributed to that user.
type ConsentGateProps = {
  getToken: () => Promise<string | null>;
  children: React.ReactNode;
};

// Consent is required before a signed-in user reaches the chat shell: they are
// shown the privacy notice - including the disclosure that queries are sent to a
// third-party LLM - and must explicitly opt in. Accepting records consent
// server-side at the moment it is given. A returning user who already consented
// is recognised server-side and skips the gate entirely.
export function ConsentGate({ getToken, children }: ConsentGateProps) {
  const [notice, setNotice] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  // null = still checking server-side status; the gate renders nothing yet so
  // a consented user never sees the form flash.
  const [consented, setConsented] = useState<boolean | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch(apiUrl("/api/privacy-notice"))
      .then((response) => response.json())
      .then((data) => {
        if (active) setNotice(data.notice);
      })
      .catch(() => {
        if (active) setNotice("Privacy notice is unavailable right now.");
      });
    void (async () => {
      try {
        const token = await getToken();
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        const response = await fetch(apiUrl("/api/consent"), { headers });
        const status = response.ok ? await response.json() : null;
        if (active) setConsented(status?.consented === true);
      } catch {
        if (active) setConsented(false);
      }
    })();
    return () => {
      active = false;
    };
    // getToken is stable for the session; the check runs once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (consented) return <>{children}</>;
  if (consented === null) return null;

  async function agree() {
    if (!accepted || submitting) return;
    setSubmitting(true);
    try {
      const token = await getToken();
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(apiUrl("/api/consent"), {
        method: "POST",
        headers,
      });
      if (response.ok) setConsented(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader>
          <span className="bg-primary/10 text-primary grid size-10 place-items-center rounded-lg">
            <ShieldCheck className="size-5" aria-hidden />
          </span>
          <CardTitle className="font-heading pt-2 text-xl">
            Before you start
          </CardTitle>
          <CardDescription>
            Please read how your data is handled. Nothing is stored, and no
            question is answered, until you consent.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <section
            aria-label="Privacy notice"
            className="bg-muted/50 max-h-[45vh] overflow-y-auto rounded-lg border p-4 text-sm leading-7 whitespace-pre-wrap"
          >
            {notice ?? "Loading the privacy notice…"}
          </section>
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
              className="accent-primary mt-1 size-4"
            />
            <span>
              I have read the privacy notice and consent to my queries being
              processed, including by a third-party LLM provider.
            </span>
          </label>
        </CardContent>
        <CardFooter>
          <Button
            type="button"
            onClick={() => void agree()}
            disabled={!accepted || submitting}
            className="min-h-11 w-full rounded-lg"
          >
            {submitting ? "Recording consent…" : "Agree and continue"}
          </Button>
        </CardFooter>
      </Card>
    </main>
  );
}
