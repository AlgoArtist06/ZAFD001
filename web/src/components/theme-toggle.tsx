"use client";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

// A self-contained light/dark switch: it owns its theme state through useTheme,
// so a server component (the landing page) can drop it in without threading any
// theme props down. The chat sidebar keeps its own prop-driven button.
export function ThemeToggle({ className }: { className?: string }) {
  const { dark, toggle } = useTheme();
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={dark ? "Use light mode" : "Use dark mode"}
      onClick={toggle}
      className={`rounded-full ${className ?? ""}`}
    >
      {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
