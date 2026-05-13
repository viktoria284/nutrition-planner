import type {
  PlanAutogeneratePayload,
  PlanBulkDeletePayload,
  PlanBulkDeleteResponse,
  PlanCreatePayload,
  PlanListItem,
  PlanRegenerateDayPayload,
  PlanRead,
  PlanReplaceSlotPayload,
  PlanSlotPatchPayload,
} from "../types/plan";
import { ApiError, apiRequest } from "./http";

const TOKEN_KEY = "access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function normalizeCreatePayload(payload: PlanCreatePayload): PlanCreatePayload {
  const title = payload.title?.trim();
  return {
    start_date: payload.start_date,
    days_count: payload.days_count,
    meals_per_day: payload.meals_per_day,
    profile_id: payload.profile_id,
    ...(title ? { title } : {}),
  };
}

function normalizeAutogeneratePayload(payload: PlanAutogeneratePayload): PlanAutogeneratePayload {
  const title = payload.title?.trim();
  const normalizedBatchCookingEntries = Object.entries(payload.batch_cooking ?? {}).filter(
    ([, value]) => value === 1 || value === 2 || value === 3,
  );
  const normalizedBatchCooking =
    normalizedBatchCookingEntries.length > 0
      ? Object.fromEntries(normalizedBatchCookingEntries)
      : undefined;

  return {
    start_date: payload.start_date,
    days_count: payload.days_count,
    meals_per_day: payload.meals_per_day,
    ...(payload.profile_id ? { profile_id: payload.profile_id } : {}),
    ...(title ? { title } : {}),
    use_public_recipes: payload.use_public_recipes,
    excluded_recipe_ids: payload.excluded_recipe_ids ?? [],
    excluded_food_ids: payload.excluded_food_ids ?? [],
    ...(payload.max_cook_time_minutes ? { max_cook_time_minutes: payload.max_cook_time_minutes } : {}),
    ...(normalizedBatchCooking ? { batch_cooking: normalizedBatchCooking } : {}),
  };
}

function normalizeReplaceSlotPayload(payload: PlanReplaceSlotPayload): PlanReplaceSlotPayload {
  return {
    use_public_recipes: payload.use_public_recipes,
    excluded_recipe_ids: payload.excluded_recipe_ids ?? [],
    excluded_food_ids: payload.excluded_food_ids ?? [],
    avoid_current_recipe: payload.avoid_current_recipe ?? true,
    ...(payload.max_cook_time_minutes ? { max_cook_time_minutes: payload.max_cook_time_minutes } : {}),
  };
}

function normalizeRegenerateDayPayload(payload: PlanRegenerateDayPayload): PlanRegenerateDayPayload {
  return {
    use_public_recipes: payload.use_public_recipes,
    excluded_recipe_ids: payload.excluded_recipe_ids ?? [],
    excluded_food_ids: payload.excluded_food_ids ?? [],
    ...(payload.max_cook_time_minutes ? { max_cook_time_minutes: payload.max_cook_time_minutes } : {}),
  };
}

async function requestWithApiError<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, err instanceof Error ? err.message : "Не удалось выполнить запрос.", err);
  }
}

export async function listPlans(): Promise<PlanListItem[]> {
  return requestWithApiError(
    apiRequest<PlanListItem[]>({
      method: "GET",
      path: "/plans",
      token: getToken(),
    }),
  );
}

export async function createPlan(payload: PlanCreatePayload): Promise<PlanRead> {
  return requestWithApiError(
    apiRequest<PlanRead>({
      method: "POST",
      path: "/plans",
      token: getToken(),
      body: normalizeCreatePayload(payload),
    }),
  );
}

export async function autogeneratePlan(payload: PlanAutogeneratePayload): Promise<PlanRead> {
  return requestWithApiError(
    apiRequest<PlanRead>({
      method: "POST",
      path: "/plans/autogenerate",
      token: getToken(),
      body: normalizeAutogeneratePayload(payload),
    }),
  );
}

export async function getPlan(id: number | string): Promise<PlanRead> {
  return requestWithApiError(
    apiRequest<PlanRead>({
      method: "GET",
      path: `/plans/${id}`,
      token: getToken(),
    }),
  );
}

export async function deletePlan(id: number | string): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "DELETE",
      path: `/plans/${id}`,
      token: getToken(),
    }),
  );
}

export async function bulkDeletePlans(
  payload: PlanBulkDeletePayload,
): Promise<PlanBulkDeleteResponse> {
  return requestWithApiError(
    apiRequest<PlanBulkDeleteResponse>({
      method: "POST",
      path: "/plans/bulk-delete",
      token: getToken(),
      body: payload,
    }),
  );
}

export async function updatePlanSlot(
  planId: number | string,
  slotId: number | string,
  payload: PlanSlotPatchPayload,
): Promise<void> {
  await requestWithApiError(
    apiRequest<void>({
      method: "PATCH",
      path: `/plans/${planId}/slots/${slotId}`,
      token: getToken(),
      body: payload,
    }),
  );
}

export async function replacePlanSlot(
  planId: number | string,
  slotId: number | string,
  payload?: PlanReplaceSlotPayload,
): Promise<PlanRead> {
  const normalizedPayload = normalizeReplaceSlotPayload(payload ?? { use_public_recipes: true });
  return requestWithApiError(
    apiRequest<PlanRead>({
      method: "POST",
      path: `/plans/${planId}/slots/${slotId}/replace`,
      token: getToken(),
      body: normalizedPayload,
    }),
  );
}

export async function regeneratePlanDay(
  planId: number | string,
  dayDate: string,
  payload: PlanRegenerateDayPayload,
): Promise<PlanRead> {
  return requestWithApiError(
    apiRequest<PlanRead>({
      method: "POST",
      path: `/plans/${planId}/days/${dayDate}/regenerate`,
      token: getToken(),
      body: normalizeRegenerateDayPayload(payload),
    }),
  );
}
