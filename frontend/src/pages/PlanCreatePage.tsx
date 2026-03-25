import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/http";
import { createPlan } from "../api/plans";
import { FormErrorSummary } from "../components/FormErrorSummary";
import type { PlanCreatePayload } from "../types/plan";
import "./PlansPage.css";

type PlanCreateFormState = {
  start_date: string;
  days_count: string;
  meals_per_day: string;
  title: string;
};

type PlanCreateFormErrors = {
  start_date?: string;
  days_count?: string;
  meals_per_day?: string;
  title?: string;
  form: string[];
};

function toTodayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function validateCreateForm(form: PlanCreateFormState): { payload: PlanCreatePayload | null; errors: PlanCreateFormErrors } {
  const errors: PlanCreateFormErrors = { form: [] };

  const dateValue = form.start_date.trim();
  if (!dateValue) {
    errors.start_date = "Укажите дату старта.";
    errors.form.push("Укажите дату старта.");
  }

  const daysCount = Number(form.days_count);
  if (!Number.isInteger(daysCount) || daysCount < 1 || daysCount > 7) {
    errors.days_count = "Допустимо значение от 1 до 7.";
    errors.form.push("Количество дней должно быть от 1 до 7.");
  }

  const mealsPerDay = Number(form.meals_per_day);
  if (!Number.isInteger(mealsPerDay) || mealsPerDay < 2 || mealsPerDay > 6) {
    errors.meals_per_day = "Допустимо значение от 2 до 6.";
    errors.form.push("Слотов в день должно быть от 2 до 6.");
  }

  const title = form.title.trim();
  if (title.length > 120) {
    errors.title = "Название слишком длинное (до 120 символов).";
    errors.form.push("Название плана должно быть не длиннее 120 символов.");
  }

  if (errors.form.length > 0) {
    return { payload: null, errors };
  }

  return {
    payload: {
      start_date: dateValue,
      days_count: daysCount,
      meals_per_day: mealsPerDay,
      ...(title ? { title } : {}),
    },
    errors: { form: [] },
  };
}

export function PlanCreatePage() {
  const navigate = useNavigate();
  const initialDate = useMemo(() => toTodayIsoDate(), []);

  const [form, setForm] = useState<PlanCreateFormState>({
    start_date: initialDate,
    days_count: "7",
    meals_per_day: "3",
    title: "",
  });
  const [errors, setErrors] = useState<PlanCreateFormErrors>({ form: [] });
  const [saving, setSaving] = useState(false);

  const updateField = (field: keyof PlanCreateFormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({
      ...prev,
      [field]: undefined,
      form: [],
    }));
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const { payload, errors: validationErrors } = validateCreateForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    setSaving(true);
    setErrors({ form: [] });
    try {
      const created = await createPlan(payload);
      navigate(`/plans/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setErrors({
          form: [`Проверьте поля формы. ${err.message}`],
        });
      } else {
        setErrors({
          form: [err instanceof Error ? err.message : "Не удалось создать план."],
        });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="plans-page">
      <div className="plans-shell">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Создание плана</h1>
            <p className="plans-subtitle">Заполните параметры и откройте календарь плана сразу после создания.</p>
          </div>
          <div className="plans-head-actions">
            <Link to="/plans" className="btn btn-secondary">
              К списку планов
            </Link>
          </div>
        </header>

        <form className="plans-form" onSubmit={onSubmit} noValidate>
          <FormErrorSummary messages={errors.form} className="plans-form-summary form-error-summary" itemClassName="plans-form-error-item" />

          <label className="plans-field" htmlFor="plan-start-date">
            <span className="plans-field-label">Дата старта</span>
            <input
              id="plan-start-date"
              className={`plans-field-input ${errors.start_date ? "is-invalid" : ""}`}
              type="date"
              value={form.start_date}
              onChange={(e) => updateField("start_date", e.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.start_date && <p className="plans-field-error">{errors.start_date}</p>}
            </div>
          </label>

          <label className="plans-field" htmlFor="plan-days-count">
            <span className="plans-field-label">Количество дней (1–7)</span>
            <input
              id="plan-days-count"
              className={`plans-field-input ${errors.days_count ? "is-invalid" : ""}`}
              type="number"
              min={1}
              max={7}
              step={1}
              value={form.days_count}
              onChange={(e) => updateField("days_count", e.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.days_count && <p className="plans-field-error">{errors.days_count}</p>}
            </div>
          </label>

          <label className="plans-field" htmlFor="plan-meals-per-day">
            <span className="plans-field-label">Слотов в день (2–6)</span>
            <input
              id="plan-meals-per-day"
              className={`plans-field-input ${errors.meals_per_day ? "is-invalid" : ""}`}
              type="number"
              min={2}
              max={6}
              step={1}
              value={form.meals_per_day}
              onChange={(e) => updateField("meals_per_day", e.target.value)}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.meals_per_day && <p className="plans-field-error">{errors.meals_per_day}</p>}
            </div>
          </label>

          <label className="plans-field" htmlFor="plan-title">
            <span className="plans-field-label">Название (опционально)</span>
            <input
              id="plan-title"
              className={`plans-field-input ${errors.title ? "is-invalid" : ""}`}
              type="text"
              value={form.title}
              onChange={(e) => updateField("title", e.target.value)}
              placeholder="Например, Неделя на сушке"
              maxLength={120}
              disabled={saving}
            />
            <div className="plans-field-error-slot" aria-live="polite">
              {errors.title && <p className="plans-field-error">{errors.title}</p>}
            </div>
          </label>

          <div className="plans-form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => navigate("/plans")} disabled={saving}>
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Создание..." : "Создать план"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
