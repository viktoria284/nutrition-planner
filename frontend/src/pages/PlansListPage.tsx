import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { bulkDeletePlans, deletePlan, listPlans } from "../api/plans";
import { Alert } from "../components/Alert";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { useProfiles } from "../context/ProfilesContext";
import type { PlanListItem } from "../types/plan";
import { formatPlanDate, planTitleWithFallback } from "./plans";
import "./PlansPage.css";

function resolvePlansListError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "Планы не найдены.";
    if (err.status === 409) return "Не удалось получить список планов из-за конфликта данных.";
    if (err.status === 422) return "Проверьте выбранные планы.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить планы.";
}

function formatPlanDateRange(startDateIso: string, daysCount: number): string {
  if (daysCount <= 1) return formatPlanDate(startDateIso);

  const [yearRaw, monthRaw, dayRaw] = startDateIso.split("-");
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return formatPlanDate(startDateIso);
  }

  const start = new Date(Date.UTC(year, month - 1, day));
  start.setUTCDate(start.getUTCDate() + daysCount - 1);
  const endIso = start.toISOString().slice(0, 10);
  return `${formatPlanDate(startDateIso)} — ${formatPlanDate(endIso)}`;
}

function formatProfileSnapshot(plan: PlanListItem): string {
  const profileLabel = plan.profile_name?.trim() || (plan.profile_id ? `Профиль #${plan.profile_id}` : "Без профиля");
  const kcalLabel = typeof plan.target_kcal === "number" ? `${plan.target_kcal} ккал` : "без цели по ккал";
  return `Профиль: ${profileLabel} — ${kcalLabel}`;
}

type PlansFilterMode = "active" | "all";

