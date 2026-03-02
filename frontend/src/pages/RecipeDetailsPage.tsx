import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  deleteRecipe,
  getRecipe,
  publishRecipe,
  reportRecipe,
  withdrawRecipe,
  type MealType,
  type RecipeRead,
} from "../api/recipes";
import { Alert } from "../components/Alert";
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
  const navigate = useNavigate();
  const currentUserId = getCurrentUserIdFromJwt();

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

  const loadRecipe = useCallback(async () => {
    const recipeId = Number(id);
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setRecipe(null);
      setError("Некорректный идентификатор рецепта.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const item = await getRecipe(recipeId);
      setRecipe(item);
    } catch (err) {
      setRecipe(null);
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить рецепт.");
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  useEffect(() => {
    if (!reportSuccess) return undefined;

    const timeoutId = window.setTimeout(() => {
      setReportSuccess(false);
    }, 2600);

    return () => window.clearTimeout(timeoutId);
  }, [reportSuccess]);

  useEffect(() => {
    if (!publishSuccess) return undefined;

    const timeoutId = window.setTimeout(() => {
      setPublishSuccess(false);
    }, 2600);

    return () => window.clearTimeout(timeoutId);
  }, [publishSuccess]);

  useEffect(() => {
    if (!withdrawSuccess) return undefined;

    const timeoutId = window.setTimeout(() => {
      setWithdrawSuccess(false);
    }, 2600);

    return () => window.clearTimeout(timeoutId);
  }, [withdrawSuccess]);

  const isOwner = Boolean(recipe && currentUserId !== null && recipe.owner_user_id === currentUserId);
  const canEditRecipe = Boolean(recipe && isOwner && recipe.source === "private" && recipe.status === "draft");
  const canPublishRecipe = canEditRecipe;
  const canDeleteRecipe = canEditRecipe;
  const canWithdrawRecipe = Boolean(
    recipe && isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const canReportRecipe = Boolean(
    recipe && !isOwner && recipe.source === "community" && recipe.status === "approved" && recipe.is_listed,
  );
  const showModerationBanner = Boolean(recipe && isOwner && recipe.status === "pending" && !recipe.is_listed);

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

  const onPublish = async () => {
    if (!recipe || publishing) return;

    setPublishing(true);
    setPublishError(null);
    setPublishSuccess(false);

    try {
      const updated = await publishRecipe(recipe.id);
      setRecipe(updated);
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
      setRecipe(updated);
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
      setRecipe(updated);
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
                          disabled={publishing || deleting || withdrawing}
                        >
                          {publishing ? "Публикация..." : "Опубликовать"}
                        </button>
                      )}
                      {canEditRecipe && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => navigate(`/recipes/${recipe.id}/edit`)}
                          disabled={publishing || deleting || withdrawing}
                        >
                          Редактировать
                        </button>
                      )}
                      {canDeleteRecipe && (
                        <button
                          type="button"
                          className="btn btn-subtle"
                          onClick={openDeleteModal}
                          disabled={publishing || deleting || withdrawing}
                        >
                          {deleting ? "Удаляем..." : "Удалить"}
                        </button>
                      )}
                      {canWithdrawRecipe && (
                        <button
                          type="button"
                          className="btn btn-subtle"
                          onClick={openWithdrawModal}
                          disabled={publishing || deleting || withdrawing}
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
