import { API_URL, ApiError, apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type DecimalValue = string | number;
export type RecipeSource = "private" | "verified" | "community";
export type RecipeStatus = "draft" | "pending" | "approved" | "rejected";

export type RecipeCreate = {
  name: string;
  description?: string | null;
  instructions?: string | null;
  image_url?: string | null;
  servings_count: number;
  meal_types: MealType[];
  cook_time_minutes?: number | null;
};

export type RecipeUpdate = Partial<RecipeCreate>;

export type RecipeRead = {
  id: number;
  owner_user_id: number;
  name: string;
  description: string | null;
  instructions: string | null;
  image_url: string | null;
  servings_count: number;
  meal_types: MealType[];
  cook_time_minutes: number | null;
  source: RecipeSource;
  status: RecipeStatus;
  reports_count: number;
  is_listed: boolean;
  is_favorite: boolean;
  ingredients?: RecipeIngredientRead[];
  steps?: RecipeStepRead[];
  total_grams: DecimalValue;
  total_kcal: DecimalValue;
  total_protein: DecimalValue;
  total_fat: DecimalValue;
  total_carbs: DecimalValue;
  total_fiber: DecimalValue;
  per_serving_kcal: DecimalValue;
  per_serving_protein: DecimalValue;
  per_serving_fat: DecimalValue;
  per_serving_carbs: DecimalValue;
  per_serving_fiber: DecimalValue;
  created_at: string;
  updated_at: string;
};

export type RecipeStepRead = {
  id: number;
  recipe_id: number;
  position: number;
  text: string;
  note: string | null;
  image_url: string | null;
  created_at: string;
  updated_at: string;
};

export type RecipeStepInput = {
  id?: number;
  position?: number;
  text: string;
  note?: string | null;
};

export type RecipeIngredientCreate = {
  food_id: number;
  grams?: DecimalValue;
  serving_id?: number;
  multiplier?: DecimalValue;
};

export type RecipeIngredientUpdate = Partial<RecipeIngredientCreate>;

export type RecipeIngredientRead = {
  id: number;
  recipe_id: number;
  food_id: number;
  grams: DecimalValue;
  serving_id?: number | null;
  multiplier?: DecimalValue | null;
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

export type RecipeNoteRead = {
  note: string | null;
};

export type ListRecipesOptions = {
  includePublic?: boolean;
  favoriteOnly?: boolean;
  mealType?: MealType;
  minCookTimeMinutes?: number;
  maxCookTimeMinutes?: number;
  limit?: number;
  offset?: number;
};

export type RecipeFavoriteState = {
  recipe_id: number;
  is_favorite: boolean;
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
      normalized.description = description || null;
    }
  }

  if (Object.prototype.hasOwnProperty.call(normalized, "instructions")) {
    if (typeof normalized.instructions === "string") {
      const instructions = normalized.instructions.trim();
      normalized.instructions = instructions || null;
    }
  }

  if (Object.prototype.hasOwnProperty.call(normalized, "image_url")) {
    if (typeof normalized.image_url === "string") {
      const imageUrl = normalized.image_url.trim();
      normalized.image_url = imageUrl || null;
    }
  }

  if (Array.isArray(normalized.meal_types)) {
    normalized.meal_types = normalizeMealTypes(normalized.meal_types);
  }

  if (Object.prototype.hasOwnProperty.call(normalized, "cook_time_minutes")) {
    const value = normalized.cook_time_minutes;
    if (value === null || value === undefined) {
      normalized.cook_time_minutes = undefined;
    }
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

export async function listRecipes(options: ListRecipesOptions = {}): Promise<RecipeRead[]> {
  const params = new URLSearchParams();
  if (options.includePublic) {
    params.set("include_public", "true");
  }
  if (options.mealType) {
    params.set("meal_type", options.mealType);
  }
  if (options.favoriteOnly) {
    params.set("favorite_only", "true");
  }
  if (typeof options.minCookTimeMinutes === "number") {
    params.set("min_cook_time_minutes", String(options.minCookTimeMinutes));
  }
  if (typeof options.maxCookTimeMinutes === "number") {
    params.set("max_cook_time_minutes", String(options.maxCookTimeMinutes));
  }
  if (typeof options.limit === "number") {
    params.set("limit", String(options.limit));
  }
  if (typeof options.offset === "number") {
    params.set("offset", String(options.offset));
  }
  const suffix = params.toString();
  return requestWithApiError(
    apiRequest<RecipeRead[]>({
      method: "GET",
      path: suffix ? `/recipes?${suffix}` : "/recipes",
      token: getToken(),
    }),
  );
}

export async function listPublicRecipes(): Promise<RecipeRead[]> {
  const items = await listRecipes({ includePublic: true, limit: 500 });
  return items.filter(
    (recipe) => recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
}

export async function listPublicRecipesFiltered(options: {
  mealType?: MealType;
  maxCookTimeMinutes?: number;
} = {}): Promise<RecipeRead[]> {
  const items = await listRecipes({
    includePublic: true,
    mealType: options.mealType,
    maxCookTimeMinutes: options.maxCookTimeMinutes,
    limit: 500,
  });
  return items.filter(
    (recipe) => recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
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

export async function addRecipeFavorite(id: number | string): Promise<RecipeFavoriteState> {
  return requestWithApiError(
    apiRequest<RecipeFavoriteState>({
      method: "POST",
      path: `/recipes/${id}/favorite`,
      token: getToken(),
    }),
  );
}

export async function removeRecipeFavorite(id: number | string): Promise<RecipeFavoriteState> {
  return requestWithApiError(
    apiRequest<RecipeFavoriteState>({
      method: "DELETE",
      path: `/recipes/${id}/favorite`,
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

export async function getRecipeNote(recipeId: number | string): Promise<RecipeNoteRead> {
  return requestWithApiError(
    apiRequest<RecipeNoteRead>({
      method: "GET",
      path: `/recipes/${recipeId}/note`,
      token: getToken(),
    }),
  );
}

export async function upsertRecipeNote(recipeId: number | string, note: string): Promise<RecipeNoteRead> {
  return requestWithApiError(
    apiRequest<RecipeNoteRead>({
      method: "PUT",
      path: `/recipes/${recipeId}/note`,
      token: getToken(),
      body: { note },
    }),
  );
}

export async function deleteRecipeNote(recipeId: number | string): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/recipes/${recipeId}/note`,
      token: getToken(),
    }),
  );
}

export async function copyRecipe(recipeId: number | string): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: `/recipes/${recipeId}/copy`,
      token: getToken(),
    }),
  );
}

export async function uploadRecipeCoverImage(recipeId: number | string, file: File): Promise<RecipeRead> {
  const formData = new FormData();
  formData.append("file", file);
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "POST",
      path: `/recipes/${recipeId}/cover-image`,
      token: getToken(),
      rawBody: formData,
    }),
  );
}

export async function deleteRecipeCoverImage(recipeId: number | string): Promise<RecipeRead> {
  return requestWithApiError(
    apiRequest<RecipeRead>({
      method: "DELETE",
      path: `/recipes/${recipeId}/cover-image`,
      token: getToken(),
    }),
  );
}

export async function getRecipeSteps(recipeId: number | string): Promise<RecipeStepRead[]> {
  return requestWithApiError(
    apiRequest<RecipeStepRead[]>({
      method: "GET",
      path: `/recipes/${recipeId}/steps`,
      token: getToken(),
    }),
  );
}

export async function replaceRecipeSteps(
  recipeId: number | string,
  steps: RecipeStepInput[],
): Promise<RecipeStepRead[]> {
  return requestWithApiError(
    apiRequest<RecipeStepRead[]>({
      method: "PUT",
      path: `/recipes/${recipeId}/steps`,
      token: getToken(),
      body: { steps },
    }),
  );
}

export async function uploadRecipeStepImage(
  recipeId: number | string,
  stepId: number | string,
  file: File,
): Promise<RecipeStepRead> {
  const formData = new FormData();
  formData.append("file", file);
  return requestWithApiError(
    apiRequest<RecipeStepRead>({
      method: "POST",
      path: `/recipes/${recipeId}/steps/${stepId}/image`,
      token: getToken(),
      rawBody: formData,
    }),
  );
}

export async function deleteRecipeStepImage(
  recipeId: number | string,
  stepId: number | string,
): Promise<RecipeStepRead> {
  return requestWithApiError(
    apiRequest<RecipeStepRead>({
      method: "DELETE",
      path: `/recipes/${recipeId}/steps/${stepId}/image`,
      token: getToken(),
    }),
  );
}

export function resolveRecipeImageSrc(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/")) return `${API_URL}${url}`;
  return `${API_URL}/${url}`;
}
