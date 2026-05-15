import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  addRecipeFavorite,
  listRecipes,
  removeRecipeFavorite,
  type MealType,
  type RecipeRead,
} from "../api/recipes";
import { Alert } from "../components/Alert";
import { RecipeGridCard } from "../components/recipes/RecipeGridCard";
import "./RecipesPage.css";

const MEAL_TYPE_OPTIONS: Array<{ value: MealType; label: string }> = [
  { value: "breakfast", label: "Завтрак" },
  { value: "lunch", label: "Обед" },
  { value: "dinner", label: "Ужин" },
  { value: "snack", label: "Перекус" },
];

const MEAL_TYPE_LABELS: Record<MealType, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  dinner: "Ужин",
  snack: "Перекус",
};

const COOK_TIME_FILTER_OPTIONS = [
  { value: "any", label: "Любое" },
  { value: "15", label: "До 15 мин" },
  { value: "30", label: "До 30 мин" },
  { value: "45", label: "До 45 мин" },
  { value: "60", label: "До 60 мин" },
] as const;

function resolvePublicRecipesError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно войти в систему.";
    if (err.status === 404) return "Публичные рецепты не найдены.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить публичные рецепты.";
}

export function PublicRecipesPage() {
  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [query, setQuery] = useState("");
  const [selectedMealTypes, setSelectedMealTypes] = useState<MealType[]>([]);
  const [cookTimeFilter, setCookTimeFilter] = useState<(typeof COOK_TIME_FILTER_OPTIONS)[number]["value"]>("any");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [favoriteUpdatingIds, setFavoriteUpdatingIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const loadRecipes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const maxCookTime = cookTimeFilter === "any" ? undefined : Number(cookTimeFilter);
      const items = await listRecipes({
        includePublic: true,
        favoriteOnly,
        maxCookTimeMinutes: Number.isFinite(maxCookTime) ? maxCookTime : undefined,
        limit: 500,
      });
      setRecipes(
        items.filter((recipe) => recipe.source === "community" && recipe.status === "approved" && recipe.is_listed),
      );
    } catch (err) {
      setRecipes([]);
      setError(resolvePublicRecipesError(err));
    } finally {
      setLoading(false);
    }
  }, [cookTimeFilter, favoriteOnly]);

  useEffect(() => {
    void loadRecipes();
  }, [loadRecipes]);

  const filteredRecipes = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return recipes.filter((recipe) => {
      const matchesQuery = !normalized || recipe.name.toLowerCase().includes(normalized);
      const matchesMealTypes =
        selectedMealTypes.length === 0 ||
        recipe.meal_types.some((mealType) => selectedMealTypes.includes(mealType));
      return matchesQuery && matchesMealTypes;
    });
  }, [query, recipes, selectedMealTypes]);

  const toggleMealFilter = (mealType: MealType) => {
    setSelectedMealTypes((prev) =>
      prev.includes(mealType) ? prev.filter((item) => item !== mealType) : [...prev, mealType],
    );
  };

  const resetFilters = () => {
    setQuery("");
    setSelectedMealTypes([]);
    setCookTimeFilter("any");
    setFavoriteOnly(false);
  };

  const toggleRecipeFavorite = async (recipe: RecipeRead) => {
    if (favoriteUpdatingIds.has(recipe.id)) return;
    const nextFavorite = !recipe.is_favorite;
    setFavoriteUpdatingIds((prev) => new Set(prev).add(recipe.id));
    setRecipes((prev) =>
      prev.map((item) => (item.id === recipe.id ? { ...item, is_favorite: nextFavorite } : item)),
    );
    try {
      if (nextFavorite) {
        await addRecipeFavorite(recipe.id);
      } else {
        await removeRecipeFavorite(recipe.id);
      }
      if (!nextFavorite && favoriteOnly) {
        setRecipes((prev) => prev.filter((item) => item.id !== recipe.id));
      }
    } catch (err) {
      setRecipes((prev) =>
        prev.map((item) => (item.id === recipe.id ? { ...item, is_favorite: recipe.is_favorite } : item)),
      );
      setError(resolvePublicRecipesError(err));
    } finally {
      setFavoriteUpdatingIds((prev) => {
        const next = new Set(prev);
        next.delete(recipe.id);
        return next;
      });
    }
  };

  const isEmpty = !loading && !error && recipes.length === 0;
  const isFilterEmpty = !loading && !error && recipes.length > 0 && filteredRecipes.length === 0;

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">Публичные рецепты</h1>
            <p className="recipes-subtitle">Публичный каталог для просмотра и использования в автоплане.</p>
          </div>

          <div className="recipes-head-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipes()} disabled={loading}>
              Обновить
            </button>
            <Link to="/recipes" className="btn btn-secondary">
              Мои рецепты
            </Link>
          </div>
        </header>

        <section className="recipes-filter-card" aria-label="Поиск публичных рецептов">
          <p className="recipes-filter-group-label">Поиск по названию</p>
          <input
            className="recipes-field-input"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Например, Овсянка"
          />
          <p className="recipes-filter-group-label">Тип приёма пищи</p>
          <div className="recipes-filter-items">
            {MEAL_TYPE_OPTIONS.map((item) => {
              const checked = selectedMealTypes.includes(item.value);
              return (
                <label
                  key={item.value}
                  className={`recipes-filter-chip ${checked ? "is-active" : ""}`}
                  htmlFor={`public-filter-${item.value}`}
                >
                  <input
                    id={`public-filter-${item.value}`}
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleMealFilter(item.value)}
                  />
                  {item.label}
                </label>
              );
            })}
          </div>
          <div className="recipes-field" aria-label="Фильтр по времени приготовления">
            <span className="recipes-filter-group-label">Время приготовления</span>
            <div className="recipes-filter-items">
              {COOK_TIME_FILTER_OPTIONS.map((option) => {
                const isActive = cookTimeFilter === option.value;
                return (
                  <button
                    key={`public-cook-time-${option.value}`}
                    type="button"
                    className={`recipes-filter-chip recipes-filter-chip-button ${isActive ? "is-active" : ""}`}
                    aria-pressed={isActive}
                    onClick={() => setCookTimeFilter(option.value)}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={resetFilters}
              disabled={!query.trim() && selectedMealTypes.length === 0 && cookTimeFilter === "any" && !favoriteOnly}
            >
              Сбросить фильтр
            </button>
          </div>
          <label className={`recipes-filter-chip ${favoriteOnly ? "is-active" : ""}`} htmlFor="filter-favorite-only-public">
            <input
              id="filter-favorite-only-public"
              type="checkbox"
              checked={favoriteOnly}
              onChange={(event) => setFavoriteOnly(event.target.checked)}
            />
            Только избранные
          </label>
        </section>

        {loading && <p className="recipes-note">Загрузка...</p>}

        {!loading && error && (
          <div className="recipes-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipes()}>
              Повторить
            </button>
          </div>
        )}

        {isEmpty && (
          <article className="recipes-empty-card">
            <p className="recipes-empty-title">Публичные рецепты пока недоступны</p>
            <p className="recipes-empty-subtitle">Попробуйте обновить список позже.</p>
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipes()}>
              Обновить
            </button>
          </article>
        )}

        {isFilterEmpty && (
          <article className="recipes-empty-card">
            <p className="recipes-empty-title">По выбранным параметрам ничего не найдено</p>
            <p className="recipes-empty-subtitle">Измените поиск или фильтр по типу приёма пищи.</p>
            <button type="button" className="btn btn-secondary" onClick={resetFilters}>
              Сбросить фильтр
            </button>
          </article>
        )}

        {!loading && !error && filteredRecipes.length > 0 && (
          <ul className="recipes-list">
            {filteredRecipes.map((recipe) => (
              <li key={recipe.id}>
                <RecipeGridCard
                  recipe={recipe}
                  mealTypeLabels={MEAL_TYPE_LABELS}
                  favoriteUpdating={favoriteUpdatingIds.has(recipe.id)}
                  onToggleFavorite={(item) => {
                    void toggleRecipeFavorite(item);
                  }}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
