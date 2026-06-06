import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  addAdminRecipeIngredient,
  deleteAdminRecipeIngredient,
  getAdminRecipe,
  moderateAdminRecipe,
  resolveAdminRecipeReport,
  updateAdminRecipeIngredient,
} from "../api/admin";
import { getFoodServings, type FoodItem, type FoodServingRead } from "../api/foods";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import {
  addIngredient,
  addRecipeFavorite,
  copyRecipe,
  deleteRecipeNote,
  deleteIngredient,
  deleteRecipe,
  getRecipe,
  getRecipeNote,
  publishRecipe,
  reportRecipe,
  resolveRecipeImageSrc,
  removeRecipeFavorite,
  upsertRecipeNote,
  updateIngredient,
  withdrawRecipe,
  type MealType,
  type RecipeIngredientRead,
  type RecipeIngredientUpdate,
  type RecipeRead,
} from "../api/recipes";
import { favoriteAuthor, listFavoriteAuthors, unfavoriteAuthor } from "../api/users";
import { Alert } from "../components/Alert";
import { CustomSelect } from "../components/CustomSelect";
import { FoodSearchSelect, type FoodSearchOption } from "../components/FoodSearchSelect";
import { MarkdownContent } from "../components/MarkdownTextarea";
import { RecipePlaceholder } from "../components/recipes/RecipePlaceholder";
import { getCurrentUserIdFromJwt } from "../utils/auth";
import { formatRoundedNumber, formatTrimmedNumber, toSafeNumber } from "../utils/numberFormat";
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

type RecipeDetailsLocationState = {
  flashMessage?: string;
  adminReturnTo?: string;
  adminReportId?: number;
  adminReportTargetType?: "food" | "recipe";
  adminReportTargetName?: string;
  adminReportQueue?: Array<{
    id: number;
    targetType: "food" | "recipe";
    targetId: number;
    targetName: string;
  }>;
  adminReportQueueIndex?: number;
};

const REPORT_REASON_OPTIONS = ["Неверные данные", "Дубликат", "Спам/мусор", "Оскорбительный контент", "Другое"] as const;
const REPORT_REASON_SELECT_OPTIONS = [
  { value: "", label: "Выберите причину" },
  ...REPORT_REASON_OPTIONS.map((reason) => ({ value: reason, label: reason })),
];

const RECIPE_LOCKED_EDIT_MESSAGE =
  "Опубликованный рецепт нельзя редактировать. Чтобы внести изменения, отзовите публикацию.";

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
  { key: "total_fiber", label: "Клетчатка (г)" },
];

const PER_SERVING_METRICS: Array<{ key: keyof RecipeRead; label: string }> = [
  { key: "per_serving_kcal", label: "Калории (ккал)" },
  { key: "per_serving_protein", label: "Белки (г)" },
  { key: "per_serving_fat", label: "Жиры (г)" },
  { key: "per_serving_carbs", label: "Углеводы (г)" },
  { key: "per_serving_fiber", label: "Клетчатка (г)" },
];

function mapApiStatusToMessage(status: number): string | null {
  if (status === 404) return "Не найдено или нет доступа";
  if (status === 409) return "Конфликт: действие уже выполнено или недопустимо в текущем состоянии";
  if (status === 422) return "Проверьте корректность полей";
  if (status === 400) return "Некорректный запрос";
  if (status === 403) return "Недостаточно прав для выполнения действия";
  if (status === 401) return "Требуется повторный вход";
  return null;
}

function resolveActionError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return mapApiStatusToMessage(err.status) ?? fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

let localRowCounter = 0;

