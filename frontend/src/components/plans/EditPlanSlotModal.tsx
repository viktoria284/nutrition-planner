import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiError } from "../../api/http";
import { updatePlanSlot } from "../../api/plans";
import type { RecipeRead } from "../../api/recipes";
import { FormErrorSummary } from "../FormErrorSummary";
import type { PlanSlot } from "../../types/plan";
import { formatDecimal } from "../../pages/plans";
import { RecipeSearchSelect, type RecipePickerOption } from "./RecipeSearchSelect";

type EditPlanSlotModalProps = {
  isOpen: boolean;
  planId: number | null;
  slot: PlanSlot | null;
  recipes: RecipeRead[];
  recipeNamesById: Record<number, string>;
  recipesLoading: boolean;
  recipesError: string | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

function toFriendlySaveError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Слот или рецепт не найден. Обновите страницу и попробуйте снова.";
    if (err.status === 422) return "Проверьте значения полей. Множитель должен быть больше нуля.";
    if (err.status === 409) return "Конфликт сохранения. Обновите страницу и повторите попытку.";
    if (err.status === 401) return "Сессия истекла. Войдите снова.";
  }
  return err instanceof Error ? err.message : "Не удалось сохранить слот.";
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

export function EditPlanSlotModal({
  isOpen,
  planId,
  slot,
  recipes,
  recipeNamesById,
  recipesLoading,
  recipesError,
  onClose,
  onSaved,
}: EditPlanSlotModalProps) {
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | null>(null);
  const [multiplier, setMultiplier] = useState("1");
  const [pinned, setPinned] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!isOpen || !slot) return;
    setSelectedRecipeId(slot.recipe_id);
    setMultiplier(slot.recipe_id === null ? "1" : formatDecimal(slot.servings_multiplier));
    setPinned(slot.pinned);
    setFormErrors([]);
    setSaving(false);
  }, [isOpen, slot]);

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
          name: recipeNamesById[slot.recipe_id] ?? `Рецепт #${slot.recipe_id}`,
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

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!slot || planId === null) return;

    const normalizedMultiplier = normalizeMultiplier(multiplier);
    if (!normalizedMultiplier.value) {
      setFormErrors([normalizedMultiplier.error ?? "Проверьте форму."]);
      return;
    }

    setSaving(true);
    setFormErrors([]);

    try {
      await updatePlanSlot(planId, slot.id, {
        recipe_id: selectedRecipeId,
        servings_multiplier: normalizedMultiplier.value,
        pinned,
      });
      await onSaved();
      onClose();
    } catch (err) {
      setFormErrors([toFriendlySaveError(err)]);
    } finally {
      setSaving(false);
    }
  };

  const onClearRecipe = async () => {
    if (!slot || planId === null) return;

    setSaving(true);
    setFormErrors([]);
    try {
      await updatePlanSlot(planId, slot.id, { recipe_id: null });
      await onSaved();
      onClose();
    } catch (err) {
      setFormErrors([toFriendlySaveError(err)]);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !slot) return null;

  return (
    <div
      className="plans-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (saving) return;
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="plans-modal" role="dialog" aria-modal="true" aria-labelledby="edit-slot-modal-title">
        <header className="plans-modal-head">
          <h2 id="edit-slot-modal-title" className="plans-modal-title">
            Редактировать слот
          </h2>
          <p className="plans-modal-subtitle">
            День: {slot.day_date} · Слот: {slot.slot_index + 1}
          </p>
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
              disabled={saving}
              onChange={setSelectedRecipeId}
            />
            <div className="plans-field-hint">
              Показываются ваши рецепты и публичные опубликованные рецепты.
            </div>
          </label>

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
              disabled={saving}
            />
          </label>

          <label className="plans-checkbox-row" htmlFor="slot-pinned">
            <input
              id="slot-pinned"
              type="checkbox"
              checked={pinned}
              onChange={(event) => setPinned(event.target.checked)}
              disabled={saving}
            />
            <span>Закрепить слот</span>
          </label>

          <div className="plans-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Отмена
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void onClearRecipe()} disabled={saving || selectedRecipeId === null}>
              Снять рецепт
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
