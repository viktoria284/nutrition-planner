import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addAdminRecipeIngredient,
  deleteAdminRecipeCoverImage,
  deleteAdminRecipeIngredient,
  deleteAdminRecipeStepImage,
  getAdminRecipe,
  replaceAdminRecipeSteps,
  updateAdminRecipe,
  updateAdminRecipeIngredient,
  uploadAdminRecipeCoverImage,
  uploadAdminRecipeStepImage,
} from "../api/admin";
import { getFoodServings, type FoodItem, type FoodServingRead } from "../api/foods";
import { ApiError } from "../api/http";
import {
  deleteRecipeCoverImage,
  deleteRecipeStepImage,
  getRecipe,
  replaceRecipeSteps,
  resolveRecipeImageSrc,
  updateRecipe,
  uploadRecipeCoverImage,
  uploadRecipeStepImage,
  type MealType,
  type RecipeIngredientRead,
  type RecipeIngredientUpdate,
  type RecipeStepInput,
  type RecipeStepRead,
  type RecipeRead,
} from "../api/recipes";
import { Alert } from "../components/Alert";
import { CustomSelect } from "../components/CustomSelect";
import { FoodSearchSelect, type FoodSearchOption } from "../components/FoodSearchSelect";
import { FormErrorSummary } from "../components/FormErrorSummary";
import { MarkdownTextarea } from "../components/MarkdownTextarea";
import { RecipePlaceholder } from "../components/recipes/RecipePlaceholder";
import { formatTrimmedNumber } from "../utils/numberFormat";
import {
  RECIPE_MEAL_TYPE_OPTIONS,
  toRecipeFormState,
  type RecipeFormErrors,
  type RecipeFormState,
  validateRecipeForm,
} from "./recipeForm";
import "./RecipesPage.css";

type StepDraft = {
  localId: string;
  id?: number;
  text: string;
  note: string;
  image_url: string | null;
};

type IngredientRowErrors = {
  food?: string;
  grams?: string;
  serving?: string;
  multiplier?: string;
};

type IngredientMode = "grams" | "serving";

type IngredientRow = {
  localId: string;
  id?: number;
  food_id?: number;
  food: FoodSearchOption | null;
  mode: IngredientMode;
  grams: string;
  serving_id?: number;
  multiplier: string;
  initialMode: IngredientMode;
  initialFoodId?: number;
  initialGrams?: number | null;
  initialServingId?: number | null;
  initialMultiplier?: number | null;
  markedForDelete?: boolean;
  errors?: IngredientRowErrors;
};

const RECIPE_LOCKED_EDIT_MESSAGE =
  "Опубликованный рецепт нельзя редактировать. Чтобы внести изменения, отзовите публикацию.";
const ADMIN_RECIPE_LOCKED_EDIT_MESSAGE = "Редактировать публичный рецепт может только администратор.";

let stepLocalCounter = 0;
let ingredientLocalCounter = 0;

function nextStepLocalId() {
  stepLocalCounter += 1;
  return `step-${Date.now()}-${stepLocalCounter}`;
}

function nextIngredientLocalId() {
  ingredientLocalCounter += 1;
  return `ingredient-${Date.now()}-${ingredientLocalCounter}`;
}

function resolveActionError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Не найдено или нет доступа.";
    if (err.status === 403) return "Недостаточно прав для выполнения действия.";
    if (err.status === 409) return ADMIN_RECIPE_LOCKED_EDIT_MESSAGE;
    if (err.status === 422) return "Проверьте корректность полей.";
    return err.message || fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

function getCoverUploadErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error ? err.message : "Не удалось загрузить фото блюда.";
  }
  if (err.status === 413) {
    return "Файл слишком большой. Максимальный размер — 5 МБ.";
  }
  const message = String(err.message || "").toLowerCase();
  if (err.status === 422 && (message.includes("unsupported image type") || message.includes("image type"))) {
    return "Поддерживаются JPG, PNG и WEBP до 5 МБ.";
  }
  return err.message || "Не удалось загрузить фото блюда.";
}

function toStepDrafts(steps: RecipeStepRead[] | undefined): StepDraft[] {
  return (steps ?? [])
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((step) => ({
      localId: nextStepLocalId(),
      id: step.id,
      text: step.text,
      note: step.note ?? "",
      image_url: step.image_url,
    }));
}

function toFoodSearchOption(ingredient: RecipeIngredientRead): FoodSearchOption | null {
  if (!ingredient.food) return null;
  return {
    id: ingredient.food.id,
    name: ingredient.food.name,
    brand: ingredient.food.brand ?? null,
  };
}

