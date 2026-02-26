import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getFood, type FoodItem } from "../api/foods";
import { Alert } from "../components/Alert";
import "./FoodsPage.css";

function formatNutrient(value: number): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  if (Number.isInteger(numeric)) return String(numeric);
  return numeric.toFixed(2).replace(/\.?0+$/, "");
}

export function FoodDetailsPage() {
  const { id } = useParams();

  const [food, setFood] = useState<FoodItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        setError(err instanceof Error ? err.message : "Не удалось загрузить продукт.");
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

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
      </div>
    </section>
  );
}
