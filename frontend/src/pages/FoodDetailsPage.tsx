import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { createServing, deleteServing, getFood, listServings, type FoodItem, type FoodServing } from "../api/foods";
import { Alert } from "../components/Alert";
import "./FoodsPage.css";

type ServingForm = {
  name: string;
  grams: string;
};

type ServingFormErrors = {
  name?: string;
  grams?: string;
  form?: string;
};

const EMPTY_SERVING_FORM: ServingForm = {
  name: "",
  grams: "",
};

function formatNutrient(value: number | string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

function resolveApiMessage(err: unknown, fallback: string, notFoundMessage: string): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Требуется повторный вход.";
    if (err.status === 404) return notFoundMessage;
  }
  return err instanceof Error ? err.message : fallback;
}

function validateServingForm(form: ServingForm): { errors: ServingFormErrors; payload: { name: string; grams: number } | null } {
  const errors: ServingFormErrors = {};

  const name = form.name.trim();
  if (!name) errors.name = "Введите название порции.";

  const gramsRaw = form.grams.trim();
  if (!gramsRaw) {
    errors.grams = "Введите число ≥ 1";
  } else {
    const grams = Number(gramsRaw);
    if (!Number.isFinite(grams) || grams < 1) errors.grams = "Введите число ≥ 1";
  }

  if (Object.keys(errors).length > 0) {
    errors.form = "Проверьте поля формы.";
    return { errors, payload: null };
  }

  return {
    errors: {},
    payload: { name, grams: Number(gramsRaw) },
  };
}

