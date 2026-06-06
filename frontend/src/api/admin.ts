import { apiRequest } from "./http";
import type { FoodCreatePayload, FoodItem, FoodItemUpdatePayload } from "./foods";
import type {
  RecipeCreate,
  RecipeIngredientCreate,
  RecipeIngredientRead,
  RecipeIngredientUpdate,
  RecipeRead,
  RecipeStepInput,
  RecipeStepRead,
  RecipeUpdate,
} from "./recipes";
import type { FoodCategory } from "../types/foodCategory";

const TOKEN_KEY = "access_token";

export type AdminSummary = {
  total_users: number;
  total_foods: number;
  total_recipes: number;
  public_foods: number;
  public_recipes: number;
  pending_or_under_review_foods: number;
  pending_or_under_review_recipes: number;
  open_food_reports: number;
  open_recipe_reports: number;
};

export type AdminOwner = {
  id: number;
  username: string;
  display_name: string | null;
};

export type AdminFoodItem = {
  id: number;
  name: string;
  brand: string | null;
  category: FoodCategory;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber: number;
  source: "private" | "verified" | "community";
  status: "draft" | "pending" | "approved" | "rejected";
  is_listed: boolean;
  reports_count: number;
  owner: AdminOwner | null;
  created_at: string;
  updated_at: string;
};

export type AdminRecipeItem = {
  id: number;
  name: string;
  description: string | null;
  instructions: string | null;
  servings_count: number;
  cook_time_minutes: number | null;
  source: "private" | "verified" | "community";
  status: "draft" | "pending" | "approved" | "rejected";
  is_listed: boolean;
  meal_types: string[];
  reports_count: number;
  owner: AdminOwner | null;
  created_at: string;
  updated_at: string;
};

export type AdminReportItem = {
  id: number;
  target_type: "food" | "recipe";
  target_id: number;
  target_name: string;
  reporter: AdminOwner | null;
  reason: string | null;
  comment: string | null;
  created_at: string;
  resolved_at: string | null;
  resolution: string | null;
  resolved_by_admin: AdminOwner | null;
  admin_comment: string | null;
};

export type AdminUserItem = {
  id: number;
  email: string;
  username: string;
  display_name: string | null;
  role: "user" | "admin" | "superadmin";
  is_active: boolean;
  created_at: string;
  profiles_count: number;
  recipes_count: number;
  plans_count: number;
};

export type AdminModerationAction = "approve" | "hide" | "reject" | "restore";
export type AdminReportResolution = "no_action" | "content_hidden" | "content_restored" | "content_rejected";
export type AdminContentOrigin = "all" | "system" | "user";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export async function getAdminSummary(): Promise<AdminSummary> {
  return apiRequest<AdminSummary>({ method: "GET", path: "/admin/summary", token: getToken() });
}

export async function listAdminFoods(params: {
  q?: string;
  source?: "private" | "verified" | "community";
  origin?: AdminContentOrigin;
  status?: "draft" | "pending" | "approved" | "rejected";
  isListed?: boolean;
  reportedOnly?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<AdminFoodItem[]> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.source) query.set("source", params.source);
  if (params.origin) query.set("origin", params.origin);
  if (params.status) query.set("status", params.status);
  if (typeof params.isListed === "boolean") query.set("is_listed", String(params.isListed));
  if (typeof params.reportedOnly === "boolean") query.set("reported_only", String(params.reportedOnly));
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString();
  return apiRequest<AdminFoodItem[]>({ method: "GET", path: suffix ? `/admin/foods?${suffix}` : "/admin/foods", token: getToken() });
}

export async function listAdminRecipes(params: {
  q?: string;
  origin?: AdminContentOrigin;
  status?: "draft" | "pending" | "approved" | "rejected";
  isListed?: boolean;
  reportedOnly?: boolean;
  mealType?: "breakfast" | "lunch" | "dinner" | "snack";
  limit?: number;
  offset?: number;
} = {}): Promise<AdminRecipeItem[]> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.origin) query.set("origin", params.origin);
  if (params.status) query.set("status", params.status);
  if (typeof params.isListed === "boolean") query.set("is_listed", String(params.isListed));
  if (typeof params.reportedOnly === "boolean") query.set("reported_only", String(params.reportedOnly));
  if (params.mealType) query.set("meal_type", params.mealType);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString();
  return apiRequest<AdminRecipeItem[]>({ method: "GET", path: suffix ? `/admin/recipes?${suffix}` : "/admin/recipes", token: getToken() });
}

export async function moderateAdminFood(foodId: number, action: AdminModerationAction, reason?: string | null): Promise<AdminFoodItem> {
  return apiRequest<AdminFoodItem>({
    method: "POST",
    path: `/admin/foods/${foodId}/moderate`,
    token: getToken(),
    body: { action, reason: reason ?? null },
  });
}

export async function createAdminFood(payload: FoodCreatePayload): Promise<FoodItem> {
  return apiRequest<FoodItem>({
    method: "POST",
    path: "/admin/foods",
    token: getToken(),
    body: payload,
  });
}

export async function updateAdminFood(foodId: number, payload: FoodItemUpdatePayload): Promise<FoodItem> {
  return apiRequest<FoodItem>({
    method: "PATCH",
    path: `/admin/foods/${foodId}`,
    token: getToken(),
    body: payload,
  });
}

