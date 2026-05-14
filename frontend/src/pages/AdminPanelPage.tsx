import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  type AdminFoodItem,
  type AdminModerationAction,
  type AdminRecipeItem,
  type AdminReportItem,
  type AdminReportResolution,
  type AdminSummary,
  type AdminUserItem,
  getAdminSummary,
  listAdminFoods,
  listAdminRecipes,
  listAdminReports,
  listAdminUsers,
  moderateAdminFood,
  moderateAdminRecipe,
  resolveAdminFoodReport,
  resolveAdminRecipeReport,
} from "../api/admin";
import { ApiError } from "../api/http";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import "./AdminPanelPage.css";

type AdminSection = "dashboard" | "reports" | "recipes" | "foods" | "users";

type ConfirmState = {
  open: boolean;
  title: string;
  message: string;
  confirmText: string;
  loadingText: string;
  action: (() => Promise<void>) | null;
};

function sectionFromPath(pathname: string): AdminSection {
  if (pathname.startsWith("/admin/reports")) return "reports";
  if (pathname.startsWith("/admin/recipes")) return "recipes";
  if (pathname.startsWith("/admin/foods")) return "foods";
  if (pathname.startsWith("/admin/users")) return "users";
  return "dashboard";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function moderationLabel(action: AdminModerationAction): string {
  if (action === "approve") return "Одобрить";
  if (action === "hide") return "Скрыть";
  if (action === "reject") return "Отклонить";
  return "Восстановить";
}

function statusLabel(status: "draft" | "pending" | "approved" | "rejected"): string {
  if (status === "draft") return "черновик";
  if (status === "pending") return "на проверке";
  if (status === "approved") return "одобрено";
  return "отклонено";
}

function resolutionLabel(action: AdminReportResolution): string {
  if (action === "no_action") return "Без действий";
  if (action === "content_hidden") return "Скрыть контент";
  if (action === "content_restored") return "Восстановить контент";
  return "Отклонить контент";
}

function resolutionValueLabel(value: string | null): string {
  if (value === "no_action") return "без действий";
  if (value === "content_hidden") return "контент скрыт";
  if (value === "content_restored") return "контент восстановлен";
  if (value === "content_rejected") return "контент отклонён";
  return "без статуса";
}

export function AdminPanelPage() {
  const location = useLocation();
  const section = useMemo(() => sectionFromPath(location.pathname), [location.pathname]);

  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [foods, setFoods] = useState<AdminFoodItem[]>([]);
  const [foodsLoading, setFoodsLoading] = useState(false);
  const [foodsError, setFoodsError] = useState<string | null>(null);
  const [foodsQuery, setFoodsQuery] = useState("");
  const [foodsReportedOnly, setFoodsReportedOnly] = useState(false);

  const [recipes, setRecipes] = useState<AdminRecipeItem[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [recipesError, setRecipesError] = useState<string | null>(null);
  const [recipesQuery, setRecipesQuery] = useState("");
  const [recipesReportedOnly, setRecipesReportedOnly] = useState(false);

  const [reports, setReports] = useState<AdminReportItem[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [reportsTargetType, setReportsTargetType] = useState<"all" | "food" | "recipe">("all");
  const [reportsOnlyOpen, setReportsOnlyOpen] = useState(true);

  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersQuery, setUsersQuery] = useState("");

  const [confirm, setConfirm] = useState<ConfirmState>({
    open: false,
    title: "",
    message: "",
    confirmText: "",
    loadingText: "Выполняем...",
    action: null,
  });
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await getAdminSummary();
      setSummary(data);
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : "Не удалось загрузить сводку.");
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadFoods = useCallback(async () => {
    setFoodsLoading(true);
    setFoodsError(null);
    try {
      const data = await listAdminFoods({ q: foodsQuery || undefined, reportedOnly: foodsReportedOnly, limit: 200 });
      setFoods(data);
    } catch (error) {
      setFoodsError(error instanceof Error ? error.message : "Не удалось загрузить продукты.");
    } finally {
      setFoodsLoading(false);
    }
  }, [foodsQuery, foodsReportedOnly]);

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true);
    setRecipesError(null);
    try {
      const data = await listAdminRecipes({ q: recipesQuery || undefined, reportedOnly: recipesReportedOnly, limit: 200 });
      setRecipes(data);
    } catch (error) {
      setRecipesError(error instanceof Error ? error.message : "Не удалось загрузить рецепты.");
    } finally {
      setRecipesLoading(false);
    }
  }, [recipesQuery, recipesReportedOnly]);

  const loadReports = useCallback(async () => {
    setReportsLoading(true);
    setReportsError(null);
    try {
      const data = await listAdminReports({ targetType: reportsTargetType, onlyOpen: reportsOnlyOpen, limit: 200 });
      setReports(data);
    } catch (error) {
      setReportsError(error instanceof Error ? error.message : "Не удалось загрузить жалобы.");
    } finally {
      setReportsLoading(false);
    }
  }, [reportsTargetType, reportsOnlyOpen]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const data = await listAdminUsers({ q: usersQuery || undefined, limit: 200 });
      setUsers(data);
    } catch (error) {
      setUsersError(error instanceof Error ? error.message : "Не удалось загрузить пользователей.");
    } finally {
      setUsersLoading(false);
    }
  }, [usersQuery]);

  useEffect(() => {
    if (section === "dashboard") {
      void loadSummary();
      return;
    }
    if (section === "foods") {
      void loadFoods();
      return;
    }
    if (section === "recipes") {
      void loadRecipes();
      return;
    }
    if (section === "reports") {
      void loadReports();
      return;
    }
    void loadUsers();
  }, [section, loadSummary, loadFoods, loadRecipes, loadReports, loadUsers]);

  const openConfirm = (params: Omit<ConfirmState, "open">) => {
    setConfirmError(null);
    setConfirm({ ...params, open: true });
  };

  const closeConfirm = () => {
    if (confirmLoading) return;
    setConfirm((prev) => ({ ...prev, open: false, action: null }));
    setConfirmError(null);
  };

  const runConfirm = async () => {
    if (!confirm.action) return;
    setConfirmLoading(true);
    setConfirmError(null);
    try {
      await confirm.action();
      setConfirm((prev) => ({ ...prev, open: false, action: null }));
    } catch (error) {
      const message = error instanceof ApiError || error instanceof Error ? error.message : "Не удалось выполнить действие.";
      setConfirmError(message);
    } finally {
      setConfirmLoading(false);
    }
  };

  const onFoodsFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    void loadFoods();
  };

  const onRecipesFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    void loadRecipes();
  };

  const onUsersFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    void loadUsers();
  };

  const handleModerateFood = (food: AdminFoodItem, action: AdminModerationAction) => {
    openConfirm({
      title: `${moderationLabel(action)} продукт`,
      message: `Действие будет применено к продукту «${food.name}».`,
      confirmText: moderationLabel(action),
      loadingText: "Сохраняем...",
      action: async () => {
        await moderateAdminFood(food.id, action);
        await loadFoods();
        await loadSummary();
      },
    });
  };

  const handleModerateRecipe = (recipe: AdminRecipeItem, action: AdminModerationAction) => {
    openConfirm({
      title: `${moderationLabel(action)} рецепт`,
      message: `Действие будет применено к рецепту «${recipe.name}».`,
      confirmText: moderationLabel(action),
      loadingText: "Сохраняем...",
      action: async () => {
        await moderateAdminRecipe(recipe.id, action);
        await loadRecipes();
        await loadSummary();
      },
    });
  };

  const handleResolveReport = (report: AdminReportItem, resolution: AdminReportResolution) => {
    openConfirm({
      title: `${resolutionLabel(resolution)}`,
      message: `Жалоба на «${report.target_name}» будет отмечена как обработанная.`,
      confirmText: resolutionLabel(resolution),
      loadingText: "Сохраняем...",
      action: async () => {
        if (report.target_type === "food") {
          await resolveAdminFoodReport(report.id, resolution);
        } else {
          await resolveAdminRecipeReport(report.id, resolution);
        }
        await loadReports();
        await loadFoods();
        await loadRecipes();
        await loadSummary();
      },
    });
  };

  return (
    <section className="admin-page">
      <div className="admin-shell">
        <header className="admin-head">
          <div>
            <h1 className="admin-title">Админ-панель</h1>
            <p className="admin-subtitle">Модерация контента и просмотр системной статистики.</p>
          </div>
        </header>

        <nav className="admin-tabs" aria-label="Разделы админ-панели">
          <NavLink to="/admin" end className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Дашборд
          </NavLink>
          <NavLink to="/admin/reports" className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Жалобы
          </NavLink>
          <NavLink to="/admin/recipes" className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Рецепты
          </NavLink>
          <NavLink to="/admin/foods" className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Продукты
          </NavLink>
          <NavLink to="/admin/users" className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Пользователи
          </NavLink>
        </nav>

        {section === "dashboard" && (
          <div className="admin-grid">
            {summaryLoading && <p className="admin-note">Загрузка сводки...</p>}
            {summaryError && <p className="admin-error">{summaryError}</p>}
            {summary && (
              <>
                <article className="admin-stat-card"><p>Пользователи</p><strong>{summary.total_users}</strong></article>
                <article className="admin-stat-card"><p>Рецепты</p><strong>{summary.total_recipes}</strong></article>
                <article className="admin-stat-card"><p>Продукты</p><strong>{summary.total_foods}</strong></article>
                <article className="admin-stat-card"><p>Публичные рецепты</p><strong>{summary.public_recipes}</strong></article>
                <article className="admin-stat-card"><p>Публичные продукты</p><strong>{summary.public_foods}</strong></article>
                <article className="admin-stat-card"><p>Рецепты на проверке</p><strong>{summary.pending_or_under_review_recipes}</strong></article>
                <article className="admin-stat-card"><p>Продукты на проверке</p><strong>{summary.pending_or_under_review_foods}</strong></article>
                <article className="admin-stat-card"><p>Открытые жалобы</p><strong>{summary.open_food_reports + summary.open_recipe_reports}</strong></article>
              </>
            )}
          </div>
        )}

        {section === "reports" && (
          <>
            <div className="admin-toolbar">
              <label className="admin-field">
                <span>Тип жалоб</span>
                <select value={reportsTargetType} onChange={(e) => setReportsTargetType(e.target.value as "all" | "food" | "recipe")}> 
                  <option value="all">Все</option>
                  <option value="food">Продукты</option>
                  <option value="recipe">Рецепты</option>
                </select>
              </label>
              <label className="admin-checkbox">
                <input type="checkbox" checked={reportsOnlyOpen} onChange={(e) => setReportsOnlyOpen(e.target.checked)} />
                <span>Только открытые</span>
              </label>
              <button type="button" className="btn btn-secondary" onClick={() => void loadReports()} disabled={reportsLoading}>Обновить</button>
            </div>
            {reportsLoading && <p className="admin-note">Загрузка жалоб...</p>}
            {reportsError && <p className="admin-error">{reportsError}</p>}
            {!reportsLoading && reports.length === 0 && <p className="admin-note">Жалобы не найдены.</p>}
            <div className="admin-list">
              {reports.map((report) => (
                <article key={`${report.target_type}-${report.id}`} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{report.target_name}</h3>
                    <p className="admin-meta-line">
                      Тип: {report.target_type === "food" ? "продукт" : "рецепт"} · Репортёр: {report.reporter?.username ?? "—"} · {formatDate(report.created_at)}
                    </p>
                    {report.reason && <p className="admin-text">Причина: {report.reason}</p>}
                    {report.comment && <p className="admin-text">Комментарий: {report.comment}</p>}
                    {report.resolved_at && (
                      <p className="admin-meta-line">
                        Обработано: {formatDate(report.resolved_at)} · {resolutionValueLabel(report.resolution)}
                      </p>
                    )}
                  </div>
                  <div className="admin-actions">
                    <Link to={report.target_type === "food" ? `/foods/${report.target_id}` : `/recipes/${report.target_id}`} className="btn btn-secondary">
                      Открыть объект
                    </Link>
                    <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "content_hidden")}>Скрыть контент</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "content_restored")}>Восстановить</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "content_rejected")}>Отклонить контент</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "no_action")}>Без действий</button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {section === "recipes" && (
          <>
            <form className="admin-toolbar" onSubmit={onRecipesFilterSubmit} noValidate>
              <label className="admin-field admin-field-grow">
                <span>Поиск</span>
                <input value={recipesQuery} onChange={(e) => setRecipesQuery(e.target.value)} placeholder="Название рецепта" />
              </label>
              <label className="admin-checkbox">
                <input type="checkbox" checked={recipesReportedOnly} onChange={(e) => setRecipesReportedOnly(e.target.checked)} />
                <span>Только с жалобами</span>
              </label>
              <button type="submit" className="btn btn-secondary" disabled={recipesLoading}>Найти</button>
            </form>
            {recipesLoading && <p className="admin-note">Загрузка рецептов...</p>}
            {recipesError && <p className="admin-error">{recipesError}</p>}
            <div className="admin-list">
              {recipes.map((recipe) => (
                <article key={recipe.id} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{recipe.name}</h3>
                    <p className="admin-meta-line">
                      Статус: {statusLabel(recipe.status)} · Публикация: {recipe.is_listed ? "в каталоге" : "скрыт"} · Жалоб: {recipe.reports_count}
                    </p>
                    <p className="admin-meta-line">Автор: {recipe.owner?.username ?? "—"} · Обновлён: {formatDate(recipe.updated_at)}</p>
                  </div>
                  <div className="admin-actions">
                    <Link to={`/recipes/${recipe.id}`} className="btn btn-secondary">Открыть рецепт</Link>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "hide")}>Скрыть</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "restore")}>Восстановить</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "reject")}>Отклонить</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "approve")}>Одобрить</button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {section === "foods" && (
          <>
            <form className="admin-toolbar" onSubmit={onFoodsFilterSubmit} noValidate>
              <label className="admin-field admin-field-grow">
                <span>Поиск</span>
                <input value={foodsQuery} onChange={(e) => setFoodsQuery(e.target.value)} placeholder="Название продукта" />
              </label>
              <label className="admin-checkbox">
                <input type="checkbox" checked={foodsReportedOnly} onChange={(e) => setFoodsReportedOnly(e.target.checked)} />
                <span>Только с жалобами</span>
              </label>
              <button type="submit" className="btn btn-secondary" disabled={foodsLoading}>Найти</button>
            </form>
            {foodsLoading && <p className="admin-note">Загрузка продуктов...</p>}
            {foodsError && <p className="admin-error">{foodsError}</p>}
            <div className="admin-list">
              {foods.map((food) => (
                <article key={food.id} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{food.brand ? `${food.name} — ${food.brand}` : food.name}</h3>
                    <p className="admin-meta-line">
                      Статус: {statusLabel(food.status)} · Публикация: {food.is_listed ? "в каталоге" : "скрыт"} · Жалоб: {food.reports_count}
                    </p>
                    <p className="admin-meta-line">Автор: {food.owner?.username ?? "—"} · Обновлён: {formatDate(food.updated_at)}</p>
                  </div>
                  <div className="admin-actions">
                    <Link to={`/foods/${food.id}`} className="btn btn-secondary">Открыть продукт</Link>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "hide")}>Скрыть</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "restore")}>Восстановить</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "reject")}>Отклонить</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "approve")}>Одобрить</button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {section === "users" && (
          <>
            <form className="admin-toolbar" onSubmit={onUsersFilterSubmit} noValidate>
              <label className="admin-field admin-field-grow">
                <span>Поиск</span>
                <input value={usersQuery} onChange={(e) => setUsersQuery(e.target.value)} placeholder="Email, username или имя" />
              </label>
              <button type="submit" className="btn btn-secondary" disabled={usersLoading}>Найти</button>
            </form>
            {usersLoading && <p className="admin-note">Загрузка пользователей...</p>}
            {usersError && <p className="admin-error">{usersError}</p>}
            <div className="admin-list">
              {users.map((user) => (
                <article key={user.id} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>
                      {user.username} {user.role === "admin" ? <span className="admin-badge">админ</span> : null}
                    </h3>
                    <p className="admin-meta-line">{user.email}</p>
                    <p className="admin-meta-line">
                      Профилей: {user.profiles_count} · Рецептов: {user.recipes_count} · Планов: {user.plans_count}
                    </p>
                    <p className="admin-meta-line">Создан: {formatDate(user.created_at)}</p>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </div>

      <PlanConfirmModal
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        confirmText={confirm.confirmText}
        loadingText={confirm.loadingText}
        loading={confirmLoading}
        errorText={confirmError}
        onClose={closeConfirm}
        onConfirm={() => {
          void runConfirm();
        }}
      />
    </section>
  );
}
