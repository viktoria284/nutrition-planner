import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/http";
import {
  calculateProfileTarget,
  getLatestProfileTargetCalculation,
  type LactationPeriod,
  type ProfileTargetCalculationActivityLevel,
  type ProfileTargetCalculationFormula,
  type ProfileTargetCalculationGoal,
  type ProfileTargetCalculationInput,
  type ProfileTargetCalculationMacroPreset,
  type ProfileTargetCalculationResult,
  type ProfileTargetCalculationSex,
  type SpecialCondition,
} from "../api/profileTargetCalculations";
import { Alert } from "../components/Alert";
import { CustomSelect } from "../components/CustomSelect";
import { InfoPopover } from "../components/InfoPopover";
import "./ProfileTargetCalculatorPage.css";

type CalculatorForm = {
  sex: ProfileTargetCalculationSex;
  age: string;
  height_cm: string;
  weight_kg: string;
  activity_level: ProfileTargetCalculationActivityLevel;
  goal: ProfileTargetCalculationGoal;
  formula: ProfileTargetCalculationFormula;
  macro_preset: ProfileTargetCalculationMacroPreset;
  special_condition: SpecialCondition;
  lactation_period: LactationPeriod | "";
};

type CalculatorErrors = {
  age?: string;
  height_cm?: string;
  weight_kg?: string;
};

const INITIAL_FORM: CalculatorForm = {
  sex: "female",
  age: "25",
  height_cm: "165",
  weight_kg: "60",
  activity_level: "moderate",
  goal: "maintain",
  formula: "mifflin_st_jeor",
  macro_preset: "balanced",
  special_condition: "none",
  lactation_period: "",
};

const FORMULA_LABELS: Record<ProfileTargetCalculationFormula, string> = {
  mifflin_st_jeor: "Миффлина–Сан Жеора",
  revised_harris_benedict: "Харриса–Бенедикта",
  who_fao_unu: "ВОЗ",
};

const GOAL_LABELS: Record<ProfileTargetCalculationGoal, string> = {
  maintain: "Поддержание",
  lose: "Снижение",
  gain: "Набор",
};

const SEX_OPTIONS = [
  { value: "male", label: "Мужской" },
  { value: "female", label: "Женский" },
];

const ACTIVITY_OPTIONS = [
  { value: "sedentary", label: "Сидячий" },
  { value: "light", label: "Лёгкая активность" },
  { value: "moderate", label: "Умеренная активность" },
  { value: "active", label: "Высокая активность" },
  { value: "very_active", label: "Очень высокая активность" },
];

const GOAL_OPTIONS = [
  { value: "maintain", label: "Поддержание" },
  { value: "lose", label: "Снижение" },
  { value: "gain", label: "Набор" },
];

const MACRO_PRESET_OPTIONS = [
  { value: "balanced", label: "Сбалансированное" },
  { value: "higher_protein", label: "Больше белка" },
  { value: "higher_carb", label: "Больше углеводов" },
];

const SPECIAL_CONDITION_OPTIONS = [
  { value: "none", label: "Нет" },
  { value: "pregnant", label: "Беременность" },
  { value: "breastfeeding", label: "Грудное вскармливание" },
  { value: "medical_special_diet", label: "Лечебное питание / ограничения по здоровью" },
];

const LACTATION_PERIOD_OPTIONS = [
  { value: "", label: "Не указано" },
  { value: "first_6_months", label: "Первые 6 месяцев" },
  { value: "after_6_months", label: "После 6 месяцев" },
  { value: "unknown", label: "Точно не знаю" },
];

