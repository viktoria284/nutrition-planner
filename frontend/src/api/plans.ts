import type { PlanCreatePayload, PlanListItem, PlanRead, PlanSlotPatchPayload } from "../types/plan";
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
    ...(title ? { title } : {}),
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
