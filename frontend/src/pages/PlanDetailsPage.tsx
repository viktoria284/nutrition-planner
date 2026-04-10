import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { getPlan, regeneratePlanDay } from "../api/plans";
import { getRecipe, listRecipes, type RecipeRead } from "../api/recipes";
import { EditPlanSlotModal } from "../components/plans/EditPlanSlotModal";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { Alert } from "../components/Alert";
import type { PlanDay, PlanRead, PlanSlot } from "../types/plan";
import { formatDecimal, formatPlanDate, planTitleWithFallback } from "./plans";
import "./PlansPage.css";

function resolvePlanDetailsError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "План не найден.";
    if (err.status === 409) return "Данные плана в конфликтном состоянии. Попробуйте обновить страницу.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить план.";
}

function resolveRecipeListError(err: unknown): string {
  if (err instanceof ApiError && err.status === 401) return "Нужно снова войти, чтобы загрузить список рецептов.";
  return err instanceof Error ? err.message : "Не удалось загрузить рецепты для выбора.";
}

function findSlotByIndex(slots: PlanSlot[], slotIndex: number): PlanSlot | null {
  const slot = slots.find((item) => item.slot_index === slotIndex);
  return slot ?? null;
}

function resolveRegenerateDayError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно войти в систему.";
    if (err.status === 404) return "План или слот не найден.";
    if (err.status === 422) return "Недостаточно рецептов для перегенерации дня.";
  }
  return "Не удалось перегенерировать день. Попробуйте ещё раз.";
}

function buildDaySlotsSignature(day: PlanDay): string {
  return day.slots
    .slice()
    .sort((left, right) => left.slot_index - right.slot_index)
    .map((slot) => `${slot.slot_index}:${slot.recipe_id ?? "null"}:${slot.servings_multiplier}:${slot.pinned ? 1 : 0}`)
    .join("|");
}

