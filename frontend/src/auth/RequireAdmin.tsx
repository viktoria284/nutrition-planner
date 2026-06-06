import { useAuth } from "./useAuth";

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="center-note">Загрузка...</div>;
  }

  if (!user || (user.role !== "admin" && user.role !== "superadmin")) {
    return (
      <section className="admin-access-denied">
        <h1 className="admin-access-denied-title">Недостаточно прав для доступа к админ-панели.</h1>
        <p className="admin-access-denied-subtitle">Требуются права администратора.</p>
      </section>
    );
  }

  return <>{children}</>;
}