export async function deleteAdminFood(foodId: number): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/admin/foods/${foodId}`,
    token: getToken(),
  });
}

export async function createAdminRecipe(payload: RecipeCreate): Promise<RecipeRead> {
  return apiRequest<RecipeRead>({
    method: "POST",
    path: "/admin/recipes",
    token: getToken(),
    body: payload,
  });
}

export async function getAdminRecipe(recipeId: number | string): Promise<RecipeRead> {
  return apiRequest<RecipeRead>({
    method: "GET",
    path: `/admin/recipes/${recipeId}`,
    token: getToken(),
  });
}

export async function updateAdminRecipe(recipeId: number, payload: RecipeUpdate): Promise<RecipeRead> {
  return apiRequest<RecipeRead>({
    method: "PATCH",
    path: `/admin/recipes/${recipeId}`,
    token: getToken(),
    body: payload,
  });
}

export async function addAdminRecipeIngredient(
  recipeId: number | string,
  payload: RecipeIngredientCreate,
): Promise<RecipeIngredientRead> {
  return apiRequest<RecipeIngredientRead>({
    method: "POST",
    path: `/admin/recipes/${recipeId}/ingredients`,
    token: getToken(),
    body: payload,
  });
}

export async function updateAdminRecipeIngredient(
  recipeId: number | string,
  ingredientId: number | string,
  payload: RecipeIngredientUpdate,
): Promise<RecipeIngredientRead> {
  return apiRequest<RecipeIngredientRead>({
    method: "PATCH",
    path: `/admin/recipes/${recipeId}/ingredients/${ingredientId}`,
    token: getToken(),
    body: payload,
  });
}

export async function deleteAdminRecipeIngredient(recipeId: number | string, ingredientId: number | string): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/admin/recipes/${recipeId}/ingredients/${ingredientId}`,
    token: getToken(),
  });
}

export async function replaceAdminRecipeSteps(recipeId: number | string, steps: RecipeStepInput[]): Promise<RecipeStepRead[]> {
  return apiRequest<RecipeStepRead[]>({
    method: "PUT",
    path: `/admin/recipes/${recipeId}/steps`,
    token: getToken(),
    body: { steps },
  });
}

export async function uploadAdminRecipeCoverImage(recipeId: number | string, file: File): Promise<RecipeRead> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<RecipeRead>({
    method: "POST",
    path: `/admin/recipes/${recipeId}/cover-image`,
    token: getToken(),
    rawBody: formData,
  });
}

export async function deleteAdminRecipeCoverImage(recipeId: number | string): Promise<RecipeRead> {
  return apiRequest<RecipeRead>({
    method: "DELETE",
    path: `/admin/recipes/${recipeId}/cover-image`,
    token: getToken(),
  });
}

export async function uploadAdminRecipeStepImage(
  recipeId: number | string,
  stepId: number | string,
  file: File,
): Promise<RecipeStepRead> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<RecipeStepRead>({
    method: "POST",
    path: `/admin/recipes/${recipeId}/steps/${stepId}/image`,
    token: getToken(),
    rawBody: formData,
  });
}

export async function deleteAdminRecipeStepImage(recipeId: number | string, stepId: number | string): Promise<RecipeStepRead> {
  return apiRequest<RecipeStepRead>({
    method: "DELETE",
    path: `/admin/recipes/${recipeId}/steps/${stepId}/image`,
    token: getToken(),
  });
}

export async function deleteAdminRecipe(recipeId: number): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/admin/recipes/${recipeId}`,
    token: getToken(),
  });
}

export async function moderateAdminRecipe(recipeId: number, action: AdminModerationAction, reason?: string | null): Promise<RecipeRead> {
  return apiRequest<RecipeRead>({
    method: "POST",
    path: `/admin/recipes/${recipeId}/moderate`,
    token: getToken(),
    body: { action, reason: reason ?? null },
  });
}

export async function listAdminReports(params: {
  targetType?: "food" | "recipe" | "all";
  onlyOpen?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<AdminReportItem[]> {
  const query = new URLSearchParams();
  if (params.targetType) query.set("target_type", params.targetType);
  if (typeof params.onlyOpen === "boolean") query.set("only_open", String(params.onlyOpen));
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString();
  return apiRequest<AdminReportItem[]>({ method: "GET", path: suffix ? `/admin/reports?${suffix}` : "/admin/reports", token: getToken() });
}

export async function resolveAdminFoodReport(reportId: number, resolution: AdminReportResolution, comment?: string | null): Promise<AdminReportItem> {
  return apiRequest<AdminReportItem>({
    method: "POST",
    path: `/admin/reports/foods/${reportId}/resolve`,
    token: getToken(),
    body: { resolution, comment: comment ?? null },
  });
}

export async function resolveAdminRecipeReport(reportId: number, resolution: AdminReportResolution, comment?: string | null): Promise<AdminReportItem> {
  return apiRequest<AdminReportItem>({
    method: "POST",
    path: `/admin/reports/recipes/${reportId}/resolve`,
    token: getToken(),
    body: { resolution, comment: comment ?? null },
  });
}

export async function listAdminUsers(params: { q?: string; limit?: number; offset?: number } = {}): Promise<AdminUserItem[]> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString();
  return apiRequest<AdminUserItem[]>({ method: "GET", path: suffix ? `/admin/users?${suffix}` : "/admin/users", token: getToken() });
}

export async function updateAdminUserRole(userId: number, role: AdminUserItem["role"]): Promise<AdminUserItem> {
  return apiRequest<AdminUserItem>({
    method: "PATCH",
    path: `/admin/users/${userId}/role`,
    token: getToken(),
    body: { role },
  });
}
