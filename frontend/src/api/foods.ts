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
