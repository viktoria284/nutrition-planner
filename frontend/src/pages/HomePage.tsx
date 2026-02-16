import { useAuth } from "../auth/useAuth";

export function HomePage() {
  const { user, logout, refreshMe } = useAuth();
  const name = user?.display_name || user?.username || "пользователь";

  return (
    <section className="home-page">
      <h1 className="home-title">Личный кабинет</h1>

      <article className="home-card">
        <p className="home-greeting">
          Привет, <b>{name}</b>
        </p>

        <p className="home-meta">
          Email: {user?.email}
          <br />
          Username: {user?.username}
          <br />
          Role: {user?.role}
        </p>

        <div className="home-actions">
          <button onClick={() => void refreshMe()} className="btn btn-secondary">
            Обновить /auth/me
          </button>
          <button onClick={logout} className="btn btn-primary">
            Выйти
          </button>
        </div>
      </article>
    </section>
  );
}
