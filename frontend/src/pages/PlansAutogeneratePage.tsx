import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { FoodItem } from "../api/foods";
import { ApiError } from "../api/http";
import { autogeneratePlan } from "../api/plans";
import { FoodSearchSelect, type FoodSearchOption } from "../components/FoodSearchSelect";
import { FormErrorSummary } from "../components/FormErrorSummary";
import { PlanProfileSelect } from "../components/plans/PlanProfileSelect";
import { useAutoSelectedProfileId } from "../components/plans/useAutoSelectedProfileId";
import { useProfiles } from "../context/ProfilesContext";
import type { PlanAutogeneratePayload } from "../types/plan";
import "./PlansPage.css";

type PlanAutogenerateFormState = {
  start_date: string;
  days_count: string;
  meals_per_day: string;
  profile_id: string;
  title: string;
  use_public_recipes: boolean;
  max_cook_time_minutes: string;
  batch_breakfast_days: string;
  batch_lunch_days: string;
  batch_dinner_days: string;
  batch_snack_days: string;
  favorite_recipes_mode: "none" | "prefer" | "only";
  excluded_food_ids: number[];
};

type PlanAutogenerateFormErrors = {
  start_date?: string;
  days_count?: string;
  meals_per_day?: string;
  profile_id?: string;
  max_cook_time_minutes?: string;
  form: string[];
};

const MEAL_TYPE_LABELS: Record<string, string> = {
  breakfast: "завтрак",
  lunch: "обед",
  dinner: "ужин",
  snack: "перекус",
};

const BATCH_OPTIONS: Array<{ value: 1 | 2 | 3; label: string }> = [
  { value: 1, label: "По возможности разные" },
  { value: 2, label: "Готовить на 2 дня" },
  { value: 3, label: "Готовить на 3 дня" },
];

function toTodayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function validateAutogenerateForm(form: PlanAutogenerateFormState): {
  payload: PlanAutogeneratePayload | null;
  errors: PlanAutogenerateFormErrors;
} {
  const errors: PlanAutogenerateFormErrors = { form: [] };

  const dateValue = form.start_date.trim();
  if (!dateValue) {
    errors.start_date = "Укажите дату старта.";
    errors.form.push("Укажите дату старта.");
  }

  const daysCount = Number(form.days_count);
  if (!Number.isInteger(daysCount) || daysCount < 1 || daysCount > 7) {
    errors.days_count = "Допустимо значение от 1 до 7.";
    errors.form.push("Количество дней должно быть от 1 до 7.");
  }

  const mealsPerDay = Number(form.meals_per_day);
  if (!Number.isInteger(mealsPerDay) || mealsPerDay < 2 || mealsPerDay > 6) {
    errors.meals_per_day = "Допустимо значение от 2 до 6.";
    errors.form.push("Слотов в день должно быть от 2 до 6.");
  }

  const profileId = Number(form.profile_id);
  if (!Number.isInteger(profileId) || profileId < 1) {
    errors.profile_id = "Выберите профиль питания.";
    errors.form.push("Нужно выбрать профиль для автоплана.");
  }

  const maxCookTimeRaw = form.max_cook_time_minutes.trim();
  let maxCookTime: number | null = null;
  if (maxCookTimeRaw) {
    const parsed = Number(maxCookTimeRaw);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 1440) {
      errors.max_cook_time_minutes = "Введите целое число от 1 до 1440.";
      errors.form.push("Максимальное время приготовления должно быть целым числом от 1 до 1440.");
    } else {
      maxCookTime = parsed;
    }
  }

  if (errors.form.length > 0) {
    return { payload: null, errors };
  }

  const batchCooking: Partial<Record<"breakfast" | "lunch" | "dinner" | "snack", 2 | 3>> = {};
  const batchBreakfastDays = Number(form.batch_breakfast_days);
  const batchLunchDays = Number(form.batch_lunch_days);
  const batchDinnerDays = Number(form.batch_dinner_days);
  const batchSnackDays = Number(form.batch_snack_days);
  if (batchBreakfastDays === 2 || batchBreakfastDays === 3) batchCooking.breakfast = batchBreakfastDays;
  if (batchLunchDays === 2 || batchLunchDays === 3) batchCooking.lunch = batchLunchDays;
  if (batchDinnerDays === 2 || batchDinnerDays === 3) batchCooking.dinner = batchDinnerDays;
  if (batchSnackDays === 2 || batchSnackDays === 3) batchCooking.snack = batchSnackDays;

  return {
    payload: {
      start_date: dateValue,
      days_count: daysCount,
      meals_per_day: mealsPerDay,
      profile_id: profileId,
      title: form.title.trim() || null,
      use_public_recipes: form.use_public_recipes,
      excluded_recipe_ids: [],
      excluded_food_ids: [...new Set(form.excluded_food_ids)],
      favorite_recipes_mode: form.favorite_recipes_mode,
      ...(maxCookTime !== null ? { max_cook_time_minutes: maxCookTime } : {}),
      ...(Object.keys(batchCooking).length > 0 ? { batch_cooking: batchCooking } : {}),
    },
    errors: { form: [] },
  };
}

