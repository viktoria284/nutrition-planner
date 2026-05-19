export function toSafeNumber(value: string | number): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

export function formatRoundedNumber(value: string | number): string {
  return String(Math.round(toSafeNumber(value)));
}

export function formatTrimmedNumber(value: string | number): string {
  const numeric = toSafeNumber(value);
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}
