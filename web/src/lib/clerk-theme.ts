// The Clerk appearance shared by the provider and the hosted auth components,
// so sign-in and sign-up wear the product's authority-navy identity instead of
// Clerk's defaults. Values mirror the tokens in globals.css.
export const clerkAppearance = {
  variables: {
    colorPrimary: "#1e3a8a",
    colorText: "#111a2e",
    colorTextSecondary: "#4b5568",
    colorBackground: "#ffffff",
    colorInputBackground: "#f7f8fa",
    borderRadius: "0.625rem",
    fontFamily:
      "var(--font-noto-sans), var(--font-noto-devanagari), var(--font-noto-tamil), var(--font-noto-gujarati), system-ui, sans-serif",
  },
  elements: {
    card: "shadow-md border border-[#e4e7ee]",
    formButtonPrimary: "min-h-11 text-sm font-semibold",
  },
} as const;
