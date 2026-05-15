export type DecimalString = string;

export type NutritionTotals = {
  kcal: DecimalString;
  protein: DecimalString;
  fat: DecimalString;
  carbs: DecimalString;
  fiber: DecimalString;
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
  slot_fiber: DecimalString;
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
  target_fiber: number | null;
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
  target_fiber: number | null;
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
  max_cook_time_minutes?: number | null;
  batch_cooking?: Partial<Record<"breakfast" | "lunch" | "dinner" | "snack", 1 | 2 | 3>>;
  favorite_recipes_mode?: "none" | "prefer" | "only";
};

export type PlanReplaceSlotPayload = {
  use_public_recipes: boolean;
  excluded_recipe_ids?: number[];
  excluded_food_ids?: number[];
  avoid_current_recipe?: boolean;
  max_cook_time_minutes?: number | null;
};

export type PlanRegenerateDayPayload = {
  use_public_recipes: boolean;
  excluded_recipe_ids?: number[];
  excluded_food_ids?: number[];
  max_cook_time_minutes?: number | null;
};

export type PlanSlotPatchPayload = {
  recipe_id?: number | null;
  servings_multiplier?: DecimalString;
  pinned?: boolean;
};

export type PlanSlotIngredientOverrideBaseItem = {
  recipe_ingredient_id: number;
  food_id?: number;
  grams?: DecimalString;
  is_excluded?: boolean;
};

export type PlanSlotManualIngredientItem = {
  food_id: number;
  grams: DecimalString;
};

export type PlanSlotIngredientOverridesReplacePayload = {
  base_overrides?: PlanSlotIngredientOverrideBaseItem[];
  manual_items?: PlanSlotManualIngredientItem[];
};

export type PlanSlotEffectiveIngredient = {
  recipe_ingredient_id: number | null;
  override_id: number | null;
  source: "base" | "overridden" | "manual";
  food_id: number;
  food_name: string;
  grams: DecimalString;
  kcal: DecimalString;
  protein: DecimalString;
  fat: DecimalString;
  carbs: DecimalString;
  fiber: DecimalString;
};

export type PlanSlotEffectiveIngredientsResponse = {
  slot_id: number;
  recipe_id: number;
  has_overrides: boolean;
  excluded_recipe_ingredient_ids: number[];
  items: PlanSlotEffectiveIngredient[];
};

export type PlanBulkDeletePayload = {
  plan_ids: number[];
};

export type PlanBulkDeleteResponse = {
  deleted_count: number;
};

export type NutrientStatus = "low" | "ok" | "high" | "no_target";

export type PlanAnalyticsTarget = {
  kcal: number | null;
  protein: number | null;
  fat: number | null;
  carbs: number | null;
  fiber: number | null;
};

export type NutrientAnalytics = {
  total: DecimalString;
  percent: DecimalString | null;
  status: NutrientStatus;
};

export type PlanDayAnalytics = {
  date: string;
  kcal: NutrientAnalytics;
  protein: NutrientAnalytics;
  fat: NutrientAnalytics;
  carbs: NutrientAnalytics;
  fiber: NutrientAnalytics;
  day_score: number;
};

export type PlanPeriodAnalytics = {
  days_count: number;
  average_kcal: DecimalString;
  average_protein: DecimalString;
  average_fat: DecimalString;
  average_carbs: DecimalString;
  average_fiber: DecimalString;
  kcal_percent: DecimalString | null;
  protein_percent: DecimalString | null;
  fat_percent: DecimalString | null;
  carbs_percent: DecimalString | null;
  fiber_percent: DecimalString | null;
  overall_score: number;
};

export type PlanAnalyticsResponse = {
  targets: PlanAnalyticsTarget;
  period_summary: PlanPeriodAnalytics;
  day_analytics: PlanDayAnalytics[];
  recommendations: string[];
};
