import { Link, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { HomePage } from "./pages/HomePage";
import { SettingsPage } from "./pages/SettingsPage";
import { RequireAuth } from "./auth/RequireAuth";
import { useAuth } from "./auth/useAuth";
import "./App.css";

function TopBar() {
  const { token, user } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand">
          Nutrition Planner
        </Link>

        <nav className="topbar-nav">
          {token ? (
            <>
              <span className="status-text">Вы вошли как {user?.username}</span>
              <Link to="/settings" className="nav-link">
                Настройки
              </Link>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">
                Вход
              </Link>
              <Link to="/register" className="nav-link nav-link-primary">
                Регистрация
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <TopBar />
      <main>
        <Routes>
          <Route
            path="/"
            element={
              <RequireAuth>
                <HomePage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            }
          />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="*" element={<div className="not-found">404</div>} />
        </Routes>
      </main>
    </div>
  );
}
