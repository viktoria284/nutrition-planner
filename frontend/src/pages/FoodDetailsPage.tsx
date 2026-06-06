import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { moderateAdminFood, resolveAdminFoodReport } from "../api/admin";
import { ApiError } from "../api/http";
import {
  createServing,
  deleteFood,
  deleteServing,
  getFood,
  listServings,
  publishFood,
  reportFood,
  withdrawFood,
  updateFood,
  type FoodItem,
  type FoodItemUpdatePayload,
  type FoodServing,
} from "../api/foods";
import { Alert } from "../components/Alert";
import { CustomSelect } from "../components/CustomSelect";
import { useAuth } from "../auth/useAuth";
import { FOOD_CATEGORIES, FOOD_CATEGORY_LABELS, isFoodCategory, type FoodCategory } from "../types/foodCategory";
import { getCurrentUserIdFromJwt } from "../utils/auth";
import "./FoodsPage.css";

type ServingForm = {
  name: string;
  grams: string;
};

type ServingFormErrors = {
  name?: string;
  grams?: string;
  form?: string;
};

type FoodEditForm = {
  name: string;
  brand: string;
  category: FoodCategory;
  kcal: string;
  protein: string;
  fat: string;
  carbs: string;
  fiber: string;
};

type FoodEditErrors = {
  name?: string;
  brand?: string;
  category?: string;
  kcal?: string;
  protein?: string;
  fat?: string;
  carbs?: string;
  fiber?: string;
  form?: string[];
};

const REPORT_REASON_OPTIONS = [
  "Неверные КБЖУ",
  "Дубликат",
  "Спам/мусор",
  "Оскорбительный контент",
  "Другое",
] as const;

const REPORT_REASON_SELECT_OPTIONS = [
  { value: "", label: "Выберите причину" },
  ...REPORT_REASON_OPTIONS.map((reason) => ({ value: reason, label: reason })),
];

const FOOD_CATEGORY_SELECT_OPTIONS = FOOD_CATEGORIES.map((category) => ({
  value: category,
  label: FOOD_CATEGORY_LABELS[category],
}));

type ReportForm = {
  reason: string;
  comment: string;
};

type ReportFormErrors = {
  reason?: string;
  comment?: string;
  form?: string;
};

type FoodDetailsLocationState = {
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

const EMPTY_SERVING_FORM: ServingForm = {
  name: "",
  grams: "",
};

const EMPTY_EDIT_FORM: FoodEditForm = {
  name: "",
  brand: "",
  category: "other",
  kcal: "",
  protein: "",
  fat: "",
  carbs: "",
  fiber: "",
};

const EMPTY_REPORT_FORM: ReportForm = {
  reason: "",
  comment: "",
};

function formatNutrient(value: number | string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

function formatFoodValueForInput(value: number | string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  if (Number.isInteger(numeric)) return String(numeric);
  return String(numeric);
}

function resolveApiMessage(err: unknown, fallback: string, notFoundMessage: string): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Требуется повторный вход.";
    if (err.status === 404) return notFoundMessage;
  }
  return err instanceof Error ? err.message : fallback;
}

function validateServingForm(form: ServingForm): { errors: ServingFormErrors; payload: { name: string; grams: number } | null } {
  const errors: ServingFormErrors = {};

  const name = form.name.trim();
  if (!name) errors.name = "Введите название порции.";

  const gramsRaw = form.grams.trim();
  if (!gramsRaw) {
    errors.grams = "Введите число ≥ 1";
  } else {
    const grams = Number(gramsRaw);
    if (!Number.isFinite(grams) || grams < 1) errors.grams = "Введите число ≥ 1";
  }

  if (Object.keys(errors).length > 0) {
    errors.form = "Проверьте поля формы.";
    return { errors, payload: null };
  }

  return {
    errors: {},
    payload: { name, grams: Number(gramsRaw) },
  };
}

