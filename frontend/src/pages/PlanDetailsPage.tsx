import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { ApiError } from "../api/http";
import { getPlan, getPlanAnalytics, regeneratePlanDay } from "../api/plans";
import { getRecipe, listRecipes, type RecipeRead } from "../api/recipes";
import { EditPlanSlotModal } from "../components/plans/EditPlanSlotModal";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { Alert } from "../components/Alert";
import type { PlanAnalyticsResponse, PlanDay, PlanRead, PlanSlot } from "../types/plan";
import { formatDecimal, formatPlanDate, formatPlanDayLabel, planTitleWithFallback } from "./plans";
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

function resolvePlanAnalyticsError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "План не найден.";
    if (err.status === 422) return "Для оценки плана нужны цели профиля.";
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить оценку плана.";
}

function buildDaySlotsSignature(day: PlanDay): string {
  return day.slots
    .slice()
    .sort((left, right) => left.slot_index - right.slot_index)
    .map((slot) => `${slot.slot_index}:${slot.recipe_id ?? "null"}:${slot.servings_multiplier}:${slot.pinned ? 1 : 0}`)
    .join("|");
}

function buildPlanTargetSummary(plan: PlanRead): string {
  const parts: string[] = [];
  if (plan.target_kcal !== null) {
    parts.push(`${plan.target_kcal} ккал`);
  }
  if (plan.target_protein !== null) {
    parts.push(`Б ${plan.target_protein}`);
  }
  if (plan.target_fat !== null) {
    parts.push(`Ж ${plan.target_fat}`);
  }
  if (plan.target_carbs !== null) {
    parts.push(`У ${plan.target_carbs}`);
  }
  if (plan.target_fiber !== null) {
    parts.push(`Клетчатка ${plan.target_fiber} г`);
  }
  if (parts.length === 0) return "Не задана";
  return parts.join(" / ");
}

