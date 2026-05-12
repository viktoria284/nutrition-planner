import type { Profile } from "../../api/profiles";

function formatTargetValue(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toString().replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

export function formatProfileOptionLabel(profile: Profile): string {
  if (
    profile.target_kcal === null ||
    profile.target_protein === null ||
    profile.target_fat === null ||
    profile.target_carbs === null
  ) {
    return profile.name;
  }

  const kcal = formatTargetValue(profile.target_kcal);
  const protein = formatTargetValue(profile.target_protein);
  const fat = formatTargetValue(profile.target_fat);
  const carbs = formatTargetValue(profile.target_carbs);

  return `${profile.name} — ${kcal} ккал / Б ${protein} / Ж ${fat} / У ${carbs}`;
}
