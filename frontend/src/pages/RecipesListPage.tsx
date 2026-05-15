import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
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

function resolveApiError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Не найдено или нет доступа";
    if (err.status === 409) return "Конфликт: действие уже выполнено или недопустимо в текущем состоянии";
    if (err.status === 422) return "Проверьте корректность полей";
    if (err.status === 400) return "Некорректный запрос";
  }
  return fallback;
}

type RecipesLocationState = {
  flashMessage?: string;
};

export function RecipesListPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [selectedMealTypes, setSelectedMealTypes] = useState<MealType[]>([]);
  const [cookTimeFilter, setCookTimeFilter] = useState<(typeof COOK_TIME_FILTER_OPTIONS)[number]["value"]>("any");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [favoriteUpdatingIds, setFavoriteUpdatingIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [flashMessage, setFlashMessage] = useState<string | null>(null);

  const loadRecipes = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const maxCookTime = cookTimeFilter === "any" ? undefined : Number(cookTimeFilter);
      const items = await listRecipes({
        maxCookTimeMinutes: Number.isFinite(maxCookTime) ? maxCookTime : undefined,
        favoriteOnly,
        limit: 500,
      });
      setRecipes(items);
    } catch (err) {
      setRecipes([]);
      setError(resolveApiError(err, "Не удалось загрузить рецепты."));
    } finally {
      setLoading(false);
    }
  }, [cookTimeFilter, favoriteOnly]);

  useEffect(() => {
    void loadRecipes();
  }, [loadRecipes]);

  useEffect(() => {
    const state = (location.state as RecipesLocationState | null) ?? null;
    if (!state?.flashMessage) return;

    setFlashMessage(state.flashMessage);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (!flashMessage) return undefined;

    const timeoutId = window.setTimeout(() => {
      setFlashMessage(null);
    }, 3000);

    return () => window.clearTimeout(timeoutId);
  }, [flashMessage]);

  const filteredRecipes = useMemo(() => {
    if (selectedMealTypes.length === 0) return recipes;
    return recipes.filter((recipe) => recipe.meal_types.some((type) => selectedMealTypes.includes(type)));
  }, [recipes, selectedMealTypes]);

  const toggleMealFilter = (mealType: MealType) => {
    setSelectedMealTypes((prev) =>
      prev.includes(mealType) ? prev.filter((item) => item !== mealType) : [...prev, mealType],
    );
  };

  const resetFilters = () => {
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
      setError(resolveApiError(err, "Не удалось обновить избранное."));
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
            <h1 className="recipes-title">Рецепты</h1>
            <p className="recipes-subtitle">Список ваших рецептов и быстрый переход к карточке.</p>
          </div>

          <div className="recipes-head-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipes()} disabled={loading}>
              Обновить
            </button>
            <Link to="/recipes/public" className="btn btn-secondary">
              Публичные рецепты
            </Link>
            <Link to="/recipes/new" className="btn btn-primary">
              Создать рецепт
            </Link>
          </div>
        </header>

        <section className="recipes-filter-card" aria-label="Фильтр по типу приёма пищи">
          <p className="recipes-filter-group-label">Тип приёма пищи</p>
          <div className="recipes-filter-items">
            {MEAL_TYPE_OPTIONS.map((item) => {
              const checked = selectedMealTypes.includes(item.value);
              return (
                <label
                  key={item.value}
                  className={`recipes-filter-chip ${checked ? "is-active" : ""}`}
                  htmlFor={`filter-${item.value}`}
                >
                  <input
                    id={`filter-${item.value}`}
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
                    key={`cook-time-${option.value}`}
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
              disabled={!selectedMealTypes.length && cookTimeFilter === "any" && !favoriteOnly}
            >
              Сбросить фильтр
            </button>
          </div>
          <label className={`recipes-filter-chip ${favoriteOnly ? "is-active" : ""}`} htmlFor="filter-favorite-only-my">
            <input
              id="filter-favorite-only-my"
              type="checkbox"
              checked={favoriteOnly}
              onChange={(event) => setFavoriteOnly(event.target.checked)}
            />
            Только избранные
          </label>
        </section>

        {flashMessage && <p className="recipes-inline-success">{flashMessage}</p>}

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
            <p className="recipes-empty-title">Рецептов пока нет</p>
            <p className="recipes-empty-subtitle">Создайте первый рецепт, чтобы увидеть его в списке.</p>
            <Link to="/recipes/new" className="btn btn-primary">
              Создать рецепт
            </Link>
          </article>
        )}

        {isFilterEmpty && (
          <article className="recipes-empty-card">
            <p className="recipes-empty-title">По выбранным фильтрам ничего не найдено</p>
            <p className="recipes-empty-subtitle">Сбросьте фильтр или выберите другой тип приёма пищи.</p>
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
