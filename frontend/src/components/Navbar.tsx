import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { useProfiles } from "../context/ProfilesContext";
import { CustomSelect } from "./CustomSelect";
import { LogoutConfirmModal } from "./LogoutConfirmModal";

function navClass({ isActive }: { isActive: boolean }) {
  return `nav-link ${isActive ? "nav-link-active" : ""}`;
}

export function Navbar() {
  const { token, user, logout } = useAuth();
  const { profiles, activeProfileId, loading, setActiveProfileId } = useProfiles();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);

  const profileValue = activeProfileId !== null ? String(activeProfileId) : "";
  const profileOptions = loading
    ? [{ value: "", label: "Загрузка…", disabled: true }]
    : profiles.length === 0
      ? [{ value: "", label: "Нет профилей", disabled: true }]
      : profiles.map((profile) => ({ value: String(profile.id), label: profile.name }));
  const isAutoplanRoute = location.pathname.startsWith("/plans/autogenerate");
  const isPlansRoute =
    location.pathname.startsWith("/plans") &&
    !location.pathname.startsWith("/plans/autogenerate") &&
    !location.pathname.startsWith("/plans/autogenerate/");

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setMobileMenuOpen(false), 0);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname]);

  const requestLogout = () => {
    setLogoutConfirmOpen(true);
  };

  const closeLogoutConfirm = () => {
    setLogoutConfirmOpen(false);
  };

  const confirmLogout = () => {
    setLogoutConfirmOpen(false);
    setMobileMenuOpen(false);
    logout();
  };

  return (
    <header className="topbar">
      <div className={`topbar-inner ${token ? "topbar-inner-auth" : ""}`}>
        {token ? (
          <>
            <div className="topbar-auth-desktop">
              <Link to="/plans" className="brand topbar-brand">
                Nutrition Planner
              </Link>

              <nav className="main-nav main-nav-centered" aria-label="Основная навигация">
                <NavLink to="/calendar" className={navClass}>
                  Календарь
                </NavLink>
                <NavLink to="/plans" className={`nav-link ${isPlansRoute ? "nav-link-active" : ""}`}>
                  Планы
                </NavLink>
                <NavLink to="/plans/autogenerate" className={`nav-link ${isAutoplanRoute ? "nav-link-active" : ""}`}>
                  Автоплан
                </NavLink>
                <NavLink to="/recipes" className={navClass}>
                  Рецепты
                </NavLink>
                <NavLink to="/foods" className={navClass}>
                  Продукты
                </NavLink>
                <NavLink to="/shopping-lists" className={navClass}>
                  Покупки
                </NavLink>
                {(user?.role === "admin" || user?.role === "superadmin") && (
                  <NavLink to="/admin" className={navClass}>
                    Админ
                  </NavLink>
                )}
              </nav>

              <nav className="topbar-nav" aria-label="Пользовательское меню">
                <div className="profile-picker">
                  <span className="sr-only">Активный профиль</span>
                  <CustomSelect
                    id="active-profile-picker"
                    value={profileValue}
                    options={profileOptions}
                    disabled={loading || profiles.length === 0}
                    ariaLabel="Активный профиль"
                    triggerClassName="profile-picker-select"
                    onChange={(nextValue) => {
                      const next = Number(nextValue);
                      if (Number.isInteger(next)) setActiveProfileId(next);
                    }}
                  />
                </div>

                <NavLink to="/settings" className={navClass}>
                  Настройки
                </NavLink>

                <button type="button" className="nav-link nav-link-button" onClick={requestLogout}>
                  Выйти
                </button>
              </nav>
            </div>

            <div className="topbar-auth-mobile">
              <Link to="/plans" className="brand topbar-brand topbar-brand-mobile">
                Nutrition
              </Link>

              <div className="profile-picker profile-picker-mobile">
                <span className="sr-only">Активный профиль</span>
                <CustomSelect
                  id="active-profile-picker-mobile"
                  value={profileValue}
                  options={profileOptions}
                  disabled={loading || profiles.length === 0}
                  ariaLabel="Активный профиль"
                  triggerClassName="profile-picker-select profile-picker-select-mobile"
                  onChange={(nextValue) => {
                    const next = Number(nextValue);
                    if (Number.isInteger(next)) setActiveProfileId(next);
                  }}
                />
              </div>

              <button
                type="button"
                className="icon-button topbar-menu-toggle"
                aria-label={mobileMenuOpen ? "Закрыть меню" : "Открыть меню"}
                aria-expanded={mobileMenuOpen}
                onClick={() => setMobileMenuOpen((prev) => !prev)}
              >
                ☰
              </button>
            </div>

            <div className={`topbar-mobile-menu ${mobileMenuOpen ? "is-open" : ""}`} aria-hidden={!mobileMenuOpen}>
              <nav className="topbar-mobile-menu-nav" aria-label="Мобильная навигация">
                <NavLink
                  to="/calendar"
                  className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Календарь
                </NavLink>
                <NavLink
                  to="/plans"
                  className={`nav-link topbar-mobile-menu-link ${isPlansRoute ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Планы
                </NavLink>
                <NavLink
                  to="/plans/autogenerate"
                  className={`nav-link topbar-mobile-menu-link ${isAutoplanRoute ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Автоплан
                </NavLink>
                <NavLink
                  to="/recipes"
                  className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Рецепты
                </NavLink>
                <NavLink
                  to="/foods"
                  className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Продукты
                </NavLink>
                <NavLink
                  to="/shopping-lists"
                  className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Покупки
                </NavLink>
                {(user?.role === "admin" || user?.role === "superadmin") && (
                  <NavLink
                    to="/admin"
                    className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Админ
                  </NavLink>
                )}
                <NavLink
                  to="/settings"
                  className={({ isActive }) => `nav-link topbar-mobile-menu-link ${isActive ? "nav-link-active" : ""}`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Настройки
                </NavLink>
                <button
                  type="button"
                  className="nav-link nav-link-button topbar-mobile-menu-link"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    requestLogout();
                  }}
                >
                  Выйти
                </button>
              </nav>
            </div>
            <LogoutConfirmModal
              open={logoutConfirmOpen}
              onCancel={closeLogoutConfirm}
              onConfirm={confirmLogout}
            />
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