export function PlanDetailsPage() {
  const { id } = useParams<{ id: string }>();

  const [plan, setPlan] = useState<PlanRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [recipesError, setRecipesError] = useState<string | null>(null);
  const [recipeNamesById, setRecipeNamesById] = useState<Record<number, string>>({});

  const [editingSlot, setEditingSlot] = useState<PlanSlot | null>(null);
  const [dayToRegenerate, setDayToRegenerate] = useState<PlanDay | null>(null);
  const [regeneratingDay, setRegeneratingDay] = useState(false);
  const [regenerateDayError, setRegenerateDayError] = useState<string | null>(null);
  const [pageNotice, setPageNotice] = useState<string | null>(null);

  const loadPlan = useCallback(async () => {
    if (!id) {
      setPlan(null);
      setLoading(false);
      setError("Некорректный идентификатор плана.");
      return;
    }

    setLoading(true);
    setError(null);
    setIsNotFound(false);

    try {
      const payload = await getPlan(id);
      setPlan(payload);
    } catch (err) {
      setPlan(null);
      if (err instanceof ApiError && err.status === 404) {
        setIsNotFound(true);
      } else {
        setError(resolvePlanDetailsError(err));
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true);
    setRecipesError(null);
    try {
      const items = await listRecipes({ includePublic: true });
      setRecipes(items);
      setRecipeNamesById((prev) => {
        const next = { ...prev };
        for (const recipe of items) next[recipe.id] = recipe.name;
        return next;
      });
    } catch (err) {
      setRecipes([]);
      setRecipesError(resolveRecipeListError(err));
    } finally {
      setRecipesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlan();
  }, [loadPlan]);

  useEffect(() => {
    void loadRecipes();
  }, [loadRecipes]);

  useEffect(() => {
    if (!plan) setEditingSlot(null);
  }, [plan]);

  useEffect(() => {
    if (!plan) {
      setDayToRegenerate(null);
      setRegenerateDayError(null);
    }
  }, [plan]);

  useEffect(() => {
    if (!plan) return;

    const recipeIds = Array.from(
      new Set(
        plan.slots
          .map((slot) => slot.recipe_id)
          .filter((recipeId): recipeId is number => recipeId !== null),
      ),
    );
    const missingIds = recipeIds.filter((recipeId) => !recipeNamesById[recipeId]);
    if (missingIds.length === 0) return;

    let cancelled = false;
    void Promise.all(
      missingIds.map(async (recipeId) => {
        try {
          const recipe = await getRecipe(recipeId);
          return { id: recipeId, name: recipe.name };
        } catch {
          return { id: recipeId, name: `Рецепт #${recipeId}` };
        }
      }),
    ).then((pairs) => {
      if (cancelled) return;
      setRecipeNamesById((prev) => {
        const next = { ...prev };
        for (const pair of pairs) next[pair.id] = pair.name;
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [plan, recipeNamesById]);

  const days = useMemo(() => plan?.days ?? [], [plan?.days]);
  const slotIndexes = useMemo(() => {
    if (!plan) return [];
    return Array.from({ length: plan.meals_per_day }, (_, index) => index);
  }, [plan]);

  const canShowCalendar = !error && !isNotFound && plan !== null;
  const initialLoading = loading && !plan;

  const handleRegenerateDay = useCallback(async () => {
    if (!plan || !dayToRegenerate) return;

    setRegeneratingDay(true);
    setRegenerateDayError(null);
    setPageNotice(null);

    const currentDay = plan.days.find((day) => day.date === dayToRegenerate.date) ?? null;

    try {
      const updatedPlan = await regeneratePlanDay(plan.id, dayToRegenerate.date, {
        use_public_recipes: true,
      });
      const updatedDay = updatedPlan.days.find((day) => day.date === dayToRegenerate.date) ?? null;
      const unchanged = Boolean(currentDay && updatedDay && buildDaySlotsSignature(currentDay) === buildDaySlotsSignature(updatedDay));

      await loadPlan();
      if (unchanged) {
        setPageNotice("День обновлён: изменения не потребовались.");
      }
      setDayToRegenerate(null);
    } catch (err) {
      setRegenerateDayError(resolveRegenerateDayError(err));
    } finally {
      setRegeneratingDay(false);
    }
  }, [dayToRegenerate, loadPlan, plan]);

  return (
    <section className="plans-page">
      <div className="plans-shell plans-shell-wide">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">{plan ? planTitleWithFallback(plan.title, plan.start_date) : "План"}</h1>
            {plan && (
              <p className="plans-subtitle">
                Старт: {formatPlanDate(plan.start_date)} · Дней: {plan.days_count} · Слотов в день: {plan.meals_per_day}
              </p>
            )}
          </div>
          <div className="plans-head-actions">
            {plan && (
              <Link to={`/plans/${plan.id}/shopping`} className="btn btn-secondary">
                Список покупок
              </Link>
            )}
            <Link to="/plans" className="btn btn-secondary">
              К списку
            </Link>
          </div>
        </header>

        {initialLoading && <p className="plans-note">Загрузка плана...</p>}
        {!initialLoading && loading && <p className="plans-note">Обновление данных...</p>}
        {recipesError && <p className="plans-note">{recipesError}</p>}
        {pageNotice && <p className="plans-note">{pageNotice}</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadPlan()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && isNotFound && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">План не найден</p>
            <p className="plans-empty-subtitle">Возможно, план удалён или у вас нет доступа.</p>
            <Link to="/plans" className="btn btn-secondary">
              Вернуться к списку
            </Link>
          </article>
        )}

        {canShowCalendar && (
          <div className="plan-calendar-card">
            <p className="plans-note plan-calendar-note">
              Закреплённые слоты отмечены бейджем и не меняются при перегенерации дня.
            </p>
            <div className="plan-calendar-scroll">
              <table className="plan-calendar-table" aria-label="Календарь плана">
                <thead>
                  <tr>
                    <th className="plan-sticky-col">Слот</th>
                    {days.map((day) => (
                      <th key={day.date}>
                        <div className="plan-day-head">
                          <p className="plan-day-date">{formatPlanDate(day.date)}</p>
                          <button
                            type="button"
                            className="btn btn-secondary plan-day-regenerate-btn"
                            onClick={() => {
                              setDayToRegenerate(day);
                              setRegenerateDayError(null);
                              setPageNotice(null);
                            }}
                            disabled={loading || regeneratingDay}
                          >
                            Перегенерировать
                          </button>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th className="plan-sticky-col">Итого за день</th>
                    {days.map((day) => (
                      <td key={`${day.date}-totals`} className="plan-totals-cell">
                        <DayTotalsCompact day={day} />
                      </td>
                    ))}
                  </tr>

                  {slotIndexes.map((slotIndex) => (
                    <tr key={`slot-row-${slotIndex}`}>
                      <th className="plan-sticky-col">Слот {slotIndex + 1}</th>
                      {days.map((day) => {
                        const slot = findSlotByIndex(day.slots, slotIndex);
                        const recipeName =
                          slot?.recipe_id === null || !slot
                            ? null
                            : recipeNamesById[slot.recipe_id] ?? `Рецепт #${slot.recipe_id}`;

                        return (
                          <td key={`${day.date}-${slotIndex}`}>
                            <SlotCell
                              slot={slot}
                              recipeName={recipeName}
                              onClick={() => {
                                if (!slot) return;
                                setEditingSlot(slot);
                              }}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <EditPlanSlotModal
        isOpen={editingSlot !== null}
        planId={plan?.id ?? null}
        slot={editingSlot}
        recipes={recipes}
        recipeNamesById={recipeNamesById}
        recipesLoading={recipesLoading}
        recipesError={recipesError}
        onClose={() => setEditingSlot(null)}
        onSaved={loadPlan}
      />

      <PlanConfirmModal
        open={dayToRegenerate !== null}
        title="Перегенерировать день"
        message={
          dayToRegenerate
            ? `Будут заново подобраны рецепты на ${formatPlanDate(dayToRegenerate.date)}.`
            : ""
        }
        hintText="Закреплённые слоты останутся без изменений."
        confirmText="Перегенерировать"
        loading={regeneratingDay}
        loadingText="Перегенерируем..."
        errorText={regenerateDayError}
        onClose={() => {
          if (regeneratingDay) return;
          setRegenerateDayError(null);
          setDayToRegenerate(null);
        }}
        onConfirm={() => {
          void handleRegenerateDay();
        }}
      />
    </section>
  );
}

function DayTotalsCompact({ day }: { day: PlanDay }) {
  return (
    <div className="plan-day-totals">
      <p className="plan-day-totals-item">Ккал: {formatDecimal(day.totals.kcal)}</p>
      <p className="plan-day-totals-item">Б: {formatDecimal(day.totals.protein)}</p>
      <p className="plan-day-totals-item">Ж: {formatDecimal(day.totals.fat)}</p>
      <p className="plan-day-totals-item">У: {formatDecimal(day.totals.carbs)}</p>
    </div>
  );
}

function SlotCell({
  slot,
  recipeName,
  onClick,
}: {
  slot: PlanSlot | null;
  recipeName: string | null;
  onClick: () => void;
}) {
  if (!slot) {
    return <p className="plan-slot-empty">Пусто</p>;
  }

  return (
    <button type="button" className="plan-slot-trigger" onClick={onClick}>
      <div className="plan-slot-cell">
        {slot.recipe_id === null ? (
          <p className="plan-slot-empty">Пусто</p>
        ) : (
          <p className="plan-slot-main">{recipeName ?? `Рецепт #${slot.recipe_id}`}</p>
        )}

        <p className="plan-slot-meta">x{formatDecimal(slot.servings_multiplier)}</p>

        {slot.pinned && <span className="plan-slot-badge">Закреплён</span>}
      </div>
    </button>
  );
}
