import type {
  ShoppingCreateFromPlanPayload,
  ShoppingItemPatchPayload,
  ShoppingListBulkDeletePayload,
  ShoppingListBulkDeleteResponse,
  ShoppingListMergePayload,
  ShoppingListRead,
  ShoppingListSummary,
  ShoppingManualItemCreatePayload,
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

export async function listShoppingLists(): Promise<ShoppingListSummary[]> {
  return requestWithApiError(
    apiRequest<ShoppingListSummary[]>({
      method: "GET",
      path: "/shopping-lists",
      token: getToken(),
    }),
  );
}

export async function createShoppingListFromPlan(payload: ShoppingCreateFromPlanPayload): Promise<ShoppingListRead> {
  return requestWithApiError(
    apiRequest<ShoppingListRead>({
      method: "POST",
      path: "/shopping-lists/from-plan",
      token: getToken(),
      body: payload,
    }),
  );
}

export async function getShoppingList(shoppingListId: number | string): Promise<ShoppingListRead> {
  return requestWithApiError(
    apiRequest<ShoppingListRead>({
      method: "GET",
      path: `/shopping-lists/${shoppingListId}`,
      token: getToken(),
    }),
  );
}

export async function deleteShoppingList(shoppingListId: number | string): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/shopping-lists/${shoppingListId}`,
      token: getToken(),
    }),
  );
}

export async function bulkDeleteShoppingLists(
  payload: ShoppingListBulkDeletePayload,
): Promise<ShoppingListBulkDeleteResponse> {
  return requestWithApiError(
    apiRequest<ShoppingListBulkDeleteResponse>({
      method: "POST",
      path: "/shopping-lists/bulk-delete",
      token: getToken(),
      body: payload,
    }),
  );
}

export async function mergeShoppingLists(payload: ShoppingListMergePayload): Promise<ShoppingListRead> {
  return requestWithApiError(
    apiRequest<ShoppingListRead>({
      method: "POST",
      path: "/shopping-lists/merge",
      token: getToken(),
      body: payload,
    }),
  );
}

export async function rebuildShoppingList(shoppingListId: number | string): Promise<ShoppingListRead> {
  return requestWithApiError(
    apiRequest<ShoppingListRead>({
      method: "POST",
      path: `/shopping-lists/${shoppingListId}/rebuild`,
      token: getToken(),
    }),
  );
}

export async function patchShoppingItem(
  shoppingListId: number | string,
  itemId: number | string,
  payload: ShoppingItemPatchPayload,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "PATCH",
      path: `/shopping-lists/${shoppingListId}/items/${itemId}`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function createManualShoppingItem(
  shoppingListId: number | string,
  payload: ShoppingManualItemCreatePayload,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "POST",
      path: `/shopping-lists/${shoppingListId}/items/manual`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function deleteShoppingListItem(
  shoppingListId: number | string,
  itemId: number | string,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/shopping-lists/${shoppingListId}/items/${itemId}`,
      token: getToken(),
    }),
  );
}
