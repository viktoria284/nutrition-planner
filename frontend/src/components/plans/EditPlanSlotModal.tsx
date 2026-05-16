import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/http";
import {
  clearPlanSlotIngredientOverrides,
  getPlanSlotIngredients,
  replacePlanSlot,
  replacePlanSlotIngredientOverrides,
  updatePlanSlot,
} from "../../api/plans";
import type { FoodItem } from "../../api/foods";
import { getRecipe, resolveRecipeImageSrc, type RecipeIngredientRead, type RecipeRead } from "../../api/recipes";
import { FormErrorSummary } from "../FormErrorSummary";
import type {
  PlanSlotEffectiveIngredientsResponse,
  PlanSlotIngredientOverridesReplacePayload,
} from "../../types/plan";
import type { PlanSlot } from "../../types/plan";
import { formatDecimal } from "../../pages/plans";
import { FoodSearchSelect, type FoodSearchOption } from "../FoodSearchSelect";
import { PlanConfirmModal } from "./PlanConfirmModal";
import { RecipeSearchSelect, type RecipePickerOption } from "./RecipeSearchSelect";

type EditPlanSlotModalProps = {
  isOpen: boolean;
  planId: number | null;
  slot: PlanSlot | null;
  recipes: RecipeRead[];
  recipeNamesById: Record<number, string>;
  recipesLoading: boolean;
  recipesError: string | null;
  replacementHistory: number[];
  onRememberReplacementRecipe: (slotId: number, recipeId: number) => void;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

type EditableBaseIngredient = {
  recipeIngredientId: number;
  defaultFoodId: number;
  defaultFoodName: string;
  defaultGrams: string;
  food: FoodSearchOption;
  grams: string;
  isExcluded: boolean;
};

type EditableManualIngredient = {
  key: string;
  food: FoodSearchOption | null;
  grams: string;
};

let manualIngredientCounter = 0;

function toFriendlySaveError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Слот или рецепт не найден. Обновите страницу и попробуйте снова.";
    if (err.status === 422) return "Проверьте значения полей. Множитель должен быть больше нуля.";
    if (err.status === 409) return "Конфликт сохранения. Обновите страницу и повторите попытку.";
    if (err.status === 401) return "Сессия истекла. Войдите снова.";
  }
  return err instanceof Error ? err.message : "Не удалось сохранить слот.";
}

function toFriendlyReplaceError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно войти в систему.";
    if (err.status === 404) return "План или слот не найден.";
    if (err.status === 422) return "Других подходящих вариантов для этого слота не найдено.";
  }
  return "Не удалось подобрать замену для этого слота.";
}

function toFriendlyIngredientsError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Не удалось загрузить ингредиенты слота.";
    if (err.status === 422) return "Сначала выберите рецепт для этого слота.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить ингредиенты слота.";
}

function toFriendlyResetError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Не удалось найти слот или ингредиенты для сброса.";
    if (err.status === 422) return "Сброс недоступен для слота без выбранного рецепта.";
    if (err.status === 401) return "Сессия истекла. Войдите снова.";
  }
  return err instanceof Error ? err.message : "Не удалось сбросить изменения ингредиентов.";
}

function normalizeMultiplier(raw: string): { value: string | null; error?: string } {
  const normalized = raw.trim().replace(",", ".");
  if (!normalized) {
    return { value: null, error: "Укажите множитель порции." };
  }

  const numeric = Number(normalized);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return { value: null, error: "Множитель должен быть больше 0." };
  }

  return { value: normalized };
}

function normalizePositiveDecimal(raw: string, errorMessage: string): { value: string | null; error?: string } {
  const normalized = raw.trim().replace(",", ".");
  if (!normalized) return { value: null, error: errorMessage };
  const numeric = Number(normalized);
  if (!Number.isFinite(numeric) || numeric <= 0) return { value: null, error: errorMessage };
  return { value: normalized };
}

