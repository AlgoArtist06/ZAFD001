import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";

import { clerkAppearance } from "@/lib/clerk-theme";
import {
  Noto_Sans,
  Noto_Sans_Devanagari,
  Noto_Sans_Gujarati,
  Noto_Sans_Tamil,
  Noto_Serif,
} from "next/font/google";
import "./globals.css";

// One humanist sans for body text and one serif for display, each with the
// Indic companions the four Supported Languages need. All are variable fonts,
// loaded with swap so text is never invisible while they arrive.
const notoSans = Noto_Sans({
  variable: "--font-noto-sans",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const notoSerif = Noto_Serif({
  variable: "--font-noto-serif",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const notoDevanagari = Noto_Sans_Devanagari({
  variable: "--font-noto-devanagari",
  subsets: ["devanagari"],
  display: "swap",
});

const notoTamil = Noto_Sans_Tamil({
  variable: "--font-noto-tamil",
  subsets: ["tamil"],
  display: "swap",
});

const notoGujarati = Noto_Sans_Gujarati({
  variable: "--font-noto-gujarati",
  subsets: ["gujarati"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Legal Saathi - Know your rights",
    template: "%s | Legal Saathi",
  },
  description:
    "Plain-language legal information for Indian citizens, grounded in cited statutory sources, in English, Hindi, Tamil, and Gujarati.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider
      appearance={clerkAppearance}
      signInFallbackRedirectUrl="/chat"
      signUpFallbackRedirectUrl="/chat"
    >
      <html
        lang="en"
        data-scroll-behavior="smooth"
        className={`${notoSans.variable} ${notoSerif.variable} ${notoDevanagari.variable} ${notoTamil.variable} ${notoGujarati.variable} h-full antialiased`}
        suppressHydrationWarning
      >
        <head>
          {/* Apply the saved (or system) theme before first paint, on every
              route - the same logic use-theme.ts keeps for the toggle. Without
              this, pages that never mount the hook render light for a
              dark-mode user, and themed pages flash light before hydration. */}
          <script
            dangerouslySetInnerHTML={{
              __html: `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||(!t&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){}})()`,
            }}
          />
        </head>
        <body className="min-h-full flex flex-col">{children}</body>
      </html>
    </ClerkProvider>
  );
}
