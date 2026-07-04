"use client";

import { useEffect, useState } from "react";

// Whether <html> currently carries the dark class. That class is the single
// source of truth: the pre-paint inline script in the root layout sets it from
// localStorage / the system preference before anything renders, and toggle()
// updates it. Reading it here means the hook starts in sync instead of assuming
// a value and clobbering what the script chose.
function domIsDark(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

// Dark mode as a class on <html>, persisted to localStorage. The hook only
// *writes* on an explicit toggle; the class itself is applied before paint by
// the root layout, so mounting a screen never resets the chosen theme.
export function useTheme() {
  // Match the server HTML (which never carries the class) on first render, then
  // reconcile to what the inline script actually applied. Only the toggle icon
  // settles after mount - the page theme, owned by the class, never flips.
  const [dark, setDark] = useState(false);

  useEffect(() => {
    // Theme is client-only state, readable only after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDark(domIsDark());
  }, []);

  function toggle() {
    setDark((value) => {
      const next = !value;
      document.documentElement.classList.toggle("dark", next);
      window.localStorage?.setItem?.("theme", next ? "dark" : "light");
      return next;
    });
  }

  return { dark, toggle };
}
