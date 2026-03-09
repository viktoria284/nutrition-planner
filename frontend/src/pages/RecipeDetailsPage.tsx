import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { type FoodItem } from "../api/foods";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import {
  addIngredient,
  deleteIngredient,
  deleteRecipe,
  getRecipe,
  publishRecipe,
  reportRecipe,
  updateIngredient,
  withdrawRecipe,
  type MealType,
  type RecipeIngredientRead,
  type RecipeIngredientUpdate,
  type RecipeRead,
} from "../api/recipes";
import { Alert } from "../components/Alert";
import { FoodSearchSelect, type FoodSearchOption } from "../components/FoodSearchSelect";
import { getCurrentUserIdFromJwt } from "../utils/auth";
import "./RecipesPage.css";

type ConfirmModalProps = {
  open: boolean;
  title: string;
  message: string;
  confirmText: string;
  loading: boolean;
  errorText?: string | null;
  onConfirm: () => void;
  onClose: () => void;
};

type ReportForm = {
  reason: string;
  comment: string;
};

type ReportFormErrors = {
  reason?: string;
  comment?: string;
  form?: string;
};

type IngredientRowErrors = {
  food?: string;
  grams?: string;
};

type IngredientRow = {
  localId: string;
  id?: number;
  food_id?: number;
  food: FoodSearchOption | null;
  grams: string;
  initialFoodId?: number;
  initialGrams?: number | null;
  markedForDelete?: boolean;
  errors?: IngredientRowErrors;
};

const REPORT_REASON_OPTIONS = ["Неверные данные", "Дубликат", "Спам/мусор", "Оскорбительный контент", "Другое"] as const;

const EMPTY_REPORT_FORM: ReportForm = {
  reason: "",
  comment: "",
};

const MEAL_TYPE_LABELS: Record<MealType, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  dinner: "Ужин",
  snack: "Перекус",
};

const TOTAL_METRICS: Array<{ key: keyof RecipeRead; label: string }> = [
  { key: "total_grams", label: "Вес (г)" },
  { key: "total_kcal", label: "Калории (ккал)" },
  { key: "total_protein", label: "Белки (г)" },
  { key: "total_fat", label: "Жиры (г)" },
  { key: "total_carbs", label: "Углеводы (г)" },
];

const PER_SERVING_METRICS: Array<{ key: keyof RecipeRead; label: string }> = [
  { key: "per_serving_kcal", label: "Калории/порция (ккал)" },
  { key: "per_serving_protein", label: "Белки/порция (г)" },
  { key: "per_serving_fat", label: "Жиры/порция (г)" },
  { key: "per_serving_carbs", label: "Углеводы/порция (г)" },
];

function formatMetric(value: string | number): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

function createLocalId(): string {
  return `row-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function toFoodSearchOption(ingredient: RecipeIngredientRead): FoodSearchOption | null {
  if (!ingredient.food) return null;
  return {
    id: ingredient.food.id,
    name: ingredient.food.name,
    brand: ingredient.food.brand ?? null,
  };
}

function buildIngredientRows(ingredients?: RecipeIngredientRead[]): IngredientRow[] {
  if (!Array.isArray(ingredients) || ingredients.length === 0) return [];

  return ingredients.map((ingredient) => {
    const initialGramsValue = Number(ingredient.grams);
    return {
      localId: createLocalId(),
      id: ingredient.id,
      food_id: ingredient.food_id,
      food: toFoodSearchOption(ingredient),
      grams: String(ingredient.grams),
      initialFoodId: ingredient.food_id,
      initialGrams: Number.isFinite(initialGramsValue) ? initialGramsValue : null,
    };
  });
}

function isBlankNewRow(row: IngredientRow): boolean {
  return !row.id && !row.food_id && row.grams.trim() === "";
}

function sameNumericValue(left: number | null | undefined, right: number): boolean {
  if (left === null || left === undefined) return false;
  return Math.abs(left - right) < 0.000001;
}

function ingredientLabel(row: IngredientRow): string {
  if (row.food) {
    return row.food.brand ? `${row.food.name} — ${row.food.brand}` : row.food.name;
  }
  if (row.food_id !== undefined) return `Продукт #${row.food_id}`;
  return "Продукт не выбран";
}

