import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../api/http";
import "./AuthPages.css";

export function LoginPage() {
  const { login, error, setError } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const nav = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const from = location.state?.from ?? "/";

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!identifier) {
      setError("Введите email или username.");
      return;
    }

    if (!password) {
      setError("Введите пароль.");
      return;
    }

    setSubmitting(true);
    try {
      await login(identifier, password);
      nav(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) setError("Неверный логин или пароль.");
        else setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Ошибка логина");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="auth-layout">
      <div className="auth-main">
        <div className="auth-main-inner">
          <h2 className="auth-title">Вход в систему</h2>
          <p className="auth-subtitle">Используй email или username и пароль.</p>

          {error && (
            <div className="auth-error" role="alert" aria-live="polite">
              {error}
            </div>
          )}

          <form className="auth-form" onSubmit={onSubmit} noValidate>
            <label className="auth-field">
              <span className="auth-label">Email или username</span>
              <input
                className="auth-input"
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoComplete="username"
                placeholder="you@mail.com"
              />
            </label>

            <label className="auth-field">
              <span className="auth-label">Пароль</span>
              <input
                className="auth-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
              />
            </label>

            <button className="auth-submit" disabled={submitting}>
              {submitting ? "Входим..." : "Войти"}
            </button>
          </form>

          <div className="auth-footer">
            Нет аккаунта?{" "}
            <Link to="/register" className="auth-footer-link">
              Регистрация
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
