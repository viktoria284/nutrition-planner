import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../api/http";
import "./AuthPages.css";

export function LoginPage() {
  const { login, error, setError } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
              <div className="auth-password-wrap">
                <input
                  className="auth-input auth-input-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((prev) => !prev)}
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
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

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M2.2 12s3.2-6 9.8-6 9.8 6 9.8 6-3.2 6-9.8 6-9.8-6-9.8-6Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M2.2 12s3.2-6 9.8-6a10.3 10.3 0 0 1 5.7 1.7M21.8 12s-3.2 6-9.8 6A10.3 10.3 0 0 1 6.3 16.3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m4 4 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
