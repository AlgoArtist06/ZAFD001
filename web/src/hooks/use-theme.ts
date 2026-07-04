"use client";

import { useEffect, useState } from "react";

// Dark mode as a class on <html>, persisted to localStorage, defaulting to the
// system preference. Kept in one hook so every screen toggles the same way.
export function useTheme() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = window.localStorage?.getItem?.("theme");
    // Theme preference is external browser state and is only available after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDark(
      saved === "dark" ||
        (!saved && window.matchMedia?.("(prefers-color-scheme: dark)").matches),
    );
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    window.localStorage?.setItem?.("theme", dark ? "dark" : "light");
  }, [dark]);

  return { dark, toggle: () => setDark((value) => !value) };
}