function createLocalId(): string {
  localRowCounter += 1;
  return `row-${Date.now()}-${localRowCounter}`;
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
    const initialMultiplierValue = Number(ingredient.multiplier);
    const hasServingMode = ingredient.serving_id !== null && ingredient.serving_id !== undefined;
    const mode: IngredientMode = hasServingMode ? "serving" : "grams";
    return {
      localId: createLocalId(),
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

function isBlankNewRow(row: IngredientRow): boolean {
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
  const [copying, setCopying] = useState(false);
  const [favoriteUpdating, setFavoriteUpdating] = useState(false);
  const [favoriteAuthorIds, setFavoriteAuthorIds] = useState<Set<number>>(new Set());
  const [favoriteAuthorUpdating, setFavoriteAuthorUpdating] = useState(false);
  const [adminActionLoading, setAdminActionLoading] = useState(false);
  const [adminActionError, setAdminActionError] = useState<string | null>(null);

  const [noteValue, setNoteValue] = useState("");
  const [noteLoading, setNoteLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteDeleting, setNoteDeleting] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [noteSuccess, setNoteSuccess] = useState<string | null>(null);
  const [recipeImageBroken, setRecipeImageBroken] = useState(false);
  const [flashMessage, setFlashMessage] = useState<string | null>(null);
  const locationState = location.state as RecipeDetailsLocationState | null;

  const [ingredientRows, setIngredientRows] = useState<IngredientRow[]>([]);
  const [ingredientsSaving, setIngredientsSaving] = useState(false);
  const [ingredientsError, setIngredientsError] = useState<string | null>(null);
  const [ingredientsSuccess, setIngredientsSuccess] = useState(false);
  const [ingredientDeleteModalOpen, setIngredientDeleteModalOpen] = useState(false);
  const [ingredientDeleteTargetLocalId, setIngredientDeleteTargetLocalId] = useState<string | null>(null);
  const servingsCacheRef = useRef<Map<number, FoodServingRead[]>>(new Map());
  const servingsLoadingRef = useRef<Set<number>>(new Set());
  const [servingsErrorsByFoodId, setServingsErrorsByFoodId] = useState<Record<number, string>>({});
  const [servingsVersion, setServingsVersion] = useState(0);

  const applyRecipePayload = useCallback((payload: RecipeRead) => {
    setRecipe(payload);
    setIngredientRows(buildIngredientRows(payload.ingredients));
    setIngredientDeleteModalOpen(false);
    setIngredientDeleteTargetLocalId(null);
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
    setNoteError(null);
    setNoteSuccess(null);

    try {
      const item = await getRecipe(recipeId);
      applyRecipePayload(item);
      setRecipeImageBroken(false);

      setNoteLoading(true);
      try {
        const notePayload = await getRecipeNote(recipeId);
        setNoteValue(notePayload.note ?? "");
      } catch (noteErr) {
        setNoteValue("");
        setNoteError(resolveActionError(noteErr, "Не удалось загрузить заметку."));
      } finally {
        setNoteLoading(false);
      }
    } catch (err) {
      setRecipe(null);
      setIngredientRows([]);
      setNoteValue("");
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(resolveActionError(err, "Не удалось загрузить рецепт."));
      }
    } finally {
      setLoading(false);
    }
  }, [id, applyRecipePayload]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  useEffect(() => {
    const state = (location.state as RecipeDetailsLocationState | null) ?? null;
    if (!state?.flashMessage) return;
    setFlashMessage(state.flashMessage);
    navigate(`${location.pathname}${location.hash}`, { replace: true, state: null });
  }, [location.hash, location.pathname, location.state, navigate]);

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

  useEffect(() => {
    if (!noteSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setNoteSuccess(null), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [noteSuccess]);

  useEffect(() => {
    if (!flashMessage) return undefined;
    const timeoutId = window.setTimeout(() => setFlashMessage(null), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [flashMessage]);

  const isOwner = Boolean(recipe && currentUserId !== null && recipe.owner_user_id === currentUserId);
  const isAdminRecipeEditor = Boolean(
    recipe &&
      (user?.role === "admin" || user?.role === "superadmin") &&
      locationState?.adminReturnTo === "/admin/recipes",
  );
  const canEditRecipe = Boolean(recipe && isOwner && recipe.source === "private" && recipe.status === "draft");
  const canPublishRecipe = canEditRecipe;
  const canDeleteRecipe = canEditRecipe;
  const canEditIngredients = canEditRecipe || isAdminRecipeEditor;
  const canWithdrawRecipe = Boolean(
    recipe && isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const canReportRecipe = Boolean(
    recipe && !isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const canFavoriteRecipe = Boolean(recipe);
  const canCopyRecipe = Boolean(
    recipe &&
      !isOwner &&
      recipe.source === "community" &&
      recipe.status === "approved" &&
      recipe.is_listed,
  );
  const currentUserIdNumber = Number(currentUserId);
  const canFavoriteAuthor = Boolean(
    recipe &&
      recipe.author_id !== null &&
      recipe.author_username &&
      Number.isFinite(currentUserIdNumber) &&
      recipe.author_id !== currentUserIdNumber,
  );
  const isAuthorFavorite = Boolean(recipe && recipe.author_id !== null && favoriteAuthorIds.has(recipe.author_id));
  const showModerationBanner = Boolean(recipe && isOwner && recipe.status === "pending" && !recipe.is_listed);
  const showAdminActionBar = Boolean((user?.role === "admin" || user?.role === "superadmin") && locationState?.adminReturnTo);
  const adminReportQueue = locationState?.adminReportQueue ?? [];
  const adminReportQueueIndex = locationState?.adminReportQueueIndex ?? -1;
  const adminPreviousReport =
    adminReportQueueIndex > 0 && adminReportQueueIndex < adminReportQueue.length ? adminReportQueue[adminReportQueueIndex - 1] : null;
  const adminNextReport =
    adminReportQueueIndex >= 0 && adminReportQueueIndex < adminReportQueue.length - 1
      ? adminReportQueue[adminReportQueueIndex + 1]
      : null;

  const loadFavoriteAuthors = useCallback(async () => {
    try {
      const items = await listFavoriteAuthors();
      setFavoriteAuthorIds(new Set(items.map((item) => item.id)));
    } catch {
      setFavoriteAuthorIds(new Set());
    }
  }, []);

  useEffect(() => {
    void loadFavoriteAuthors();
  }, [loadFavoriteAuthors]);

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
      value: formatRoundedNumber(recipe[item.key] as string | number),
    }));
  }, [recipe]);

  const perServingMetrics = useMemo(() => {
    if (!recipe) return [];
    const perServingWeight = (() => {
      const direct = recipe.per_serving_grams;
      if (direct !== undefined && direct !== null) return direct;
      const servings = Number(recipe.servings_count);
      if (!Number.isFinite(servings) || servings <= 0) return 0;
      return toSafeNumber(recipe.total_grams) / servings;
    })();

    const metrics = PER_SERVING_METRICS.map((item) => ({
      label: item.label,
      value: formatRoundedNumber(recipe[item.key] as string | number),
    }));

    return [
      { label: "Вес (г)", value: formatRoundedNumber(perServingWeight) },
      ...metrics,
    ];
  }, [recipe]);

  const visibleIngredientRows = useMemo(
    () => ingredientRows.filter((row) => !row.markedForDelete),
    [ingredientRows],
  );
  const servingsCache = servingsCacheRef.current;

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
        [foodId]: resolveActionError(err, "Не удалось загрузить порции"),
      }));
    } finally {
      servingsLoadingRef.current.delete(foodId);
      setServingsVersion((prev) => prev + 1);
    }
  }, []);

  useEffect(() => {
    for (const row of visibleIngredientRows) {
      if (row.mode === "serving" && row.food_id) {
        void ensureFoodServingsLoaded(row.food_id);
      }
    }
  }, [ensureFoodServingsLoaded, visibleIngredientRows]);

  useEffect(() => {
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
  }, [servingsVersion]);

  const ingredientDeleteTarget = useMemo(
    () => ingredientRows.find((row) => row.localId === ingredientDeleteTargetLocalId) ?? null,
    [ingredientRows, ingredientDeleteTargetLocalId],
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
    setIngredientRows((prev) => [
      ...prev,
      { localId: createLocalId(), food: null, mode: "grams", grams: "", multiplier: "", initialMode: "grams" },
    ]);
    setIngredientsError(null);
    setIngredientsSuccess(false);
  };

  const openIngredientDeleteModal = (localId: string) => {
    if (!canEditIngredients || ingredientsSaving) return;
    setIngredientDeleteTargetLocalId(localId);
    setIngredientDeleteModalOpen(true);
  };

  const closeIngredientDeleteModal = () => {
    if (ingredientsSaving) return;
    setIngredientDeleteModalOpen(false);
    setIngredientDeleteTargetLocalId(null);
  };

  const onConfirmIngredientDelete = () => {
    if (!canEditIngredients || ingredientsSaving || !ingredientDeleteTargetLocalId) return;
    const localId = ingredientDeleteTargetLocalId;

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
    closeIngredientDeleteModal();
  };

  const onIngredientFoodChange = (localId: string, food: FoodItem | null) => {
    if (food?.id) void ensureFoodServingsLoaded(food.id);

    updateIngredientRow(localId, (row) => {
      const isSameFood = row.food_id === food?.id;
      return {
        ...row,
        food: food
          ? {
              id: food.id,
              name: food.name,
              brand: food.brand ?? null,
            }
          : null,
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
        errors: {
          ...row.errors,
          grams: undefined,
          serving: undefined,
          multiplier: undefined,
        },
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

  const onSaveIngredients = async () => {
    if (!recipe || ingredientsSaving || !canEditIngredients) return;

    setIngredientsError(null);
    setIngredientsSuccess(false);

    let hasValidationErrors = false;
    const validatedRows = ingredientRows.map((row) => {
      if (row.markedForDelete) return { ...row, errors: {} };
      if (isBlankNewRow(row)) return { ...row, errors: {} };

      const errors: IngredientRowErrors = {};
      if (!row.food_id) errors.food = "Выберите продукт.";

      if (row.mode === "grams") {
        const gramsRaw = row.grams.trim();
        const grams = Number(gramsRaw);
        if (!gramsRaw || !Number.isFinite(grams) || grams <= 0) errors.grams = "Введите число > 0.";
      } else {
        const multiplierRaw = row.multiplier.trim();
        const multiplier = Number(multiplierRaw);
        if (!row.serving_id) errors.serving = "Выберите порцию.";
        if (!multiplierRaw || !Number.isFinite(multiplier) || multiplier <= 0) errors.multiplier = "Введите число > 0.";
      }

      if (errors.food || errors.grams || errors.serving || errors.multiplier) hasValidationErrors = true;
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
          await (isAdminRecipeEditor ? deleteAdminRecipeIngredient(recipe.id, row.id) : deleteIngredient(recipe.id, row.id));
        }
      }

      for (const row of validatedRows) {
        if (row.markedForDelete || isBlankNewRow(row)) continue;
        if (!row.food_id) continue;

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

          await (isAdminRecipeEditor ? updateAdminRecipeIngredient(recipe.id, row.id, payload) : updateIngredient(recipe.id, row.id, payload));
          continue;
        }

        if (row.mode === "grams") {
          const grams = Number(row.grams.trim());
          await (isAdminRecipeEditor
            ? addAdminRecipeIngredient(recipe.id, { food_id: row.food_id, grams })
            : addIngredient(recipe.id, { food_id: row.food_id, grams }));
        } else {
          const multiplier = Number(row.multiplier.trim());
          const payload = {
            food_id: row.food_id,
            serving_id: row.serving_id,
            multiplier,
          };
          await (isAdminRecipeEditor ? addAdminRecipeIngredient(recipe.id, payload) : addIngredient(recipe.id, payload));
        }
      }

      const refreshed = await (isAdminRecipeEditor ? getAdminRecipe(recipe.id) : getRecipe(recipe.id));
      applyRecipePayload(refreshed);
      setIngredientsSuccess(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setIngredientsError(RECIPE_LOCKED_EDIT_MESSAGE);
      } else {
        setIngredientsError(resolveActionError(err, "Не удалось сохранить ингредиенты."));
      }
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
      setPublishError(resolveActionError(err, "Не удалось опубликовать рецепт."));
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
      setDeleteModalError(resolveActionError(err, "Не удалось удалить рецепт."));
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
      const message = resolveActionError(err, "Не удалось отозвать рецепт.");
      setWithdrawError(message);
      setWithdrawModalError(message);
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
      setReportErrors({ form: resolveActionError(err, "Не удалось отправить жалобу.") });
    } finally {
      setReporting(false);
    }
  };

  const onCopyRecipe = async () => {
    if (!recipe || copying) return;
    setCopying(true);
    setNoteError(null);
    try {
      const copied = await copyRecipe(recipe.id);
      navigate(`/recipes/${copied.id}`, {
        replace: true,
        state: { flashMessage: "Рецепт скопирован в ваши рецепты." },
      });
    } catch (err) {
      setNoteError(resolveActionError(err, "Не удалось скопировать рецепт."));
    } finally {
      setCopying(false);
    }
  };

  const onToggleFavorite = async () => {
    if (!recipe || favoriteUpdating) return;
    const nextFavorite = !recipe.is_favorite;
    setFavoriteUpdating(true);
    setRecipe((prev) => (prev ? { ...prev, is_favorite: nextFavorite } : prev));
    try {
      if (nextFavorite) {
        await addRecipeFavorite(recipe.id);
      } else {
        await removeRecipeFavorite(recipe.id);
      }
    } catch (err) {
      setRecipe((prev) => (prev ? { ...prev, is_favorite: recipe.is_favorite } : prev));
      setError(resolveActionError(err, "Не удалось обновить избранное."));
    } finally {
      setFavoriteUpdating(false);
    }
  };

  const onToggleFavoriteAuthor = async () => {
    if (!recipe || recipe.author_id === null || !canFavoriteAuthor || favoriteAuthorUpdating) return;
    setFavoriteAuthorUpdating(true);
    try {
      if (favoriteAuthorIds.has(recipe.author_id)) {
        await unfavoriteAuthor(recipe.author_id);
      } else {
        await favoriteAuthor(recipe.author_id);
      }
      await loadFavoriteAuthors();
    } catch (err) {
      setError(resolveActionError(err, "Не удалось обновить избранных авторов."));
    } finally {
      setFavoriteAuthorUpdating(false);
    }
  };

  const onSaveNote = async () => {
    if (!recipe || noteSaving || noteLoading) return;
    const normalized = noteValue.trim();
    if (!normalized) {
      setNoteError("Введите текст заметки перед сохранением.");
      return;
    }

    setNoteSaving(true);
    setNoteError(null);
    setNoteSuccess(null);
    try {
      const result = await upsertRecipeNote(recipe.id, normalized);
      setNoteValue(result.note ?? "");
      setNoteSuccess("Заметка сохранена.");
    } catch (err) {
      setNoteError(resolveActionError(err, "Не удалось сохранить заметку."));
    } finally {
      setNoteSaving(false);
    }
  };

  const onDeleteNote = async () => {
    if (!recipe || noteDeleting || noteLoading || !noteValue.trim()) return;
    setNoteDeleting(true);
    setNoteError(null);
    setNoteSuccess(null);
    try {
      await deleteRecipeNote(recipe.id);
      setNoteValue("");
      setNoteSuccess("Заметка удалена.");
    } catch (err) {
      setNoteError(resolveActionError(err, "Не удалось удалить заметку."));
    } finally {
      setNoteDeleting(false);
    }
  };

  const onAdminToggleRecipeVisibility = async () => {
    if (!recipe || adminActionLoading) return;
    setAdminActionLoading(true);
    setAdminActionError(null);
    try {
      await moderateAdminRecipe(recipe.id, recipe.is_listed ? "hide" : "restore");
      const refreshed = await getRecipe(recipe.id);
      applyRecipePayload(refreshed);
    } catch (err) {
      setAdminActionError(resolveActionError(err, "Не удалось выполнить действие администратора."));
    } finally {
      setAdminActionLoading(false);
    }
  };

  const onAdminResolveRecipeReport = async (resolution: "no_action" | "content_hidden") => {
    if (!locationState?.adminReportId || locationState.adminReportTargetType !== "recipe" || adminActionLoading) return;
    setAdminActionLoading(true);
    setAdminActionError(null);
    try {
      await resolveAdminRecipeReport(locationState.adminReportId, resolution);
      if (recipe && resolution === "content_hidden") {
        const refreshed = await getRecipe(recipe.id).catch(() => null);
        if (refreshed) applyRecipePayload(refreshed);
      }
    } catch (err) {
      setAdminActionError(resolveActionError(err, "Не удалось закрыть жалобу."));
    } finally {
      setAdminActionLoading(false);
    }
  };

  const buildAdminReportState = (
    item: NonNullable<typeof adminNextReport>,
    indexOffset: -1 | 1,
  ): RecipeDetailsLocationState => ({
    ...(locationState ?? {}),
    adminReturnTo: locationState?.adminReturnTo ?? "/admin/reports",
    adminReportId: item.id,
    adminReportTargetType: item.targetType,
    adminReportTargetName: item.targetName,
    adminReportQueue,
    adminReportQueueIndex: adminReportQueueIndex + indexOffset,
  });

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
            <Link to="/recipes/public" className="btn btn-secondary">
              Публичные рецепты
            </Link>
          </div>
        </header>

        {loading && <p className="recipes-note">Загрузка...</p>}
        {flashMessage && <p className="recipes-inline-success">{flashMessage}</p>}

        {showAdminActionBar && (
          <div className="admin-context-bar">
            <div>
              <b>Админский просмотр</b>
              <p>{locationState?.adminReportTargetName ? `Жалоба: ${locationState.adminReportTargetName}` : "Объект открыт из админки."}</p>
              {!recipe && !loading && <p className="admin-context-error">Объект не найден или уже удалён. Жалобу всё ещё можно закрыть.</p>}
              {adminActionError && <p className="admin-context-error">{adminActionError}</p>}
            </div>
            <div className="admin-context-actions">
              <Link to={locationState?.adminReturnTo ?? "/admin/reports"} className="btn btn-secondary">
                Вернуться без решения
              </Link>
              {recipe && !locationState?.adminReportId && (
                <button type="button" className="btn btn-secondary" onClick={() => void onAdminToggleRecipeVisibility()} disabled={adminActionLoading}>
                  {recipe.is_listed ? "Скрыть объект" : "Восстановить объект"}
                </button>
              )}
              {locationState?.adminReportTargetType === "recipe" && locationState.adminReportId && recipe && (
                <>
                  <button type="button" className="btn btn-secondary" onClick={() => void onAdminResolveRecipeReport("content_hidden")} disabled={adminActionLoading}>
                    Скрыть объект и закрыть жалобу
                  </button>
                  <button type="button" className="btn btn-primary" onClick={() => void onAdminResolveRecipeReport("no_action")} disabled={adminActionLoading}>
                    Оставить объект и закрыть жалобу
                  </button>
                </>
              )}
              {locationState?.adminReportTargetType === "recipe" && locationState.adminReportId && !recipe && !loading && (
                <button type="button" className="btn btn-primary" onClick={() => void onAdminResolveRecipeReport("no_action")} disabled={adminActionLoading}>
                  Закрыть жалобу
                </button>
              )}
              {adminPreviousReport && (
                <Link
                  to={adminPreviousReport.targetType === "food" ? `/foods/${adminPreviousReport.targetId}` : `/recipes/${adminPreviousReport.targetId}`}
                  state={buildAdminReportState(adminPreviousReport, -1)}
                  className="btn btn-secondary"
                >
                  Предыдущая жалоба
                </Link>
              )}
              {adminNextReport && (
                <Link
                  to={adminNextReport.targetType === "food" ? `/foods/${adminNextReport.targetId}` : `/recipes/${adminNextReport.targetId}`}
                  state={buildAdminReportState(adminNextReport, 1)}
                  className="btn btn-secondary"
                >
                  Следующая жалоба
                </Link>
              )}
            </div>
          </div>
        )}

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
                <div className="recipe-header-main">
                  <div className="recipe-cover">
                    {recipe.image_url && !recipeImageBroken ? (
                      <img
                        src={resolveRecipeImageSrc(recipe.image_url) ?? undefined}
                        alt={`Фото блюда: ${recipe.name}`}
                        className="recipe-cover-image"
                        onError={() => setRecipeImageBroken(true)}
                      />
                    ) : (
                      <RecipePlaceholder name={recipe.name} mealTypes={recipe.meal_types} className="recipe-cover-fallback" />
                    )}
                  </div>

                  <h2 className="recipe-card-title">{recipe.name}</h2>
                  {recipe.description && <p className="recipe-description">{recipe.description}</p>}
                </div>

                {(canFavoriteRecipe || canPublishRecipe || canEditRecipe || canDeleteRecipe || canWithdrawRecipe || canReportRecipe || canCopyRecipe) && (
                  <div className="recipe-action-block">
                    <div className="recipe-action-row">
                      <button
                        type="button"
                        className={recipe.is_favorite ? "btn btn-primary" : "btn btn-secondary"}
                        onClick={() => void onToggleFavorite()}
                        disabled={favoriteUpdating}
                      >
                        {favoriteUpdating
                          ? "Сохраняем..."
                          : recipe.is_favorite
                            ? "В избранном"
                            : "В избранное"}
                      </button>
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
                      {canCopyRecipe && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => void onCopyRecipe()}
                          disabled={copying}
                        >
                          {copying ? "Копируем..." : "Скопировать себе"}
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
                {recipe.author_username && (
                  <div className="recipe-meta-row recipe-meta-row-author">
                    <b>Автор:</b>{" "}
                    {recipe.author_id === null ? (
                      <span>{recipe.author_username}</span>
                    ) : (
                      <Link
                        to={`/recipes/public?author=${recipe.author_id}${recipe.author_username ? `&author_username=${encodeURIComponent(recipe.author_username)}` : ""}`}
                        className="recipe-author-link"
                      >
                        @{recipe.author_username}
                      </Link>
                    )}
                    {canFavoriteAuthor && (
                      <button
                        type="button"
                        className={isAuthorFavorite ? "btn btn-secondary btn-sm" : "btn btn-primary btn-sm"}
                        onClick={() => void onToggleFavoriteAuthor()}
                        disabled={favoriteAuthorUpdating}
                      >
                        {favoriteAuthorUpdating
                          ? "Сохраняем..."
                          : isAuthorFavorite
                            ? "Автор в избранном"
                            : "Добавить автора в избранное"}
                      </button>
                    )}
                  </div>
                )}
                <p className="recipe-meta-row">
                  <b>Порций:</b> <span>{recipe.servings_count}</span>
                </p>
                {typeof recipe.cook_time_minutes === "number" && (
                  <p className="recipe-meta-row">
                    <b>Время приготовления:</b> <span>{recipe.cook_time_minutes} мин</span>
                  </p>
                )}
                <div className="recipe-meta-row">
                  <b>Типы:</b>
                  {recipe.meal_types.map((mealType) => (
                    <span key={mealType} className="recipe-meal-badge">
                      {MEAL_TYPE_LABELS[mealType]}
                    </span>
                  ))}
                </div>
              </div>

              {!recipe.instructions && !(recipe.steps && recipe.steps.length > 0) && isOwner && (
                <p className="recipes-note">Способ приготовления пока не указан.</p>
              )}
              {recipe.instructions && (
                <section className="recipe-instructions">
                  <h3 className="recipe-metrics-title">Способ приготовления</h3>
                  <MarkdownContent value={recipe.instructions} />
                </section>
              )}
              {Array.isArray(recipe.steps) && recipe.steps.length > 0 && (
                <section className="recipe-steps-display">
                  <h3 className="recipe-metrics-title">Шаги приготовления</h3>
                  <ol className="recipe-steps-display-list">
                    {recipe.steps
                      .slice()
                      .sort((left, right) => {
                        const leftPosition = Number.isFinite(left.position) ? left.position : Number.MAX_SAFE_INTEGER;
                        const rightPosition = Number.isFinite(right.position) ? right.position : Number.MAX_SAFE_INTEGER;
                        return leftPosition - rightPosition;
                      })
                      .map((step, index) => {
                        const displayNumber =
                          typeof step.position === "number" && step.position > 0 ? step.position : index + 1;
                        return (
                          <li key={step.id} className="recipe-steps-display-item">
                            <div className="recipe-step-number" aria-hidden="true">
                              {displayNumber}
                            </div>
                            <div className="recipe-step-content">
                              <div className="recipe-steps-display-text">
                                <MarkdownContent value={step.text} />
                              </div>
                              {step.image_url && (
                                <div className="recipe-step-image-wrap">
                                  <img
                                    src={resolveRecipeImageSrc(step.image_url) ?? undefined}
                                    alt={`Шаг ${displayNumber}`}
                                    className="recipe-step-image"
                                    onError={(event) => {
                                      event.currentTarget.style.display = "none";
                                    }}
                                  />
                                </div>
                              )}
                              {step.note && (
                                <div className="recipe-step-note">
                                  <p className="recipe-step-note-title">Совет</p>
                                  <MarkdownContent value={step.note} />
                                </div>
                              )}
                            </div>
                          </li>
                        );
                      })}
                  </ol>
                </section>
              )}
            </article>

            <article className="recipe-card">
              <h3 className="recipe-metrics-title">Мои заметки</h3>
              <p className="recipes-note">Заметка видна только вам.</p>
              {noteError && (
                <div className="recipes-form-summary form-error-summary is-error" role="alert">
                  <p className="recipes-form-error-item">{noteError}</p>
                </div>
              )}
              {noteSuccess && <p className="recipes-inline-success">{noteSuccess}</p>}
              <label className="recipes-field" htmlFor="recipe-note-textarea">
                <textarea
                  id="recipe-note-textarea"
                  className="recipes-field-textarea"
                  value={noteValue}
                  onChange={(event) => {
                    setNoteValue(event.target.value);
                    setNoteError(null);
                    setNoteSuccess(null);
                  }}
                  placeholder="Добавьте личную заметку к рецепту"
                  disabled={noteLoading || noteSaving || noteDeleting}
                />
              </label>
              <div className="recipes-form-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void onDeleteNote()}
                  disabled={noteLoading || noteSaving || noteDeleting || !noteValue.trim()}
                >
                  {noteDeleting ? "Удаляем..." : "Удалить заметку"}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void onSaveNote()}
                  disabled={noteLoading || noteSaving || noteDeleting}
                >
                  {noteSaving ? "Сохраняем..." : "Сохранить заметку"}
                </button>
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
              {recipe && isOwner && !canEditRecipe && (
                <p className="recipes-note">{RECIPE_LOCKED_EDIT_MESSAGE}</p>
              )}

              {visibleIngredientRows.length === 0 && <p className="recipes-note">Ингредиентов пока нет</p>}
              {canEditIngredients && visibleIngredientRows.length === 0 && (
                <p className="recipes-note">Добавьте ингредиенты, чтобы увидеть расчёт КБЖУ.</p>
              )}

              {visibleIngredientRows.length > 0 && canEditIngredients && (
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
                          <div className="ingredients-error-slot">{row.errors?.food && <p className="recipes-field-error">{row.errors.food}</p>}</div>
                        </div>

                        <button
                          type="button"
                          className="btn btn-subtle ingredients-delete-icon-btn"
                          onClick={() => openIngredientDeleteModal(row.localId)}
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
                              onChange={(e) => onIngredientGramsChange(row.localId, e.target.value)}
                              placeholder="Граммы"
                              disabled={ingredientsSaving}
                            />
                            <div className="ingredients-error-slot">{row.errors?.grams && <p className="recipes-field-error">{row.errors.grams}</p>}</div>
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
                                onChange={(e) => onIngredientMultiplierChange(row.localId, e.target.value)}
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

              {visibleIngredientRows.length > 0 && !canEditIngredients && (
                <ul className="ingredients-readonly-list">
                  {visibleIngredientRows.map((row) => (
                    <li key={row.localId} className="ingredients-readonly-row">
                      <span>
                        {ingredientLabel(row)}
                        {row.mode === "serving" && row.serving_id
                          ? (() => {
                              const serving = row.food_id
                                ? (servingsCache.get(row.food_id) ?? []).find((item) => item.id === row.serving_id)
                                : null;
                              const servingName = serving?.name ?? "порция";
                              return ` · ${servingName} × ${row.multiplier || "1"}`;
                            })()
                          : ""}
                      </span>
                      <b>{formatTrimmedNumber(row.grams)} г</b>
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

      <ConfirmModal
        open={ingredientDeleteModalOpen}
        title="Удалить ингредиент"
        message={
          ingredientDeleteTarget
            ? `Удалить ингредиент «${ingredientLabel(ingredientDeleteTarget)}» из рецепта?`
            : "Удалить ингредиент?"
        }
        confirmText="Удалить"
        loading={false}
        onConfirm={onConfirmIngredientDelete}
        onClose={closeIngredientDeleteModal}
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
                <CustomSelect
                  id="report_recipe_reason"
                  value={reportForm.reason}
                  options={REPORT_REASON_SELECT_OPTIONS}
                  onChange={(nextValue) => updateReportField("reason", nextValue)}
                  disabled={reporting}
                  invalid={Boolean(reportErrors.reason)}
                  triggerClassName="recipes-field-input"
                  ariaLabel="Причина жалобы"
                />
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