function validateFoodEditForm(form: FoodEditForm): { errors: FoodEditErrors; payload: FoodItemUpdatePayload | null } {
  const errors: FoodEditErrors = {};
  const formErrors: string[] = [];

  const name = form.name.trim();
  const brand = form.brand.trim();
  const category = form.category;

  if (!name) {
    errors.name = "invalid";
    formErrors.push("Введите название продукта.");
  }
  if (!isFoodCategory(category)) {
    errors.category = "invalid";
    formErrors.push("Выберите корректный раздел магазина.");
  }

  const numericKeys: Array<keyof Pick<FoodEditForm, "kcal" | "protein" | "fat" | "carbs">> = [
    "kcal",
    "protein",
    "fat",
    "carbs",
  ];

  const parsed: Partial<Record<"kcal" | "protein" | "fat" | "carbs", number>> = {};
  let hasInvalidNumeric = false;
  let hasNegative = false;
  let hasMacroUpper = false;
  let hasKcalUpper = false;
  let hasFiberUpper = false;

  for (const key of numericKeys) {
    const raw = form[key].trim();
    if (!raw) {
      errors[key] = "invalid";
      hasInvalidNumeric = true;
      continue;
    }

    const value = Number(raw);
    if (!Number.isFinite(value)) {
      errors[key] = "invalid";
      hasInvalidNumeric = true;
      continue;
    }

    if (value < 0) {
      errors[key] = "invalid";
      hasNegative = true;
    }

    if (key === "kcal" && value > 1000) {
      errors[key] = "invalid";
      hasKcalUpper = true;
    }

    if ((key === "protein" || key === "fat" || key === "carbs") && value > 100) {
      errors[key] = "invalid";
      hasMacroUpper = true;
    }

    parsed[key] = value;
  }

  const fiberRaw = form.fiber.trim();
  const fiberValue = fiberRaw ? Number(fiberRaw) : 0;
  if (!Number.isFinite(fiberValue)) {
    errors.fiber = "invalid";
    hasInvalidNumeric = true;
  } else {
    if (fiberValue < 0) {
      errors.fiber = "invalid";
      hasNegative = true;
    }
    if (fiberValue > 100) {
      errors.fiber = "invalid";
      hasFiberUpper = true;
    }
  }

  if (hasInvalidNumeric) formErrors.push("Заполните корректные числовые значения КБЖУ.");
  if (hasNegative) formErrors.push("Значения не могут быть отрицательными.");
  if (hasMacroUpper) formErrors.push("Белки, жиры и углеводы должны быть не больше 100 г на 100 г продукта.");
  if (hasKcalUpper) formErrors.push("Калорийность должна быть не больше 1000 ккал на 100 г.");
  if (hasFiberUpper) formErrors.push("Клетчатка должна быть не больше 100 г на 100 г продукта.");

  if (formErrors.length > 0) {
    errors.form = formErrors;
    return { errors, payload: null };
  }

  return {
    errors: {},
    payload: {
      name,
      brand: brand || null,
      category,
      kcal: parsed.kcal as number,
      protein: parsed.protein as number,
      fat: parsed.fat as number,
      carbs: parsed.carbs as number,
      fiber: fiberValue,
    },
  };
}

function toEditForm(food: FoodItem): FoodEditForm {
  return {
    name: food.name,
    brand: food.brand ?? "",
    category: food.category,
    kcal: formatFoodValueForInput(food.kcal),
    protein: formatFoodValueForInput(food.protein),
    fat: formatFoodValueForInput(food.fat),
    carbs: formatFoodValueForInput(food.carbs),
    fiber: formatFoodValueForInput(food.fiber),
  };
}

function validateReportForm(form: ReportForm): { errors: ReportFormErrors; reason: string | null } {
  const errors: ReportFormErrors = {};

  const reason = form.reason;
  const comment = form.comment.trim();

  if (!reason) errors.reason = "Выберите причину.";
  if (reason === "Другое" && !comment) errors.comment = "Для причины «Другое» добавьте комментарий.";

  if (Object.keys(errors).length > 0) {
    return { errors, reason: null };
  }

  return {
    errors: {},
    reason: `${reason}${comment ? `: ${comment}` : ""}`,
  };
}

type ConfirmModalProps = {
  open: boolean;
  title: string;
  message: string;
  confirmText: string;
  loading: boolean;
  errorText?: string | null;
  confirmClassName?: string;
  onConfirm: () => void;
  onClose: () => void;
};

