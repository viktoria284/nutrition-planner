export function formatQuantityValue(value: string | number | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined || value === "") return "";
  const numeric = Number(String(value).trim().replace(",", "."));
  if (!Number.isFinite(numeric)) return "";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(maximumFractionDigits).replace(/\.?0+$/, "");
}

export function formatQuantityForInput(value: string | number | null | undefined): string {
  return formatQuantityValue(value, 2);
}

export function formatQuantityDisplay(value: string | number | null | undefined): string {
  return formatQuantityValue(value, 2);
}
