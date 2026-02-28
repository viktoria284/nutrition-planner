const TOKEN_KEY = "access_token";

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = `${normalized}${"=".repeat((4 - (normalized.length % 4)) % 4)}`;
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function getCurrentUserIdFromJwt(): number | null {
  if (typeof window === "undefined") return null;

  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;

  const parts = token.split(".");
  if (parts.length < 2) return null;

  try {
    const payload = JSON.parse(decodeBase64Url(parts[1])) as { sub?: unknown; user_id?: unknown };
    const rawUserId = payload.sub ?? payload.user_id;

    if (rawUserId === null || rawUserId === undefined) return null;

    const parsed = typeof rawUserId === "number" ? rawUserId : Number(String(rawUserId));
    if (!Number.isFinite(parsed)) return null;

    return parsed;
  } catch {
    return null;
  }
}
