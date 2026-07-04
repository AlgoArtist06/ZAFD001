// The Clerk appearance shared by the provider and the hosted auth components,
// so sign-in, sign-up, and the profile editor wear the product's identity
// instead of Clerk's defaults. Every color points at the theme tokens in
// globals.css, which flip with the `dark` class on <html> - so Clerk's UI
// follows the app's light/dark toggle live instead of staying a white card.
export const clerkAppearance = {
  variables: {
    colorPrimary: "var(--primary)",
    colorPrimaryForeground: "var(--primary-foreground)",
    colorForeground: "var(--foreground)",
    colorMutedForeground: "var(--muted-foreground)",
    colorMuted: "var(--muted)",
    colorNeutral: "var(--foreground)",
    colorBackground: "var(--card)",
    colorInput: "var(--input)",
    colorInputForeground: "var(--foreground)",
    colorBorder: "var(--border)",
    colorDanger: "var(--destructive)",
    colorRing: "var(--ring)",
    borderRadius: "0.625rem",
    fontFamily:
      "var(--font-noto-sans), var(--font-noto-devanagari), var(--font-noto-tamil), var(--font-noto-gujarati), system-ui, sans-serif",
  },
  elements: {
    card: "shadow-md border border-[var(--border)]",
    formButtonPrimary: "min-h-11 text-sm font-semibold",
  },
} as const;