function ConfirmModal({
  open,
  title,
  message,
  confirmText,
  loading,
  errorText = null,
  confirmClassName = "btn btn-primary",
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div
      className="foods-modal-backdrop"
      role="presentation"
      onClick={() => {
        if (!loading) onClose();
      }}
    >
      <div
        className="foods-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="foods-modal-title">{title}</h2>
        <p className="foods-modal-text">{message}</p>
        {errorText && <Alert text={errorText} />}

        <div className="foods-create-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button type="button" className={confirmClassName} onClick={onConfirm} disabled={loading}>
            {loading ? "Подтверждаем..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

export function FoodDetailsPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const currentUserId = user?.id ?? getCurrentUserIdFromJwt();
  const locationState = location.state as FoodDetailsLocationState | null;

  const [food, setFood] = useState<FoodItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [servings, setServings] = useState<FoodServing[]>([]);
  const [servingsLoading, setServingsLoading] = useState(false);
  const [servingsError, setServingsError] = useState<string | null>(null);
  const [servingsReloadSeq, setServingsReloadSeq] = useState(0);

  const [servingForm, setServingForm] = useState<ServingForm>(EMPTY_SERVING_FORM);
  const [servingErrors, setServingErrors] = useState<ServingFormErrors>({});
  const [creatingServing, setCreatingServing] = useState(false);
  const [deletingServingId, setDeletingServingId] = useState<number | null>(null);
  const [servingToDelete, setServingToDelete] = useState<FoodServing | null>(null);
  const [servingDeleteError, setServingDeleteError] = useState<string | null>(null);

  const [reportingFood, setReportingFood] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reportForm, setReportForm] = useState<ReportForm>(EMPTY_REPORT_FORM);
  const [reportFormErrors, setReportFormErrors] = useState<ReportFormErrors>({});

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState<FoodEditForm>(EMPTY_EDIT_FORM);
  const [editErrors, setEditErrors] = useState<FoodEditErrors>({});
  const [savingFood, setSavingFood] = useState(false);
  const [deletingFood, setDeletingFood] = useState(false);
  const [foodActionError, setFoodActionError] = useState<string | null>(null);
  const [publishingFood, setPublishingFood] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState(false);
  const [withdrawingFood, setWithdrawingFood] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawSuccess, setWithdrawSuccess] = useState(false);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteModalError, setDeleteModalError] = useState<string | null>(null);
  const [withdrawModalOpen, setWithdrawModalOpen] = useState(false);
  const [withdrawModalError, setWithdrawModalError] = useState<string | null>(null);
  const [adminActionLoading, setAdminActionLoading] = useState(false);
  const [adminActionError, setAdminActionError] = useState<string | null>(null);

  const refreshServings = () => setServingsReloadSeq((prev) => prev + 1);
  const canEditFood = Boolean(food && food.source === "private" && food.status === "draft");
  const isFoodOwner = Boolean(food && currentUserId !== null && food.owner_user_id === currentUserId);
  const canWithdrawFood = Boolean(
    food && food.source === "community" && food.status === "approved" && food.is_listed === true && isFoodOwner,
  );
  const canReportFood = Boolean(food && food.source === "community" && (currentUserId === null || !isFoodOwner));
  const showAdminActionBar = Boolean((user?.role === "admin" || user?.role === "superadmin") && locationState?.adminReturnTo);
  const adminReportQueue = locationState?.adminReportQueue ?? [];
  const adminReportQueueIndex = locationState?.adminReportQueueIndex ?? -1;
  const adminPreviousReport =
    adminReportQueueIndex > 0 && adminReportQueueIndex < adminReportQueue.length ? adminReportQueue[adminReportQueueIndex - 1] : null;
  const adminNextReport =
    adminReportQueueIndex >= 0 && adminReportQueueIndex < adminReportQueue.length - 1
      ? adminReportQueue[adminReportQueueIndex + 1]
      : null;

  useEffect(() => {
    if (!id) {
      setFood(null);
      setLoading(false);
      setError("Некорректный id продукта.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setReportSuccess(false);
    setReportingFood(false);
    setReportModalOpen(false);
    setReportForm(EMPTY_REPORT_FORM);
    setReportFormErrors({});
    setFoodActionError(null);
    setEditModalOpen(false);
    setPublishError(null);
    setPublishSuccess(false);
    setPublishingFood(false);
    setWithdrawError(null);
    setWithdrawSuccess(false);
    setWithdrawingFood(false);
    setDeleteModalOpen(false);
    setDeleteModalError(null);
    setWithdrawModalOpen(false);
    setWithdrawModalError(null);
    setServingToDelete(null);
    setServingDeleteError(null);

    getFood(id)
      .then((item) => {
        if (cancelled) return;
        setFood(item);
      })
      .catch((err) => {
        if (cancelled) return;
        setFood(null);
        setError(resolveApiMessage(err, "Не удалось загрузить продукт.", "Продукт не найден."));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id) {
      setServings([]);
      setServingsLoading(false);
      setServingsError("Некорректный id продукта.");
      return;
    }

    let cancelled = false;
    setServingsLoading(true);
    setServingsError(null);

    listServings(id)
      .then((items) => {
        if (cancelled) return;
        setServings(items);
      })
      .catch((err) => {
        if (cancelled) return;
        setServings([]);
        setServingsError(resolveApiMessage(err, "Не удалось загрузить порции.", "Продукт не найден."));
      })
      .finally(() => {
        if (cancelled) return;
        setServingsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, servingsReloadSeq]);

  useEffect(() => {
    if (!reportSuccess) return undefined;

    const timeoutId = window.setTimeout(() => {
      setReportSuccess(false);
    }, 2800);

    return () => window.clearTimeout(timeoutId);
  }, [reportSuccess]);

  const updateServingField = (field: keyof ServingForm, value: string) => {
    setServingForm((prev) => ({ ...prev, [field]: value }));
    setServingErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onCreateServing = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!id) {
      setServingErrors({ form: "Некорректный id продукта." });
      return;
    }

    const { errors, payload } = validateServingForm(servingForm);
    if (!payload) {
      setServingErrors(errors);
      return;
    }

    setCreatingServing(true);
    setServingErrors({});

    try {
      await createServing(id, payload);
      setServingForm(EMPTY_SERVING_FORM);
      refreshServings();
    } catch (err) {
      setServingErrors({
        form: resolveApiMessage(err, "Не удалось добавить порцию.", "Продукт не найден."),
      });
    } finally {
      setCreatingServing(false);
    }
  };

  const openDeleteServingModal = (serving: FoodServing) => {
    if (deletingServingId !== null) return;
    setServingDeleteError(null);
    setServingToDelete(serving);
  };

  const closeDeleteServingModal = () => {
    if (deletingServingId !== null) return;
    setServingToDelete(null);
    setServingDeleteError(null);
  };

  const onConfirmDeleteServing = async () => {
    if (!servingToDelete || deletingServingId !== null) return;

    setDeletingServingId(servingToDelete.id);
    setServingDeleteError(null);
    setServingErrors((prev) => {
      if (!prev.form) return prev;
      const next = { ...prev };
      delete next.form;
      return next;
    });

    try {
      await deleteServing(servingToDelete.id);
      setServingToDelete(null);
      refreshServings();
    } catch (err) {
      const message = resolveApiMessage(err, "Не удалось удалить порцию.", "Порция не найдена.");
      setServingDeleteError(message);
      setServingErrors({ form: message });
    } finally {
      setDeletingServingId(null);
    }
  };

  const openReportModal = () => {
    if (!food || reportingFood || !canReportFood) return;
    setReportForm(EMPTY_REPORT_FORM);
    setReportFormErrors({});
    setReportModalOpen(true);
  };

  const closeReportModal = () => {
    if (reportingFood) return;
    setReportModalOpen(false);
    setReportFormErrors({});
  };

  const updateReportField = (field: keyof ReportForm, value: string) => {
    setReportForm((prev) => ({ ...prev, [field]: value }));
    setReportFormErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onSubmitReport = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!food) {
      setReportFormErrors({ form: "Продукт не найден." });
      return;
    }

    const { errors, reason } = validateReportForm(reportForm);
    if (!reason) {
      setReportFormErrors(errors);
      return;
    }

    setReportingFood(true);
    setReportFormErrors({});
    setReportSuccess(false);

    try {
      await reportFood(food.id, { reason });
      setReportModalOpen(false);
      setReportForm(EMPTY_REPORT_FORM);
      setReportSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setReportFormErrors({ form: "Нельзя жаловаться на свой продукт" });
        } else if (err.status === 409) {
          setReportFormErrors({ form: "Вы уже отправляли жалобу" });
        } else {
          setReportFormErrors({ form: "Не удалось отправить жалобу" });
        }
      } else {
        setReportFormErrors({ form: "Не удалось отправить жалобу" });
      }
    } finally {
      setReportingFood(false);
    }
  };

  const openEditModal = () => {
    if (!food) return;
    setEditForm(toEditForm(food));
    setEditErrors({});
    setFoodActionError(null);
    setEditModalOpen(true);
  };

  const closeEditModal = () => {
    if (savingFood) return;
    setEditModalOpen(false);
    setEditErrors({});
  };

  const updateEditField = (field: keyof FoodEditForm, value: string) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
    setEditErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onSaveFood = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!food) {
      setEditErrors({ form: ["Продукт не найден."] });
      return;
    }

    const { errors, payload } = validateFoodEditForm(editForm);
    if (!payload) {
      setEditErrors(errors);
      return;
    }

    setSavingFood(true);
    setEditErrors({});

    try {
      const updated = await updateFood(food.id, payload);
      setFood(updated);
      setEditModalOpen(false);
      setFoodActionError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setEditErrors({ form: ["Этот продукт нельзя редактировать (только личные черновики)."] });
        } else if (err.status === 404) {
          setEditErrors({ form: ["Продукт не найден"] });
        } else {
          setEditErrors({ form: ["Не удалось сохранить изменения."] });
        }
      } else {
        setEditErrors({ form: ["Не удалось сохранить изменения."] });
      }
    } finally {
      setSavingFood(false);
    }
  };

  const openDeleteModal = () => {
    if (!food || deletingFood || !canEditFood) return;
    setDeleteModalError(null);
    setDeleteModalOpen(true);
  };

  const closeDeleteModal = () => {
    if (deletingFood) return;
    setDeleteModalOpen(false);
    setDeleteModalError(null);
  };

  const onConfirmDeleteFood = async () => {
    if (!food || deletingFood) return;

    setDeletingFood(true);
    setFoodActionError(null);
    setDeleteModalError(null);

    try {
      await deleteFood(food.id);
      navigate("/foods");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          const message = "Этот продукт нельзя редактировать (только личные черновики).";
          setFoodActionError(message);
          setDeleteModalError(message);
        } else if (err.status === 404) {
          const message = "Продукт не найден";
          setFoodActionError(message);
          setDeleteModalError(message);
        } else {
          const message = "Не удалось удалить продукт.";
          setFoodActionError(message);
          setDeleteModalError(message);
        }
      } else {
        const message = "Не удалось удалить продукт.";
        setFoodActionError(message);
        setDeleteModalError(message);
      }
    } finally {
      setDeletingFood(false);
    }
  };

  const onPublishFood = async () => {
    if (!food || publishingFood) return;

    setPublishingFood(true);
    setPublishError(null);
    setPublishSuccess(false);
    setWithdrawError(null);
    setWithdrawSuccess(false);
    setFoodActionError(null);

    try {
      const published = await publishFood(food.id);
      setFood(published);
      setEditModalOpen(false);
      setPublishSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setPublishError("Этот продукт уже опубликован или не может быть опубликован.");
        } else if (err.status === 404) {
          setPublishError("Продукт не найден.");
        } else {
          setPublishError("Не удалось опубликовать продукт.");
        }
      } else {
        setPublishError("Не удалось опубликовать продукт.");
      }
    } finally {
      setPublishingFood(false);
    }
  };

  const openWithdrawModal = () => {
    if (!canWithdrawFood || withdrawingFood) return;
    setWithdrawModalError(null);
    setWithdrawModalOpen(true);
  };

  const closeWithdrawModal = () => {
    if (withdrawingFood) return;
    setWithdrawModalOpen(false);
    setWithdrawModalError(null);
  };

  const onConfirmWithdrawFood = async () => {
    if (!food || withdrawingFood) return;

    setWithdrawingFood(true);
    setWithdrawError(null);
    setWithdrawSuccess(false);
    setWithdrawModalError(null);

    try {
      const updated = await withdrawFood(food.id);
      setFood(updated);
      setPublishSuccess(false);
      setWithdrawSuccess(true);
      setWithdrawModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          const message = "Нельзя отозвать";
          setWithdrawError(message);
          setWithdrawModalError(message);
        } else if (err.status === 403) {
          const message = "Нет прав";
          setWithdrawError(message);
          setWithdrawModalError(message);
        } else {
          const message = "Ошибка";
          setWithdrawError(message);
          setWithdrawModalError(message);
        }
      } else {
        const message = "Ошибка";
        setWithdrawError(message);
        setWithdrawModalError(message);
      }
    } finally {
      setWithdrawingFood(false);
    }
  };

  const onAdminToggleFoodVisibility = async () => {
    if (!food || adminActionLoading) return;
    setAdminActionLoading(true);
    setAdminActionError(null);
    try {
      const updated = await moderateAdminFood(food.id, food.is_listed ? "hide" : "restore");
      setFood(updated);
    } catch (err) {
      setAdminActionError(resolveApiMessage(err, "Не удалось выполнить действие администратора.", "Не удалось выполнить действие администратора."));
    } finally {
      setAdminActionLoading(false);
    }
  };

  const onAdminResolveFoodReport = async (resolution: "no_action" | "content_hidden") => {
    if (!locationState?.adminReportId || locationState.adminReportTargetType !== "food" || adminActionLoading) return;
    setAdminActionLoading(true);
    setAdminActionError(null);
    try {
      const resolved = await resolveAdminFoodReport(locationState.adminReportId, resolution);
      if (food && resolution === "content_hidden") {
        setFood((prev) => (prev ? { ...prev, is_listed: false } : prev));
      }
      void resolved;
    } catch (err) {
      setAdminActionError(resolveApiMessage(err, "Не удалось закрыть жалобу.", "Не удалось закрыть жалобу."));
    } finally {
      setAdminActionLoading(false);
    }
  };

  const buildAdminReportState = (
    item: NonNullable<typeof adminNextReport>,
    indexOffset: -1 | 1,
  ): FoodDetailsLocationState => ({
    ...(locationState ?? {}),
    adminReturnTo: locationState?.adminReturnTo ?? "/admin/reports",
    adminReportId: item.id,
    adminReportTargetType: item.targetType,
    adminReportTargetName: item.targetName,
    adminReportQueue,
    adminReportQueueIndex: adminReportQueueIndex + indexOffset,
  });

  return (
    <section className="foods-page">
      <div className="foods-shell">
        <div className="foods-details-head">
          <Link to="/foods" className="btn btn-secondary">
            Назад
          </Link>
        </div>

        {showAdminActionBar && (
          <div className="admin-context-bar">
            <div>
              <b>Админский просмотр</b>
              <p>{locationState?.adminReportTargetName ? `Жалоба: ${locationState.adminReportTargetName}` : "Объект открыт из админки."}</p>
              {!food && !loading && <p className="admin-context-error">Объект не найден или уже удалён. Жалобу всё ещё можно закрыть.</p>}
              {adminActionError && <p className="admin-context-error">{adminActionError}</p>}
            </div>
            <div className="admin-context-actions">
              <Link to={locationState?.adminReturnTo ?? "/admin/reports"} className="btn btn-secondary">
                Вернуться без решения
              </Link>
              {food && !locationState?.adminReportId && (
                <button type="button" className="btn btn-secondary" onClick={() => void onAdminToggleFoodVisibility()} disabled={adminActionLoading}>
                  {food.is_listed ? "Скрыть объект" : "Восстановить объект"}
                </button>
              )}
              {locationState?.adminReportTargetType === "food" && locationState.adminReportId && food && (
                <>
                  <button type="button" className="btn btn-secondary" onClick={() => void onAdminResolveFoodReport("content_hidden")} disabled={adminActionLoading}>
                    Скрыть объект и закрыть жалобу
                  </button>
                  <button type="button" className="btn btn-primary" onClick={() => void onAdminResolveFoodReport("no_action")} disabled={adminActionLoading}>
                    Оставить объект и закрыть жалобу
                  </button>
                </>
              )}
              {locationState?.adminReportTargetType === "food" && locationState.adminReportId && !food && !loading && (
                <button type="button" className="btn btn-primary" onClick={() => void onAdminResolveFoodReport("no_action")} disabled={adminActionLoading}>
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

        {loading && <p className="foods-note">Загрузка...</p>}
        {!loading && error && <Alert text={error} />}

        {!loading && !error && food && (
          <article className="food-details-card">
            <div className="food-details-top">
              <div className="food-details-heading">
                <h1 className="food-details-title">{food.name}</h1>
                {food.brand && <p className="food-details-brand">{food.brand}</p>}
                <p className="food-details-brand">{FOOD_CATEGORY_LABELS[food.category]}</p>
              </div>

              {(canEditFood || canWithdrawFood || canReportFood) && (
                <div className="food-details-actions">
                  <div className="food-details-actions-row">
                    {canEditFood && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={onPublishFood}
                        disabled={publishingFood || deletingFood || withdrawingFood}
                      >
                        {publishingFood ? "Публикация..." : "Опубликовать"}
                      </button>
                    )}
                    {canEditFood && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={openEditModal}
                        disabled={deletingFood || publishingFood || withdrawingFood}
                      >
                        Редактировать
                      </button>
                    )}
                    {canEditFood && (
                      <button
                        type="button"
                        className="btn btn-subtle"
                        onClick={openDeleteModal}
                        disabled={deletingFood || publishingFood || withdrawingFood}
                      >
                        {deletingFood ? "Удаляем..." : "Удалить"}
                      </button>
                    )}
                    {canWithdrawFood && (
                      <button
                        type="button"
                        className="btn btn-subtle"
                        onClick={openWithdrawModal}
                        disabled={withdrawingFood || deletingFood || publishingFood}
                      >
                        {withdrawingFood ? "Отзываем..." : "Отозвать публикацию"}
                      </button>
                    )}
                    {canReportFood && (
                      <button
                        type="button"
                        className="btn btn-subtle"
                        onClick={openReportModal}
                        disabled={reportingFood || withdrawingFood}
                      >
                        Пожаловаться
                      </button>
                    )}
                  </div>
                  {publishError && <p className="food-report-error">{publishError}</p>}
                  {withdrawError && <p className="food-report-error">{withdrawError}</p>}
                  {foodActionError && <p className="food-report-error">{foodActionError}</p>}
                  {reportSuccess && <p className="food-report-success-inline">Жалоба отправлена</p>}
                </div>
              )}
            </div>

            <p className="food-details-subtitle">Нутриенты на 100 г</p>
            {publishSuccess && (
              <p className="food-publish-success">
                Продукт опубликован в сообществе. После публикации редактирование и удаление недоступны.
              </p>
            )}
            {withdrawSuccess && <p className="food-publish-success">Публикация отозвана</p>}

            <dl className="food-nutrients">
              <div className="food-nutrients-row">
                <dt>Калории</dt>
                <dd>{formatNutrient(food.kcal)} ккал</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Белки</dt>
                <dd>{formatNutrient(food.protein)} г</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Жиры</dt>
                <dd>{formatNutrient(food.fat)} г</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Углеводы</dt>
                <dd>{formatNutrient(food.carbs)} г</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Клетчатка</dt>
                <dd>{formatNutrient(food.fiber)} г</dd>
              </div>
            </dl>
          </article>
        )}

        {!loading && !error && food && (
          <article className="food-details-card servings-card">
            <div className="servings-head">
              <h2 className="servings-title">Порции</h2>
            </div>

            {servingsLoading && <p className="foods-note">Загрузка...</p>}

            {!servingsLoading && servingsError && (
              <div className="servings-error-block">
                <Alert text={servingsError} />
                <button type="button" className="btn btn-secondary" onClick={refreshServings}>
                  Повторить
                </button>
              </div>
            )}

            {!servingsLoading && !servingsError && servings.length === 0 && <p className="foods-note">Порций пока нет</p>}

            {!servingsLoading && !servingsError && servings.length > 0 && (
              <ul className="servings-list">
                {servings.map((serving) => (
                  <li key={serving.id} className="serving-row">
                    <p className="serving-line">
                      {serving.name} — {formatNutrient(serving.grams)} г
                    </p>
                    <button
                      type="button"
                      className="btn btn-secondary serving-delete-btn"
                      onClick={() => openDeleteServingModal(serving)}
                      disabled={deletingServingId !== null}
                    >
                      {deletingServingId === serving.id ? "Удаляем..." : "Удалить"}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {servingErrors.form && <Alert text={servingErrors.form} />}

            {canEditFood && (
              <form className="serving-form" onSubmit={onCreateServing} noValidate>
                <h3 className="serving-form-title">Добавить порцию</h3>

                <div className="serving-form-grid">
                  <label className="foods-field" htmlFor="serving_name">
                    <span className="foods-field-label">Название</span>
                    <input
                      id="serving_name"
                      className={`foods-field-input ${servingErrors.name ? "is-invalid" : ""}`}
                      type="text"
                      value={servingForm.name}
                      onChange={(e) => updateServingField("name", e.target.value)}
                      placeholder="Например, 1 штука"
                    />
                    {servingErrors.name && <p className="foods-field-error">{servingErrors.name}</p>}
                  </label>

                  <label className="foods-field" htmlFor="serving_grams">
                    <span className="foods-field-label">Граммы</span>
                    <input
                      id="serving_grams"
                      className={`foods-field-input ${servingErrors.grams ? "is-invalid" : ""}`}
                      type="number"
                      min={1}
                      step="any"
                      value={servingForm.grams}
                      onChange={(e) => updateServingField("grams", e.target.value)}
                      placeholder="120"
                    />
                    {servingErrors.grams && <p className="foods-field-error">{servingErrors.grams}</p>}
                  </label>
                </div>

                <div className="foods-create-actions">
                  <button type="submit" className="btn btn-primary" disabled={creatingServing || deletingServingId !== null}>
                    {creatingServing ? "Добавляем..." : "Добавить порцию"}
                  </button>
                </div>
              </form>
            )}
          </article>
        )}
      </div>

      <ConfirmModal
        open={Boolean(servingToDelete)}
        title="Удалить порцию"
        message={
          servingToDelete
            ? `Удалить порцию «${servingToDelete.name}»? Это действие нельзя отменить.`
            : "Удалить порцию? Это действие нельзя отменить."
        }
        confirmText="Удалить"
        loading={deletingServingId !== null}
        errorText={servingDeleteError}
        confirmClassName="btn btn-primary"
        onConfirm={onConfirmDeleteServing}
        onClose={closeDeleteServingModal}
      />

      {reportModalOpen && (
        <div className="foods-modal-backdrop" role="presentation" onClick={closeReportModal}>
          <div
            className="foods-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-food-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="report-food-title" className="foods-modal-title">
              Пожаловаться
            </h2>

            <form className="foods-create-form" onSubmit={onSubmitReport} noValidate>
              <label className="foods-field" htmlFor="report_food_reason">
                <span className="foods-field-label">Причина</span>
                <CustomSelect
                  id="report_food_reason"
                  value={reportForm.reason}
                  options={REPORT_REASON_SELECT_OPTIONS}
                  onChange={(value) => updateReportField("reason", value)}
                  invalid={Boolean(reportFormErrors.reason)}
                  ariaLabel="Причина жалобы"
                  triggerClassName="foods-field-input"
                />
                {reportFormErrors.reason && <p className="foods-field-error">{reportFormErrors.reason}</p>}
              </label>

              <label className="foods-field" htmlFor="report_food_comment">
                <span className="foods-field-label">Комментарий</span>
                <textarea
                  id="report_food_comment"
                  className={`foods-field-textarea ${reportFormErrors.comment ? "is-invalid" : ""}`}
                  value={reportForm.comment}
                  onChange={(e) => updateReportField("comment", e.target.value)}
                  placeholder="Опишите проблему (необязательно)"
                />
                {reportFormErrors.comment && <p className="foods-field-error">{reportFormErrors.comment}</p>}
              </label>

              {reportFormErrors.form && <p className="foods-modal-error-text">{reportFormErrors.form}</p>}

              <div className="foods-create-actions">
                <button type="button" className="btn btn-secondary" onClick={closeReportModal} disabled={reportingFood}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={reportingFood}>
                  {reportingFood ? "Отправка..." : "Отправить"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editModalOpen && (
        <div className="foods-modal-backdrop" role="presentation" onClick={closeEditModal}>
          <div
            className="foods-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-food-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="edit-food-title" className="foods-modal-title">
              Редактировать продукт
            </h2>

            {editErrors.form && editErrors.form.length > 0 && (
              <div className="foods-form-errors" role="alert">
                {editErrors.form.map((message, index) => (
                  <p key={`${message}-${index}`} className="foods-form-error-item">
                    {message}
                  </p>
                ))}
              </div>
            )}

            <form className="foods-create-form" onSubmit={onSaveFood} noValidate>
              <label className="foods-field" htmlFor="edit_food_name">
                <span className="foods-field-label">Название</span>
                <input
                  id="edit_food_name"
                  className={`foods-field-input ${editErrors.name ? "is-invalid" : ""}`}
                  type="text"
                  value={editForm.name}
                  onChange={(e) => updateEditField("name", e.target.value)}
                  placeholder="Например, Кефир 2.5%"
                  autoFocus
                />
              </label>

              <label className="foods-field" htmlFor="edit_food_brand">
                <span className="foods-field-label">Brand (опционально)</span>
                <input
                  id="edit_food_brand"
                  className={`foods-field-input ${editErrors.brand ? "is-invalid" : ""}`}
                  type="text"
                  value={editForm.brand}
                  onChange={(e) => updateEditField("brand", e.target.value)}
                  placeholder="Например, Простоквашино"
                />
              </label>

              <label className="foods-field" htmlFor="edit_food_category">
                <span className="foods-field-label">Раздел магазина</span>
                <CustomSelect
                  id="edit_food_category"
                  value={editForm.category}
                  options={FOOD_CATEGORY_SELECT_OPTIONS}
                  onChange={(value) => updateEditField("category", value as FoodCategory)}
                  invalid={Boolean(editErrors.category)}
                  ariaLabel="Раздел магазина"
                  triggerClassName="foods-field-input"
                />
              </label>

              <div className="foods-grid">
                <label className="foods-field" htmlFor="edit_food_kcal">
                  <span className="foods-field-label">Калории (ккал)</span>
                  <input
                    id="edit_food_kcal"
                    className={`foods-field-input ${editErrors.kcal ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={editForm.kcal}
                    onChange={(e) => updateEditField("kcal", e.target.value)}
                    placeholder="0"
                  />
                </label>

                <label className="foods-field" htmlFor="edit_food_protein">
                  <span className="foods-field-label">Белки (г)</span>
                  <input
                    id="edit_food_protein"
                    className={`foods-field-input ${editErrors.protein ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={editForm.protein}
                    onChange={(e) => updateEditField("protein", e.target.value)}
                    placeholder="0"
                  />
                </label>

                <label className="foods-field" htmlFor="edit_food_fat">
                  <span className="foods-field-label">Жиры (г)</span>
                  <input
                    id="edit_food_fat"
                    className={`foods-field-input ${editErrors.fat ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={editForm.fat}
                    onChange={(e) => updateEditField("fat", e.target.value)}
                    placeholder="0"
                  />
                </label>

                <label className="foods-field" htmlFor="edit_food_carbs">
                  <span className="foods-field-label">Углеводы (г)</span>
                  <input
                    id="edit_food_carbs"
                    className={`foods-field-input ${editErrors.carbs ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={editForm.carbs}
                    onChange={(e) => updateEditField("carbs", e.target.value)}
                    placeholder="0"
                  />
                </label>

                <label className="foods-field" htmlFor="edit_food_fiber">
                  <span className="foods-field-label">Клетчатка (г)</span>
                  <input
                    id="edit_food_fiber"
                    className={`foods-field-input ${editErrors.fiber ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    max={100}
                    step="any"
                    value={editForm.fiber}
                    onChange={(e) => updateEditField("fiber", e.target.value)}
                    placeholder="0"
                  />
                </label>
              </div>

              <div className="foods-create-actions">
                <button type="button" className="btn btn-secondary" onClick={closeEditModal} disabled={savingFood}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingFood}>
                  {savingFood ? "Сохраняем..." : "Сохранить"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmModal
        open={deleteModalOpen}
        title="Удалить продукт"
        message={food ? `Удалить продукт «${food.name}»? Это действие нельзя отменить.` : "Удалить продукт? Это действие нельзя отменить."}
        confirmText="Удалить"
        loading={deletingFood}
        errorText={deleteModalError}
        confirmClassName="btn btn-primary"
        onConfirm={onConfirmDeleteFood}
        onClose={closeDeleteModal}
      />

      <ConfirmModal
        open={withdrawModalOpen}
        title="Отозвать публикацию"
        message="Отозвать публикацию? Продукт исчезнет из поиска."
        confirmText="Отозвать"
        loading={withdrawingFood}
        errorText={withdrawModalError}
        confirmClassName="btn btn-primary"
        onConfirm={onConfirmWithdrawFood}
        onClose={closeWithdrawModal}
      />
    </section>
  );
}
