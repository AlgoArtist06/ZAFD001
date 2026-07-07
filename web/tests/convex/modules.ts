/// <reference types="vite/client" />
// The module map convex-test needs to resolve function references. Tests live
// outside convex/ so the Convex CLI never tries to bundle them on push.
export const modules = import.meta.glob([
  "../../convex/**/*.js",
  "../../convex/**/*.ts",
  "!../../convex/**/*.d.ts",
]);
