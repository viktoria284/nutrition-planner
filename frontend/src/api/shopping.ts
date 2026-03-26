import type {
  ShoppingItemPatchPayload,
  ShoppingListRead,
  ShoppingManualItemCreatePayload,
  ShoppingManualItem,
} from "../types/shopping";
import { ApiError, apiRequest } from "./http";

const TOKEN_KEY = "access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

async function requestWithApiError<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, err instanceof Error ? err.message : "Не удалось выполнить запрос.", err);
  }
}

export async function getPlanShoppingList(planId: number | string): Promise<ShoppingListRead> {
  return requestWithApiError(
    apiRequest<ShoppingListRead>({
      method: "GET",
      path: `/plans/${planId}/shopping-list`,
      token: getToken(),
    }),
  );
}

export async function patchShoppingItem(
  planId: number | string,
  foodId: number | string,
  payload: ShoppingItemPatchPayload,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "PATCH",
      path: `/plans/${planId}/shopping-list/${foodId}`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function createManualShoppingItem(
  planId: number | string,
  payload: ShoppingManualItemCreatePayload,
): Promise<ShoppingManualItem> {
  return requestWithApiError(
    apiRequest<ShoppingManualItem>({
      method: "POST",
      path: `/plans/${planId}/shopping-list/manual`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function deleteManualShoppingItem(
  planId: number | string,
  manualItemId: number | string,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/plans/${planId}/shopping-list/manual/${manualItemId}`,
      token: getToken(),
    }),
  );
}
