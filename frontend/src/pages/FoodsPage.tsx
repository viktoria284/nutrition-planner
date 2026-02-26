import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createFood, searchFoods, type FoodCreatePayload, type FoodItem, type FoodSource } from "../api/foods";
import { Alert } from "../components/Alert";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import "./FoodsPage.css";

type CreateFoodForm = {
  name: string;
  brand: string;
  kcal: string;
  protein: string;
  fat: string;
  carbs: string;
};

type CreateFoodErrors = {
  name?: string;
  brand?: string;
  kcal?: string;
  protein?: string;
  fat?: string;
  carbs?: string;
  form?: string;
};

const EMPTY_CREATE_FORM: CreateFoodForm = {
  name: "",
  brand: "",
  kcal: "",
  protein: "",
  fat: "",
  carbs: "",
};

const SOURCE_LABELS: Record<FoodSource, string> = {
  private: "Мои",
  verified: "Verified",
  community: "Community",
};

function formatNutrient(value: number): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

function sourceBadgeClass(source: FoodSource): string {
  if (source === "private") return "food-source-badge is-private";
  if (source === "verified") return "food-source-badge is-verified";
  return "food-source-badge is-community";
}

function validateCreateForm(form: CreateFoodForm): { errors: CreateFoodErrors; payload: FoodCreatePayload | null } {
  const errors: CreateFoodErrors = {};

  const name = form.name.trim();
  const brand = form.brand.trim();

  if (!name) errors.name = "Введите название.";

  const numericKeys: Array<keyof Pick<CreateFoodForm, "kcal" | "protein" | "fat" | "carbs">> = [
    "kcal",
    "protein",
    "fat",
    "carbs",
  ];

  const parsed: Partial<Record<"kcal" | "protein" | "fat" | "carbs", number>> = {};

  for (const key of numericKeys) {
    const raw = form[key].trim();
    if (!raw) continue;

    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0) {
      errors[key] = "Введите число ≥ 0";
      continue;
    }

    parsed[key] = value;
  }

  if (Object.keys(errors).length > 0) {
    errors.form = "Проверьте поля формы.";
    return { errors, payload: null };
  }

  if (parsed.kcal === undefined || parsed.protein === undefined || parsed.fat === undefined || parsed.carbs === undefined) {
    return {
      errors: { form: "Заполните kcal, protein, fat и carbs." },
      payload: null,
    };
  }

  return {
    errors: {},
    payload: {
      name,
      brand: brand || undefined,
      kcal: parsed.kcal as number,
      protein: parsed.protein as number,
      fat: parsed.fat as number,
      carbs: parsed.carbs as number,
    },
  };
}

