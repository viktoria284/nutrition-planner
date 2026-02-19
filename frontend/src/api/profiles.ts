import { apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type Profile = {
  id: number;
  user_id: number;
  name: string;
  target_kcal: number | null;
  target_protein: number | null;
  target_fat: number | null;
  target_carbs: number | null;
};

export type ProfileUpdatePayload = {
  name?: string;
  target_kcal?: number | null;
  target_protein?: number | null;
  target_fat?: number | null;
  target_carbs?: number | null;
};

export type ProfileCreatePayload = {
  name: string;
  target_kcal?: number | null;
  target_protein?: number | null;
  target_fat?: number | null;
  target_carbs?: number | null;
};

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export async function getProfiles(): Promise<Profile[]> {
  return apiRequest<Profile[]>({ method: "GET", path: "/profiles", token: getToken() });
}

export async function updateProfile(id: number, payload: Partial<ProfileUpdatePayload>): Promise<Profile> {
  return apiRequest<Profile>({
    method: "PATCH",
    path: `/profiles/${id}`,
    token: getToken(),
    body: payload,
  });
}

export async function createProfile(payload: ProfileCreatePayload): Promise<Profile> {
  return apiRequest<Profile>({
    method: "POST",
    path: "/profiles",
    token: getToken(),
    body: payload,
  });
}

export async function deleteProfile(id: number): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/profiles/${id}`,
    token: getToken(),
  });
}