function normalizeDecimalToNumber(value: string): number {
  const numeric = Number(value.replace(",", "."));
  return Number.isFinite(numeric) ? numeric : 0;
}

function computeDefaultSlotIngredientGrams(
  ingredient: RecipeIngredientRead,
  recipeServingsCount: number,
  slotMultiplier: number,
): string {
  const grams = (Number(ingredient.grams) / recipeServingsCount) * slotMultiplier;
  return formatDecimal(grams);
}

function makeManualKey() {
  manualIngredientCounter += 1;
  return `manual_${manualIngredientCounter}`;
}

function areCloseNumbers(left: number, right: number): boolean {
  return Math.abs(left - right) < 0.005;
}

function buildOverridePayload(
  baseIngredients: EditableBaseIngredient[],
  manualIngredients: EditableManualIngredient[],
): { payload: PlanSlotIngredientOverridesReplacePayload | null; errors: string[] } {
  const errors: string[] = [];
  const base_overrides: NonNullable<PlanSlotIngredientOverridesReplacePayload["base_overrides"]> = [];
  const manual_items: NonNullable<PlanSlotIngredientOverridesReplacePayload["manual_items"]> = [];

  for (const row of baseIngredients) {
    if (row.isExcluded) {
      base_overrides.push({ recipe_ingredient_id: row.recipeIngredientId, is_excluded: true });
      continue;
    }

    const gramsParsed = normalizePositiveDecimal(row.grams, `Проверьте количество для ингредиента «${row.food.name}».`);
    if (!gramsParsed.value) {
      errors.push(gramsParsed.error ?? "Проверьте количество ингредиента.");
      continue;
    }

    const currentGrams = normalizeDecimalToNumber(gramsParsed.value);
    const defaultGrams = normalizeDecimalToNumber(row.defaultGrams);
    const foodChanged = row.food.id !== row.defaultFoodId;
    const gramsChanged = !areCloseNumbers(currentGrams, defaultGrams);

    if (!foodChanged && !gramsChanged) continue;

    base_overrides.push({
      recipe_ingredient_id: row.recipeIngredientId,
      ...(foodChanged ? { food_id: row.food.id } : {}),
      ...(gramsChanged ? { grams: gramsParsed.value } : {}),
      is_excluded: false,
    });
  }

  for (const row of manualIngredients) {
    if (!row.food) {
      errors.push("Выберите продукт для добавленного ингредиента.");
      continue;
    }
    const gramsParsed = normalizePositiveDecimal(row.grams, `Проверьте количество для ингредиента «${row.food.name}».`);
    if (!gramsParsed.value) {
      errors.push(gramsParsed.error ?? "Проверьте количество добавленного ингредиента.");
      continue;
    }

    manual_items.push({
      food_id: row.food.id,
      grams: gramsParsed.value,
    });
  }

  if (errors.length > 0) {
    return { payload: null, errors };
  }

  return {
    payload: {
      base_overrides,
      manual_items,
    },
    errors: [],
  };
}