export function FoodsPage() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 350);

  const [foods, setFoods] = useState<FoodItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadSeq, setReloadSeq] = useState(0);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateFoodForm>(EMPTY_CREATE_FORM);
  const [createErrors, setCreateErrors] = useState<CreateFoodErrors>({});
  const [createLoading, setCreateLoading] = useState(false);

  const trimmedQuery = query.trim();
  const canSearch = trimmedQuery.length >= 2;

  useEffect(() => {
    const q = debouncedQuery.trim();
    if (q.length < 2) {
      setFoods([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    searchFoods({ q })
      .then((items) => {
        if (cancelled) return;
        setFoods(items);
      })
      .catch((err) => {
        if (cancelled) return;
        setFoods([]);
        setError(err instanceof Error ? err.message : "Не удалось загрузить продукты.");
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, reloadSeq]);

  const openCreateModal = () => {
    setCreateForm(EMPTY_CREATE_FORM);
    setCreateErrors({});
    setCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    if (createLoading) return;
    setCreateModalOpen(false);
    setCreateErrors({});
  };

  const updateCreateField = (field: keyof CreateFoodForm, value: string) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
    setCreateErrors((prev) => {
      if (!prev[field] && !prev.form) return prev;
      const next = { ...prev };
      delete next[field];
      delete next.form;
      return next;
    });
  };

  const onCreateFood = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const { errors, payload } = validateCreateForm(createForm);
    if (!payload) {
      setCreateErrors(errors);
      return;
    }

    setCreateLoading(true);
    setCreateErrors({});

    try {
      const created = await createFood(payload);
      const createdQuery = created.name.trim();

      setCreateModalOpen(false);
      setCreateForm(EMPTY_CREATE_FORM);

      if (createdQuery.length >= 2) {
        if (createdQuery.toLowerCase() === trimmedQuery.toLowerCase()) {
          setReloadSeq((prev) => prev + 1);
        }
        setQuery(createdQuery);
      } else if (trimmedQuery.length >= 2) {
        setReloadSeq((prev) => prev + 1);
      } else {
        setFoods((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      }
    } catch (err) {
      setCreateErrors({ form: err instanceof Error ? err.message : "Не удалось создать продукт." });
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <section className="foods-page">
      <div className="foods-shell">
        <div className="foods-head">
          <div>
            <h1 className="foods-title">Продукты</h1>
            <p className="foods-subtitle">Поиск по названию и бренду.</p>
          </div>

          <button type="button" className="btn btn-primary" onClick={openCreateModal}>
            Добавить продукт
          </button>
        </div>

        <label className="foods-search-field" htmlFor="foods-search-input">
          <span className="foods-search-label">Поиск</span>
          <input
            id="foods-search-input"
            className="foods-search-input"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Например, кефир"
            autoComplete="off"
          />
        </label>

        {!canSearch && <p className="foods-note">Введите минимум 2 символа</p>}
        {canSearch && loading && <p className="foods-note">Загрузка...</p>}
        {canSearch && !loading && error && <Alert text={error} />}
        {canSearch && !loading && !error && foods.length === 0 && <p className="foods-note">Ничего не найдено</p>}

        {canSearch && !loading && !error && foods.length > 0 && (
          <ul className="foods-list">
            {foods.map((food) => (
              <li key={food.id}>
                <Link to={`/foods/${food.id}`} className="food-row-link">
                  <div className="food-row-main">
                    <p className="food-row-title">{food.brand ? `${food.name} — ${food.brand}` : food.name}</p>
                  </div>

                  <div className="food-row-meta">
                    <span className={sourceBadgeClass(food.source)}>{SOURCE_LABELS[food.source]}</span>
                    <span className="food-row-kcal">{formatNutrient(food.kcal)} ккал</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {createModalOpen && (
        <div className="foods-modal-backdrop" role="presentation" onClick={closeCreateModal}>
          <div
            className="foods-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="foods-create-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="foods-create-title" className="foods-modal-title">
              Добавить продукт
            </h2>

            {createErrors.form && <Alert text={createErrors.form} />}

            <form className="foods-create-form" onSubmit={onCreateFood} noValidate>
              <label className="foods-field" htmlFor="create_food_name">
                <span className="foods-field-label">Название</span>
                <input
                  id="create_food_name"
                  className={`foods-field-input ${createErrors.name ? "is-invalid" : ""}`}
                  type="text"
                  value={createForm.name}
                  onChange={(e) => updateCreateField("name", e.target.value)}
                  placeholder="Например, Кефир 2.5%"
                  autoFocus
                />
                {createErrors.name && <p className="foods-field-error">{createErrors.name}</p>}
              </label>

              <label className="foods-field" htmlFor="create_food_brand">
                <span className="foods-field-label">Brand (опционально)</span>
                <input
                  id="create_food_brand"
                  className={`foods-field-input ${createErrors.brand ? "is-invalid" : ""}`}
                  type="text"
                  value={createForm.brand}
                  onChange={(e) => updateCreateField("brand", e.target.value)}
                  placeholder="Например, Простоквашино"
                />
                {createErrors.brand && <p className="foods-field-error">{createErrors.brand}</p>}
              </label>

              <div className="foods-grid">
                <label className="foods-field" htmlFor="create_food_kcal">
                  <span className="foods-field-label">Калории (ккал)</span>
                  <input
                    id="create_food_kcal"
                    className={`foods-field-input ${createErrors.kcal ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={createForm.kcal}
                    onChange={(e) => updateCreateField("kcal", e.target.value)}
                    placeholder="0"
                  />
                  {createErrors.kcal && <p className="foods-field-error">{createErrors.kcal}</p>}
                </label>

                <label className="foods-field" htmlFor="create_food_protein">
                  <span className="foods-field-label">Белки (г)</span>
                  <input
                    id="create_food_protein"
                    className={`foods-field-input ${createErrors.protein ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={createForm.protein}
                    onChange={(e) => updateCreateField("protein", e.target.value)}
                    placeholder="0"
                  />
                  {createErrors.protein && <p className="foods-field-error">{createErrors.protein}</p>}
                </label>

                <label className="foods-field" htmlFor="create_food_fat">
                  <span className="foods-field-label">Жиры (г)</span>
                  <input
                    id="create_food_fat"
                    className={`foods-field-input ${createErrors.fat ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={createForm.fat}
                    onChange={(e) => updateCreateField("fat", e.target.value)}
                    placeholder="0"
                  />
                  {createErrors.fat && <p className="foods-field-error">{createErrors.fat}</p>}
                </label>

                <label className="foods-field" htmlFor="create_food_carbs">
                  <span className="foods-field-label">Углеводы (г)</span>
                  <input
                    id="create_food_carbs"
                    className={`foods-field-input ${createErrors.carbs ? "is-invalid" : ""}`}
                    type="number"
                    min={0}
                    step="any"
                    value={createForm.carbs}
                    onChange={(e) => updateCreateField("carbs", e.target.value)}
                    placeholder="0"
                  />
                  {createErrors.carbs && <p className="foods-field-error">{createErrors.carbs}</p>}
                </label>
              </div>

              <div className="foods-create-actions">
                <button type="button" className="btn btn-secondary" onClick={closeCreateModal} disabled={createLoading}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={createLoading}>
                  {createLoading ? "Создание..." : "Создать"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
