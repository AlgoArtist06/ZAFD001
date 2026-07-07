// Locate the repository root (the directory holding data/) from any working
// directory - robust under both Node scripts and jsdom test environments,
// where import.meta.url is not a file: URL.
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

export function repoRoot(): string {
  let dir = process.cwd();
  for (;;) {
    if (existsSync(join(dir, "data", "eval", "seam2_gold.json"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) {
      throw new Error("could not locate the repository root (data/eval missing)");
    }
    dir = parent;
  }
}

export function dataPath(...parts: string[]): string {
  return join(repoRoot(), "data", ...parts);
}