export function PlanDetailsPage() {
  const { id } = useParams<{ id: string }>();

  const [plan, setPlan] = useState<PlanRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [analytics, setAnalytics] = useState<PlanAnalyticsResponse | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  const [recipes, setRecipes] = useState<RecipeRead[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [recipesError, setRecipesError] = useState<string | null>(null);
  const [recipeNamesById, setRecipeNamesById] = useState<Record<number, string>>({});

  const [editingSlot, setEditingSlot] = useState<PlanSlot | null>(null);
  const [dayToRegenerate, setDayToRegenerate] = useState<PlanDay | null>(null);
  const [regeneratingDay, setRegeneratingDay] = useState(false);
  const [regenerateDayError, setRegenerateDayError] = useState<string | null>(null);
  const [pageNotice, setPageNotice] = useState<string | null>(null);
  const [replacementHistoryBySlotId, setReplacementHistoryBySlotId] = useState<Record<number, number[]>>({});
  const [selectedMobileDayDate, setSelectedMobileDayDate] = useState<string | null>(null);

  const loadAnalytics = useCallback(async (planId: number | string) => {
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    try {
      const payload = await getPlanAnalytics(planId);
      setAnalytics(payload);
    } catch (err) {
      setAnalytics(null);
      setAnalyticsError(resolvePlanAnalyticsError(err));
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  const loadPlan = useCallback(async () => {
    if (!id) {
      setPlan(null);
      setAnalytics(null);
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
      await loadAnalytics(payload.id);
    } catch (err) {
      setPlan(null);
      setAnalytics(null);
      if (err instanceof ApiError && err.status === 404) {
        setIsNotFound(true);
      } else {
        setError(resolvePlanDetailsError(err));
      }
    } finally {
      setLoading(false);
    }
  }, [id, loadAnalytics]);

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
          return { id: recipeId, name: "Рецепт недоступен" };
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
  const selectedMobileDay = useMemo(() => {
    if (days.length === 0) return null;
    if (!selectedMobileDayDate) return days[0];
    return days.find((day) => day.date === selectedMobileDayDate) ?? days[0];
  }, [days, selectedMobileDayDate]);
  const slotIndexes = useMemo(() => {
    if (!plan) return [];
    return Array.from({ length: plan.meals_per_day }, (_, index) => index);
  }, [plan]);

  useEffect(() => {
    if (days.length === 0) {
      setSelectedMobileDayDate(null);
      return;
    }
    setSelectedMobileDayDate((prev) => (prev && days.some((day) => day.date === prev) ? prev : days[0].date));
  }, [days]);

  const canShowCalendar = !error && !isNotFound && plan !== null;
  const initialLoading = loading && !plan;
  const rememberReplacementRecipe = useCallback((slotId: number, recipeId: number) => {
    setReplacementHistoryBySlotId((prev) => {
      const current = prev[slotId] ?? [];
      if (current.includes(recipeId)) return prev;
      return {
        ...prev,
        [slotId]: [...current, recipeId],
      };
    });
  }, []);

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
              <>
                <p className="plans-subtitle">
                  Старт: {formatPlanDate(plan.start_date)} · Дней: {plan.days_count} · Слотов в день: {plan.meals_per_day}
                </p>
                <p className="plan-profile-summary">
                  Профиль: {plan.profile_name ?? (plan.profile_id ? "Профиль недоступен" : "не указан")}
                </p>
                <p className="plan-profile-summary">Цель: {buildPlanTargetSummary(plan)}</p>
                <p className="plan-profile-hint">
                  План привязан к этому профилю. Смена активного профиля сверху не меняет уже созданный план.
                </p>
              </>
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
              <table className="plan-calendar-table plan-calendar-table-desktop" aria-label="Календарь плана">
                <thead>
                  <tr>
                    <th className="plan-sticky-col">Слот</th>
                    {days.map((day) => (
                      <th key={day.date}>
                        <div className="plan-day-head">
                          <span className="plan-day-title">{formatPlanDayLabel(day.date)}</span>
                          <button
                            type="button"
                            className="icon-button icon-button--secondary icon-button--compact plan-day-regenerate-btn"
                            aria-label="Перегенерировать день"
                            onClick={() => {
                              setDayToRegenerate(day);
                              setRegenerateDayError(null);
                              setPageNotice(null);
                            }}
                            disabled={loading || regeneratingDay}
                          >
                            <RefreshCw aria-hidden="true" size={16} />
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
                        <DayTotalsCompact
                          day={{
                            ...day,
                            analytics: analytics?.day_analytics.find((item) => item.date === day.date),
                          }}
                        />
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
                            : recipeNamesById[slot.recipe_id] ?? "Рецепт недоступен";

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

            <div className="plan-mobile-days" aria-label="План по дням">
              <div className="plan-mobile-day-switcher" role="tablist" aria-label="Выбор дня плана">
                {days.map((day) => (
                  <button
                    key={`mobile-day-tab-${day.date}`}
                    type="button"
                    role="tab"
                    aria-selected={selectedMobileDay?.date === day.date}
                    className={`plan-mobile-day-chip ${selectedMobileDay?.date === day.date ? "is-active" : ""}`}
                    onClick={() => setSelectedMobileDayDate(day.date)}
                  >
                    {formatPlanDayLabel(day.date)}
                  </button>
                ))}
              </div>

              {selectedMobileDay && (
                <article key={`mobile-day-${selectedMobileDay.date}`} className="plan-mobile-day-card">
                  <header className="plan-mobile-day-head">
                    <h2 className="plan-mobile-day-title">{formatPlanDayLabel(selectedMobileDay.date)}</h2>
                    <button
                      type="button"
                      className="icon-button icon-button--secondary icon-button--compact plan-day-regenerate-btn"
                      aria-label="Перегенерировать день"
                      onClick={() => {
                        setDayToRegenerate(selectedMobileDay);
                        setRegenerateDayError(null);
                        setPageNotice(null);
                      }}
                      disabled={loading || regeneratingDay}
                    >
                      <RefreshCw aria-hidden="true" size={16} />
                    </button>
                  </header>

                  <div className="plan-mobile-day-totals">
                    <DayTotalsCompact
                      day={{
                        ...selectedMobileDay,
                        analytics: analytics?.day_analytics.find((item) => item.date === selectedMobileDay.date),
                      }}
                    />
                  </div>

                  <div className="plan-mobile-slots">
                    {slotIndexes.map((slotIndex) => {
                      const slot = findSlotByIndex(selectedMobileDay.slots, slotIndex);
                      const recipeName =
                        slot?.recipe_id === null || !slot
                          ? null
                          : recipeNamesById[slot.recipe_id] ?? "Рецепт недоступен";

                      return (
                        <div key={`mobile-slot-${selectedMobileDay.date}-${slotIndex}`} className="plan-mobile-slot-card">
                          <p className="plan-mobile-slot-title">Слот {slotIndex + 1}</p>
                          <SlotCell
                            slot={slot}
                            recipeName={recipeName}
                            onClick={() => {
                              if (!slot) return;
                              setEditingSlot(slot);
                            }}
                          />
                        </div>
                      );
                    })}
                  </div>
                </article>
              )}
            </div>
          </div>
        )}

        {canShowCalendar && (
          <PlanAnalyticsSection
            plan={plan}
            analytics={analytics}
            loading={analyticsLoading}
            error={analyticsError}
            onRetry={() => {
              if (!plan) return;
              void loadAnalytics(plan.id);
            }}
          />
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
        replacementHistory={editingSlot ? replacementHistoryBySlotId[editingSlot.id] ?? [] : []}
        onRememberReplacementRecipe={rememberReplacementRecipe}
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

function DayTotalsCompact({
  day,
}: {
  day: PlanDay & { analytics?: PlanAnalyticsResponse["day_analytics"][number] };
}) {
  const dayAnalytics = day.analytics ?? null;
  const dayDeviations = dayAnalytics ? collectDayDeviationBadges(dayAnalytics) : [];

  return (
    <div className="plan-day-totals">
      <div className="plan-day-totals-head">
        <p className="plan-day-totals-item">Ккал: {formatDecimal(day.totals.kcal)}</p>
        {dayDeviations.length > 0 && <DayAnalyticsIndicator items={dayDeviations} />}
      </div>
      <p className="plan-day-totals-item">Б: {formatDecimal(day.totals.protein)}</p>
      <p className="plan-day-totals-item">Ж: {formatDecimal(day.totals.fat)}</p>
      <p className="plan-day-totals-item">У: {formatDecimal(day.totals.carbs)}</p>
      <p className="plan-day-totals-item">Клетчатка: {formatDecimal(day.totals.fiber)}</p>
    </div>
  );
}

function DayAnalyticsIndicator({
  items,
}: {
  items: Array<{ label: string; tone: "low" | "high" | "info"; percent: string | null }>;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const root = rootRef.current;
      if (!root) return;
      if (root.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="plan-day-indicator-wrap"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="plan-day-indicator-btn"
        aria-label="Показать отклонения за день"
        aria-expanded={open}
        onFocus={() => setOpen(true)}
        onBlur={(event) => {
          const next = event.relatedTarget as Node | null;
          if (!next || !rootRef.current?.contains(next)) {
            setOpen(false);
          }
        }}
        onClick={() => setOpen((prev) => !prev)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      >
        !
      </button>

      {open && (
        <div className="plan-day-indicator-popover" role="dialog" aria-label="Отклонения за день">
          <p className="plan-day-indicator-title">Отклонения за день</p>
          <ul className="plan-day-indicator-list">
            {items.map((item) => (
              <li key={item.label} className={`plan-day-indicator-item is-${item.tone}`}>
                <span>{item.label}</span>
                <span>{item.percent === null ? "—" : `${item.percent}%`}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PlanAnalyticsSection({
  plan,
  analytics,
  loading,
  error,
  onRetry,
}: {
  plan: PlanRead;
  analytics: PlanAnalyticsResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <section className="plan-analytics-card">
        <h2 className="plan-analytics-title">Оценка плана</h2>
        <p className="plans-note">Загрузка оценки плана...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="plan-analytics-card">
        <h2 className="plan-analytics-title">Оценка плана</h2>
        <p className="plans-note">{error}</p>
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Повторить
        </button>
      </section>
    );
  }

  if (!analytics) return null;

  const period = computeDisplayPeriodFromPlan(plan);
  const score = analytics.period_summary.overall_score;
  const rows = [
    { label: "Калории", percent: period.kcal_percent, status: resolveStatusByPercent(period.kcal_percent, "kcal") },
    { label: "Белки", percent: period.protein_percent, status: resolveStatusByPercent(period.protein_percent, "macro") },
    { label: "Жиры", percent: period.fat_percent, status: resolveStatusByPercent(period.fat_percent, "macro") },
    { label: "Углеводы", percent: period.carbs_percent, status: resolveStatusByPercent(period.carbs_percent, "macro") },
  ];

  const showFiber = plan.target_fiber !== null || period.average_fiber > 0;
  if (showFiber) {
    rows.push({
      label: "Клетчатка",
      percent: period.fiber_percent,
      status: resolveStatusByPercent(period.fiber_percent, plan.target_fiber && plan.target_fiber > 0 ? "fiber" : "none"),
    });
  }

  const metricCards = [
    { label: "Ккал", value: `${formatMetric(period.average_kcal)} ккал`, target: plan.target_kcal !== null ? `${plan.target_kcal}` : "—" },
    { label: "Белки", value: `${formatMetric(period.average_protein)} г`, target: plan.target_protein !== null ? `${plan.target_protein} г` : "—" },
    { label: "Жиры", value: `${formatMetric(period.average_fat)} г`, target: plan.target_fat !== null ? `${plan.target_fat} г` : "—" },
    { label: "Углеводы", value: `${formatMetric(period.average_carbs)} г`, target: plan.target_carbs !== null ? `${plan.target_carbs} г` : "—" },
  ];
  if (showFiber) {
    metricCards.push({
      label: "Клетчатка",
      value: `${formatMetric(period.average_fiber)} г`,
      target: plan.target_fiber !== null ? `${plan.target_fiber} г` : "—",
    });
  }

  return (
    <section className="plan-analytics-card">
      <div className="plan-analytics-head">
        <div>
          <h2 className="plan-analytics-title">Оценка плана</h2>
          <p className="plan-analytics-subtitle">Оценка рассчитана по средним значениям за период.</p>
        </div>
        <span className="plan-analytics-score">Оценка {score}/100</span>
      </div>

      <div className="plan-analytics-grid">
        <article className="plan-analytics-panel">
          <h3 className="plan-analytics-panel-title">Среднее за день</h3>
          <div className="plan-analytics-metrics">
            {metricCards.map((item) => (
              <div key={item.label} className="plan-analytics-metric-card">
                <p className="plan-analytics-metric-label">{item.label}</p>
                <p className="plan-analytics-metric-value">{item.value}</p>
                <p className="plan-analytics-metric-target">цель: {item.target}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="plan-analytics-panel">
          <h3 className="plan-analytics-panel-title">Попадание в цели</h3>
          <ul className="plan-analytics-targets">
            {rows.map((row) => (
              <li key={row.label} className={`plan-analytics-target-row is-${row.status}`}>
                <div className="plan-analytics-target-row-top">
                  <span>{row.label}</span>
                  <span>{formatPercentValue(row.percent)}</span>
                </div>
                <div className="plan-analytics-progress">
                  <div
                    className="plan-analytics-progress-fill"
                    style={{ width: `${resolveProgressWidth(row.percent)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </article>

        <article className="plan-analytics-panel">
          <h3 className="plan-analytics-panel-title">Рекомендации</h3>
          <ul className="plan-analytics-recommendations">
            {analytics.recommendations.slice(0, 3).map((item, index) => (
              <li key={`${index}-${item}`}>{item}</li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}

function formatPercentValue(value: string | null): string {
  if (value === null) return "—";
  return `${value}%`;
}

function formatMetric(value: number): string {
  return value.toFixed(2);
}

function resolveProgressWidth(value: string | null): number {
  if (value === null) return 0;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return 0;
  return Math.min(100, Math.round(numeric));
}

function resolveStatusByPercent(
  value: string | null,
  mode: "kcal" | "macro" | "fiber" | "none",
): "low" | "ok" | "high" | "no-target" {
  if (mode === "none" || value === null) return "no-target";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "no-target";

  if (mode === "kcal") {
    if (numeric < 90) return "low";
    if (numeric > 110) return "high";
    return "ok";
  }

  if (mode === "fiber") {
    if (numeric < 85) return "low";
    if (numeric > 180) return "high";
    return "ok";
  }

  if (numeric < 85) return "low";
  if (numeric > 115) return "high";
  return "ok";
}

function collectDayDeviationBadges(day: PlanAnalyticsResponse["day_analytics"][number]): Array<{
  label: string;
  tone: "low" | "high" | "info";
  percent: string | null;
}> {
  const candidates: Array<{ label: string; tone: "low" | "high" | "info"; priority: number; percent: string | null }> = [];

  const pushCandidate = (
    shortLabel: string,
    status: "low" | "ok" | "high" | "no_target",
    priority: number,
    options?: { isFiber?: boolean; percent?: string | null },
  ) => {
    if (status === "ok" || status === "no_target") return;
    if (options?.isFiber && status === "high") {
      const fiberPercent = Number(options.percent ?? "0");
      if (Number.isFinite(fiberPercent) && fiberPercent < 220) return;
    }
    const label = `${shortLabel} ${status === "low" ? "ниже" : "выше"}`;
    if (options?.isFiber && status === "high") {
      candidates.push({ label, tone: "info", priority, percent: options.percent ?? null });
      return;
    }
    candidates.push({ label, tone: status === "low" ? "low" : "high", priority, percent: options?.percent ?? null });
  };

  pushCandidate("Калории", day.kcal.status, 1, { percent: day.kcal.percent });
  pushCandidate("Белок", day.protein.status, 2, { percent: day.protein.percent });
  pushCandidate("Жиры", day.fat.status, 3, { percent: day.fat.percent });
  pushCandidate("Углеводы", day.carbs.status, 4, { percent: day.carbs.percent });
  pushCandidate("Клетчатка", day.fiber.status, 5, { isFiber: true, percent: day.fiber.percent });

  return candidates
    .sort((left, right) => left.priority - right.priority)
    .slice(0, 3)
    .map((item) => ({ label: item.label, tone: item.tone, percent: item.percent }));
}

function toNumber(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function roundTo(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function buildPercent(value: number, target: number | null): string | null {
  if (!target || target <= 0) return null;
  return roundTo((value / target) * 100, 1).toFixed(1);
}

function computeDisplayPeriodFromPlan(plan: PlanRead): {
  average_kcal: number;
  average_protein: number;
  average_fat: number;
  average_carbs: number;
  average_fiber: number;
  kcal_percent: string | null;
  protein_percent: string | null;
  fat_percent: string | null;
  carbs_percent: string | null;
  fiber_percent: string | null;
} {
  const dayCount = Math.max(plan.days.length, 1);
  const sums = plan.days.reduce(
    (acc, day) => {
      acc.kcal += toNumber(day.totals.kcal);
      acc.protein += toNumber(day.totals.protein);
      acc.fat += toNumber(day.totals.fat);
      acc.carbs += toNumber(day.totals.carbs);
      acc.fiber += toNumber(day.totals.fiber);
      return acc;
    },
    { kcal: 0, protein: 0, fat: 0, carbs: 0, fiber: 0 },
  );

  const average_kcal = roundTo(sums.kcal / dayCount, 2);
  const average_protein = roundTo(sums.protein / dayCount, 2);
  const average_fat = roundTo(sums.fat / dayCount, 2);
  const average_carbs = roundTo(sums.carbs / dayCount, 2);
  const average_fiber = roundTo(sums.fiber / dayCount, 2);

  return {
    average_kcal,
    average_protein,
    average_fat,
    average_carbs,
    average_fiber,
    kcal_percent: buildPercent(average_kcal, plan.target_kcal),
    protein_percent: buildPercent(average_protein, plan.target_protein),
    fat_percent: buildPercent(average_fat, plan.target_fat),
    carbs_percent: buildPercent(average_carbs, plan.target_carbs),
    fiber_percent: buildPercent(average_fiber, plan.target_fiber),
  };
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
          <p className="plan-slot-main">{recipeName ?? "Рецепт недоступен"}</p>
        )}

        <p className="plan-slot-meta">x{formatDecimal(slot.servings_multiplier)}</p>
        <div className="plan-slot-nutrition">
          <span>Ккал: {formatDecimal(slot.slot_kcal)}</span>
          <span>Б: {formatDecimal(slot.slot_protein)}</span>
          <span>Ж: {formatDecimal(slot.slot_fat)}</span>
          <span>У: {formatDecimal(slot.slot_carbs)}</span>
          <span>Клетчатка: {formatDecimal(slot.slot_fiber)}</span>
        </div>

        <div className="plan-slot-badges">
          {slot.pinned && <span className="plan-slot-badge">Закреплён</span>}
          {slot.has_overrides && <span className="plan-slot-badge">Ингредиенты изменены</span>}
        </div>
      </div>
    </button>
  );
}