function tryBuildNotEnoughRecipesHint(detail: string): string | null {
  const match = detail.match(/meal_type=([a-z_]+)\s+on\s+(\d{4}-\d{2}-\d{2})/i);
  if (!match) return null;

  const mealType = match[1].toLowerCase();
  const dayDate = match[2];
  const mealLabel = MEAL_TYPE_LABELS[mealType] ?? mealType;
  return `Не хватает рецептов для слота «${mealLabel}» на дату ${dayDate}.`;
}

function mapAutogenerateError(err: unknown): string[] {
    if (err instanceof ApiError) {
      if (err.status === 401) return ["Нужно войти в систему."];
      if (err.status === 404) return ["Выбранный профиль недоступен. Выберите другой профиль и попробуйте снова."];
      if (err.status === 422) {
        const detailRaw = typeof err.payload?.detail === "string" ? err.payload.detail.trim() : "";
        if (detailRaw.toLowerCase().includes("недостаточно быстрых рецептов")) {
          return [
            "Недостаточно быстрых рецептов для выбранных условий.",
            "Попробуйте увеличить время приготовления до 30 минут или выбрать приготовление обедов/ужинов на 2 дня.",
          ];
        }
        if (detailRaw.toLowerCase().includes("not enough recipes")) {
          const detailHint = tryBuildNotEnoughRecipesHint(detailRaw);
          return detailHint
            ? ["Недостаточно рецептов для выбранных параметров.", detailHint]
            : ["Недостаточно рецептов для выбранных параметров."];
        }
        if (detailRaw) return [detailRaw];
        return ["Проверьте параметры автоплана и повторите попытку."];
      }
    if (err.status === 0) return ["Не удалось сгенерировать план. Попробуйте ещё раз."];
    return ["Не удалось сгенерировать план. Попробуйте ещё раз."];
  }
  return ["Не удалось сгенерировать план. Попробуйте ещё раз."];
}

