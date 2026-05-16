import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { listPlans } from "../api/plans";
import { Alert } from "../components/Alert";
import { useProfiles } from "../context/ProfilesContext";
import type { PlanListItem } from "../types/plan";
import { formatPlanDate, planTitleWithFallback } from "./plans";
import "./CalendarPage.css";

type CalendarMode = "month" | "week";

type PlanOccurrence = {
  plan: PlanListItem;
  isStart: boolean;
  isEnd: boolean;
  colorClass: string;
};

type CalendarProfileFilterValue = "all" | "none" | `profile:${number}`;

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const PLAN_COLOR_CLASSES = [
  "calendar-plan-color-0",
  "calendar-plan-color-1",
  "calendar-plan-color-2",
  "calendar-plan-color-3",
  "calendar-plan-color-4",
  "calendar-plan-color-5",
  "calendar-plan-color-6",
  "calendar-plan-color-7",
];

const monthTitleFormatter = new Intl.DateTimeFormat("ru-RU", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

const dayNumberFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  timeZone: "UTC",
});

const dayMonthFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
});

const dayMonthShortFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

const dayMonthYearFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function toTodayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoDate(isoDate: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;

  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return date;
}

function formatIsoDate(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * DAY_MS);
}

function startOfWeek(date: Date): Date {
  const dayIndex = (date.getUTCDay() + 6) % 7;
  return addDays(date, -dayIndex);
}

function buildMonthGrid(date: Date): Date[] {
  const monthStart = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  const firstCell = startOfWeek(monthStart);
  return Array.from({ length: 42 }, (_, index) => addDays(firstCell, index));
}

function resolveCalendarError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "Планы не найдены.";
  }
  return "Не удалось загрузить планы.";
}

function formatWeekRange(start: Date, end: Date): string {
  const sameMonth = start.getUTCFullYear() === end.getUTCFullYear() && start.getUTCMonth() === end.getUTCMonth();
  if (sameMonth) {
    const startDay = dayNumberFormatter.format(start);
    const endLabel = dayMonthYearFormatter.format(end);
    return `${startDay}–${endLabel}`;
  }
  return `${dayMonthShortFormatter.format(start)} — ${dayMonthYearFormatter.format(end)}`;
}

function formatMealsLabel(mealsPerDay: number): string {
  return `${mealsPerDay} приёма`;
}

