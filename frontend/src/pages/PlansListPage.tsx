import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { listPlans } from "../api/plans";
import { Alert } from "../components/Alert";
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

export function PlansListPage() {
  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const isEmpty = !loading && !error && plans.length === 0;

  return (
    <section className="plans-page">
      <div className="plans-shell">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Планы питания</h1>
            <p className="plans-subtitle">Создавайте планы и открывайте календарную раскладку по дням.</p>
          </div>
          <div className="plans-head-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void loadPlans()} disabled={loading}>
              Обновить
            </button>
            <Link to="/plans/new" className="btn btn-primary">
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

        {isEmpty && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Планов пока нет</p>
            <p className="plans-empty-subtitle">Создайте первый план, чтобы увидеть календарь по дням.</p>
            <Link to="/plans/new" className="btn btn-primary">
              Создать план
            </Link>
          </article>
        )}

        {!loading && !error && plans.length > 0 && (
          <ul className="plans-list">
            {plans.map((plan) => (
              <li key={plan.id} className="plan-list-item">
                <div className="plan-list-main">
                  <p className="plan-list-title">{planTitleWithFallback(plan.title, plan.start_date)}</p>
                  <div className="plan-list-meta">
                    <span>Старт: {formatPlanDate(plan.start_date)}</span>
                    <span>Дней: {plan.days_count}</span>
                    <span>Слотов в день: {plan.meals_per_day}</span>
                  </div>
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
