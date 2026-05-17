import { apiRequest } from "./http";
import type { FoodCategory } from "../types/foodCategory";

const TOKEN_KEY = "access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export type PantryFood = {
  id: number;
  name: string;
  brand: string | null;
  category: FoodCategory;
};

export type PantryItem = {
  id: number;
  user_id: number;
  food_id: number;
  note: string | null;
  created_at: string;
  food: PantryFood;
};

export type PantryItemCreatePayload = {
  food_id: number;
  note?: string | null;
};

export async function listPantryItems(): Promise<PantryItem[]> {
  return apiRequest<PantryItem[]>({
    method: "GET",
    path: "/pantry",
    token: getToken(),
  });
}

export async function addPantryItem(payload: PantryItemCreatePayload): Promise<PantryItem> {
  return apiRequest<PantryItem>({
    method: "POST",
    path: "/pantry",
    token: getToken(),
    body: payload,
  });
}

export async function deletePantryItem(foodId: number | string): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/pantry/${foodId}`,
    token: getToken(),
  });
}