function toIngredientRows(ingredients: RecipeIngredientRead[] | undefined): IngredientRow[] {
  return (ingredients ?? []).map((ingredient) => {
    const initialGramsValue = Number(ingredient.grams);
    const initialMultiplierValue = Number(ingredient.multiplier);
    const hasServingMode = ingredient.serving_id !== null && ingredient.serving_id !== undefined;
    const mode: IngredientMode = hasServingMode ? "serving" : "grams";

    return {
      localId: nextIngredientLocalId(),
      id: ingredient.id,
      food_id: ingredient.food_id,
      food: toFoodSearchOption(ingredient),
      mode,
      grams: formatTrimmedNumber(ingredient.grams),
      serving_id: hasServingMode ? ingredient.serving_id ?? undefined : undefined,
      multiplier:
        hasServingMode && ingredient.multiplier !== null && ingredient.multiplier !== undefined
          ? formatTrimmedNumber(ingredient.multiplier)
          : "",
      initialMode: mode,
      initialFoodId: ingredient.food_id,
      initialGrams: Number.isFinite(initialGramsValue) ? initialGramsValue : null,
      initialServingId: hasServingMode ? ingredient.serving_id ?? null : null,
      initialMultiplier: hasServingMode && Number.isFinite(initialMultiplierValue) ? initialMultiplierValue : null,
    };
  });
}

function isBlankNewIngredientRow(row: IngredientRow): boolean {
  return !row.id && !row.food_id && row.grams.trim() === "" && !row.serving_id && row.multiplier.trim() === "";
}

function sameNumericValue(left: number | null | undefined, right: number): boolean {
  if (left === null || left === undefined) return false;
  return Math.abs(left - right) < 0.000001;
}

function ingredientLabel(row: IngredientRow): string {
  if (row.food) {
    return row.food.brand ? `${row.food.name} — ${row.food.brand}` : row.food.name;
  }
  if (row.food_id !== undefined) return "Продукт";
  return "Продукт не выбран";
}

type RecipeEditPageProps = {
  adminMode?: boolean;
};

