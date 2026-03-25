import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { useProfiles } from "../context/ProfilesContext";

function navClass({ isActive }: { isActive: boolean }) {
  return `nav-link ${isActive ? "nav-link-active" : ""}`;
}

export function Navbar() {
  const { token, logout } = useAuth();
  const { profiles, activeProfileId, loading, setActiveProfileId } = useProfiles();

  const profileValue = activeProfileId !== null ? String(activeProfileId) : "";

  return (
    <header className="topbar">
      <div className={`topbar-inner ${token ? "topbar-inner-auth" : ""}`}>
        {token ? (
          <>
            <Link to="/planner" className="brand topbar-brand">
              Nutrition Planner
            </Link>

            <nav className="main-nav main-nav-centered" aria-label="Основная навигация">
              <NavLink to="/planner" className={navClass}>
                Планировщик
              </NavLink>
              <NavLink to="/foods" className={navClass}>
                Foods
              </NavLink>
              <NavLink to="/recipes" className={navClass}>
                Рецепты
              </NavLink>
              <NavLink to="/shopping" className={navClass}>
                Покупки
              </NavLink>
              <NavLink to="/plans" className={navClass}>
                Планы
              </NavLink>
            </nav>

            <nav className="topbar-nav" aria-label="Пользовательское меню">
              <label className="profile-picker" htmlFor="active-profile-picker">
                <span className="sr-only">Активный профиль</span>
                <select
                  id="active-profile-picker"
                  className="profile-picker-select"
                  value={profileValue}
                  disabled={loading || profiles.length === 0}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    if (Number.isInteger(next)) setActiveProfileId(next);
                  }}
                >
                  {loading && <option value="">Загрузка…</option>}
                  {!loading && profiles.length === 0 && <option value="">Нет профилей</option>}
                  {!loading &&
                    profiles.map((profile) => (
                      <option key={profile.id} value={String(profile.id)}>
                        {profile.name}
                      </option>
                    ))}
                </select>
              </label>

              <NavLink to="/settings" className={navClass}>
                Настройки
              </NavLink>

              <button type="button" className="nav-link nav-link-button" onClick={logout}>
                Выйти
              </button>
            </nav>
          </>
        ) : (
          <>
            <div className="topbar-left">
              <Link to="/" className="brand">
                Nutrition Planner
              </Link>
            </div>

            <nav className="topbar-nav" aria-label="Пользовательское меню">
              <Link to="/login" className="nav-link">
                Вход
              </Link>
              <Link to="/register" className="nav-link nav-link-primary">
                Регистрация
              </Link>
            </nav>
          </>
        )}
      </div>
    </header>
  );
}