export function PlansAutogeneratePage() {
  const navigate = useNavigate();
  const { profiles, activeProfileId, loading: loadingProfiles, error: profilesError } = useProfiles();
  const initialDate = useMemo(() => toTodayIsoDate(), []);

  const [form, setForm] = useState<PlanAutogenerateFormState>({
    start_date: initialDate,
    days_count: "7",
    meals_per_day: "3",
    profile_id: activeProfileId ? String(activeProfileId) : "",
    title: "",
    use_public_recipes: true,
    max_cook_time_minutes: "",
    batch_breakfast_days: "1",
    batch_lunch_days: "1",
    batch_dinner_days: "1",
    batch_snack_days: "1",
    favorite_recipes_mode: "none",
    excluded_food_ids: [],
  });
  const [errors, setErrors] = useState<PlanAutogenerateFormErrors>({ form: [] });
  const [saving, setSaving] = useState(false);
  const [isMaxCookTimeTouchedManually, setIsMaxCookTimeTouchedManually] = useState(false);
  const [excludedFoods, setExcludedFoods] = useState<FoodSearchOption[]>([]);
  const [excludedFoodInputKey, setExcludedFoodInputKey] = useState(0);

  const selectedProfile = useMemo(() => {
    const profileId = Number(form.profile_id);
    if (!Number.isInteger(profileId) || profileId < 1) return null;
    return profiles.find((profile) => profile.id === profileId) ?? null;
  }, [form.profile_id, profiles]);

  const shouldShowHighCalorieHint = useMemo(() => {
    const mealsPerDay = Number(form.meals_per_day);
    if (!Number.isInteger(mealsPerDay) || mealsPerDay >= 5) return false;
    if (!selectedProfile) return false;
    const hasHighCalories = typeof selectedProfile.target_kcal === "number" && selectedProfile.target_kcal >= 3200;
    const hasHighCarbs = typeof selectedProfile.target_carbs === "number" && selectedProfile.target_carbs >= 450;
    return hasHighCalories || hasHighCarbs;
  }, [form.meals_per_day, selectedProfile]);

  const setAutoProfileId = useCallback((nextProfileId: string) => {
    setForm((prev) => {
      if (prev.profile_id === nextProfileId) return prev;
      return { ...prev, profile_id: nextProfileId };
    });
  }, []);

  useAutoSelectedProfileId({
    profiles,
    activeProfileId,
    currentProfileId: form.profile_id,
    setProfileId: setAutoProfileId,
  });

  useEffect(() => {
    if (isMaxCookTimeTouchedManually) return;
    const profileDefaultValue =
      selectedProfile && selectedProfile.max_cook_time_minutes !== null
        ? String(selectedProfile.max_cook_time_minutes)
        : "";

    setForm((prev) => {
      if (prev.max_cook_time_minutes === profileDefaultValue) return prev;
      return { ...prev, max_cook_time_minutes: profileDefaultValue };
    });
  }, [isMaxCookTimeTouchedManually, selectedProfile]);

  const updateTextField = (
    field:
      | "start_date"
      | "days_count"
      | "meals_per_day"
      | "profile_id"
      | "title"
      | "max_cook_time_minutes"
      | "batch_breakfast_days"
      | "batch_lunch_days"
      | "batch_dinner_days"
      | "batch_snack_days"
      | "favorite_recipes_mode",
    value: string,
  ) => {
    if (field === "max_cook_time_minutes") {
      setIsMaxCookTimeTouchedManually(true);
    }
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined, form: [] }));
  };

  const updateUsePublicRecipes = (value: boolean) => {
    setForm((prev) => ({ ...prev, use_public_recipes: value }));
    setErrors((prev) => ({ ...prev, form: [] }));
  };

  const onExcludedFoodSelected = (food: FoodItem | null) => {
    if (!food) return;

    setForm((prev) => {
      if (prev.excluded_food_ids.includes(food.id)) return prev;
      return { ...prev, excluded_food_ids: [...prev.excluded_food_ids, food.id] };
    });

    setExcludedFoods((prev) => {
      if (prev.some((item) => item.id === food.id)) return prev;
      return [...prev, { id: food.id, name: food.name, brand: food.brand ?? null }];
    });

    setExcludedFoodInputKey((prev) => prev + 1);
  };

  const removeExcludedFood = (foodId: number) => {
    setForm((prev) => ({
      ...prev,
      excluded_food_ids: prev.excluded_food_ids.filter((id) => id !== foodId),
    }));
    setExcludedFoods((prev) => prev.filter((food) => food.id !== foodId));
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const { payload, errors: validationErrors } = validateAutogenerateForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    setSaving(true);
    setErrors({ form: [] });
    try {
      const createdPlan = await autogeneratePlan(payload);
      navigate(`/plans/${createdPlan.id}`);
    } catch (err) {
      setErrors({ form: mapAutogenerateError(err) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="plans-page">
      <div className="plans-shell">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Автоплан</h1>
            <p className="plans-subtitle">Укажите параметры и получите заполненный план питания на несколько дней.</p>
          </div>
          <div className="plans-head-actions">
            <Link to="/plans" className="btn btn-secondary">
              К списку планов
            </Link>
          </div>
        </header>

        <form className="plans-form" onSubmit={onSubmit} noValidate>
          {errors.form.length > 0 && (
            <FormErrorSummary
              messages={errors.form}
              className="plans-form-summary form-error-summary"
              itemClassName="plans-form-error-item"
            />
          )}

          <label className="plans-field" htmlFor="autoplan-start-date">
            <span className="plans-field-label">Дата старта</span>
            <input
              id="autoplan-start-date"
              className={`plans-field-input ${errors.start_date ? "is-invalid" : ""}`}
              type="date"
              value={form.start_date}
              onChange={(event) => updateTextField("start_date", event.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.start_date && <p className="plans-field-error">{errors.start_date}</p>}
            </div>
          </label>

          <label className="plans-field" htmlFor="autoplan-days-count">
            <span className="plans-field-label">Количество дней (1–7)</span>
            <input
              id="autoplan-days-count"
              className={`plans-field-input ${errors.days_count ? "is-invalid" : ""}`}
              type="number"
              min={1}
              max={7}
              step={1}
              value={form.days_count}
              onChange={(event) => updateTextField("days_count", event.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.days_count && <p className="plans-field-error">{errors.days_count}</p>}
            </div>
          </label>

          <label className="plans-field" htmlFor="autoplan-meals-per-day">
            <span className="plans-field-label">Слотов в день (2–6)</span>
            <input
              id="autoplan-meals-per-day"
              className={`plans-field-input ${errors.meals_per_day ? "is-invalid" : ""}`}
              type="number"
              min={2}
              max={6}
              step={1}
              value={form.meals_per_day}
              onChange={(event) => updateTextField("meals_per_day", event.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.meals_per_day && <p className="plans-field-error">{errors.meals_per_day}</p>}
            </div>
          </label>

          <PlanProfileSelect
            id="autoplan-profile"
            profiles={profiles}
            value={form.profile_id}
            onChange={(value) => updateTextField("profile_id", value)}
            error={errors.profile_id}
            disabled={saving || loadingProfiles || profiles.length === 0}
            hint="План будет создан с целями выбранного профиля."
          />
          {selectedProfile?.target_fiber !== null && (
            <p className="plans-field-hint">
              Автоплан также учитывает цель по клетчатке, если она указана в профиле.
            </p>
          )}

          {!loadingProfiles && profiles.length === 0 && (
            <div className="plans-empty-card">
              <p className="plans-empty-title">Сначала создайте профиль питания.</p>
              <p className="plans-empty-subtitle">Без профиля невозможно создать автоплан.</p>
              <Link to="/profiles" className="btn btn-secondary">
                К профилям
              </Link>
            </div>
          )}

          {profilesError && <p className="plans-note">{profilesError}</p>}

          <label className="plans-field" htmlFor="autoplan-title">
            <span className="plans-field-label">Название плана</span>
            <input
              id="autoplan-title"
              className="plans-field-input"
              type="text"
              value={form.title}
              onChange={(event) => updateTextField("title", event.target.value)}
              placeholder="Например, Рацион на неделю"
              disabled={saving}
            />
            <p className="plans-field-hint">Если оставить пустым, название будет создано автоматически.</p>
          </label>

          <label className="plans-field" htmlFor="autoplan-max-cook-time">
            <span className="plans-field-label">Максимальное время приготовления, мин</span>
            <input
              id="autoplan-max-cook-time"
              className={`plans-field-input ${errors.max_cook_time_minutes ? "is-invalid" : ""}`}
              type="number"
              min={1}
              max={1440}
              step={1}
              value={form.max_cook_time_minutes}
              onChange={(event) => updateTextField("max_cook_time_minutes", event.target.value)}
              placeholder="Например, 45"
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.max_cook_time_minutes && <p className="plans-field-error">{errors.max_cook_time_minutes}</p>}
            </div>
            <p className="plans-field-hint">
              По умолчанию берётся из выбранного профиля. Здесь можно задать значение только для этой генерации.
            </p>
          </label>

          <label className="plans-checkbox-row" htmlFor="autoplan-use-public">
            <input
              id="autoplan-use-public"
              type="checkbox"
              checked={form.use_public_recipes}
              onChange={(event) => updateUsePublicRecipes(event.target.checked)}
              disabled={saving}
            />
            <span>Использовать публичные рецепты</span>
          </label>
          <p className="plans-field-hint">
            Если включено, автоплан сможет использовать ваши рецепты и публичные опубликованные рецепты.
          </p>

          <label className="plans-field" htmlFor="autoplan-favorite-mode">
            <span className="plans-field-label">Избранные рецепты</span>
            <select
              id="autoplan-favorite-mode"
              className="plans-field-input"
              value={form.favorite_recipes_mode}
              onChange={(event) => updateTextField("favorite_recipes_mode", event.target.value)}
              disabled={saving}
            >
              <option value="none">Не учитывать</option>
              <option value="prefer">Использовать в приоритете</option>
              <option value="only">Только избранные</option>
            </select>
            <p className="plans-field-hint">
              Приоритет избранных повышает вероятность выбора сохранённых рецептов, но не нарушает ограничения профиля.
            </p>
            {form.favorite_recipes_mode === "only" && (
              <p className="plans-field-hint">План будет составляться только из избранных доступных рецептов.</p>
            )}
          </label>

          <div className="plans-field">
            <span className="plans-field-label">Исключить продукты</span>
            <div className="plans-excluded-foods">
              <FoodSearchSelect
                key={excludedFoodInputKey}
                value={null}
                onChange={onExcludedFoodSelected}
                placeholder="Найдите продукт, который нужно исключить"
                disabled={saving}
              />
              {excludedFoods.length > 0 && (
                <ul className="plans-chip-list">
                  {excludedFoods.map((food) => (
                    <li key={food.id} className="plans-chip">
                      <span className="plans-chip-label">{food.brand ? `${food.name} — ${food.brand}` : food.name}</span>
                      <button
                        type="button"
                        className="plans-chip-remove"
                        onClick={() => removeExcludedFood(food.id)}
                        disabled={saving}
                        aria-label={`Удалить ${food.name} из исключений`}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="plans-field-hint">
              Выбранные продукты не будут использоваться при автогенерации.
            </p>
          </div>

          <details className="plans-advanced-card">
            <summary className="plans-advanced-summary">Приготовление на несколько дней</summary>
            <p className="plans-field-hint">
              Если выбрать приготовление на 2–3 дня, блюдо может повторяться несколько дней подряд — это считается запланированным повтором.
            </p>
            <div className="plans-batch-grid">
              <label className="plans-field" htmlFor="autoplan-batch-breakfast">
                <span className="plans-field-label">Завтрак</span>
                <select
                  id="autoplan-batch-breakfast"
                  className="plans-field-input"
                  value={form.batch_breakfast_days}
                  onChange={(event) => updateTextField("batch_breakfast_days", event.target.value)}
                  disabled={saving}
                >
                  {BATCH_OPTIONS.map((option) => (
                    <option key={`batch-breakfast-${option.value}`} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="plans-field" htmlFor="autoplan-batch-lunch">
                <span className="plans-field-label">Обед</span>
                <select
                  id="autoplan-batch-lunch"
                  className="plans-field-input"
                  value={form.batch_lunch_days}
                  onChange={(event) => updateTextField("batch_lunch_days", event.target.value)}
                  disabled={saving}
                >
                  {BATCH_OPTIONS.map((option) => (
                    <option key={`batch-lunch-${option.value}`} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="plans-field" htmlFor="autoplan-batch-dinner">
                <span className="plans-field-label">Ужин</span>
                <select
                  id="autoplan-batch-dinner"
                  className="plans-field-input"
                  value={form.batch_dinner_days}
                  onChange={(event) => updateTextField("batch_dinner_days", event.target.value)}
                  disabled={saving}
                >
                  {BATCH_OPTIONS.map((option) => (
                    <option key={`batch-dinner-${option.value}`} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="plans-field" htmlFor="autoplan-batch-snack">
                <span className="plans-field-label">Перекус</span>
                <select
                  id="autoplan-batch-snack"
                  className="plans-field-input"
                  value={form.batch_snack_days}
                  onChange={(event) => updateTextField("batch_snack_days", event.target.value)}
                  disabled={saving}
                >
                  {BATCH_OPTIONS.map((option) => (
                    <option key={`batch-snack-${option.value}`} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </details>

          {shouldShowHighCalorieHint && (
            <p className="plans-inline-hint">
              Для высокой калорийности и большого количества углеводов лучше выбрать 5–6 приёмов пищи.
            </p>
          )}

          <div className="plans-form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => navigate("/plans")} disabled={saving}>
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || loadingProfiles || profiles.length === 0}>
              {saving ? "Генерация..." : "Сгенерировать план"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