function parseNumber(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

function validateForm(form: CalculatorForm): { errors: CalculatorErrors; payload: ProfileTargetCalculationInput | null } {
  const errors: CalculatorErrors = {};

  const age = parseNumber(form.age);
  if (age === null || !Number.isInteger(age) || age < 18 || age > 100) {
    errors.age = "Возраст должен быть целым числом от 18 до 100.";
  }

  const heightCm = parseNumber(form.height_cm);
  if (heightCm === null || heightCm < 100 || heightCm > 250) {
    errors.height_cm = "Рост должен быть в диапазоне от 100 до 250 см.";
  }

  const weightKg = parseNumber(form.weight_kg);
  if (weightKg === null || weightKg < 30 || weightKg > 300) {
    errors.weight_kg = "Вес должен быть в диапазоне от 30 до 300 кг.";
  }

  if (Object.keys(errors).length > 0 || age === null || heightCm === null || weightKg === null) {
    return { errors, payload: null };
  }

  return {
    errors,
    payload: {
      sex: form.sex,
      age,
      height_cm: heightCm,
      weight_kg: weightKg,
      activity_level: form.activity_level,
      goal: form.goal,
      formula: form.formula,
      macro_preset: form.macro_preset,
      special_condition: form.special_condition,
      lactation_period: form.special_condition === "breastfeeding" ? (form.lactation_period || "unknown") : null,
    },
  };
}

function formatMacro(value: number): string {
  return value.toFixed(1);
}

type ProfileTargetCalculatorPageProps = {
  embedded?: boolean;
};

export function ProfileTargetCalculatorPage({ embedded = false }: ProfileTargetCalculatorPageProps) {
  const [form, setForm] = useState<CalculatorForm>(INITIAL_FORM);
  const [errors, setErrors] = useState<CalculatorErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ProfileTargetCalculationResult | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadLatest = async () => {
      setLoadingLatest(true);
      try {
        const latest = await getLatestProfileTargetCalculation();
        if (cancelled) return;
        setResult(latest);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setResult(null);
          setApiError(null);
        } else {
          setApiError(err instanceof Error ? err.message : "Не удалось загрузить последний расчёт.");
        }
      } finally {
        if (!cancelled) setLoadingLatest(false);
      }
    };

    void loadLatest();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateField = <K extends keyof CalculatorForm>(field: K, value: CalculatorForm[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setApiError(null);
    setErrors((prev) => {
      if (!(field in prev)) return prev;
      const next = { ...prev };
      delete next[field as keyof CalculatorErrors];
      return next;
    });
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const { errors: validationErrors, payload } = validateForm(form);
    setErrors(validationErrors);
    if (!payload) {
      return;
    }

    setSubmitting(true);
    setApiError(null);
    try {
      const nextResult = await calculateProfileTarget(payload);
      setResult(nextResult);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Не удалось выполнить расчёт.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className={`calculator-page ${embedded ? "calculator-page-embedded" : ""}`.trim()}>
      <div className="calculator-shell">
        <header className="calculator-head">
          <div>
            <h1 className="calculator-title">Калькулятор КБЖУ</h1>
            <p className="calculator-subtitle">
              Калькулятор помогает получить ориентировочные значения калорийности, белков, жиров и углеводов для
              профиля. Это не медицинская рекомендация.
            </p>
          </div>
        </header>

        <form className="calculator-form" onSubmit={onSubmit} noValidate>
          <div className="calculator-grid">
            <label className="calculator-field" htmlFor="calculator-sex">
              <span className="calculator-label">Пол</span>
              <CustomSelect
                id="calculator-sex"
                value={form.sex}
                options={SEX_OPTIONS}
                onChange={(value) => updateField("sex", value as ProfileTargetCalculationSex)}
                disabled={submitting}
                ariaLabel="Пол"
                triggerClassName="calculator-input"
              />
              <div className="calculator-error-slot" aria-live="polite" />
            </label>

            <label className="calculator-field" htmlFor="calculator-age">
              <span className="calculator-label">Возраст</span>
              <input
                id="calculator-age"
                className={`calculator-input ${errors.age ? "is-invalid" : ""}`}
                type="number"
                min={18}
                max={100}
                step={1}
                value={form.age}
                onChange={(e) => updateField("age", e.target.value)}
                disabled={submitting}
              />
              <div className="calculator-error-slot" aria-live="polite">
                {errors.age && <p className="calculator-error">{errors.age}</p>}
              </div>
            </label>

            <label className="calculator-field" htmlFor="calculator-height">
              <span className="calculator-label">Рост, см</span>
              <input
                id="calculator-height"
                className={`calculator-input ${errors.height_cm ? "is-invalid" : ""}`}
                type="number"
                min={100}
                max={250}
                step={0.1}
                value={form.height_cm}
                onChange={(e) => updateField("height_cm", e.target.value)}
                disabled={submitting}
              />
              <div className="calculator-error-slot" aria-live="polite">
                {errors.height_cm && <p className="calculator-error">{errors.height_cm}</p>}
              </div>
            </label>

            <label className="calculator-field" htmlFor="calculator-weight">
              <span className="calculator-label">Вес, кг</span>
              <input
                id="calculator-weight"
                className={`calculator-input ${errors.weight_kg ? "is-invalid" : ""}`}
                type="number"
                min={30}
                max={300}
                step={0.1}
                value={form.weight_kg}
                onChange={(e) => updateField("weight_kg", e.target.value)}
                disabled={submitting}
              />
              <div className="calculator-error-slot" aria-live="polite">
                {errors.weight_kg && <p className="calculator-error">{errors.weight_kg}</p>}
              </div>
            </label>

            <label className="calculator-field" htmlFor="calculator-activity">
              <span className="calculator-label">Уровень активности</span>
              <CustomSelect
                id="calculator-activity"
                value={form.activity_level}
                options={ACTIVITY_OPTIONS}
                onChange={(value) => updateField("activity_level", value as ProfileTargetCalculationActivityLevel)}
                disabled={submitting}
                ariaLabel="Уровень активности"
                triggerClassName="calculator-input"
              />
              <div className="calculator-error-slot" aria-live="polite" />
            </label>

            <label className="calculator-field" htmlFor="calculator-goal">
              <span className="calculator-label">Цель</span>
              <CustomSelect
                id="calculator-goal"
                value={form.goal}
                options={GOAL_OPTIONS}
                onChange={(value) => updateField("goal", value as ProfileTargetCalculationGoal)}
                disabled={submitting}
                ariaLabel="Цель"
                triggerClassName="calculator-input"
              />
              <div className="calculator-error-slot" aria-live="polite" />
            </label>

            <div className="calculator-field calculator-field-full">
              <span className="calculator-label">Формула расчёта</span>
              <p className="calculator-hint">Выберите способ оценки базового обмена.</p>
              <fieldset className="calculator-formula-cards" aria-label="Формула расчёта">
                <label className={`calculator-formula-card ${form.formula === "mifflin_st_jeor" ? "is-selected" : ""}`}>
                  <input
                    type="radio"
                    name="calculator-formula"
                    value="mifflin_st_jeor"
                    checked={form.formula === "mifflin_st_jeor"}
                    onChange={(e) => updateField("formula", e.target.value as ProfileTargetCalculationFormula)}
                    disabled={submitting}
                    className="sr-only"
                  />
                  <span className="calculator-formula-card-head">
                    <span className="calculator-formula-card-title">Миффлина–Сан Жеора</span>
                    <InfoPopover
                      ariaLabel="Пояснение по формуле Миффлина–Сан Жеора"
                      text="Формула по умолчанию для ориентировочной оценки базового обмена у взрослых."
                    />
                  </span>
                  <span className="calculator-formula-card-subtitle">По умолчанию</span>
                </label>

                <label className={`calculator-formula-card ${form.formula === "revised_harris_benedict" ? "is-selected" : ""}`}>
                  <input
                    type="radio"
                    name="calculator-formula"
                    value="revised_harris_benedict"
                    checked={form.formula === "revised_harris_benedict"}
                    onChange={(e) => updateField("formula", e.target.value as ProfileTargetCalculationFormula)}
                    disabled={submitting}
                    className="sr-only"
                  />
                  <span className="calculator-formula-card-head">
                    <span className="calculator-formula-card-title">Харриса–Бенедикта</span>
                    <InfoPopover
                      ariaLabel="Пояснение по формуле Харриса–Бенедикта"
                      text="Альтернативная формула оценки базового обмена. Результат может немного отличаться."
                    />
                  </span>
                  <span className="calculator-formula-card-subtitle">Альтернативный расчёт</span>
                </label>

                <label className={`calculator-formula-card ${form.formula === "who_fao_unu" ? "is-selected" : ""}`}>
                  <input
                    type="radio"
                    name="calculator-formula"
                    value="who_fao_unu"
                    checked={form.formula === "who_fao_unu"}
                    onChange={(e) => updateField("formula", e.target.value as ProfileTargetCalculationFormula)}
                    disabled={submitting}
                    className="sr-only"
                  />
                  <span className="calculator-formula-card-head">
                    <span className="calculator-formula-card-title">ВОЗ</span>
                    <InfoPopover
                      ariaLabel="Пояснение по формуле ВОЗ"
                      text="Расчёт по международной методике FAO/WHO/UNU. В интерфейсе она сокращённо указана как ВОЗ."
                    />
                  </span>
                  <span className="calculator-formula-card-subtitle">Международная методика</span>
                </label>
              </fieldset>
              <div className="calculator-error-slot" aria-live="polite" />
            </div>

            <label className="calculator-field" htmlFor="calculator-macros">
              <span className="calculator-label">Распределение БЖУ</span>
              <CustomSelect
                id="calculator-macros"
                value={form.macro_preset}
                options={MACRO_PRESET_OPTIONS}
                onChange={(value) => updateField("macro_preset", value as ProfileTargetCalculationMacroPreset)}
                disabled={submitting}
                ariaLabel="Распределение БЖУ"
                triggerClassName="calculator-input"
              />
              <div className="calculator-error-slot" aria-live="polite" />
            </label>

            <label className="calculator-field" htmlFor="calculator-special-condition">
              <span className="calculator-label">Дополнительные параметры</span>
              <p className="calculator-hint">Укажите, если расчёт требует дополнительных уточнений.</p>
              <CustomSelect
                id="calculator-special-condition"
                value={form.special_condition}
                options={SPECIAL_CONDITION_OPTIONS}
                onChange={(value) => {
                  const next = value as SpecialCondition;
                  updateField("special_condition", next);
                  if (next !== "breastfeeding") {
                    updateField("lactation_period", "");
                  }
                }}
                disabled={submitting}
                ariaLabel="Дополнительные параметры"
                triggerClassName="calculator-input"
              />
              <div className="calculator-error-slot" aria-live="polite" />
            </label>

            {form.special_condition === "breastfeeding" && (
              <label className="calculator-field" htmlFor="calculator-lactation-period">
                <span className="calculator-label">Период грудного вскармливания</span>
                <CustomSelect
                  id="calculator-lactation-period"
                  value={form.lactation_period}
                  options={LACTATION_PERIOD_OPTIONS}
                  onChange={(value) => updateField("lactation_period", value as LactationPeriod | "")}
                  disabled={submitting}
                  ariaLabel="Период грудного вскармливания"
                  triggerClassName="calculator-input"
                />
                <div className="calculator-error-slot" aria-live="polite" />
              </label>
            )}
          </div>

          {apiError && <Alert text={apiError} />}

          <div className="calculator-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? "Считаем..." : "Рассчитать"}
            </button>
          </div>
        </form>

        {loadingLatest && !result ? <p className="calculator-loading">Загружаем последний расчёт...</p> : null}

        {!loadingLatest && !result && !apiError && (
          <p className="calculator-empty-state">
            Последнего расчёта пока нет. Заполните параметры и нажмите «Рассчитать».
          </p>
        )}

        {result && (
          <section className="calculator-result-card" aria-live="polite">
            <h2 className="calculator-result-title">Результат расчёта</h2>
            <dl className="calculator-result-grid">
              <div>
                <dt className="calculator-term-with-info">
                  <span>Базовый обмен, BMR</span>
                  <InfoPopover
                    ariaLabel="Пояснение по BMR"
                    text="BMR — базовый обмен веществ. Это примерная энергия, которую организм тратит в состоянии покоя на базовые функции: дыхание, работу сердца, поддержание температуры и другие процессы."
                  />
                </dt>
                <dd>{result.bmr} ккал</dd>
              </div>
              <div>
                <dt className="calculator-term-with-info">
                  <span>Суточная потребность с учётом активности, TDEE</span>
                  <InfoPopover
                    ariaLabel="Пояснение по TDEE"
                    text="TDEE — ориентировочная суточная потребность в энергии с учётом активности. Рассчитывается как BMR, умноженный на коэффициент активности."
                  />
                </dt>
                <dd>{result.tdee} ккал</dd>
              </div>
              <div>
                <dt>Калории</dt>
                <dd>{result.target_kcal} ккал</dd>
              </div>
              <div>
                <dt>Белки</dt>
                <dd>{formatMacro(result.target_protein)} г</dd>
              </div>
              <div>
                <dt>Жиры</dt>
                <dd>{formatMacro(result.target_fat)} г</dd>
              </div>
              <div>
                <dt>Углеводы</dt>
                <dd>{formatMacro(result.target_carbs)} г</dd>
              </div>
              <div>
                <dt className="calculator-term-with-info">
                  <span>Клетчатка</span>
                  <InfoPopover
                    ariaLabel="Пояснение по клетчатке"
                    text="Клетчатка не рассчитывается по выбранной формуле BMR. В калькуляторе используется ориентировочное значение 25 г в день, которое можно вручную изменить в профиле."
                  />
                </dt>
                <dd>{formatMacro(result.target_fiber)} г</dd>
              </div>
              <div>
                <dt>Формула</dt>
                <dd>{FORMULA_LABELS[result.formula]}</dd>
              </div>
              <div>
                <dt>Цель</dt>
                <dd>{GOAL_LABELS[result.goal]}</dd>
              </div>
            </dl>

            {result.warning_message && (
              <div className="calculator-warning" role="status" aria-live="polite">
                {result.warning_message}
              </div>
            )}
          </section>
        )}

        <section className="calculator-info" aria-label="Важная информация">
          <p>
            Значения являются ориентировочными. Система не ставит диагнозы, не назначает лечебные диеты и не
            заменяет консультацию специалиста. При заболеваниях, беременности, грудном вскармливании или других
            состояниях, требующих особого питания, необходимо обратиться к врачу или диетологу. В приложении можно
            использовать исключения продуктов, ограничения профиля и собственные рецепты, но система не подбирает
            лечебное питание.
          </p>
        </section>
      </div>
    </section>
  );
}
