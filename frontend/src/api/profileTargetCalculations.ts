import { apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type ProfileTargetCalculationSex = "male" | "female";
export type ProfileTargetCalculationActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type ProfileTargetCalculationGoal = "maintain" | "lose" | "gain";
export type ProfileTargetCalculationFormula = "mifflin_st_jeor" | "revised_harris_benedict" | "who_fao_unu";
export type ProfileTargetCalculationMacroPreset = "balanced" | "higher_protein" | "higher_carb";
export type SpecialCondition = "none" | "pregnant" | "breastfeeding" | "medical_special_diet";
export type LactationPeriod = "first_6_months" | "after_6_months" | "unknown";

export type ProfileTargetCalculationInput = {
  sex: ProfileTargetCalculationSex;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ProfileTargetCalculationActivityLevel;
  goal: ProfileTargetCalculationGoal;
  formula: ProfileTargetCalculationFormula;
  macro_preset: ProfileTargetCalculationMacroPreset;
  special_condition: SpecialCondition;
  lactation_period: LactationPeriod | null;
};

export type ProfileTargetCalculationResult = {
  id: number;
  user_id: number;
  sex: ProfileTargetCalculationSex;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ProfileTargetCalculationActivityLevel;
  goal: ProfileTargetCalculationGoal;
  formula: ProfileTargetCalculationFormula;
  macro_preset: ProfileTargetCalculationMacroPreset;
  special_condition: SpecialCondition;
  lactation_period: LactationPeriod | null;
  bmr: number;
  tdee: number;
  target_kcal: number;
  target_protein: number;
  target_fat: number;
  target_carbs: number;
  target_fiber: number;
  warning_message: string | null;
  created_at: string;
  updated_at: string;
};

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export async function calculateProfileTarget(
  payload: ProfileTargetCalculationInput,
): Promise<ProfileTargetCalculationResult> {
  return apiRequest<ProfileTargetCalculationResult>({
    method: "POST",
    path: "/profile-target-calculations/calculate",
    token: getToken(),
    body: payload,
  });
}

export async function getLatestProfileTargetCalculation(): Promise<ProfileTargetCalculationResult> {
  return apiRequest<ProfileTargetCalculationResult>({
    method: "GET",
    path: "/profile-target-calculations/latest",
    token: getToken(),
  });
}
