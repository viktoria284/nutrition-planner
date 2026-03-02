import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createRecipe, type MealType } from "../api/recipes";
import { FormErrorSummary } from "../components/FormErrorSummary";
import {
  EMPTY_RECIPE_FORM,
  RECIPE_MEAL_TYPE_OPTIONS,
  type RecipeFormErrors,
  type RecipeFormState,
  validateRecipeForm,
} from "./recipeForm";
import "./RecipesPage.css";

export function RecipeCreatePage() {
  const navigate = useNavigate();

  const [form, setForm] = useState<RecipeFormState>(EMPTY_RECIPE_FORM);
  const [errors, setErrors] = useState<RecipeFormErrors>({ form: [] });
  const [submitting, setSubmitting] = useState(false);

  const updateField = (field: keyof Omit<RecipeFormState, "meal_types">, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined, form: [] }));
  };

  const toggleMealType = (mealType: MealType) => {
    setForm((prev) => {
      const meal_types = prev.meal_types.includes(mealType)
        ? prev.meal_types.filter((value) => value !== mealType)
        : [...prev.meal_types, mealType];

      return { ...prev, meal_types };
    });
    setErrors((prev) => ({ ...prev, meal_types: undefined, form: [] }));
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const { errors: validationErrors, payload } = validateRecipeForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    setSubmitting(true);
    setErrors({ form: [] });

    try {
      const created = await createRecipe(payload);
      navigate(`/recipes/${created.id}`, { replace: true });
    } catch (err) {
      setErrors({
        form: [err instanceof Error ? err.message : "Не удалось создать рецепт."],
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">Создание рецепта</h1>
            <p className="recipes-subtitle">Заполните базовые поля. Ингредиенты добавим на следующем шаге.</p>
          </div>

          <div className="recipes-head-actions">
            <Link to="/recipes" className="btn btn-secondary">
              К списку рецептов
            </Link>
          </div>
        </header>

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
            <button type="button" className="btn btn-secondary" onClick={() => navigate("/recipes")} disabled={submitting}>
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? "Создание..." : "Создать рецепт"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
