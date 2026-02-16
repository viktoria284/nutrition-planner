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
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
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
      await register({ email, username, password, display_name: displayName ? displayName : null });
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
              <span className="auth-label">Display name (опционально)</span>
              <input
                className="auth-input"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoComplete="nickname"
                placeholder="Как к тебе обращаться"
              />
            </label>

            <label className="auth-field">
              <span className="auth-label">Пароль</span>
              <input
                className="auth-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                placeholder="Минимум 8 символов"
              />
            </label>

            <label className="auth-field">
              <span className="auth-label">Повтори пароль</span>
              <input
                className="auth-input"
                type="password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••"
              />
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
