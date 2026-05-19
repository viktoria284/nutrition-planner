import { apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type User = {
  id: number | string;
  email: string;
  username: string;
  display_name?: string | null;
  is_active: boolean;
  role: "user" | "admin";
  created_at?: string;
};

export type TokenResponse = { access_token: string; token_type: string; };

export type RegisterRequest = {
  email: string;
  username: string;
  password: string;
  display_name?: string | null;
};

export type UpdateMeRequest = {
  email?: string;
  username?: string;
};

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

export async function register(req: RegisterRequest): Promise<User> {
  return apiRequest<User>({ method: "POST", path: "/auth/register", body: req });
}

export async function login(identifier: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.set("username", identifier);
  form.set("password", password);
  form.set("grant_type", "password");

  return apiRequest<TokenResponse>({
    method: "POST",
    path: "/auth/login",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    rawBody: form.toString(),
  });
}

export async function me(token: string): Promise<User> {
  return apiRequest<User>({ method: "GET", path: "/auth/me", token });
}

export async function updateMe(req: UpdateMeRequest): Promise<User> {
  return apiRequest<User>({ method: "PATCH", path: "/auth/me", body: req, token: localStorage.getItem(TOKEN_KEY) });
}

export async function changePassword(req: ChangePasswordRequest): Promise<void> {
  await apiRequest<string>({
    method: "PATCH",
    path: "/auth/me/password",
    body: req,
    token: localStorage.getItem(TOKEN_KEY),
  });
}