function buildEditableIngredientsState(
  recipe: RecipeRead,
  slotMultiplier: string,
  response: PlanSlotEffectiveIngredientsResponse,
): {
  base: EditableBaseIngredient[];
  manual: EditableManualIngredient[];
} {
  const effectiveByRecipeIngredientId = new Map<number, { food_id: number; food_name: string; grams: string }>();
  for (const item of response.items) {
    if (item.recipe_ingredient_id === null) continue;
    effectiveByRecipeIngredientId.set(item.recipe_ingredient_id, {
      food_id: item.food_id,
      food_name: item.food_name,
      grams: String(item.grams),
    });
  }

  const excludedIds = new Set(response.excluded_recipe_ingredient_ids);
  const slotMultiplierNumber = Number(slotMultiplier.replace(",", "."));
  const safeMultiplier = Number.isFinite(slotMultiplierNumber) && slotMultiplierNumber > 0 ? slotMultiplierNumber : 1;

  const base = [...(recipe.ingredients ?? [])]
    .sort((left, right) => left.id - right.id)
    .map((ingredient) => {
      const defaultGrams = computeDefaultSlotIngredientGrams(ingredient, recipe.servings_count, safeMultiplier);
      const effective = effectiveByRecipeIngredientId.get(ingredient.id);
      const ingredientFood = ingredient.food;
      const defaultFoodId = ingredientFood?.id ?? ingredient.food_id;
      const defaultFoodName = ingredientFood?.name ?? "Продукт";

      const resolvedFoodId = effective?.food_id ?? defaultFoodId;
      const resolvedFoodName = effective?.food_name ?? defaultFoodName;

      return {
        recipeIngredientId: ingredient.id,
        defaultFoodId,
        defaultFoodName,
        defaultGrams,
        food: {
          id: resolvedFoodId,
          name: resolvedFoodName,
          brand: null,
        },
        grams: effective?.grams ?? defaultGrams,
        isExcluded: excludedIds.has(ingredient.id),
      } satisfies EditableBaseIngredient;
    });

  const manual = response.items
    .filter((item) => item.source === "manual")
    .map((item) => ({
      key: makeManualKey(),
      food: {
        id: item.food_id,
        name: item.food_name,
        brand: null,
      },
      grams: String(item.grams),
    }));

  return { base, manual };
}