export function RecipeEditPage({ adminMode = false }: RecipeEditPageProps) {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [form, setForm] = useState<RecipeFormState | null>(null);
  const [steps, setSteps] = useState<StepDraft[]>([]);
  const [stepFiles, setStepFiles] = useState<Record<string, File | null>>({});
  const [ingredientRows, setIngredientRows] = useState<IngredientRow[]>([]);
  const [ingredientsSaving, setIngredientsSaving] = useState(false);
  const [ingredientsError, setIngredientsError] = useState<string | null>(null);
  const [ingredientsSuccess, setIngredientsSuccess] = useState(false);
  const servingsCacheRef = useRef<Map<number, FoodServingRead[]>>(new Map());
  const servingsLoadingRef = useRef<Set<number>>(new Set());
  const [servingsErrorsByFoodId, setServingsErrorsByFoodId] = useState<Record<number, string>>({});
  const [servingsVersion, setServingsVersion] = useState(0);

  const [errors, setErrors] = useState<RecipeFormErrors>({ form: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [coverUploading, setCoverUploading] = useState(false);
  const [coverError, setCoverError] = useState<string | null>(null);
  const [coverSuccess, setCoverSuccess] = useState<string | null>(null);

  const [stepsSaving, setStepsSaving] = useState(false);
  const [stepsError, setStepsError] = useState<string | null>(null);
  const [stepsSuccess, setStepsSuccess] = useState<string | null>(null);
  const isStepInteractionDisabled = stepsSaving || submitting;

  const recipeId = useMemo(() => Number(id), [id]);
  const isRecipeEditable = Boolean(recipe && (adminMode || (recipe.source === "private" && recipe.status === "draft")));
  const lockedEditMessage = adminMode ? ADMIN_RECIPE_LOCKED_EDIT_MESSAGE : RECIPE_LOCKED_EDIT_MESSAGE;
  const visibleIngredientRows = useMemo(() => ingredientRows.filter((row) => !row.markedForDelete), [ingredientRows]);
  const servingsCache = servingsCacheRef.current;

  const loadRecipe = useCallback(async () => {
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setForm(null);
      setRecipe(null);
      setSteps([]);
      setIngredientRows([]);
      setLoading(false);
      setError("Некорректный идентификатор рецепта.");
      return;
    }

    setLoading(true);
    setError(null);
    setErrors({ form: [] });

    try {
      const loaded = adminMode ? await getAdminRecipe(recipeId) : await getRecipe(recipeId);
      setRecipe(loaded);
      setForm(toRecipeFormState(loaded));
      setSteps(toStepDrafts(loaded.steps));
      setIngredientRows(toIngredientRows(loaded.ingredients));
      setStepFiles({});
      setIngredientsError(null);
      setIngredientsSuccess(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить рецепт.");
      }
      setForm(null);
      setRecipe(null);
      setSteps([]);
      setIngredientRows([]);
    } finally {
      setLoading(false);
    }
  }, [adminMode, id, recipeId]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  useEffect(() => {
    if (!coverSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setCoverSuccess(null), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [coverSuccess]);

  useEffect(() => {
    if (!stepsSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setStepsSuccess(null), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [stepsSuccess]);

  useEffect(() => {
    if (!ingredientsSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setIngredientsSuccess(false), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [ingredientsSuccess]);

  const ensureFoodServingsLoaded = useCallback(async (foodId: number) => {
    if (servingsCacheRef.current.has(foodId) || servingsLoadingRef.current.has(foodId)) return;

    servingsLoadingRef.current.add(foodId);
    setServingsVersion((prev) => prev + 1);
    setServingsErrorsByFoodId((prev) => {
      if (!Object.prototype.hasOwnProperty.call(prev, foodId)) return prev;
      const next = { ...prev };
      delete next[foodId];
      return next;
    });

    try {
      const servings = await getFoodServings(foodId);
      servingsCacheRef.current.set(foodId, servings);
    } catch (err) {
      setServingsErrorsByFoodId((prev) => ({
        ...prev,
        [foodId]: resolveActionError(err, "Не удалось загрузить порции."),
      }));
    } finally {
      servingsLoadingRef.current.delete(foodId);
      setServingsVersion((prev) => prev + 1);
    }
  }, []);

  useEffect(() => {
    if (!adminMode) return;
    for (const row of visibleIngredientRows) {
      if (row.mode === "serving" && row.food_id) {
        void ensureFoodServingsLoaded(row.food_id);
      }
    }
  }, [adminMode, ensureFoodServingsLoaded, visibleIngredientRows]);

  useEffect(() => {
    if (!adminMode) return;
    setIngredientRows((prev) => {
      let changed = false;
      const next = prev.map((row) => {
        if (row.mode !== "serving" || !row.food_id || !servingsCacheRef.current.has(row.food_id)) return row;
        if ((servingsCacheRef.current.get(row.food_id)?.length ?? 0) > 0) return row;
        changed = true;
        return {
          ...row,
          mode: "grams" as IngredientMode,
          serving_id: undefined,
          multiplier: "",
          errors: { ...row.errors, serving: undefined, multiplier: undefined },
        };
      });
      return changed ? next : prev;
    });
  }, [adminMode, servingsVersion]);

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

  const updateIngredientRow = (localId: string, updater: (row: IngredientRow) => IngredientRow) => {
    setIngredientRows((prev) => prev.map((row) => (row.localId === localId ? updater(row) : row)));
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const addIngredientRow = () => {
    if (!adminMode || ingredientsSaving) return;
    setIngredientRows((prev) => [
      ...prev,
      { localId: nextIngredientLocalId(), food: null, mode: "grams", grams: "", multiplier: "", initialMode: "grams" },
    ]);
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const removeIngredientRow = (localId: string) => {
    if (!adminMode || ingredientsSaving) return;
    setIngredientRows((prev) => {
      const target = prev.find((row) => row.localId === localId);
      if (!target) return prev;
      if (target.id) {
        return prev.map((row) => (row.localId === localId ? { ...row, markedForDelete: true, errors: {} } : row));
      }
      return prev.filter((row) => row.localId !== localId);
    });
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const onIngredientFoodChange = (localId: string, food: FoodItem | null) => {
    if (food?.id) void ensureFoodServingsLoaded(food.id);

    updateIngredientRow(localId, (row) => {
      const isSameFood = row.food_id === food?.id;
      return {
        ...row,
        food: food ? { id: food.id, name: food.name, brand: food.brand ?? null } : null,
        food_id: food?.id,
        mode: isSameFood ? row.mode : "grams",
        serving_id: isSameFood ? row.serving_id : undefined,
        multiplier: isSameFood ? row.multiplier : "",
        errors: { ...row.errors, food: undefined, serving: undefined, multiplier: undefined },
      };
    });
  };

  const onIngredientModeChange = (localId: string, mode: IngredientMode) => {
    updateIngredientRow(localId, (row) => {
      if (mode === "serving" && row.food_id) {
        void ensureFoodServingsLoaded(row.food_id);
      }

      return {
        ...row,
        mode,
        serving_id: mode === "serving" ? row.serving_id : undefined,
        multiplier: mode === "serving" ? row.multiplier.trim() || "1" : "",
        errors: { ...row.errors, grams: undefined, serving: undefined, multiplier: undefined },
      };
    });
  };

  const onIngredientGramsChange = (localId: string, value: string) => {
    updateIngredientRow(localId, (row) => ({
      ...row,
      grams: value,
      errors: { ...row.errors, grams: undefined },
    }));
  };

  const onIngredientServingChange = (localId: string, value: string) => {
    updateIngredientRow(localId, (row) => ({
      ...row,
      serving_id: value ? Number(value) : undefined,
      errors: { ...row.errors, serving: undefined },
    }));
  };

  const onIngredientMultiplierChange = (localId: string, value: string) => {
    updateIngredientRow(localId, (row) => ({
      ...row,
      multiplier: value,
      errors: { ...row.errors, multiplier: undefined },
    }));
  };

  const saveIngredients = async () => {
    if (!recipe || !adminMode || ingredientsSaving) return;

    setIngredientsError(null);
    setIngredientsSuccess(false);

    let hasValidationErrors = false;
    const validatedRows = ingredientRows.map((row) => {
      if (row.markedForDelete) return { ...row, errors: {} };
      if (isBlankNewIngredientRow(row)) return { ...row, errors: {} };

      const rowErrors: IngredientRowErrors = {};
      if (!row.food_id) rowErrors.food = "Выберите продукт.";

      if (row.mode === "grams") {
        const gramsRaw = row.grams.trim();
        const grams = Number(gramsRaw);
        if (!gramsRaw || !Number.isFinite(grams) || grams <= 0) rowErrors.grams = "Введите число > 0.";
      } else {
        const multiplierRaw = row.multiplier.trim();
        const multiplier = Number(multiplierRaw);
        if (!row.serving_id) rowErrors.serving = "Выберите порцию.";
        if (!multiplierRaw || !Number.isFinite(multiplier) || multiplier <= 0) rowErrors.multiplier = "Введите число > 0.";
      }

      if (rowErrors.food || rowErrors.grams || rowErrors.serving || rowErrors.multiplier) hasValidationErrors = true;
      return { ...row, errors: rowErrors };
    });

    setIngredientRows(validatedRows);

    if (hasValidationErrors) {
      setIngredientsError("Исправьте ошибки в строках ингредиентов.");
      return;
    }

    setIngredientsSaving(true);

    try {
      for (const row of validatedRows) {
        if (row.markedForDelete && row.id) {
          await deleteAdminRecipeIngredient(recipe.id, row.id);
        }
      }

      for (const row of validatedRows) {
        if (row.markedForDelete || isBlankNewIngredientRow(row) || !row.food_id) continue;

        if (row.id) {
          const changedFood = row.food_id !== row.initialFoodId;
          const changedMode = row.mode !== row.initialMode;
          const payload: RecipeIngredientUpdate = {};

          if (row.mode === "grams") {
            const grams = Number(row.grams.trim());
            const changedGrams = !sameNumericValue(row.initialGrams, grams);
            if (!changedFood && !changedMode && !changedGrams) continue;
            if (changedFood) payload.food_id = row.food_id;
            payload.grams = grams;
          } else {
            const multiplier = Number(row.multiplier.trim());
            const changedServing = row.serving_id !== row.initialServingId;
            const changedMultiplier = !sameNumericValue(row.initialMultiplier, multiplier);
            if (!changedFood && !changedMode && !changedServing && !changedMultiplier) continue;
            if (changedFood) payload.food_id = row.food_id;
            payload.serving_id = row.serving_id;
            payload.multiplier = multiplier;
          }

          await updateAdminRecipeIngredient(recipe.id, row.id, payload);
          continue;
        }

        if (row.mode === "grams") {
          await addAdminRecipeIngredient(recipe.id, { food_id: row.food_id, grams: Number(row.grams.trim()) });
        } else {
          await addAdminRecipeIngredient(recipe.id, {
            food_id: row.food_id,
            serving_id: row.serving_id,
            multiplier: Number(row.multiplier.trim()),
          });
        }
      }

      const refreshed = await getAdminRecipe(recipe.id);
      setRecipe(refreshed);
      setForm(toRecipeFormState(refreshed));
      setIngredientRows(toIngredientRows(refreshed.ingredients));
      setIngredientsSuccess(true);
    } catch (err) {
      setIngredientsError(resolveActionError(err, "Не удалось сохранить ингредиенты."));
    } finally {
      setIngredientsSaving(false);
    }
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form || !id || !Number.isInteger(recipeId) || recipeId < 1) {
      setErrors({ form: ["Некорректный идентификатор рецепта."] });
      return;
    }
    if (!isRecipeEditable) {
      setErrors({ form: [lockedEditMessage] });
      return;
    }

    const { errors: validationErrors, payload } = validateRecipeForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    const invalidStep = steps.find((step) => !step.text.trim());
    if (invalidStep) {
      setStepsError("У каждого шага должно быть описание.");
      setErrors({ form: ["Исправьте шаги приготовления перед сохранением."] });
      return;
    }

    setSubmitting(true);
    setErrors({ form: [] });
    setStepsError(null);

    try {
      await (adminMode ? updateAdminRecipe(recipeId, payload) : updateRecipe(recipeId, payload));
      const stepsPayload: RecipeStepInput[] = steps.map((step, index) => ({
        id: step.id,
        text: step.text,
        note: step.note.trim() || null,
        position: index + 1,
      }));
      const savedSteps = await (adminMode ? replaceAdminRecipeSteps(recipeId, stepsPayload) : replaceRecipeSteps(recipeId, stepsPayload));
      setSteps(toStepDrafts(savedSteps));
      setStepFiles({});
      if (adminMode) {
        const refreshed = await getAdminRecipe(recipeId);
        setRecipe(refreshed);
        setForm(toRecipeFormState(refreshed));
        setSteps(toStepDrafts(refreshed.steps));
        setIngredientRows(toIngredientRows(refreshed.ingredients));
        setStepsSuccess("Рецепт сохранён.");
        return;
      }
      navigate(adminMode ? `/recipes/${recipeId}` : `/recipes/${recipeId}`, {
        replace: true,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrors({ form: [lockedEditMessage] });
      } else if (err instanceof ApiError && err.status === 404) {
        setErrors({ form: ["Рецепт не найден."] });
      } else {
        setErrors({ form: [err instanceof Error ? err.message : "Не удалось сохранить рецепт и шаги."] });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onUploadCover = async () => {
    if (!recipe || !fileInputRef.current?.files?.[0]) return;
    if (!isRecipeEditable) {
      setCoverError(lockedEditMessage);
      return;
    }
    const file = fileInputRef.current.files[0];
    setCoverUploading(true);
    setCoverError(null);
    setCoverSuccess(null);
    try {
      const updated = await (adminMode ? uploadAdminRecipeCoverImage(recipe.id, file) : uploadRecipeCoverImage(recipe.id, file));
      setRecipe(updated);
      setForm(toRecipeFormState(updated));
      if (fileInputRef.current) fileInputRef.current.value = "";
      setCoverSuccess("Фото блюда обновлено.");
    } catch (err) {
      setCoverError(err instanceof ApiError && err.status === 409 ? lockedEditMessage : getCoverUploadErrorMessage(err));
    } finally {
      setCoverUploading(false);
    }
  };

  const onDeleteCover = async () => {
    if (!recipe) return;
    if (!isRecipeEditable) {
      setCoverError(lockedEditMessage);
      return;
    }
    setCoverUploading(true);
    setCoverError(null);
    setCoverSuccess(null);
    try {
      const updated = await (adminMode ? deleteAdminRecipeCoverImage(recipe.id) : deleteRecipeCoverImage(recipe.id));
      setRecipe(updated);
      setForm(toRecipeFormState(updated));
      setCoverSuccess("Фото блюда удалено.");
    } catch (err) {
      setCoverError(
        err instanceof ApiError && err.status === 409
          ? lockedEditMessage
          : err instanceof Error
            ? err.message
            : "Не удалось удалить фото.",
      );
    } finally {
      setCoverUploading(false);
    }
  };

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      {
        localId: nextStepLocalId(),
        text: "",
        note: "",
        image_url: null,
      },
    ]);
    setStepsError(null);
  };

  const updateStep = (localId: string, patch: Partial<StepDraft>) => {
    setSteps((prev) => prev.map((step) => (step.localId === localId ? { ...step, ...patch } : step)));
    setStepsError(null);
  };

  const removeStep = (localId: string) => {
    setSteps((prev) => prev.filter((step) => step.localId !== localId));
    setStepFiles((prev) => {
      const next = { ...prev };
      delete next[localId];
      return next;
    });
    setStepsError(null);
  };

  const moveStep = (localId: string, direction: -1 | 1) => {
    setSteps((prev) => {
      const index = prev.findIndex((step) => step.localId === localId);
      if (index < 0) return prev;
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
    setStepsError(null);
  };

  const uploadStepImage = async (localId: string) => {
    if (!recipe) return;
    if (!isRecipeEditable) {
      setStepsError(lockedEditMessage);
      return;
    }
    const step = steps.find((item) => item.localId === localId);
    const file = stepFiles[localId];
    if (!step?.id || !file) {
      setStepsError("Сохраните рецепт, чтобы добавить фото к этому шагу.");
      return;
    }

    setStepsSaving(true);
    setStepsError(null);
    setStepsSuccess(null);
    try {
      const saved = await (adminMode ? uploadAdminRecipeStepImage(recipe.id, step.id, file) : uploadRecipeStepImage(recipe.id, step.id, file));
      setSteps((prev) => prev.map((item) => (item.localId === localId ? { ...item, image_url: saved.image_url } : item)));
      setStepFiles((prev) => ({ ...prev, [localId]: null }));
      setStepsSuccess("Фото шага загружено.");
    } catch (err) {
      setStepsError(
        err instanceof ApiError && err.status === 409
          ? lockedEditMessage
          : err instanceof Error
            ? err.message
            : "Не удалось загрузить фото шага.",
      );
    } finally {
      setStepsSaving(false);
    }
  };

  const removeStepImage = async (localId: string) => {
    if (!recipe) return;
    if (!isRecipeEditable) {
      setStepsError(lockedEditMessage);
      return;
    }
    const step = steps.find((item) => item.localId === localId);
    if (!step?.id) return;

    setStepsSaving(true);
    setStepsError(null);
    setStepsSuccess(null);
    try {
      const saved = await (adminMode ? deleteAdminRecipeStepImage(recipe.id, step.id) : deleteRecipeStepImage(recipe.id, step.id));
      setSteps((prev) => prev.map((item) => (item.localId === localId ? { ...item, image_url: saved.image_url } : item)));
      setStepsSuccess("Фото шага удалено.");
    } catch (err) {
      setStepsError(
        err instanceof ApiError && err.status === 409
          ? lockedEditMessage
          : err instanceof Error
            ? err.message
            : "Не удалось удалить фото шага.",
      );
    } finally {
      setStepsSaving(false);
    }
  };

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">{adminMode ? "Редактирование публичного рецепта" : "Редактирование рецепта"}</h1>
          </div>

          <div className="recipes-head-actions">
            <Link to={adminMode ? "/admin/recipes" : id ? `/recipes/${id}` : "/recipes"} className="btn btn-secondary">
              {adminMode ? "К публичным рецептам" : "Назад"}
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

        {!loading && !error && form && recipe && !isRecipeEditable && (
          <div className="recipes-error-block">
            <Alert text={lockedEditMessage} />
            <Link to={adminMode ? "/admin/recipes" : `/recipes/${recipe.id}`} className="btn btn-secondary">
              {adminMode ? "К публичным рецептам" : "К рецепту"}
            </Link>
          </div>
        )}

        {!loading && !error && form && recipe && isRecipeEditable && (
          <>
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

              <MarkdownTextarea
                id="recipe_instructions"
                label="Общие инструкции (опционально)"
                value={form.instructions}
                onChange={(next) => updateField("instructions", next)}
                placeholder="Например, как подготовить ингредиенты до шагов"
                disabled={submitting}
                rows={4}
              />

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
                  onClick={() => navigate(adminMode ? "/admin/recipes" : id ? `/recipes/${id}` : "/recipes")}
                  disabled={submitting}
                >
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Сохраняем..." : "Сохранить рецепт"}
                </button>
              </div>
            </form>

            {adminMode && (
              <article className="recipe-card">
                <div className="ingredients-head">
                  <div>
                    <h2 className="recipe-metrics-title">Ингредиенты</h2>
                    <p className="recipes-note">Поиск продукта, граммы и сохранённые порции работают как в пользовательском редакторе.</p>
                  </div>
                  <div className="ingredients-head-actions">
                    <button type="button" className="btn btn-secondary" onClick={addIngredientRow} disabled={ingredientsSaving}>
                      Добавить ингредиент
                    </button>
                    <button type="button" className="btn btn-primary" onClick={() => void saveIngredients()} disabled={ingredientsSaving}>
                      {ingredientsSaving ? "Сохраняем..." : "Сохранить ингредиенты"}
                    </button>
                  </div>
                </div>

                {ingredientsError && <Alert text={ingredientsError} />}
                {ingredientsSuccess && <p className="recipes-inline-success">Ингредиенты сохранены.</p>}
                {visibleIngredientRows.length === 0 && <p className="recipes-note">Ингредиентов пока нет. Добавьте ингредиенты, чтобы рассчитать КБЖУ.</p>}

                {visibleIngredientRows.length > 0 && (
                  <ul className="ingredients-edit-list">
                    {visibleIngredientRows.map((row) => (
                      <li key={row.localId} className="ingredients-edit-row">
                        <div className="ingredients-edit-row-top">
                          <div className="ingredients-row-food">
                            <FoodSearchSelect
                              value={row.food}
                              onChange={(food) => onIngredientFoodChange(row.localId, food)}
                              placeholder="Выберите продукт"
                              disabled={ingredientsSaving}
                            />
                            <div className="ingredients-error-slot">
                              {row.errors?.food && <p className="recipes-field-error">{row.errors.food}</p>}
                            </div>
                          </div>

                          <button
                            type="button"
                            className="btn btn-subtle ingredients-delete-icon-btn"
                            onClick={() => removeIngredientRow(row.localId)}
                            disabled={ingredientsSaving}
                            aria-label={`Удалить ингредиент ${ingredientLabel(row)}`}
                          >
                            <span aria-hidden="true">×</span>
                          </button>
                        </div>

                        <div className="ingredients-edit-row-bottom">
                          <div className="ingredients-row-mode">
                            <CustomSelect
                              value={row.mode}
                              onChange={(value) => onIngredientModeChange(row.localId, value as IngredientMode)}
                              disabled={ingredientsSaving}
                              ariaLabel="Способ ввода количества ингредиента"
                              options={[
                                { value: "grams", label: "Граммы" },
                                ...(row.mode === "serving" || (row.food_id ? (servingsCache.get(row.food_id)?.length ?? 0) > 0 : false)
                                  ? [{ value: "serving", label: "Порция" }]
                                  : []),
                              ]}
                            />
                            <div className="ingredients-error-slot" />
                          </div>

                          {row.mode === "grams" ? (
                            <div className="ingredients-row-field">
                              <input
                                className={`recipes-field-input ${row.errors?.grams ? "is-invalid" : ""}`}
                                type="number"
                                min={0}
                                step="any"
                                value={row.grams}
                                onChange={(event) => onIngredientGramsChange(row.localId, event.target.value)}
                                placeholder="Граммы"
                                disabled={ingredientsSaving}
                              />
                              <div className="ingredients-error-slot">
                                {row.errors?.grams && <p className="recipes-field-error">{row.errors.grams}</p>}
                              </div>
                            </div>
                          ) : (
                            <div className="ingredients-serving-grid">
                              <div className="ingredients-row-field">
                                <CustomSelect
                                  value={row.serving_id ? String(row.serving_id) : ""}
                                  onChange={(value) => onIngredientServingChange(row.localId, value)}
                                  disabled={ingredientsSaving || !row.food_id || servingsLoadingRef.current.has(row.food_id ?? -1)}
                                  invalid={Boolean(row.errors?.serving)}
                                  ariaLabel="Выберите порцию ингредиента"
                                  placeholder="Выберите порцию"
                                  options={[
                                    { value: "", label: "Выберите порцию" },
                                    ...(row.food_id ? servingsCache.get(row.food_id) ?? [] : []).map((serving) => ({
                                      value: String(serving.id),
                                      label: `${serving.name} (${formatTrimmedNumber(serving.grams)} г)`,
                                    })),
                                  ]}
                                />
                                <div className="ingredients-error-slot">
                                  {row.errors?.serving && <p className="recipes-field-error">{row.errors.serving}</p>}
                                  {!row.errors?.serving && row.food_id && servingsErrorsByFoodId[row.food_id] && (
                                    <p className="recipes-field-error">{servingsErrorsByFoodId[row.food_id]}</p>
                                  )}
                                  {!row.errors?.serving &&
                                    row.food_id &&
                                    !servingsErrorsByFoodId[row.food_id] &&
                                    !servingsLoadingRef.current.has(row.food_id ?? -1) &&
                                    (servingsCache.get(row.food_id)?.length ?? 0) === 0 && (
                                      <p className="recipes-field-error">У выбранного продукта нет сохранённых порций.</p>
                                    )}
                                </div>
                              </div>

                              <div className="ingredients-row-field">
                                <input
                                  className={`recipes-field-input ${row.errors?.multiplier ? "is-invalid" : ""}`}
                                  type="number"
                                  min={0}
                                  step="any"
                                  value={row.multiplier}
                                  onChange={(event) => onIngredientMultiplierChange(row.localId, event.target.value)}
                                  placeholder="Множитель"
                                  disabled={ingredientsSaving}
                                />
                                <div className="ingredients-error-slot">
                                  {row.errors?.multiplier && <p className="recipes-field-error">{row.errors.multiplier}</p>}
                                </div>
                              </div>

                              <p className="ingredients-serving-hint">
                                {(() => {
                                  const servings = row.food_id ? servingsCache.get(row.food_id) ?? [] : [];
                                  const serving = servings.find((item) => item.id === row.serving_id);
                                  const multiplier = Number(row.multiplier.trim());
                                  if (!serving || !Number.isFinite(multiplier) || multiplier <= 0) {
                                    return "Итого грамм: —";
                                  }
                                  return `Итого грамм: ${formatTrimmedNumber(serving.grams * multiplier)} г`;
                                })()}
                              </p>
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            )}

            <article className="recipe-card">
              <h2 className="recipe-metrics-title">Фото блюда</h2>
              {coverError && <Alert text={coverError} />}
              {coverSuccess && <p className="recipes-inline-success">{coverSuccess}</p>}
              <div className="recipe-cover-edit-grid">
                <div className="recipe-cover">
                  {recipe.image_url ? (
                    <img src={resolveRecipeImageSrc(recipe.image_url) ?? undefined} alt={`Фото блюда: ${recipe.name}`} className="recipe-cover-image" />
                  ) : (
                    <RecipePlaceholder name={recipe.name} mealTypes={recipe.meal_types} className="recipe-cover-fallback" />
                  )}
                </div>
                <div className="recipes-field">
                  <input
                    ref={fileInputRef}
                    className="recipes-field-input"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={coverUploading}
                  />
                  <p className="recipes-field-hint">Поддерживаются JPG, PNG и WEBP до 5 МБ.</p>
                  <div className="recipes-form-actions recipes-form-actions-start">
                    <button type="button" className="btn btn-primary" onClick={() => void onUploadCover()} disabled={coverUploading}>
                      {coverUploading ? "Загружаем..." : "Загрузить фото"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void onDeleteCover()}
                      disabled={coverUploading || !recipe.image_url}
                    >
                      Удалить фото
                    </button>
                  </div>
                </div>
              </div>
            </article>

            <article className="recipe-card">
              <div className="recipe-steps-head">
                <h2 className="recipe-metrics-title">Шаги приготовления</h2>
              </div>

              {stepsError && <Alert text={stepsError} />}
              {stepsSuccess && <p className="recipes-inline-success">{stepsSuccess}</p>}

              {steps.length === 0 && <p className="recipes-note">Шаги пока не добавлены.</p>}

              {steps.length > 0 && (
                <div className="recipe-steps-list">
                  {steps.map((step, index) => (
                    <section key={step.localId} className="recipe-step-card">
                      <div className="recipe-step-head">
                        <h3 className="recipe-step-title">Шаг {index + 1}</h3>
                        <div className="recipe-step-actions">
                          <button type="button" className="btn btn-secondary" onClick={() => moveStep(step.localId, -1)} disabled={isStepInteractionDisabled || index === 0}>
                            Вверх
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => moveStep(step.localId, 1)}
                            disabled={isStepInteractionDisabled || index === steps.length - 1}
                          >
                            Вниз
                          </button>
                          <button type="button" className="btn btn-subtle" onClick={() => removeStep(step.localId)} disabled={isStepInteractionDisabled}>
                            Удалить
                          </button>
                        </div>
                      </div>

                      <MarkdownTextarea
                        id={`step-text-${step.localId}`}
                        label="Описание шага"
                        value={step.text}
                        onChange={(next) => updateStep(step.localId, { text: next })}
                        placeholder="Опишите, что нужно сделать на этом шаге"
                        disabled={isStepInteractionDisabled}
                        rows={3}
                        compact
                        textareaClassName="recipe-step-text-input"
                      />

                      <MarkdownTextarea
                        id={`step-note-${step.localId}`}
                        label="Совет или примечание (опционально)"
                        value={step.note}
                        onChange={(next) => updateStep(step.localId, { note: next })}
                        placeholder="Например, как улучшить вкус или ускорить процесс"
                        disabled={isStepInteractionDisabled}
                        rows={2}
                        compact
                        textareaClassName="recipe-step-note-input"
                      />

                      <div className="recipe-step-image-grid">
                        <div className="recipe-step-image-preview">
                          {step.image_url ? (
                            <img src={resolveRecipeImageSrc(step.image_url) ?? undefined} alt={`Шаг ${index + 1}`} className="recipe-cover-image" />
                          ) : (
                            <div className="recipe-cover-fallback" aria-hidden="true">
                              {index + 1}
                            </div>
                          )}
                        </div>
                        <div className="recipes-field">
                          <input
                            type="file"
                            className="recipes-field-input"
                            accept="image/jpeg,image/png,image/webp"
                            onChange={(event) => {
                              const file = event.target.files?.[0] ?? null;
                              setStepFiles((prev) => ({ ...prev, [step.localId]: file }));
                            }}
                            disabled={isStepInteractionDisabled || !step.id}
                          />
                          <div className="recipes-form-actions recipes-form-actions-start">
                            <button
                              type="button"
                              className="btn btn-primary"
                              onClick={() => void uploadStepImage(step.localId)}
                              disabled={isStepInteractionDisabled || !step.id || !stepFiles[step.localId]}
                            >
                              Загрузить фото шага
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => void removeStepImage(step.localId)}
                              disabled={isStepInteractionDisabled || !step.image_url || !step.id}
                            >
                              Удалить фото шага
                            </button>
                          </div>
                          {!step.id && (
                            <p className="recipes-field-hint">Фото к новым шагам можно добавить после сохранения рецепта.</p>
                          )}
                        </div>
                      </div>
                    </section>
                  ))}
                </div>
              )}

              <div className="recipes-form-actions">
                <button type="button" className="btn btn-secondary" onClick={addStep} disabled={isStepInteractionDisabled}>
                  Добавить шаг
                </button>
              </div>
            </article>
          </>
        )}
      </div>
    </section>
  );
}
