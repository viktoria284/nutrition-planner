export type DecimalString = string;

export type NutritionTotals = {
  kcal: DecimalString;
  protein: DecimalString;
  fat: DecimalString;
  carbs: DecimalString;
};

export type PlanSlot = {
  id: number;
  plan_id: number;
  day_date: string;
  slot_index: number;
  recipe_id: number | null;
  servings_multiplier: DecimalString;
  slot_kcal: DecimalString;
  slot_protein: DecimalString;
  slot_fat: DecimalString;
  slot_carbs: DecimalString;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type PlanDay = {
  date: string;
  totals: NutritionTotals;
  slots: PlanSlot[];
};

export type PlanListItem = {
  id: number;
  owner_user_id: number;
  profile_id: number | null;
  profile_name: string | null;
  start_date: string;
  days_count: number;
  meals_per_day: number;
  title: string | null;
  target_kcal: number | null;
  target_protein: number | null;
  target_fat: number | null;
  target_carbs: number | null;
  created_at: string;
  updated_at: string;
};

export type PlanRead = {
  id: number;
  owner_user_id: number;
  profile_id: number | null;
  profile_name: string | null;
  start_date: string;
  days_count: number;
  meals_per_day: number;
  title: string | null;
  target_kcal: number | null;
  target_protein: number | null;
  target_fat: number | null;
  target_carbs: number | null;
  slots: PlanSlot[];
  days: PlanDay[];
  created_at: string;
  updated_at: string;
};

export type PlanCreatePayload = {
  start_date: string;
  days_count: number;
  meals_per_day: number;
  profile_id: number;
  title?: string;
};

export type PlanAutogeneratePayload = {
  start_date: string;
  days_count: number;
  meals_per_day: number;
  profile_id?: number;
  title?: string | null;
  use_public_recipes: boolean;
  excluded_recipe_ids?: number[];
  excluded_food_ids?: number[];
};

export type PlanReplaceSlotPayload = {
  use_public_recipes: boolean;
  excluded_recipe_ids?: number[];
  excluded_food_ids?: number[];
  avoid_current_recipe?: boolean;
};

export type PlanRegenerateDayPayload = {
  use_public_recipes: boolean;
  excluded_recipe_ids?: number[];
  excluded_food_ids?: number[];
};

export type PlanSlotPatchPayload = {
  recipe_id?: number | null;
  servings_multiplier?: DecimalString;
  pinned?: boolean;
};

export type PlanBulkDeletePayload = {
  plan_ids: number[];
};

export type PlanBulkDeleteResponse = {
  deleted_count: number;
};
