import { apiRequest } from "./http";

const TOKEN_KEY = "access_token";

export type FavoriteAuthor = {
  id: number;
  username: string;
  public_recipes_count: number;
  is_favorite: boolean;
};

export async function favoriteAuthor(authorId: number): Promise<{ author_id: number; is_favorite: boolean }> {
  return apiRequest<{ author_id: number; is_favorite: boolean }>({
    method: "POST",
    path: `/users/${authorId}/favorite-author`,
    token: localStorage.getItem(TOKEN_KEY),
  });
}

export async function unfavoriteAuthor(authorId: number): Promise<{ author_id: number; is_favorite: boolean }> {
  return apiRequest<{ author_id: number; is_favorite: boolean }>({
    method: "DELETE",
    path: `/users/${authorId}/favorite-author`,
    token: localStorage.getItem(TOKEN_KEY),
  });
}

export async function listFavoriteAuthors(): Promise<FavoriteAuthor[]> {
  return apiRequest<FavoriteAuthor[]>({
    method: "GET",
    path: "/users/favorite-authors",
    token: localStorage.getItem(TOKEN_KEY),
  });
}
