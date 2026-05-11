import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { getPlan } from "../api/plans";
import { createShoppingListFromPlan, listShoppingLists } from "../api/shopping";
import { Alert } from "../components/Alert";
import type { PlanRead } from "../types/plan";
import type { ShoppingListSummary } from "../types/shopping";
import "./PlansPage.css";

function resolveError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "План не найден.";
  }
  return err instanceof Error ? err.message : "Не удалось открыть список покупок.";
}

export function PlanShoppingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<PlanRead | null>(null);
  const [shoppingLists, setShoppingLists] = useState<ShoppingListSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const planId = useMemo(() => {
    const parsed = Number(id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [id]);

  useEffect(() => {
    if (!planId) {
      setError("Некорректный идентификатор плана.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getPlan(planId), listShoppingLists()])
      .then(([loadedPlan, loadedLists]) => {
        if (cancelled) return;
        setPlan(loadedPlan);
        setShoppingLists(loadedLists);

        const latestForPlan = loadedLists.find((item) => item.source_plan_ids.includes(planId));
        if (latestForPlan) {
          navigate(`/shopping-lists/${latestForPlan.id}`, { replace: true });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setPlan(null);
        setShoppingLists([]);
        setError(resolveError(err));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [planId, navigate]);

  const handleCreate = async () => {
    if (!planId) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createShoppingListFromPlan({ plan_id: planId });
      navigate(`/shopping-lists/${created.id}`, { replace: true });
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setCreating(false);
    }
  };

  return (
    <section className="plans-page">
      <div className="plans-shell plans-shell-wide">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Список покупок</h1>
            <p className="plans-subtitle">Материализованный список, который можно пересобирать без потери ручных правок.</p>
          </div>
          <div className="plans-head-actions">
            <Link to={planId ? `/plans/${planId}` : "/plans"} className="btn btn-secondary">
              Назад к плану
            </Link>
          </div>
        </header>

        {loading && <p className="plans-note">Проверяем список покупок для плана...</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => window.location.reload()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && !error && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Список покупок ещё не собран</p>
            <p className="plans-empty-subtitle">
              {plan
                ? `План: «${plan.title ?? `${plan.start_date} (${plan.days_count} дн.)`}».`
                : "Соберите первый список из текущего плана."}
            </p>
            {shoppingLists.length > 0 && (
              <p className="plans-note">
                У вас есть другие списки: {shoppingLists.length}. Можно создать отдельный список и для этого плана.
              </p>
            )}
            <button type="button" className="btn btn-primary" onClick={() => void handleCreate()} disabled={creating}>
              {creating ? "Собираем..." : "Собрать список покупок"}
            </button>
          </article>
        )}
      </div>
    </section>
  );
}
