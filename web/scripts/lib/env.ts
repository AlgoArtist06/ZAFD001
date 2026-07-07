// Load web/.env.local into process.env for operator scripts, the way the
// Convex CLI does. The shell always wins; a missing file is a no-op.
import { readFileSync } from "node:fs";
import { join } from "node:path";

export function loadEnvLocal(webDir: string): void {
  let lines: string;
  try {
    lines = readFileSync(join(webDir, ".env.local"), "utf8");
  } catch {
    return; // rely on the shell environment
  }
  for (const raw of lines.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}