export function EditPlanSlotModal({
  isOpen,
  planId,
  slot,
  recipes,
  recipeNamesById,
  recipesLoading,
  recipesError,
  replacementHistory,
  onRememberReplacementRecipe,
  onClose,
  onSaved,
}: EditPlanSlotModalProps) {
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | null>(null);
  const [multiplier, setMultiplier] = useState("1");
  const [pinned, setPinned] = useState(false);
  const [busyAction, setBusyAction] = useState<"save" | "clear" | "replace" | "reset" | null>(null);
  const [formErrors, setFormErrors] = useState<string[]>([]);
  const [previewRecipe, setPreviewRecipe] = useState<RecipeRead | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewImageBroken, setPreviewImageBroken] = useState(false);
  const [ingredientsLoading, setIngredientsLoading] = useState(false);
  const [ingredientsError, setIngredientsError] = useState<string | null>(null);
  const [ingredientsResponse, setIngredientsResponse] = useState<PlanSlotEffectiveIngredientsResponse | null>(null);
  const [baseIngredients, setBaseIngredients] = useState<EditableBaseIngredient[]>([]);
  const [manualIngredients, setManualIngredients] = useState<EditableManualIngredient[]>([]);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const isBusy = busyAction !== null;

  const originalRecipeId = slot?.recipe_id ?? null;
  const canEditCurrentSlotIngredients =
    isOpen && slot !== null && selectedRecipeId !== null && originalRecipeId !== null && selectedRecipeId === originalRecipeId;

  useEffect(() => {
    if (!isOpen || !slot) return;
    setSelectedRecipeId(slot.recipe_id);
    setMultiplier(slot.recipe_id === null ? "1" : formatDecimal(slot.servings_multiplier));
    setPinned(slot.pinned);
    setFormErrors([]);
    setBusyAction(null);
    setPreviewImageBroken(false);
    setIngredientsLoading(false);
    setIngredientsError(null);
    setIngredientsResponse(null);
    setBaseIngredients([]);
    setManualIngredients([]);
    setResetConfirmOpen(false);
  }, [isOpen, slot]);

  useEffect(() => {
    if (!isOpen || selectedRecipeId === null) {
      setPreviewRecipe(null);
      setPreviewError(null);
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewImageBroken(false);

    void getRecipe(selectedRecipeId)
      .then((payload) => {
        if (cancelled) return;
        setPreviewRecipe(payload);
      })
      .catch((err) => {
        if (cancelled) return;
        setPreviewRecipe(null);
        setPreviewError(toFriendlySaveError(err));
      })
      .finally(() => {
        if (cancelled) return;
        setPreviewLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, selectedRecipeId]);

  useEffect(() => {
    if (!canEditCurrentSlotIngredients || !slot || planId === null || !previewRecipe) {
      setIngredientsLoading(false);
      setIngredientsError(null);
      setIngredientsResponse(null);
      setBaseIngredients([]);
      setManualIngredients([]);
      return;
    }

    let cancelled = false;
    setIngredientsLoading(true);
    setIngredientsError(null);

    void getPlanSlotIngredients(planId, slot.id)
      .then((response) => {
        if (cancelled) return;
        setIngredientsResponse(response);
        const prepared = buildEditableIngredientsState(previewRecipe, String(slot.servings_multiplier), response);
        setBaseIngredients(prepared.base);
        setManualIngredients(prepared.manual);
      })
      .catch((err) => {
        if (cancelled) return;
        setIngredientsResponse(null);
        setBaseIngredients([]);
        setManualIngredients([]);
        setIngredientsError(toFriendlyIngredientsError(err));
      })
      .finally(() => {
        if (cancelled) return;
        setIngredientsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [canEditCurrentSlotIngredients, slot, planId, previewRecipe]);

  const recipeOptions = useMemo<RecipePickerOption[]>(() => {
    const options: RecipePickerOption[] = recipes.map((recipe) => ({
      id: recipe.id,
      name: recipe.name,
      meal_types: recipe.meal_types,
      servings_count: recipe.servings_count,
      per_serving_kcal: recipe.per_serving_kcal,
      source: recipe.source,
    }));

    if (slot?.recipe_id !== null && slot?.recipe_id !== undefined) {
      const exists = options.some((option) => option.id === slot.recipe_id);
      if (!exists) {
        options.push({
          id: slot.recipe_id,
          name: recipeNamesById[slot.recipe_id] ?? "Рецепт недоступен",
        });
      }
    }

    const sourceRank: Record<NonNullable<RecipePickerOption["source"]>, number> = {
      private: 0,
      verified: 1,
      community: 2,
    };

    return [...options].sort((left, right) => {
      const leftRank = left.source ? sourceRank[left.source] ?? 99 : 99;
      const rightRank = right.source ? sourceRank[right.source] ?? 99 : 99;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.name.localeCompare(right.name, "ru");
    });
  }, [recipeNamesById, recipes, slot?.recipe_id]);

  const currentOverridesState = useMemo(() => {
    const built = buildOverridePayload(baseIngredients, manualIngredients);
    if (built.errors.length > 0 || !built.payload) {
      return { hasOverrides: false, payload: null as PlanSlotIngredientOverridesReplacePayload | null };
    }
    const hasOverrides = (built.payload.base_overrides?.length ?? 0) > 0 || (built.payload.manual_items?.length ?? 0) > 0;
    return { hasOverrides, payload: built.payload };
  }, [baseIngredients, manualIngredients]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!slot || planId === null) return;

    const normalizedMultiplier = normalizeMultiplier(multiplier);
    if (!normalizedMultiplier.value) {
      setFormErrors([normalizedMultiplier.error ?? "Проверьте форму."]);
      return;
    }

    const nextErrors: string[] = [];
    let overridesPayload: PlanSlotIngredientOverridesReplacePayload | null = null;

    const willSaveOverrides = canEditCurrentSlotIngredients && ingredientsResponse !== null;
    if (willSaveOverrides) {
      const built = buildOverridePayload(baseIngredients, manualIngredients);
      if (built.errors.length > 0 || !built.payload) {
        nextErrors.push(...built.errors);
      } else {
        overridesPayload = built.payload;
      }
    }

    if (nextErrors.length > 0) {
      setFormErrors(nextErrors);
      return;
    }

    setBusyAction("save");
    setFormErrors([]);

    try {
      await updatePlanSlot(planId, slot.id, {
        recipe_id: selectedRecipeId,
        servings_multiplier: normalizedMultiplier.value,
        pinned,
      });

      if (willSaveOverrides && selectedRecipeId === originalRecipeId && overridesPayload) {
        await replacePlanSlotIngredientOverrides(planId, slot.id, overridesPayload);
      }

      await onSaved();
      onClose();
    } catch (err) {
      setFormErrors([toFriendlySaveError(err)]);
    } finally {
      setBusyAction(null);
    }
  };

  const onClearRecipe = async () => {
    if (!slot || planId === null) return;

    setBusyAction("clear");
    setFormErrors([]);
    try {
      await updatePlanSlot(planId, slot.id, { recipe_id: null });
      await onSaved();
      onClose();
    } catch (err) {
      setFormErrors([toFriendlySaveError(err)]);
    } finally {
      setBusyAction(null);
    }
  };

  const onReplaceRecipe = async () => {
    if (!slot || planId === null) return;

    setBusyAction("replace");
    setFormErrors([]);
    try {
      const excludedRecipeIdsSet = new Set<number>(replacementHistory);
      if (slot.recipe_id !== null) {
        excludedRecipeIdsSet.add(slot.recipe_id);
        onRememberReplacementRecipe(slot.id, slot.recipe_id);
      }

      const updatedPlan = await replacePlanSlot(planId, slot.id, {
        use_public_recipes: true,
        excluded_recipe_ids: Array.from(excludedRecipeIdsSet),
      });
      const replacedSlot = updatedPlan.slots.find((value) => value.id === slot.id) ?? null;
      if (replacedSlot && replacedSlot.recipe_id !== null) {
        onRememberReplacementRecipe(slot.id, replacedSlot.recipe_id);
      }
      await onSaved();
      onClose();
    } catch (err) {
      setFormErrors([toFriendlyReplaceError(err)]);
    } finally {
      setBusyAction(null);
    }
  };

  const onResetIngredientsConfirm = async () => {
    if (!slot || !previewRecipe || !ingredientsResponse || !canEditCurrentSlotIngredients || planId === null) {
      setResetConfirmOpen(false);
      return;
    }

    const hasPersistedOverrides = ingredientsResponse.has_overrides;
    setBusyAction("reset");
    setFormErrors([]);

    try {
      if (hasPersistedOverrides) {
        const cleared = await clearPlanSlotIngredientOverrides(planId, slot.id);
        setIngredientsResponse(cleared);
        const prepared = buildEditableIngredientsState(previewRecipe, String(slot.servings_multiplier), cleared);
        setBaseIngredients(prepared.base);
        setManualIngredients(prepared.manual);
        await onSaved();
      } else {
        const prepared = buildEditableIngredientsState(previewRecipe, String(slot.servings_multiplier), ingredientsResponse);
        setBaseIngredients(prepared.base);
        setManualIngredients(prepared.manual);
      }
      setResetConfirmOpen(false);
    } catch (err) {
      setFormErrors([toFriendlyResetError(err)]);
    } finally {
      setBusyAction(null);
    }
  };

  if (!isOpen || !slot) return null;

  const multiplierNumeric = Number(multiplier.replace(",", "."));
  const normalizedMultiplier = Number.isFinite(multiplierNumeric) && multiplierNumeric > 0 ? multiplierNumeric : 1;
  const previewIngredients = (previewRecipe?.ingredients ?? []).slice(0, 5);
  const previewIngredientsHiddenCount = Math.max(0, (previewRecipe?.ingredients?.length ?? 0) - previewIngredients.length);

  const showRecipeChangeHint = selectedRecipeId !== null && originalRecipeId !== null && selectedRecipeId !== originalRecipeId;
  const canShowIngredientSection = selectedRecipeId !== null;

  return (
    <>
      <div
        className="plans-modal-backdrop"
        role="presentation"
        onClick={(event) => {
          if (isBusy) return;
          if (event.target === event.currentTarget) onClose();
        }}
      >
        <div className="plans-modal plans-modal-slot" role="dialog" aria-modal="true" aria-labelledby="edit-slot-modal-title">
          <header className="plans-modal-head">
            <div className="plans-modal-head-row">
              <h2 id="edit-slot-modal-title" className="plans-modal-title">
                Редактировать слот
              </h2>
              <button
                type="button"
                className="icon-button icon-button--secondary plans-modal-close-btn"
                aria-label="Закрыть"
                onClick={onClose}
                disabled={isBusy}
              >
                ×
              </button>
            </div>
            <p className="plans-modal-subtitle">День: {slot.day_date} · Слот: {slot.slot_index + 1}</p>
          </header>

          <form className="plans-modal-form" onSubmit={onSubmit} noValidate>
            <FormErrorSummary messages={formErrors} className="plans-form-summary form-error-summary" itemClassName="plans-form-error-item" />

            <label className="plans-field">
              <span className="plans-field-label">Рецепт</span>
              <RecipeSearchSelect
                valueId={selectedRecipeId}
                options={recipeOptions}
                loading={recipesLoading}
                error={recipesError}
                disabled={isBusy}
                onChange={setSelectedRecipeId}
              />
            </label>

            {selectedRecipeId !== null && (
              <section className="plan-slot-preview" aria-label="Текущий рецепт в слоте">
                <div className="plan-slot-preview-head">
                  <div className="plan-slot-preview-cover">
                    {previewRecipe?.image_url && !previewImageBroken ? (
                      <img
                        src={resolveRecipeImageSrc(previewRecipe.image_url) ?? undefined}
                        alt={`Фото блюда: ${previewRecipe.name}`}
                        className="plan-slot-preview-cover-image"
                        onError={() => setPreviewImageBroken(true)}
                      />
                    ) : (
                      <div className="plan-slot-preview-cover-fallback" aria-hidden="true">
                        {(previewRecipe?.name ?? recipeNamesById[selectedRecipeId] ?? "Р").slice(0, 1).toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div className="plan-slot-preview-main">
                    <Link className="plan-slot-preview-title-link" to={`/recipes/${selectedRecipeId}`}>
                      {previewRecipe?.name ?? recipeNamesById[selectedRecipeId] ?? "Рецепт"}
                    </Link>
                    {typeof previewRecipe?.cook_time_minutes === "number" && (
                      <p className="plan-slot-preview-meta">Время приготовления: {previewRecipe.cook_time_minutes} мин</p>
                    )}
                  </div>
                </div>

                {previewLoading && <p className="plans-note">Загружаем краткий состав...</p>}
                {previewError && !previewLoading && <p className="plans-field-error">{previewError}</p>}
                {!previewLoading && !previewError && previewIngredients.length > 0 && (
                  <ul className="plan-slot-preview-ingredients">
                    {previewIngredients.map((ingredient) => (
                      <li key={ingredient.id} className="plan-slot-preview-ingredient-row">
                        <span>{ingredient.food?.name ?? "Продукт"}</span>
                        <b>{formatDecimal((Number(ingredient.grams) / (previewRecipe?.servings_count ?? 1)) * normalizedMultiplier)} г</b>
                      </li>
                    ))}
                  </ul>
                )}
                {!previewLoading && !previewError && previewIngredientsHiddenCount > 0 && (
                  <p className="plans-note">и ещё {previewIngredientsHiddenCount}</p>
                )}
              </section>
            )}

            {!canShowIngredientSection && (
              <p className="plans-note">Выберите рецепт, чтобы настроить ингредиенты.</p>
            )}

            {canShowIngredientSection && (
              <section className="plan-slot-ingredients-card" aria-label="Ингредиенты в этом слоте">
                <div className="plan-slot-ingredients-head">
                  <h3 className="plan-slot-ingredients-title">Ингредиенты в этом слоте</h3>
                  {(ingredientsResponse?.has_overrides || currentOverridesState.hasOverrides) && (
                    <span className="plan-slot-ingredients-badge">Ингредиенты изменены</span>
                  )}
                </div>
                <p className="plans-field-hint">
                  Изменения применяются только к этому слоту и не меняют исходный рецепт.
                </p>

                {showRecipeChangeHint && (
                  <p className="plans-inline-hint">
                    При смене рецепта изменения ингредиентов будут сброшены после сохранения.
                  </p>
                )}

                {!showRecipeChangeHint && selectedRecipeId !== originalRecipeId && (
                  <p className="plans-note">Сохраните рецепт в слоте, чтобы настроить ингредиенты.</p>
                )}

                {selectedRecipeId !== null && originalRecipeId === null && (
                  <p className="plans-note">Сохраните рецепт, чтобы настроить ингредиенты в этом слоте.</p>
                )}

                {canEditCurrentSlotIngredients && ingredientsLoading && <p className="plans-note">Загружаем ингредиенты слота...</p>}
                {canEditCurrentSlotIngredients && ingredientsError && <p className="plans-field-error">{ingredientsError}</p>}

                {canEditCurrentSlotIngredients && !ingredientsLoading && !ingredientsError && (
                  <div className="plan-slot-ingredients-grid">
                    {baseIngredients.map((item) => (
                      <div key={item.recipeIngredientId} className={`plan-slot-ingredient-row ${item.isExcluded ? "is-excluded" : ""}`}>
                        <div className="plan-slot-ingredient-main">
                          <FoodSearchSelect
                            value={item.food}
                            onChange={(food: FoodItem | null) => {
                              if (!food) return;
                              setBaseIngredients((prev) =>
                                prev.map((row) =>
                                  row.recipeIngredientId === item.recipeIngredientId
                                    ? {
                                        ...row,
                                        food: {
                                          id: food.id,
                                          name: food.name,
                                          brand: food.brand ?? null,
                                        },
                                      }
                                    : row,
                                ),
                              );
                            }}
                            disabled={isBusy || item.isExcluded}
                            placeholder="Заменить продукт"
                          />
                        </div>
                        <div className="plan-slot-ingredient-grams-wrap">
                          <input
                            className="plans-field-input"
                            type="text"
                            inputMode="decimal"
                            value={item.grams}
                            onChange={(event) => {
                              const next = event.target.value;
                              setBaseIngredients((prev) =>
                                prev.map((row) =>
                                  row.recipeIngredientId === item.recipeIngredientId
                                    ? {
                                        ...row,
                                        grams: next,
                                      }
                                    : row,
                                ),
                              );
                            }}
                            disabled={isBusy || item.isExcluded}
                            placeholder="г"
                          />
                        </div>
                        <div className="plan-slot-ingredient-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setBaseIngredients((prev) =>
                                prev.map((row) =>
                                  row.recipeIngredientId === item.recipeIngredientId
                                    ? {
                                        ...row,
                                        isExcluded: !row.isExcluded,
                                      }
                                    : row,
                                ),
                              );
                            }}
                            disabled={isBusy}
                          >
                            {item.isExcluded ? "Вернуть" : "Убрать"}
                          </button>
                          {!item.isExcluded && item.food.id !== item.defaultFoodId && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setBaseIngredients((prev) =>
                                  prev.map((row) =>
                                    row.recipeIngredientId === item.recipeIngredientId
                                      ? {
                                          ...row,
                                          food: {
                                            id: row.defaultFoodId,
                                            name: row.defaultFoodName,
                                            brand: null,
                                          },
                                        }
                                      : row,
                                  ),
                                );
                              }}
                              disabled={isBusy}
                            >
                              Сбросить продукт
                            </button>
                          )}
                        </div>
                      </div>
                    ))}

                    {manualIngredients.map((item) => (
                      <div key={item.key} className="plan-slot-ingredient-row plan-slot-ingredient-row-manual">
                        <div className="plan-slot-ingredient-main">
                          <FoodSearchSelect
                            value={item.food}
                            onChange={(food: FoodItem | null) => {
                              setManualIngredients((prev) =>
                                prev.map((row) =>
                                  row.key === item.key
                                    ? {
                                        ...row,
                                        food: food
                                          ? {
                                              id: food.id,
                                              name: food.name,
                                              brand: food.brand ?? null,
                                            }
                                          : null,
                                      }
                                    : row,
                                ),
                              );
                            }}
                            disabled={isBusy}
                            placeholder="Выберите продукт"
                          />
                        </div>
                        <div className="plan-slot-ingredient-grams-wrap">
                          <input
                            className="plans-field-input"
                            type="text"
                            inputMode="decimal"
                            value={item.grams}
                            onChange={(event) => {
                              const next = event.target.value;
                              setManualIngredients((prev) =>
                                prev.map((row) =>
                                  row.key === item.key
                                    ? {
                                        ...row,
                                        grams: next,
                                      }
                                    : row,
                                ),
                              );
                            }}
                            disabled={isBusy}
                            placeholder="г"
                          />
                        </div>
                        <div className="plan-slot-ingredient-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setManualIngredients((prev) => prev.filter((row) => row.key !== item.key));
                            }}
                            disabled={isBusy}
                          >
                            Удалить
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {canEditCurrentSlotIngredients && !ingredientsLoading && !ingredientsError && (
                  <div className="plan-slot-ingredients-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setManualIngredients((prev) => [
                          ...prev,
                          {
                            key: makeManualKey(),
                            food: null,
                            grams: "",
                          },
                        ]);
                      }}
                      disabled={isBusy}
                    >
                      Добавить ингредиент
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setResetConfirmOpen(true)}
                      disabled={isBusy || (!ingredientsResponse?.has_overrides && !currentOverridesState.hasOverrides)}
                    >
                      Сбросить изменения ингредиентов
                    </button>
                  </div>
                )}
              </section>
            )}

            <label className="plans-field" htmlFor="slot-multiplier">
              <span className="plans-field-label">Множитель порции</span>
              <input
                id="slot-multiplier"
                className="plans-field-input"
                type="text"
                inputMode="decimal"
                value={multiplier}
                onChange={(event) => setMultiplier(event.target.value)}
                placeholder="Например, 1.25"
                disabled={isBusy}
              />
            </label>

            <label className="plans-checkbox-row" htmlFor="slot-pinned">
              <input
                id="slot-pinned"
                type="checkbox"
                checked={pinned}
                onChange={(event) => setPinned(event.target.checked)}
                disabled={isBusy}
              />
              <span>Закрепить слот</span>
            </label>

            <div className="plans-modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => void onReplaceRecipe()}
                disabled={isBusy}
              >
                {busyAction === "replace" ? "Подбираем..." : "Заменить"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void onClearRecipe()} disabled={isBusy || selectedRecipeId === null}>
                Снять рецепт
              </button>
              <button type="submit" className="btn btn-primary" disabled={isBusy}>
                {busyAction === "save" ? "Сохраняем..." : "Сохранить"}
              </button>
            </div>
          </form>
        </div>
      </div>

      <PlanConfirmModal
        open={resetConfirmOpen}
        title="Сбросить изменения ингредиентов?"
        message="Ингредиенты снова будут рассчитаны по исходному рецепту и множителю порции."
        confirmText="Сбросить"
        loading={busyAction === "reset"}
        loadingText="Сбрасываем..."
        onClose={() => setResetConfirmOpen(false)}
        onConfirm={() => void onResetIngredientsConfirm()}
      />
    </>
  );
}
