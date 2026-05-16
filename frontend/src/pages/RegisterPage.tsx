import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../api/http";
import "./AuthPages.css";

export function RegisterPage() {
  const { register, error, setError } = useAuth();
  const nav = useNavigate();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showPassword2, setShowPassword2] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !username || !password) {
      setError("Заполни email, username и пароль.");
      return;
    }
    if (password !== password2) {
      setError("Пароли не совпадают.");
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, username, password });
      nav("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) setError("Неверный логин или пароль.");
        else if (err.status === 409) setError("Email или username уже заняты.");
        else setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Ошибка регистрации");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="auth-layout">
      <div className="auth-main">
        <div className="auth-main-inner">
          <h2 className="auth-title">Регистрация</h2>
          <p className="auth-subtitle">Заполни поля и начни пользоваться сервисом.</p>

          {error && (
            <div className="auth-error" role="alert" aria-live="polite">
              {error}
            </div>
          )}

          <form className="auth-form" onSubmit={onSubmit} noValidate>
            <label className="auth-field">
              <span className="auth-label">Email</span>
              <input
                className="auth-input"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="you@mail.com"
              />
            </label>

            <label className="auth-field">
              <span className="auth-label">Username</span>
              <input
                className="auth-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="username"
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
                  autoComplete="new-password"
                  placeholder="Минимум 8 символов"
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

            <label className="auth-field">
              <span className="auth-label">Повтори пароль</span>
              <div className="auth-password-wrap">
                <input
                  className="auth-input auth-input-password"
                  type={showPassword2 ? "text" : "password"}
                  value={password2}
                  onChange={(e) => setPassword2(e.target.value)}
                  autoComplete="new-password"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  aria-label={showPassword2 ? "Скрыть пароль" : "Показать пароль"}
                  aria-pressed={showPassword2}
                  onClick={() => setShowPassword2((prev) => !prev)}
                >
                  {showPassword2 ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
            </label>

            <button className="auth-submit" disabled={submitting}>
              {submitting ? "Создаём..." : "Зарегистрироваться"}
            </button>
          </form>

          <div className="auth-footer">
            Уже есть аккаунт?{" "}
            <Link to="/login" className="auth-footer-link">
              Войти
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