function validateReportForm(form: ReportForm): { errors: ReportFormErrors; payload: { reason: string; comment?: string } | null } {
  const errors: ReportFormErrors = {};

  const reason = form.reason.trim();
  const comment = form.comment.trim();

  if (!reason) errors.reason = "Выберите причину.";
  if (reason === "Другое" && !comment) errors.comment = "Для причины «Другое» добавьте комментарий.";

  if (Object.keys(errors).length > 0) {
    return { errors, payload: null };
  }

  return {
    errors: {},
    payload: {
      reason,
      ...(comment ? { comment } : {}),
    },
  };
}

function ConfirmModal({
  open,
  title,
  message,
  confirmText,
  loading,
  errorText = null,
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div
      className="recipes-modal-backdrop"
      role="presentation"
      onClick={() => {
        if (!loading) onClose();
      }}
    >
      <div className="recipes-modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <h2 className="recipes-modal-title">{title}</h2>
        <p className="recipes-modal-text">{message}</p>
        {errorText && <Alert text={errorText} />}

        <div className="recipes-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={loading}>
            {loading ? "Подтверждаем..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

export function RecipeDetailsPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const currentUserId = user?.id ?? getCurrentUserIdFromJwt();
  const ingredientsAnchorRef = useRef<HTMLElement | null>(null);
  const hasScrolledToIngredientsRef = useRef(false);

  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState(false);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteModalError, setDeleteModalError] = useState<string | null>(null);

  const [withdrawModalOpen, setWithdrawModalOpen] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawSuccess, setWithdrawSuccess] = useState(false);
  const [withdrawModalError, setWithdrawModalError] = useState<string | null>(null);

  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);
  const [reportForm, setReportForm] = useState<ReportForm>(EMPTY_REPORT_FORM);
  const [reportErrors, setReportErrors] = useState<ReportFormErrors>({});

  const [ingredientRows, setIngredientRows] = useState<IngredientRow[]>([]);
  const [ingredientsSaving, setIngredientsSaving] = useState(false);
  const [ingredientsError, setIngredientsError] = useState<string | null>(null);
  const [ingredientsSuccess, setIngredientsSuccess] = useState(false);

  const applyRecipePayload = useCallback((payload: RecipeRead) => {
    setRecipe(payload);
    setIngredientRows(buildIngredientRows(payload.ingredients));
  }, []);

  const loadRecipe = useCallback(async () => {
    const recipeId = Number(id);
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setRecipe(null);
      setIngredientRows([]);
      setError("Некорректный идентификатор рецепта.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const item = await getRecipe(recipeId);
      applyRecipePayload(item);
    } catch (err) {
      setRecipe(null);
      setIngredientRows([]);
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить рецепт.");
      }
    } finally {
      setLoading(false);
    }
  }, [id, applyRecipePayload]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  useEffect(() => {
    if (!reportSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setReportSuccess(false), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [reportSuccess]);

  useEffect(() => {
    if (!publishSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setPublishSuccess(false), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [publishSuccess]);

  useEffect(() => {
    if (!withdrawSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setWithdrawSuccess(false), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [withdrawSuccess]);

  useEffect(() => {
    if (!ingredientsSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setIngredientsSuccess(false), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [ingredientsSuccess]);

  const isOwner = Boolean(recipe && currentUserId !== null && recipe.owner_user_id === currentUserId);
  const canEditRecipe = Boolean(recipe && isOwner && recipe.source === "private" && recipe.status === "draft");
  const canPublishRecipe = canEditRecipe;
  const canDeleteRecipe = canEditRecipe;
  const canEditIngredients = isOwner;
  const canWithdrawRecipe = Boolean(
    recipe && isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const canReportRecipe = Boolean(
    recipe && !isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const showModerationBanner = Boolean(recipe && isOwner && recipe.status === "pending" && !recipe.is_listed);

  useEffect(() => {
    hasScrolledToIngredientsRef.current = false;
  }, [id]);

  useEffect(() => {
    if (location.hash !== "#ingredients") return;
    if (loading || !recipe) return;
    if (hasScrolledToIngredientsRef.current) return;

    hasScrolledToIngredientsRef.current = true;
    ingredientsAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [loading, recipe, location.hash]);

  const totalMetrics = useMemo(() => {
    if (!recipe) return [];
    return TOTAL_METRICS.map((item) => ({
      label: item.label,
      value: formatMetric(recipe[item.key] as string | number),
    }));
  }, [recipe]);

  const perServingMetrics = useMemo(() => {
    if (!recipe) return [];
    return PER_SERVING_METRICS.map((item) => ({
      label: item.label,
      value: formatMetric(recipe[item.key] as string | number),
    }));
  }, [recipe]);

  const visibleIngredientRows = useMemo(
    () => ingredientRows.filter((row) => !row.markedForDelete),
    [ingredientRows],
  );

  const updateIngredientRow = (localId: string, updater: (row: IngredientRow) => IngredientRow) => {
    setIngredientRows((prev) =>
      prev.map((row) => {
        if (row.localId !== localId) return row;
        return updater(row);
      }),
    );
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const addIngredientRow = () => {
    if (!canEditIngredients || ingredientsSaving) return;
    setIngredientRows((prev) => [...prev, { localId: createLocalId(), food: null, grams: "" }]);
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const removeIngredientRow = (localId: string) => {
    if (!canEditIngredients || ingredientsSaving) return;

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
    updateIngredientRow(localId, (row) => ({
      ...row,
      food: food
        ? {
            id: food.id,
            name: food.name,
            brand: food.brand ?? null,
          }
        : null,
      food_id: food?.id,
      errors: { ...row.errors, food: undefined },
    }));
  };

  const onIngredientGramsChange = (localId: string, value: string) => {
    updateIngredientRow(localId, (row) => ({
      ...row,
      grams: value,
      errors: { ...row.errors, grams: undefined },
    }));
  };

  const onSaveIngredients = async () => {
    if (!recipe || ingredientsSaving || !canEditIngredients) return;

    setIngredientsError(null);
    setIngredientsSuccess(false);

    let hasValidationErrors = false;
    const validatedRows = ingredientRows.map((row) => {
      if (row.markedForDelete) return { ...row, errors: {} };
      if (isBlankNewRow(row)) return { ...row, errors: {} };

      const errors: IngredientRowErrors = {};
      const gramsRaw = row.grams.trim();
      const grams = Number(gramsRaw);

      if (!row.food_id) errors.food = "Выберите продукт.";
      if (!gramsRaw || !Number.isFinite(grams) || grams <= 0) errors.grams = "Введите число > 0.";

      if (errors.food || errors.grams) hasValidationErrors = true;
      return { ...row, errors };
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
          await deleteIngredient(recipe.id, row.id);
        }
      }

      for (const row of validatedRows) {
        if (row.markedForDelete || isBlankNewRow(row)) continue;
        if (!row.food_id) continue;

        const grams = Number(row.grams.trim());

        if (row.id) {
          const changedFood = row.food_id !== row.initialFoodId;
          const changedGrams = !sameNumericValue(row.initialGrams, grams);

          if (!changedFood && !changedGrams) continue;

          const payload: RecipeIngredientUpdate = {};
          if (changedFood) payload.food_id = row.food_id;
          if (changedGrams) payload.grams = grams;

          await updateIngredient(recipe.id, row.id, payload);
          continue;
        }

        await addIngredient(recipe.id, { food_id: row.food_id, grams });
      }

      const refreshed = await getRecipe(recipe.id);
      applyRecipePayload(refreshed);
      setIngredientsSuccess(true);
    } catch (err) {
      setIngredientsError(err instanceof Error ? err.message : "Не удалось сохранить ингредиенты.");
    } finally {
      setIngredientsSaving(false);
    }
  };

  const onPublish = async () => {
    if (!recipe || publishing) return;

    setPublishing(true);
    setPublishError(null);
    setPublishSuccess(false);

    try {
      const updated = await publishRecipe(recipe.id);
      applyRecipePayload(updated);
      setPublishSuccess(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPublishError("Этот рецепт уже опубликован или не может быть опубликован.");
      } else {
        setPublishError(err instanceof Error ? err.message : "Не удалось опубликовать рецепт.");
      }
    } finally {
      setPublishing(false);
    }
  };

  const openDeleteModal = () => {
    if (!canDeleteRecipe || deleting) return;
    setDeleteModalError(null);
    setDeleteModalOpen(true);
  };

  const closeDeleteModal = () => {
    if (deleting) return;
    setDeleteModalOpen(false);
    setDeleteModalError(null);
  };

  const onConfirmDelete = async () => {
    if (!recipe || deleting) return;

    setDeleting(true);
    setDeleteModalError(null);

    try {
      await deleteRecipe(recipe.id);
      navigate("/recipes", { replace: true, state: { flashMessage: "Рецепт удалён" } });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setDeleteModalError("Этот рецепт нельзя удалить (доступно только для private draft).");
      } else if (err instanceof ApiError && err.status === 404) {
        setDeleteModalError("Рецепт не найден.");
      } else {
        setDeleteModalError(err instanceof Error ? err.message : "Не удалось удалить рецепт.");
      }
    } finally {
      setDeleting(false);
    }
  };

  const openWithdrawModal = () => {
    if (!canWithdrawRecipe || withdrawing) return;
    setWithdrawModalError(null);
    setWithdrawModalOpen(true);
  };

  const closeWithdrawModal = () => {
    if (withdrawing) return;
    setWithdrawModalOpen(false);
    setWithdrawModalError(null);
  };

  const onConfirmWithdraw = async () => {
    if (!recipe || withdrawing) return;

    setWithdrawing(true);
    setWithdrawError(null);
    setWithdrawSuccess(false);
    setWithdrawModalError(null);

    try {
      const updated = await withdrawRecipe(recipe.id);
      applyRecipePayload(updated);
      setWithdrawSuccess(true);
      setWithdrawModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        const message = "Нет прав на отзыв публикации.";
        setWithdrawError(message);
        setWithdrawModalError(message);
      } else if (err instanceof ApiError && err.status === 409) {
        const message = "Этот рецепт нельзя отозвать.";
        setWithdrawError(message);
        setWithdrawModalError(message);
      } else {
        const message = err instanceof Error ? err.message : "Не удалось отозвать рецепт.";
        setWithdrawError(message);
        setWithdrawModalError(message);
      }
    } finally {
      setWithdrawing(false);
    }
  };

  const openReportModal = () => {
    if (!canReportRecipe || reporting) return;
    setReportForm(EMPTY_REPORT_FORM);
    setReportErrors({});
    setReportModalOpen(true);
  };

  const closeReportModal = () => {
    if (reporting) return;
    setReportModalOpen(false);
    setReportErrors({});
  };

  const updateReportField = (field: keyof ReportForm, value: string) => {
    setReportForm((prev) => ({ ...prev, [field]: value }));
    setReportErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onSubmitReport = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!recipe) return;

    const { errors, payload } = validateReportForm(reportForm);
    if (!payload) {
      setReportErrors(errors);
      return;
    }

    setReporting(true);
    setReportErrors({});
    setReportSuccess(false);

    try {
      const updated = await reportRecipe(recipe.id, payload);
      applyRecipePayload(updated);
      setReportModalOpen(false);
      setReportForm(EMPTY_REPORT_FORM);
      setReportSuccess(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setReportErrors({ form: "Жалоба недоступна для этого рецепта." });
      } else if (err instanceof ApiError && err.status === 409) {
        setReportErrors({ form: "Вы уже отправляли жалобу на этот рецепт." });
      } else {
        setReportErrors({ form: err instanceof Error ? err.message : "Не удалось отправить жалобу." });
      }
    } finally {
      setReporting(false);
    }
  };

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">Рецепт</h1>
            <p className="recipes-subtitle">Базовая информация и расчётные КБЖУ.</p>
          </div>

          <div className="recipes-head-actions">
            <Link to="/recipes" className="btn btn-secondary">
              Назад к списку
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

        {!loading && !error && recipe && (
          <>
            <article className="recipe-card">
              <div className="recipe-card-head">
                <div>
                  <h2 className="recipe-card-title">{recipe.name}</h2>
                  {recipe.description && <p className="recipe-description">{recipe.description}</p>}
                </div>

                {(canPublishRecipe || canEditRecipe || canDeleteRecipe || canWithdrawRecipe || canReportRecipe) && (
                  <div className="recipe-action-block">
                    <div className="recipe-action-row">
                      {canPublishRecipe && (
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => void onPublish()}
                          disabled={publishing || deleting || withdrawing || ingredientsSaving}
                        >
                          {publishing ? "Публикация..." : "Опубликовать"}
                        </button>
                      )}
                      {canEditRecipe && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => navigate(`/recipes/${recipe.id}/edit`)}
                          disabled={publishing || deleting || withdrawing || ingredientsSaving}
                        >
                          Редактировать
                        </button>
                      )}
                      {canDeleteRecipe && (
                        <button
                          type="button"
                          className="btn btn-subtle"
                          onClick={openDeleteModal}
                          disabled={publishing || deleting || withdrawing || ingredientsSaving}
                        >
                          {deleting ? "Удаляем..." : "Удалить"}
                        </button>
                      )}
                      {canWithdrawRecipe && (
                        <button
                          type="button"
                          className="btn btn-subtle"
                          onClick={openWithdrawModal}
                          disabled={publishing || deleting || withdrawing || ingredientsSaving}
                        >
                          {withdrawing ? "Отзываем..." : "Отозвать"}
                        </button>
                      )}
                      {canReportRecipe && (
                        <button type="button" className="btn btn-subtle" onClick={openReportModal} disabled={reporting}>
                          Пожаловаться
                        </button>
                      )}
                    </div>

                    {publishError && <p className="recipe-inline-error">{publishError}</p>}
                    {withdrawError && <p className="recipe-inline-error">{withdrawError}</p>}
                    {publishSuccess && <p className="recipes-inline-success">Рецепт опубликован.</p>}
                    {withdrawSuccess && <p className="recipes-inline-success">Публикация снята.</p>}
                    {reportSuccess && <p className="recipes-inline-success">Жалоба отправлена.</p>}
                  </div>
                )}
              </div>

              {showModerationBanner && (
                <p className="recipe-owner-banner">
                  Рецепт снят с публикации из-за жалоб пользователей и ожидает проверки.
                </p>
              )}

              <div className="recipe-meta-grid">
                <p className="recipe-meta-row">
                  <b>Порций:</b> <span>{recipe.servings_count}</span>
                </p>
                <div className="recipe-meta-row">
                  <b>Типы:</b>
                  {recipe.meal_types.map((mealType) => (
                    <span key={mealType} className="recipe-meal-badge">
                      {MEAL_TYPE_LABELS[mealType]}
                    </span>
                  ))}
                </div>
              </div>
            </article>

            <article id="ingredients" ref={ingredientsAnchorRef} className="recipe-card">
              <div className="ingredients-head">
                <h3 className="recipe-metrics-title">Ингредиенты</h3>
                {canEditIngredients && (
                  <div className="ingredients-head-actions">
                    <button type="button" className="btn btn-secondary" onClick={addIngredientRow} disabled={ingredientsSaving}>
                      Добавить ингредиент
                    </button>
                    <button type="button" className="btn btn-primary" onClick={() => void onSaveIngredients()} disabled={ingredientsSaving}>
                      {ingredientsSaving ? "Сохраняем..." : "Сохранить ингредиенты"}
                    </button>
                  </div>
                )}
              </div>

              {ingredientsError && (
                <div className="recipes-form-summary form-error-summary is-error" role="alert">
                  <p className="recipes-form-error-item">{ingredientsError}</p>
                </div>
              )}
              {ingredientsSuccess && <p className="recipes-inline-success">Ингредиенты сохранены.</p>}

              {visibleIngredientRows.length === 0 && <p className="recipes-note">Ингредиентов пока нет</p>}
              {canEditIngredients && visibleIngredientRows.length === 0 && (
                <p className="recipes-note">Добавьте ингредиенты, чтобы увидеть расчёт КБЖУ.</p>
              )}

              {visibleIngredientRows.length > 0 && canEditIngredients && (
                <ul className="ingredients-edit-list">
                  {visibleIngredientRows.map((row) => (
                    <li key={row.localId} className="ingredients-edit-row">
                      <div className="ingredients-row-field">
                        <FoodSearchSelect
                          value={row.food}
                          onChange={(food) => onIngredientFoodChange(row.localId, food)}
                          placeholder="Выберите продукт"
                          disabled={ingredientsSaving}
                        />
                        <div className="ingredients-error-slot">{row.errors?.food && <p className="recipes-field-error">{row.errors.food}</p>}</div>
                      </div>

                      <div className="ingredients-row-field">
                        <input
                          className={`recipes-field-input ${row.errors?.grams ? "is-invalid" : ""}`}
                          type="number"
                          min={0}
                          step="0.1"
                          value={row.grams}
                          onChange={(e) => onIngredientGramsChange(row.localId, e.target.value)}
                          placeholder="Граммы"
                          disabled={ingredientsSaving}
                        />
                        <div className="ingredients-error-slot">{row.errors?.grams && <p className="recipes-field-error">{row.errors.grams}</p>}</div>
                      </div>

                      <button
                        type="button"
                        className="btn btn-subtle ingredients-delete-btn"
                        onClick={() => removeIngredientRow(row.localId)}
                        disabled={ingredientsSaving}
                      >
                        Удалить
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {visibleIngredientRows.length > 0 && !canEditIngredients && (
                <ul className="ingredients-readonly-list">
                  {visibleIngredientRows.map((row) => (
                    <li key={row.localId} className="ingredients-readonly-row">
                      <span>{ingredientLabel(row)}</span>
                      <b>{formatMetric(row.grams)} г</b>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <section className="recipe-metrics-grid" aria-label="Пищевая ценность">
              <article className="recipe-metrics-card">
                <h3 className="recipe-metrics-title">Итого</h3>
                <ul className="recipe-metrics-list">
                  {totalMetrics.map((metric) => (
                    <li key={metric.label} className="recipe-metrics-item">
                      <span className="recipe-metrics-label">{metric.label}</span>
                      <span className="recipe-metrics-value">{metric.value}</span>
                    </li>
                  ))}
                </ul>
              </article>

              <article className="recipe-metrics-card">
                <h3 className="recipe-metrics-title">На порцию</h3>
                <ul className="recipe-metrics-list">
                  {perServingMetrics.map((metric) => (
                    <li key={metric.label} className="recipe-metrics-item">
                      <span className="recipe-metrics-label">{metric.label}</span>
                      <span className="recipe-metrics-value">{metric.value}</span>
                    </li>
                  ))}
                </ul>
              </article>
            </section>
          </>
        )}
      </div>

      <ConfirmModal
        open={deleteModalOpen}
        title="Удалить рецепт"
        message={recipe ? `Удалить рецепт «${recipe.name}»? Это действие нельзя отменить.` : "Удалить рецепт?"}
        confirmText="Удалить"
        loading={deleting}
        errorText={deleteModalError}
        onConfirm={() => void onConfirmDelete()}
        onClose={closeDeleteModal}
      />

      <ConfirmModal
        open={withdrawModalOpen}
        title="Отозвать публикацию"
        message="Отозвать публикацию? Рецепт исчезнет из публичной выдачи."
        confirmText="Отозвать"
        loading={withdrawing}
        errorText={withdrawModalError}
        onConfirm={() => void onConfirmWithdraw()}
        onClose={closeWithdrawModal}
      />

      {reportModalOpen && (
        <div className="recipes-modal-backdrop" role="presentation" onClick={closeReportModal}>
          <div
            className="recipes-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-recipe-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="report-recipe-title" className="recipes-modal-title">
              Пожаловаться на рецепт
            </h2>

            <form className="recipes-form recipes-form-compact" onSubmit={onSubmitReport} noValidate>
              <label className="recipes-field" htmlFor="report_recipe_reason">
                <span className="recipes-field-label">Причина</span>
                <select
                  id="report_recipe_reason"
                  className={`recipes-field-input ${reportErrors.reason ? "is-invalid" : ""}`}
                  value={reportForm.reason}
                  onChange={(e) => updateReportField("reason", e.target.value)}
                  disabled={reporting}
                >
                  <option value="">Выберите причину</option>
                  {REPORT_REASON_OPTIONS.map((reason) => (
                    <option key={reason} value={reason}>
                      {reason}
                    </option>
                  ))}
                </select>
                <div className="recipes-field-error-slot" aria-live="polite">
                  {reportErrors.reason && <p className="recipes-field-error">{reportErrors.reason}</p>}
                </div>
              </label>

              <label className="recipes-field" htmlFor="report_recipe_comment">
                <span className="recipes-field-label">Комментарий (опционально)</span>
                <textarea
                  id="report_recipe_comment"
                  className={`recipes-field-textarea ${reportErrors.comment ? "is-invalid" : ""}`}
                  value={reportForm.comment}
                  onChange={(e) => updateReportField("comment", e.target.value)}
                  placeholder="Опишите проблему"
                  disabled={reporting}
                />
                <div className="recipes-field-error-slot" aria-live="polite">
                  {reportErrors.comment && <p className="recipes-field-error">{reportErrors.comment}</p>}
                </div>
              </label>

              {reportErrors.form && <p className="recipe-inline-error">{reportErrors.form}</p>}

              <div className="recipes-modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeReportModal} disabled={reporting}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={reporting}>
                  {reporting ? "Отправка..." : "Отправить"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