function useCompactCalendar(): boolean {
  const [compact, setCompact] = useState<boolean>(() => (typeof window !== "undefined" ? window.innerWidth <= 768 : false));

  useEffect(() => {
    const onResize = () => {
      setCompact(window.innerWidth <= 768);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return compact;
}

export function CalendarPage() {
  const { profiles } = useProfiles();
  const todayIso = useMemo(() => toTodayIsoDate(), []);
  const todayDate = useMemo(() => parseIsoDate(todayIso) ?? new Date(), [todayIso]);

  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<CalendarMode>("month");
  const [periodDate, setPeriodDate] = useState<Date>(todayDate);
  const [selectedDateIso, setSelectedDateIso] = useState<string>(todayIso);
  const [profileFilter, setProfileFilter] = useState<CalendarProfileFilterValue>("all");
  const isCompact = useCompactCalendar();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const items = await listPlans();
        if (cancelled) return;
        setPlans(items);
      } catch (err) {
        if (cancelled) return;
        setPlans([]);
        setError(resolveCalendarError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedDate = useMemo(() => parseIsoDate(selectedDateIso) ?? todayDate, [selectedDateIso, todayDate]);

  const filteredPlans = useMemo(() => {
    if (profileFilter === "all") return plans;
    if (profileFilter === "none") return plans.filter((plan) => plan.profile_id === null);

    const rawProfileId = profileFilter.slice("profile:".length);
    const profileId = Number(rawProfileId);
    if (!Number.isInteger(profileId) || profileId < 1) return plans;
    return plans.filter((plan) => plan.profile_id === profileId);
  }, [plans, profileFilter]);

  const monthDays = useMemo(() => buildMonthGrid(periodDate), [periodDate]);
  const weekStart = useMemo(() => startOfWeek(periodDate), [periodDate]);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);

  const plansByDay = useMemo(() => {
    const map = new Map<string, PlanOccurrence[]>();

    filteredPlans.forEach((plan) => {
      const startDate = parseIsoDate(plan.start_date);
      if (!startDate || plan.days_count < 1) return;

      const colorClass = PLAN_COLOR_CLASSES[Math.abs(plan.id) % PLAN_COLOR_CLASSES.length];
      for (let offset = 0; offset < plan.days_count; offset += 1) {
        const current = addDays(startDate, offset);
        const dateIso = formatIsoDate(current);
        const next = map.get(dateIso) ?? [];
        next.push({
          plan,
          isStart: offset === 0,
          isEnd: offset === plan.days_count - 1,
          colorClass,
        });
        map.set(dateIso, next);
      }
    });

    map.forEach((items, key) => {
      const sorted = [...items].sort((left, right) => {
        if (left.plan.start_date !== right.plan.start_date) {
          return left.plan.start_date.localeCompare(right.plan.start_date);
        }
        return left.plan.id - right.plan.id;
      });
      map.set(key, sorted);
    });

    return map;
  }, [filteredPlans]);

  const selectedDayPlans = useMemo(() => plansByDay.get(selectedDateIso) ?? [], [plansByDay, selectedDateIso]);

  const periodTitle = useMemo(() => {
    if (mode === "month") {
      const label = monthTitleFormatter.format(periodDate);
      return label.charAt(0).toUpperCase() + label.slice(1);
    }
    const end = addDays(weekStart, 6);
    return formatWeekRange(weekStart, end);
  }, [mode, periodDate, weekStart]);

  const onSelectDate = (dateIso: string, adjustPeriod = false) => {
    setSelectedDateIso(dateIso);
    if (adjustPeriod) {
      const parsed = parseIsoDate(dateIso);
      if (parsed) setPeriodDate(parsed);
    }
  };

  const goToPreviousPeriod = () => {
    setPeriodDate((prev) => (mode === "month" ? new Date(Date.UTC(prev.getUTCFullYear(), prev.getUTCMonth() - 1, 1)) : addDays(prev, -7)));
  };

  const goToNextPeriod = () => {
    setPeriodDate((prev) => (mode === "month" ? new Date(Date.UTC(prev.getUTCFullYear(), prev.getUTCMonth() + 1, 1)) : addDays(prev, 7)));
  };

  const goToToday = () => {
    const next = parseIsoDate(toTodayIsoDate()) ?? new Date();
    setPeriodDate(next);
    setSelectedDateIso(formatIsoDate(next));
  };

  const isEmpty = !loading && !error && plans.length === 0;
  const hasFilteredPlans = filteredPlans.length > 0;
  const selectedDateLabel = dayMonthFormatter.format(selectedDate);
  const selectedDateQuery = `startDate=${selectedDateIso}`;

  const profileFilterOptions = useMemo(() => {
    const options: Array<{ value: CalendarProfileFilterValue; label: string }> = [
      { value: "all", label: "Все профили" },
      { value: "none", label: "Без профиля" },
    ];
    profiles.forEach((profile) => {
      options.push({ value: `profile:${profile.id}`, label: profile.name });
    });
    return options;
  }, [profiles]);

  const isProfileFiltered = profileFilter !== "all";
  const selectedDayEmptyText = isProfileFiltered
    ? "На этот день нет планов для выбранного профиля."
    : "На этот день планов нет.";
  const selectedFilterLabel = profileFilterOptions.find((option) => option.value === profileFilter)?.label ?? "Все профили";

  return (
    <section className="calendar-page">
      <div className="calendar-shell">
        <header className="calendar-head">
          <div className="calendar-head-main">
            <h1 className="calendar-title">Календарь питания</h1>
            <p className="calendar-subtitle">Планы по датам: переключайтесь между месяцем и неделей.</p>
          </div>
          <div className="calendar-head-actions">
            <Link to={`/plans/new?${selectedDateQuery}`} className="btn btn-secondary">
              Создать план
            </Link>
            <Link to={`/plans/autogenerate?${selectedDateQuery}`} className="btn btn-primary">
              Автоплан
            </Link>
          </div>
        </header>

        <div className="calendar-toolbar">
          <div className="calendar-mode-switch" role="tablist" aria-label="Режим календаря">
            <button
              type="button"
              className={`calendar-mode-btn ${mode === "month" ? "is-active" : ""}`}
              onClick={() => {
                setMode("month");
                setPeriodDate(selectedDate);
              }}
              aria-selected={mode === "month"}
            >
              Месяц
            </button>
            <button
              type="button"
              className={`calendar-mode-btn ${mode === "week" ? "is-active" : ""}`}
              onClick={() => {
                setMode("week");
                setPeriodDate(selectedDate);
              }}
              aria-selected={mode === "week"}
            >
              Неделя
            </button>
          </div>

          <label className="calendar-profile-filter" htmlFor="calendar-profile-filter">
            <span>Профиль</span>
            <select
              id="calendar-profile-filter"
              className="calendar-profile-filter-select"
              value={profileFilter}
              onChange={(event) => {
                const nextValue = event.target.value;
                if (nextValue === "all" || nextValue === "none" || nextValue.startsWith("profile:")) {
                  setProfileFilter(nextValue as CalendarProfileFilterValue);
                }
              }}
            >
              {profileFilterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="calendar-period-nav">
            <button type="button" className="btn btn-secondary calendar-nav-btn" onClick={goToPreviousPeriod} aria-label="Предыдущий период">
              ←
            </button>
            <p className="calendar-period-title">{periodTitle}</p>
            <button type="button" className="btn btn-secondary calendar-nav-btn" onClick={goToNextPeriod} aria-label="Следующий период">
              →
            </button>
            <button type="button" className="btn btn-secondary calendar-today-btn" onClick={goToToday}>
              Сегодня
            </button>
          </div>
        </div>

        {!loading && !error && plans.length > 0 && !hasFilteredPlans && (
          <p className="calendar-note">По фильтру «{selectedFilterLabel}» планы не найдены.</p>
        )}

        {loading && <p className="calendar-note">Загрузка календаря…</p>}

        {!loading && error && (
          <div className="calendar-error-block">
            <Alert text={error || "Не удалось загрузить планы."} />
          </div>
        )}

        {isEmpty && (
          <article className="calendar-empty-card">
            <p className="calendar-empty-title">Пока нет планов питания.</p>
            <p className="calendar-empty-subtitle">Создайте план вручную или сгенерируйте автоплан.</p>
            <div className="calendar-empty-actions">
              <Link to={`/plans/new?${selectedDateQuery}`} className="btn btn-secondary">
                Создать план
              </Link>
              <Link to={`/plans/autogenerate?${selectedDateQuery}`} className="btn btn-primary">
                Автоплан
              </Link>
            </div>
          </article>
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="calendar-layout">
            <div className="calendar-main">
              {mode === "month" && (
                <div className="calendar-month-view">
                  <div className="calendar-weekdays" role="presentation">
                    {WEEKDAY_LABELS.map((weekday) => (
                      <div key={weekday} className="calendar-weekday">
                        {weekday}
                      </div>
                    ))}
                  </div>

                  <div className="calendar-month-grid">
                    {monthDays.map((date) => {
                      const dateIso = formatIsoDate(date);
                      const dayPlans = plansByDay.get(dateIso) ?? [];
                      const isOutsideMonth = date.getUTCMonth() !== periodDate.getUTCMonth();
                      const isSelected = dateIso === selectedDateIso;
                      const isToday = dateIso === todayIso;
                      const displayPlans = dayPlans.slice(0, 2);
                      const hiddenCount = Math.max(0, dayPlans.length - displayPlans.length);

                      return (
                        <div
                          key={dateIso}
                          className={`calendar-day-cell ${isOutsideMonth ? "is-outside" : ""} ${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""}`}
                          onClick={() => onSelectDate(dateIso, isOutsideMonth)}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onSelectDate(dateIso);
                            }
                          }}
                        >
                          <div className="calendar-day-number">{dayNumberFormatter.format(date)}</div>

                          <div className="calendar-day-plans-desktop">
                            {displayPlans.map((item) => (
                              <Link
                                key={`${dateIso}-${item.plan.id}`}
                                to={`/plans/${item.plan.id}`}
                                className={`calendar-plan-pill ${item.colorClass} ${item.isStart ? "is-start" : ""} ${item.isEnd ? "is-end" : ""}`}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <span className="calendar-plan-pill-title">
                                  {planTitleWithFallback(item.plan.title, item.plan.start_date)}
                                </span>
                              </Link>
                            ))}
                            {hiddenCount > 0 && <span className="calendar-day-more">+ ещё {hiddenCount}</span>}
                          </div>

                          <div className="calendar-day-dots-mobile" aria-hidden="true">
                            {dayPlans.slice(0, 3).map((item) => (
                              <span key={`${dateIso}-dot-${item.plan.id}`} className={`calendar-plan-dot ${item.colorClass}`} />
                            ))}
                            {dayPlans.length > 3 && <span className="calendar-dot-more">+{dayPlans.length - 3}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {mode === "week" && (
                <div className="calendar-week-view">
                  {!isCompact && (
                    <div className="calendar-week-grid">
                      {weekDays.map((date) => {
                        const dateIso = formatIsoDate(date);
                        const dayPlans = plansByDay.get(dateIso) ?? [];
                        const isSelected = dateIso === selectedDateIso;
                        const isToday = dateIso === todayIso;
                        return (
                          <article
                            key={dateIso}
                            className={`calendar-week-day-card ${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""}`}
                            onClick={() => onSelectDate(dateIso)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                onSelectDate(dateIso);
                              }
                            }}
                          >
                            <header className="calendar-week-day-head">
                              <span>{WEEKDAY_LABELS[(date.getUTCDay() + 6) % 7]}</span>
                              <span>{dayMonthShortFormatter.format(date)}</span>
                            </header>
                            <div className="calendar-week-day-plans">
                              {dayPlans.length === 0 && <p className="calendar-week-empty">Нет планов</p>}
                              {dayPlans.map((item) => (
                                <Link
                                  key={`${dateIso}-${item.plan.id}`}
                                  to={`/plans/${item.plan.id}`}
                                  className={`calendar-week-plan ${item.colorClass}`}
                                  onClick={(event) => event.stopPropagation()}
                                >
                                  <strong>{planTitleWithFallback(item.plan.title, item.plan.start_date)}</strong>
                                  <span>{item.plan.profile_name?.trim() || "Без профиля"}</span>
                                  <span>{formatMealsLabel(item.plan.meals_per_day)}</span>
                                </Link>
                              ))}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}

                  {isCompact && (
                    <div className="calendar-week-chips" role="tablist" aria-label="Дни недели">
                      {weekDays.map((date) => {
                        const dateIso = formatIsoDate(date);
                        const dayPlans = plansByDay.get(dateIso) ?? [];
                        const isSelected = dateIso === selectedDateIso;
                        return (
                          <button
                            key={dateIso}
                            type="button"
                            className={`calendar-week-chip ${isSelected ? "is-selected" : ""}`}
                            onClick={() => onSelectDate(dateIso)}
                            aria-selected={isSelected}
                          >
                            <span>{WEEKDAY_LABELS[(date.getUTCDay() + 6) % 7]}</span>
                            <strong>{dayNumberFormatter.format(date)}</strong>
                            {dayPlans.length > 0 && <em>{dayPlans.length}</em>}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            <aside className="calendar-day-panel">
              <h2 className="calendar-day-panel-title">Планы на день</h2>
              <p className="calendar-day-panel-date">{selectedDateLabel}</p>

              {selectedDayPlans.length === 0 && (
                <p className="calendar-day-panel-empty">{selectedDayEmptyText}</p>
              )}

              {selectedDayPlans.length > 0 && (
                <ul className="calendar-day-plan-list">
                  {selectedDayPlans.map((item) => (
                    <li key={`selected-${selectedDateIso}-${item.plan.id}`} className="calendar-day-plan-item">
                      <Link to={`/plans/${item.plan.id}`} className={`calendar-day-plan-link ${item.colorClass}`}>
                        <span className="calendar-day-plan-title">
                          {planTitleWithFallback(item.plan.title, item.plan.start_date)}
                        </span>
                        <span className="calendar-day-plan-meta">
                          {formatPlanDate(item.plan.start_date)} · {item.plan.days_count} дн. · {formatMealsLabel(item.plan.meals_per_day)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}

              <div className="calendar-day-panel-actions">
                <Link to={`/plans/new?${selectedDateQuery}`} className="btn btn-secondary">
                  Создать план
                </Link>
                <Link to={`/plans/autogenerate?${selectedDateQuery}`} className="btn btn-primary calendar-autoplan-btn">
                  Сгенерировать автоплан
                </Link>
              </div>
            </aside>
          </div>
        )}
      </div>
    </section>
  );
}