export function FoodDetailsPage() {
  const { id } = useParams();

  const [food, setFood] = useState<FoodItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [servings, setServings] = useState<FoodServing[]>([]);
  const [servingsLoading, setServingsLoading] = useState(false);
  const [servingsError, setServingsError] = useState<string | null>(null);
  const [servingsReloadSeq, setServingsReloadSeq] = useState(0);

  const [servingForm, setServingForm] = useState<ServingForm>(EMPTY_SERVING_FORM);
  const [servingErrors, setServingErrors] = useState<ServingFormErrors>({});
  const [creatingServing, setCreatingServing] = useState(false);
  const [deletingServingId, setDeletingServingId] = useState<number | null>(null);

  const refreshServings = () => setServingsReloadSeq((prev) => prev + 1);

  useEffect(() => {
    if (!id) {
      setFood(null);
      setLoading(false);
      setError("Некорректный id продукта.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getFood(id)
      .then((item) => {
        if (cancelled) return;
        setFood(item);
      })
      .catch((err) => {
        if (cancelled) return;
        setFood(null);
        setError(resolveApiMessage(err, "Не удалось загрузить продукт.", "Продукт не найден."));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id) {
      setServings([]);
      setServingsLoading(false);
      setServingsError("Некорректный id продукта.");
      return;
    }

    let cancelled = false;
    setServingsLoading(true);
    setServingsError(null);

    listServings(id)
      .then((items) => {
        if (cancelled) return;
        setServings(items);
      })
      .catch((err) => {
        if (cancelled) return;
        setServings([]);
        setServingsError(resolveApiMessage(err, "Не удалось загрузить порции.", "Продукт не найден."));
      })
      .finally(() => {
        if (cancelled) return;
        setServingsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, servingsReloadSeq]);

  const updateServingField = (field: keyof ServingForm, value: string) => {
    setServingForm((prev) => ({ ...prev, [field]: value }));
    setServingErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onCreateServing = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!id) {
      setServingErrors({ form: "Некорректный id продукта." });
      return;
    }

    const { errors, payload } = validateServingForm(servingForm);
    if (!payload) {
      setServingErrors(errors);
      return;
    }

    setCreatingServing(true);
    setServingErrors({});

    try {
      await createServing(id, payload);
      setServingForm(EMPTY_SERVING_FORM);
      refreshServings();
    } catch (err) {
      setServingErrors({
        form: resolveApiMessage(err, "Не удалось добавить порцию.", "Продукт не найден."),
      });
    } finally {
      setCreatingServing(false);
    }
  };

  const onDeleteServing = async (serving: FoodServing) => {
    if (deletingServingId !== null) return;

    const confirmed = window.confirm(`Удалить порцию "${serving.name}"?`);
    if (!confirmed) return;

    setDeletingServingId(serving.id);
    setServingErrors((prev) => {
      if (!prev.form) return prev;
      const next = { ...prev };
      delete next.form;
      return next;
    });

    try {
      await deleteServing(serving.id);
      refreshServings();
    } catch (err) {
      setServingErrors({
        form: resolveApiMessage(err, "Не удалось удалить порцию.", "Порция не найдена."),
      });
    } finally {
      setDeletingServingId(null);
    }
  };

  return (
    <section className="foods-page">
      <div className="foods-shell">
        <div className="foods-details-head">
          <Link to="/foods" className="btn btn-secondary">
            Назад
          </Link>
        </div>

        {loading && <p className="foods-note">Загрузка...</p>}
        {!loading && error && <Alert text={error} />}

        {!loading && !error && food && (
          <article className="food-details-card">
            <h1 className="food-details-title">{food.name}</h1>
            {food.brand && <p className="food-details-brand">{food.brand}</p>}
            <p className="food-details-subtitle">Нутриенты на 100 г</p>

            <dl className="food-nutrients">
              <div className="food-nutrients-row">
                <dt>Калории</dt>
                <dd>{formatNutrient(food.kcal)} ккал</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Белки</dt>
                <dd>{formatNutrient(food.protein)} г</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Жиры</dt>
                <dd>{formatNutrient(food.fat)} г</dd>
              </div>
              <div className="food-nutrients-row">
                <dt>Углеводы</dt>
                <dd>{formatNutrient(food.carbs)} г</dd>
              </div>
            </dl>
          </article>
        )}

        {!loading && !error && food && (
          <article className="food-details-card servings-card">
            <div className="servings-head">
              <h2 className="servings-title">Порции</h2>
            </div>

            {servingsLoading && <p className="foods-note">Загрузка...</p>}

            {!servingsLoading && servingsError && (
              <div className="servings-error-block">
                <Alert text={servingsError} />
                <button type="button" className="btn btn-secondary" onClick={refreshServings}>
                  Повторить
                </button>
              </div>
            )}

            {!servingsLoading && !servingsError && servings.length === 0 && <p className="foods-note">Порций пока нет</p>}

            {!servingsLoading && !servingsError && servings.length > 0 && (
              <ul className="servings-list">
                {servings.map((serving) => (
                  <li key={serving.id} className="serving-row">
                    <p className="serving-line">
                      {serving.name} — {formatNutrient(serving.grams)} г
                    </p>
                    <button
                      type="button"
                      className="btn btn-secondary serving-delete-btn"
                      onClick={() => void onDeleteServing(serving)}
                      disabled={deletingServingId !== null}
                    >
                      {deletingServingId === serving.id ? "Удаляем..." : "Удалить"}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {servingErrors.form && <Alert text={servingErrors.form} />}

            <form className="serving-form" onSubmit={onCreateServing} noValidate>
              <h3 className="serving-form-title">Добавить порцию</h3>

              <div className="serving-form-grid">
                <label className="foods-field" htmlFor="serving_name">
                  <span className="foods-field-label">Название</span>
                  <input
                    id="serving_name"
                    className={`foods-field-input ${servingErrors.name ? "is-invalid" : ""}`}
                    type="text"
                    value={servingForm.name}
                    onChange={(e) => updateServingField("name", e.target.value)}
                    placeholder="Например, 1 штука"
                  />
                  {servingErrors.name && <p className="foods-field-error">{servingErrors.name}</p>}
                </label>

                <label className="foods-field" htmlFor="serving_grams">
                  <span className="foods-field-label">Граммы</span>
                  <input
                    id="serving_grams"
                    className={`foods-field-input ${servingErrors.grams ? "is-invalid" : ""}`}
                    type="number"
                    min={1}
                    step="any"
                    value={servingForm.grams}
                    onChange={(e) => updateServingField("grams", e.target.value)}
                    placeholder="120"
                  />
                  {servingErrors.grams && <p className="foods-field-error">{servingErrors.grams}</p>}
                </label>
              </div>

              <div className="foods-create-actions">
                <button type="submit" className="btn btn-primary" disabled={creatingServing || deletingServingId !== null}>
                  {creatingServing ? "Добавляем..." : "Добавить порцию"}
                </button>
              </div>
            </form>
          </article>
        )}
      </div>
    </section>
  );
}