export function PlansListPage() {
  const { activeProfile, activeProfileId } = useProfiles();
  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<PlansFilterMode>(activeProfileId ? "active" : "all");
  const [filterTouched, setFilterTouched] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [planToDelete, setPlanToDelete] = useState<PlanListItem | null>(null);
  const [deletingOne, setDeletingOne] = useState(false);
  const [deleteOneError, setDeleteOneError] = useState<string | null>(null);

  const [bulkDeleteIds, setBulkDeleteIds] = useState<number[]>([]);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkDeleteError, setBulkDeleteError] = useState<string | null>(null);

  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listPlans();
      setPlans(items);
    } catch (err) {
      setPlans([]);
      setError(resolvePlansListError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  useEffect(() => {
    if (activeProfileId === null) {
      setFilterMode("all");
      return;
    }
    if (!filterTouched) {
      setFilterMode("active");
    }
  }, [activeProfileId, filterTouched]);

  const visiblePlans = useMemo(() => {
    if (filterMode !== "active" || activeProfileId === null) return plans;
    return plans.filter((plan) => plan.profile_id === activeProfileId);
  }, [plans, filterMode, activeProfileId]);

  useEffect(() => {
    setSelectedIds((prev) => {
      const availableIds = new Set(plans.map((plan) => plan.id));
      const next = new Set([...prev].filter((id) => availableIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [plans]);

  const isEmpty = !loading && !error && plans.length === 0;
  const isFilteredEmpty = !loading && !error && visiblePlans.length === 0 && filterMode === "active" && activeProfileId !== null;
  const showProfileFilter = activeProfileId !== null;
  const selectedCount = selectedIds.size;

  const onFilterChange = (mode: PlansFilterMode) => {
    setFilterTouched(true);
    setFilterMode(mode);
  };

  const toggleSelected = (planId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(planId)) next.delete(planId);
      else next.add(planId);
      return next;
    });
  };

  const handleDeleteOne = async () => {
    if (!planToDelete) return;
    setDeletingOne(true);
    setDeleteOneError(null);
    try {
      await deletePlan(planToDelete.id);
      setPlans((prev) => prev.filter((plan) => plan.id !== planToDelete.id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(planToDelete.id);
        return next;
      });
      setPlanToDelete(null);
    } catch (err) {
      setDeleteOneError(resolvePlansListError(err));
    } finally {
      setDeletingOne(false);
    }
  };

  const openBulkDeleteModal = () => {
    if (selectedIds.size === 0) return;
    setBulkDeleteIds([...selectedIds]);
    setBulkDeleteError(null);
  };

  const handleBulkDelete = async () => {
    if (bulkDeleteIds.length === 0) return;
    setBulkDeleting(true);
    setBulkDeleteError(null);
    try {
      await bulkDeletePlans({ plan_ids: bulkDeleteIds });
      const deletedIds = new Set(bulkDeleteIds);
      setPlans((prev) => prev.filter((plan) => !deletedIds.has(plan.id)));
      setSelectedIds(new Set());
      setBulkDeleteIds([]);
    } catch (err) {
      setBulkDeleteError(resolvePlansListError(err));
    } finally {
      setBulkDeleting(false);
    }
  };

  return (
    <section className="plans-page">
      <div className="plans-shell">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Планы питания</h1>
            <p className="plans-subtitle">Создавайте планы вручную или генерируйте автоматически по параметрам.</p>
          </div>
          <div className="plans-head-actions">
            <button type="button" className="btn btn-secondary" disabled={selectedCount < 1} onClick={openBulkDeleteModal}>
              Удалить выбранные
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void loadPlans()} disabled={loading}>
              Обновить
            </button>
            <Link to="/plans/autogenerate" className="btn btn-primary">
              Автоплан
            </Link>
            <Link to="/plans/new" className="btn btn-secondary">
              Создать план
            </Link>
          </div>
        </header>

        {loading && <p className="plans-note">Загрузка планов...</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadPlans()}>
              Повторить
            </button>
          </div>
        )}

        {isEmpty && !isFilteredEmpty && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Планов пока нет</p>
            <p className="plans-empty-subtitle">Создайте первый план, чтобы увидеть календарь по дням.</p>
            <Link to="/plans/autogenerate" className="btn btn-primary">
              Сгенерировать автоматически
            </Link>
            <Link to="/plans/new" className="btn btn-secondary">
              Создать план
            </Link>
          </article>
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="plans-filter-row">
            {showProfileFilter && (
              <>
                <button
                  type="button"
                  className={`plans-filter-chip ${filterMode === "active" ? "is-active" : ""}`}
                  onClick={() => onFilterChange("active")}
                >
                  Планы активного профиля
                </button>
                <button
                  type="button"
                  className={`plans-filter-chip ${filterMode === "all" ? "is-active" : ""}`}
                  onClick={() => onFilterChange("all")}
                >
                  Все планы
                </button>
              </>
            )}
            {!showProfileFilter && (
              <p className="plans-filter-note">Активный профиль не выбран. Показаны все планы.</p>
            )}
          </div>
        )}

        {isFilteredEmpty && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Для выбранного профиля пока нет планов</p>
            <p className="plans-empty-subtitle">Можно создать ручной план или автоплан.</p>
            {activeProfile && <p className="plans-filter-note">Текущий профиль: {activeProfile.name}</p>}
            <Link to="/plans/autogenerate" className="btn btn-primary">
              Сгенерировать автоматически
            </Link>
            <Link to="/plans/new" className="btn btn-secondary">
              Создать план
            </Link>
          </article>
        )}

        {!loading && !error && visiblePlans.length > 0 && (
          <>
            <div className="shopping-lists-toolbar" aria-live="polite">
              <span>{selectedCount > 0 ? `Выбрано: ${selectedCount}` : "Выберите планы для удаления."}</span>
            </div>

            <ul className="plans-list">
              {visiblePlans.map((plan) => {
                const isSelected = selectedIds.has(plan.id);
                return (
                  <li key={plan.id} className={`plan-list-item plan-select-card ${isSelected ? "is-selected" : ""}`}>
                    <label className="shopping-list-card-select">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        aria-label={`Выбрать план «${planTitleWithFallback(plan.title, plan.start_date)}»`}
                        onChange={() => toggleSelected(plan.id)}
                      />
                      <span className="sr-only">Выбрать план</span>
                    </label>

                    <Link to={`/plans/${plan.id}`} className="plan-list-main plan-list-main-link">
                      <p className="plan-list-title">{planTitleWithFallback(plan.title, plan.start_date)}</p>
                      <div className="plan-list-meta">
                        <span>Даты: {formatPlanDateRange(plan.start_date, plan.days_count)}</span>
                        <span>Дней: {plan.days_count}</span>
                        <span>Приёмов пищи: {plan.meals_per_day}</span>
                      </div>
                      <p className="plan-profile-summary">{formatProfileSnapshot(plan)}</p>
                    </Link>
                    <div className="plan-list-actions plan-select-card-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={deletingOne && planToDelete?.id === plan.id}
                        onClick={() => {
                          setDeleteOneError(null);
                          setPlanToDelete(plan);
                        }}
                      >
                        Удалить
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>

      <PlanConfirmModal
        open={planToDelete !== null}
        title="Удалить выбранный план?"
        message="План и его слоты будут удалены. Списки покупок, созданные ранее, останутся отдельными документами."
        confirmText="Удалить"
        loading={deletingOne}
        loadingText="Удаляем..."
        errorText={deleteOneError}
        onClose={() => {
          if (deletingOne) return;
          setPlanToDelete(null);
          setDeleteOneError(null);
        }}
        onConfirm={() => {
          void handleDeleteOne();
        }}
      />

      <PlanConfirmModal
        open={bulkDeleteIds.length > 0}
        title={bulkDeleteIds.length === 1 ? "Удалить выбранный план?" : "Удалить выбранные планы?"}
        message={
          bulkDeleteIds.length === 1
            ? "План и его слоты будут удалены. Списки покупок, созданные ранее, останутся отдельными документами."
            : `Будет удалено планов: ${bulkDeleteIds.length}. Списки покупок, созданные ранее, останутся отдельными документами.`
        }
        confirmText="Удалить"
        loading={bulkDeleting}
        loadingText="Удаляем..."
        errorText={bulkDeleteError}
        onClose={() => {
          if (bulkDeleting) return;
          setBulkDeleteIds([]);
          setBulkDeleteError(null);
        }}
        onConfirm={() => {
          void handleBulkDelete();
        }}
      />
    </section>
  );
}
