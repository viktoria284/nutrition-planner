import { ApiError, apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type DecimalValue = string | number;
export type RecipeSource = "private" | "verified" | "community";
export type RecipeStatus = "draft" | "pending" | "approved" | "rejected";

export type RecipeCreate = {
  name: string;
  description?: string;
  servings_count: number;
  meal_types: MealType[];
};

export type RecipeUpdate = Partial<RecipeCreate>;

export type RecipeRead = {
  id: number;
  owner_user_id: number;
  name: string;
  description: string | null;
  servings_count: number;
  meal_types: MealType[];
  source: RecipeSource;
  status: RecipeStatus;
  reports_count: number;
  is_listed: boolean;
  ingredients?: RecipeIngredientRead[];
  total_grams: DecimalValue;
  total_kcal: DecimalValue;
  total_protein: DecimalValue;
  total_fat: DecimalValue;
  total_carbs: DecimalValue;
  per_serving_kcal: DecimalValue;
  per_serving_protein: DecimalValue;
  per_serving_fat: DecimalValue;
  per_serving_carbs: DecimalValue;
  created_at: string;
  updated_at: string;
};

export type RecipeIngredientCreate = {
  food_id: number;
  grams: DecimalValue;
};

export type RecipeIngredientUpdate = Partial<RecipeIngredientCreate>;

export type RecipeIngredientRead = {
  id: number;
  recipe_id: number;
  food_id: number;
  grams: DecimalValue;
  food?: {
    id: number;
    name: string;
    brand?: string | null;
  } | null;
  created_at: string;
  updated_at: string;
};

export type RecipeReportPayload = {
  reason: string;
  comment?: string | null;
};

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function normalizeMealTypes(values: MealType[]): MealType[] {
  return Array.from(new Set(values.map((value) => value.trim().toLowerCase() as MealType)));
}

function normalizeRecipePayload(payload: RecipeCreate | RecipeUpdate): RecipeCreate | RecipeUpdate {
  const normalized: RecipeCreate | RecipeUpdate = { ...payload };

  if (typeof normalized.name === "string") {
    normalized.name = normalized.name.trim();
  }

  if (Object.prototype.hasOwnProperty.call(normalized, "description")) {
    if (typeof normalized.description === "string") {
      const description = normalized.description.trim();
      normalized.description = description || undefined;
    }
  }

  if (Array.isArray(normalized.meal_types)) {
    normalized.meal_types = normalizeMealTypes(normalized.meal_types);
  }

  return normalized;
}

async function requestWithApiError<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, err instanceof Error ? err.message : "Не удалось выполнить запрос.", err);
  }
}

export async function listRecipes(): Promise<RecipeRead[]> {
  return requestWithApiError(
    apiRequest<RecipeRead[]>({
      method: "GET",
      path: "/recipes",
      token: getToken(),
    }),
  );
}

export async function createRecipe(payload: RecipeCreate): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: "/recipes",
      token: getToken(),
      body: normalizeRecipePayload(payload),
    }),
  );
}

export async function getRecipe(id: number | string): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "GET",
      path: `/recipes/${id}`,
      token: getToken(),
    }),
  );
}

export async function updateRecipe(id: number | string, payload: RecipeUpdate): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "PATCH",
      path: `/recipes/${id}`,
      token: getToken(),
      body: normalizeRecipePayload(payload),
    }),
  );
}

export async function deleteRecipe(id: number | string): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/recipes/${id}`,
      token: getToken(),
    }),
  );
}

export async function publishRecipe(id: number | string): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: `/recipes/${id}/publish`,
      token: getToken(),
    }),
  );
}

export async function withdrawRecipe(id: number | string): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: `/recipes/${id}/withdraw`,
      token: getToken(),
    }),
  );
}

export async function reportRecipe(id: number | string, payload: RecipeReportPayload): Promise<RecipeRead> {
  const reason = payload.reason.trim();
  const comment = typeof payload.comment === "string" ? payload.comment.trim() : payload.comment;

  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: `/recipes/${id}/report`,
      token: getToken(),
      body: {
        reason,
        ...(comment ? { comment } : {}),
      },
    }),
  );
}

export async function addIngredient(
  recipeId: number | string,
  payload: RecipeIngredientCreate,
): Promise<RecipeIngredientRead> {
  return requestWithApiError(
    apiRequest<RecipeIngredientRead>({
      method: "POST",
      path: `/recipes/${recipeId}/ingredients`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function updateIngredient(
  recipeId: number | string,
  ingId: number | string,
  payload: RecipeIngredientUpdate,
): Promise<RecipeIngredientRead> {
  return requestWithApiError(
    apiRequest<RecipeIngredientRead>({
      method: "PATCH",
      path: `/recipes/${recipeId}/ingredients/${ingId}`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function deleteIngredient(recipeId: number | string, ingId: number | string): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/recipes/${recipeId}/ingredients/${ingId}`,
      token: getToken(),
    }),
  );
}
