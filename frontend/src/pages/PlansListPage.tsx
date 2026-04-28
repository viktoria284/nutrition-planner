import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { listPlans } from "../api/plans";
import { Alert } from "../components/Alert";
import { useProfiles } from "../context/ProfilesContext";
import type { PlanListItem } from "../types/plan";
import { formatPlanDate, planTitleWithFallback } from "./plans";
import "./PlansPage.css";

function resolvePlansListError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "Планы не найдены.";
    if (err.status === 409) return "Не удалось получить список планов из-за конфликта данных.";
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

  const isEmpty = !loading && !error && plans.length === 0;
  const isFilteredEmpty = !loading && !error && visiblePlans.length === 0 && filterMode === "active" && activeProfileId !== null;
  const showProfileFilter = activeProfileId !== null;

  const onFilterChange = (mode: PlansFilterMode) => {
    setFilterTouched(true);
    setFilterMode(mode);
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
          <ul className="plans-list">
            {visiblePlans.map((plan) => (
              <li key={plan.id} className="plan-list-item">
                <div className="plan-list-main">
                  <p className="plan-list-title">{planTitleWithFallback(plan.title, plan.start_date)}</p>
                  <div className="plan-list-meta">
                    <span>Даты: {formatPlanDateRange(plan.start_date, plan.days_count)}</span>
                    <span>Дней: {plan.days_count}</span>
                    <span>Приёмов пищи: {plan.meals_per_day}</span>
                  </div>
                  <p className="plan-profile-summary">{formatProfileSnapshot(plan)}</p>
                </div>
                <div className="plan-list-actions">
                  <Link to={`/plans/${plan.id}`} className="btn btn-secondary">
                    Открыть
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
