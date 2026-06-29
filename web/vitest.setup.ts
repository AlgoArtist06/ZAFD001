import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount React trees between tests so each one starts from a clean DOM.
afterEach(() => {
  cleanup();
});
