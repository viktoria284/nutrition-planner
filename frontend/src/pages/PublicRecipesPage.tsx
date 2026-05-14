import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { listRecipes, resolveRecipeImageSrc, type MealType, type RecipeRead } from "../api/recipes";
import { Alert } from "../components/Alert";
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

function formatMetric(value: string | number): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

export function PublicRecipesPage() {
  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [query, setQuery] = useState("");
  const [selectedMealTypes, setSelectedMealTypes] = useState<MealType[]>([]);
  const [cookTimeFilter, setCookTimeFilter] = useState<(typeof COOK_TIME_FILTER_OPTIONS)[number]["value"]>("any");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRecipes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const maxCookTime = cookTimeFilter === "any" ? undefined : Number(cookTimeFilter);
      const items = await listRecipes({
        includePublic: true,
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
  }, [cookTimeFilter]);

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
              disabled={!query.trim() && selectedMealTypes.length === 0 && cookTimeFilter === "any"}
            >
              Сбросить фильтр
            </button>
          </div>
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
                <Link to={`/recipes/${recipe.id}`} className="recipe-row-link">
                  <div className="recipe-row-top">
                    <div className="recipe-row-main">
                      <div className="recipe-row-cover">
                        {recipe.image_url ? (
                          <>
                            <img
                              src={resolveRecipeImageSrc(recipe.image_url) ?? undefined}
                              alt={`Фото блюда: ${recipe.name}`}
                              className="recipe-row-cover-image"
                              onError={(event) => {
                                event.currentTarget.style.display = "none";
                                const fallback = event.currentTarget.nextElementSibling as HTMLElement | null;
                                if (fallback) fallback.style.display = "grid";
                              }}
                            />
                            <div className="recipe-row-cover-fallback" style={{ display: "none" }} aria-hidden="true">
                              {recipe.name.slice(0, 1).toUpperCase()}
                            </div>
                          </>
                        ) : (
                          <div className="recipe-row-cover-fallback" aria-hidden="true">
                            {recipe.name.slice(0, 1).toUpperCase()}
                          </div>
                        )}
                      </div>
                      <div className="recipe-row-text">
                        <p className="recipe-row-title">{recipe.name}</p>
                        {recipe.description && <p className="recipe-row-description">{recipe.description}</p>}
                      </div>
                    </div>
                    <p className="recipe-row-servings">{recipe.servings_count} порц.</p>
                  </div>

                  <div className="recipe-row-meta">
                    {recipe.meal_types.map((mealType) => (
                      <span key={`${recipe.id}-${mealType}`} className="recipe-meal-badge">
                        {MEAL_TYPE_LABELS[mealType]}
                      </span>
                    ))}
                    {typeof recipe.cook_time_minutes === "number" && (
                      <span className="recipe-row-kcal">{recipe.cook_time_minutes} мин</span>
                    )}
                    <span className="recipe-row-kcal">{formatMetric(recipe.per_serving_kcal)} ккал/порц.</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
