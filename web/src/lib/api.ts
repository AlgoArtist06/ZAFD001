// The backend's base URL. The shell, the privacy notice, and the consent
// endpoint all live under it, so they share one origin from one env var.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The absolute URL for a backend path (for example `/api/answer`).
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
