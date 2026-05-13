import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { getRecipe, updateRecipe, type MealType } from "../api/recipes";
import { Alert } from "../components/Alert";
import { FormErrorSummary } from "../components/FormErrorSummary";
import {
  RECIPE_MEAL_TYPE_OPTIONS,
  toRecipeFormState,
  type RecipeFormErrors,
  type RecipeFormState,
  validateRecipeForm,
} from "./recipeForm";
import "./RecipesPage.css";

export function RecipeEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [form, setForm] = useState<RecipeFormState | null>(null);
  const [errors, setErrors] = useState<RecipeFormErrors>({ form: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadRecipe = useCallback(async () => {
    const recipeId = Number(id);
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setForm(null);
      setLoading(false);
      setError("Некорректный идентификатор рецепта.");
      return;
    }

    setLoading(true);
    setError(null);
    setErrors({ form: [] });

    try {
      const recipe = await getRecipe(recipeId);
      setForm(toRecipeFormState(recipe));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить рецепт.");
      }
      setForm(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  const updateField = (field: keyof Omit<RecipeFormState, "meal_types">, value: string) => {
    setForm((prev) => (prev ? { ...prev, [field]: value } : prev));
    setErrors((prev) => ({ ...prev, [field]: undefined, form: [] }));
  };

  const toggleMealType = (mealType: MealType) => {
    setForm((prev) => {
      if (!prev) return prev;
      const meal_types = prev.meal_types.includes(mealType)
        ? prev.meal_types.filter((value) => value !== mealType)
        : [...prev.meal_types, mealType];

      return { ...prev, meal_types };
    });
    setErrors((prev) => ({ ...prev, meal_types: undefined, form: [] }));
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form) return;

    const recipeId = Number(id);
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setErrors({ form: ["Некорректный идентификатор рецепта."] });
      return;
    }

    const { errors: validationErrors, payload } = validateRecipeForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    setSubmitting(true);
    setErrors({ form: [] });

    try {
      await updateRecipe(recipeId, payload);
      navigate(`/recipes/${recipeId}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrors({ form: ["Этот рецепт нельзя редактировать (только private draft)."] });
      } else if (err instanceof ApiError && err.status === 404) {
        setErrors({ form: ["Рецепт не найден."] });
      } else {
        setErrors({ form: [err instanceof Error ? err.message : "Не удалось сохранить рецепт."] });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">Редактирование рецепта</h1>
            <p className="recipes-subtitle">Изменения сохраняются только для editable-рецептов.</p>
          </div>

          <div className="recipes-head-actions">
            <Link to={id ? `/recipes/${id}` : "/recipes"} className="btn btn-secondary">
              Назад
            </Link>
          </div>
        </header>

        {loading && <p className="recipes-note">Загрузка...</p>}

        {!loading && error && (
          <div className="recipes-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipe()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && !error && form && (
          <form className="recipes-form" onSubmit={onSubmit} noValidate>
            <FormErrorSummary
              messages={errors.form}
              className="form-error-summary recipes-form-summary"
              itemClassName="recipes-form-error-item"
            />

            <label className="recipes-field" htmlFor="recipe_name">
              <span className="recipes-field-label">Название</span>
              <input
                id="recipe_name"
                className={`recipes-field-input ${errors.name ? "is-invalid" : ""}`}
                type="text"
                value={form.name}
                onChange={(e) => updateField("name", e.target.value)}
                placeholder="Например, Омлет с овощами"
                autoFocus
                disabled={submitting}
              />
              <div className="recipes-field-error-slot" aria-live="polite">
                {errors.name && <p className="recipes-field-error">{errors.name}</p>}
              </div>
            </label>

            <label className="recipes-field" htmlFor="recipe_description">
              <span className="recipes-field-label">Описание (опционально)</span>
              <textarea
                id="recipe_description"
                className="recipes-field-textarea"
                value={form.description}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="Короткое описание рецепта"
                disabled={submitting}
              />
            </label>

            <label className="recipes-field" htmlFor="recipe_servings_count">
              <span className="recipes-field-label">Количество порций</span>
              <input
                id="recipe_servings_count"
                className={`recipes-field-input ${errors.servings_count ? "is-invalid" : ""}`}
                type="number"
                min={1}
                step={1}
                value={form.servings_count}
                onChange={(e) => updateField("servings_count", e.target.value)}
                disabled={submitting}
              />
              <div className="recipes-field-error-slot" aria-live="polite">
                {errors.servings_count && <p className="recipes-field-error">{errors.servings_count}</p>}
              </div>
            </label>

            <label className="recipes-field" htmlFor="recipe_cook_time_minutes">
              <span className="recipes-field-label">Время приготовления, мин</span>
              <input
                id="recipe_cook_time_minutes"
                className={`recipes-field-input ${errors.cook_time_minutes ? "is-invalid" : ""}`}
                type="number"
                min={1}
                max={1440}
                step={1}
                value={form.cook_time_minutes}
                onChange={(e) => updateField("cook_time_minutes", e.target.value)}
                placeholder="Например, 25"
                disabled={submitting}
              />
              <div className="recipes-field-error-slot" aria-live="polite">
                {errors.cook_time_minutes && <p className="recipes-field-error">{errors.cook_time_minutes}</p>}
              </div>
            </label>

            <div className="recipes-field">
              <span className="recipes-field-label">Тип приёма пищи</span>
              <div className="recipes-meal-grid">
                {RECIPE_MEAL_TYPE_OPTIONS.map((mealType) => {
                  const checked = form.meal_types.includes(mealType.value);
                  return (
                    <label
                      key={mealType.value}
                      htmlFor={`meal-type-${mealType.value}`}
                      className={`recipes-meal-checkbox ${checked ? "is-active" : ""}`}
                    >
                      <input
                        id={`meal-type-${mealType.value}`}
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleMealType(mealType.value)}
                        disabled={submitting}
                      />
                      {mealType.label}
                    </label>
                  );
                })}
              </div>
              <div className="recipes-field-error-slot" aria-live="polite">
                {errors.meal_types && <p className="recipes-field-error">{errors.meal_types}</p>}
              </div>
            </div>

            <div className="recipes-form-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => navigate(id ? `/recipes/${id}` : "/recipes")}
                disabled={submitting}
              >
                Отмена
              </button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "Сохраняем..." : "Сохранить"}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
