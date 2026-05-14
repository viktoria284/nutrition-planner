import { useMemo } from "react";
import { useProfiles } from "../context/ProfilesContext";

export function PlannerPage() {
  const { activeProfile, loading, error } = useProfiles();

  const targets = useMemo(() => {
    if (!activeProfile) return [];

    const rows: string[] = [];
    if (activeProfile.target_kcal !== null) rows.push(`Калории: ${activeProfile.target_kcal} ккал`);
    if (activeProfile.target_protein !== null) rows.push(`Белки: ${activeProfile.target_protein} г`);
    if (activeProfile.target_fat !== null) rows.push(`Жиры: ${activeProfile.target_fat} г`);
    if (activeProfile.target_carbs !== null) rows.push(`Углеводы: ${activeProfile.target_carbs} г`);
    if (activeProfile.target_fiber !== null) rows.push(`Клетчатка: ${activeProfile.target_fiber} г`);
    return rows;
  }, [activeProfile]);

  return (
    <section className="stub-page">
      <h1 className="stub-title">Планировщик</h1>
      <p className="stub-subtitle">В разработке</p>

      {loading && <p className="stub-note">Загрузка профилей...</p>}
      {!loading && error && <p className="stub-note">{error}</p>}

      {!loading && !error && (
        <article className="stub-card">
          <p className="stub-row">
            <b>Активный профиль:</b> {activeProfile?.name ?? "Не выбран"}
          </p>

          {targets.length > 0 ? (
            <ul className="stub-list">
              {targets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="stub-row">Цели не заданы.</p>
          )}
        </article>
      )}
    </section>
  );
}
