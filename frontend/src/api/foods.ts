import { apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type FoodSource = "private" | "verified" | "community";
export type FoodStatus = "draft" | "pending" | "approved" | "rejected";

export type FoodItem = {
  id: number;
  name: string;
  brand?: string | null;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
  source: FoodSource;
  status: FoodStatus;
  is_listed: boolean;
  owner_user_id?: number | null;
  created_at?: string;
  updated_at?: string;
};

export type FoodCreatePayload = {
  name: string;
  brand?: string | null;
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
};

export type FoodItemUpdatePayload = {
  name?: string;
  brand?: string | null;
  kcal?: number;
  protein?: number;
  fat?: number;
  carbs?: number;
};

export type FoodServing = {
  id: number;
  food_id: number;
  name: string;
  grams: number;
  created_at?: string;
  updated_at?: string;
};
export type FoodServingRead = FoodServing;

export type FoodServingCreatePayload = {
  name: string;
  grams: number;
};

export type FoodReportPayload = {
  reason?: string | null;
};

type FoodSearchParams = {
  q: string;
  limit?: number;
  offset?: number;
};

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export async function searchFoods(params: FoodSearchParams): Promise<FoodItem[]> {
  const query = new URLSearchParams();
  query.set("q", params.q);

  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));

  return apiRequest<FoodItem[]>({
    method: "GET",
    path: `/foods/search?${query.toString()}`,
    token: getToken(),
  });
}

export async function createFood(payload: FoodCreatePayload): Promise<FoodItem> {
  const normalizedBrand = typeof payload.brand === "string" ? payload.brand.trim() : payload.brand;
  const body: FoodCreatePayload = {
    name: payload.name,
    kcal: payload.kcal,
    protein: payload.protein,
    fat: payload.fat,
    carbs: payload.carbs,
    ...(normalizedBrand ? { brand: normalizedBrand } : {}),
  };

  return apiRequest<FoodItem>({
    method: "POST",
    path: "/foods",
    token: getToken(),
    body,
  });
}

export async function getFood(id: number | string): Promise<FoodItem> {
  return apiRequest<FoodItem>({
    method: "GET",
    path: `/foods/${id}`,
    token: getToken(),
  });
}

export async function updateFood(id: number | string, payload: FoodItemUpdatePayload): Promise<FoodItem> {
  const body: FoodItemUpdatePayload = { ...payload };

  if (Object.prototype.hasOwnProperty.call(body, "brand")) {
    const normalizedBrand = typeof body.brand === "string" ? body.brand.trim() : body.brand;
    body.brand = normalizedBrand || null;
  }

  return apiRequest<FoodItem>({
    method: "PATCH",
    path: `/foods/${id}`,
    token: getToken(),
    body,
  });
}

export async function deleteFood(id: number | string): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/foods/${id}`,
    token: getToken(),
  });
}

export async function publishFood(id: number): Promise<FoodItem> {
  return apiRequest<FoodItem>({
    method: "POST",
    path: `/foods/${id}/publish`,
    token: getToken(),
  });
}

export async function withdrawFood(id: number): Promise<FoodItem> {
  return apiRequest<FoodItem>({
    method: "POST",
    path: `/foods/${id}/withdraw`,
    token: getToken(),
  });
}

export async function listServings(foodId: number | string): Promise<FoodServing[]> {
  return apiRequest<FoodServing[]>({
    method: "GET",
    path: `/foods/${foodId}/servings`,
    token: getToken(),
  });
}

export async function getFoodServings(foodId: number | string): Promise<FoodServingRead[]> {
  return listServings(foodId);
}

export async function createServing(
  foodId: number | string,
  payload: FoodServingCreatePayload,
): Promise<FoodServing> {
  const body: FoodServingCreatePayload = {
    name: payload.name.trim(),
    grams: payload.grams,
  };

  return apiRequest<FoodServing>({
    method: "POST",
    path: `/foods/${foodId}/servings`,
    token: getToken(),
    body,
  });
}

export async function deleteServing(servingId: number | string): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/servings/${servingId}`,
    token: getToken(),
  });
}

export async function reportFood(
  foodId: number,
  payload?: FoodReportPayload,
): Promise<void | any> {
  const normalizedReason = typeof payload?.reason === "string" ? payload.reason.trim() : payload?.reason;
  const body: FoodReportPayload = normalizedReason ? { reason: normalizedReason } : {};

  return apiRequest<void | any>({
    method: "POST",
    path: `/foods/${foodId}/reports`,
    token: getToken(),
    body,
  });
}
