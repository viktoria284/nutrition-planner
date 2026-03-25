import type { DecimalString } from "../types/plan";

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatPlanDate(dateIso: string): string {
  const [yearRaw, monthRaw, dayRaw] = dateIso.split("-");
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return dateIso;

  const date = new Date(Date.UTC(year, month - 1, day));
  return dateFormatter.format(date);
}

export function planTitleWithFallback(title: string | null, startDate: string): string {
  const normalized = title?.trim();
  if (normalized) return normalized;
  return `План с ${formatPlanDate(startDate)}`;
}

export function formatDecimal(value: DecimalString | number | null | undefined): string {
  if (value === null || value === undefined) return "0.00";
  return String(value);
}
