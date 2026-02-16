function sanitizeValidationMessage(raw: unknown): string {
  if (typeof raw !== "string") return "Ошибка валидации";
  const cleaned = raw.replace(/^Value error,\s*/i, "").trim();
  return cleaned || "Ошибка валидации";
}

export function normalizeApiError(payload: any): string {
  const detail = payload?.detail ?? payload;
  if (!detail) return "Неизвестная ошибка";
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const msgs = detail
      .map((e) => sanitizeValidationMessage(typeof e === "string" ? e : e?.msg))
      .filter(Boolean);
    return msgs.length ? msgs.join("\n") : "Ошибка валидации";
  }

  if (typeof detail === "object") {
    try { return JSON.stringify(detail); } catch { return "Ошибка"; }
  }
  return String(detail);
}
