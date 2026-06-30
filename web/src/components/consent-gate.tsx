"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
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
// server-side at the moment it is given, then reveals the gated app.
export function ConsentGate({ getToken, children }: ConsentGateProps) {
  const [notice, setNotice] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [consented, setConsented] = useState(false);
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
    return () => {
      active = false;
    };
  }, []);

  if (consented) return <>{children}</>;

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
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center gap-6 px-4 py-12">
      <h1 className="text-xl font-semibold tracking-tight">
        Before you start
      </h1>
      <section
        aria-label="Privacy notice"
        className="max-h-[50vh] overflow-y-auto rounded-lg border p-4 text-sm leading-7 whitespace-pre-wrap"
      >
        {notice ?? "Loading the privacy notice…"}
      </section>
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(event) => setAccepted(event.target.checked)}
          className="mt-1 h-4 w-4"
        />
        <span>
          I have read the privacy notice and consent to my queries being
          processed, including by a third-party LLM provider.
        </span>
      </label>
      <Button
        type="button"
        onClick={() => void agree()}
        disabled={!accepted || submitting}
      >
        {submitting ? "Recording consent…" : "Agree and continue"}
      </Button>
    </main>
  );
}
