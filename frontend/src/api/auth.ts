import { apiRequest } from "./http";

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
