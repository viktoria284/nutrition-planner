import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  type AdminContentOrigin,
  type AdminFoodItem,
  type AdminModerationAction,
  type AdminRecipeItem,
  type AdminReportItem,
  type AdminReportResolution,
  type AdminSummary,
  type AdminUserItem,
  createAdminFood,
  deleteAdminFood,
  deleteAdminRecipe,
  getAdminSummary,
  listAdminFoods,
  listAdminRecipes,
  listAdminReports,
  listAdminUsers,
  moderateAdminFood,
  moderateAdminRecipe,
  resolveAdminFoodReport,
  resolveAdminRecipeReport,
  updateAdminFood,
  updateAdminUserRole,
} from "../api/admin";
import type { FoodCreatePayload, FoodItemUpdatePayload } from "../api/foods";
import { ApiError } from "../api/http";
import { CustomSelect } from "../components/CustomSelect";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { useAuth } from "../auth/useAuth";
import { FOOD_CATEGORIES, FOOD_CATEGORY_LABELS, isFoodCategory, type FoodCategory } from "../types/foodCategory";
import "./AdminPanelPage.css";

type AdminSection = "dashboard" | "reports" | "recipes" | "foods" | "users";

type AdminReportQueueItem = {
  id: number;
  targetType: "food" | "recipe";
  targetId: number;
  targetName: string;
};

type ConfirmState = {
  open: boolean;
  title: string;
  message: string;
  confirmText: string;
  loadingText: string;
  action: (() => Promise<void>) | null;
};

type FoodAdminForm = {
  name: string;
  brand: string;
  category: FoodCategory;
  kcal: string;
  protein: string;
  fat: string;
  carbs: string;
  fiber: string;
};

type AdminFormMode = "create" | "edit";

type FoodEditorState = {
  open: boolean;
  mode: AdminFormMode;
  target: AdminFoodItem | null;
  form: FoodAdminForm;
  errors: string[];
  loading: boolean;
};

const REPORT_TARGET_TYPE_OPTIONS = [
  { value: "all", label: "Все" },
  { value: "food", label: "Продукты" },
  { value: "recipe", label: "Рецепты" },
];

const FOOD_CATEGORY_SELECT_OPTIONS = FOOD_CATEGORIES.map((category) => ({
  value: category,
  label: FOOD_CATEGORY_LABELS[category],
}));

const RECIPES_ORIGIN_TABS: Array<{ value: Exclude<AdminContentOrigin, "all">; label: string }> = [
  { value: "system", label: "Рецепты приложения" },
  { value: "user", label: "Рецепты пользователей" },
];

const FOODS_ORIGIN_TABS: Array<{ value: Exclude<AdminContentOrigin, "all">; label: string }> = [
  { value: "system", label: "Продукты приложения" },
  { value: "user", label: "Продукты пользователей" },
];

const EMPTY_FOOD_ADMIN_FORM: FoodAdminForm = {
  name: "",
  brand: "",
  category: "other",
  kcal: "",
  protein: "",
  fat: "",
  carbs: "",
  fiber: "",
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

function sourceLabel(source: "private" | "verified" | "community"): string {
  if (source === "verified") return "проверенный";
  if (source === "community") return "публичный";
  return "личный";
}

function ownerLabel(owner: { username: string } | null): string {
  return owner?.username ?? "Nutrition Planner";
}

function contentOriginLabel(item: { owner: AdminFoodItem["owner"] | AdminRecipeItem["owner"] }, target: "food" | "recipe"): string {
  if (!item.owner) {
    return target === "food" ? "Системный продукт · Добавлено администрацией" : "Системный рецепт · Добавлено администрацией";
  }
  return `Пользовательский контент · Автор: ${ownerLabel(item.owner)}`;
}

function buildFoodFormFromItem(food: AdminFoodItem): FoodAdminForm {
  return {
    name: food.name,
    brand: food.brand ?? "",
    category: food.category,
    kcal: String(food.kcal),
    protein: String(food.protein),
    fat: String(food.fat),
    carbs: String(food.carbs),
    fiber: String(food.fiber),
  };
}

function parseAdminFoodForm(form: FoodAdminForm, mode: AdminFormMode): { payload: FoodCreatePayload | FoodItemUpdatePayload | null; errors: string[] } {
  const errors: string[] = [];
  const name = form.name.trim();
  const brand = form.brand.trim();
  const category = form.category;

  if (!name) errors.push("Введите название продукта.");
  if (!isFoodCategory(category)) errors.push("Выберите корректный раздел магазина.");

  const parseRequired = (raw: string, label: string, max: number): number | null => {
    const value = Number(raw.trim());
    if (!raw.trim() || !Number.isFinite(value) || value < 0 || value > max) {
      errors.push(`${label}: число от 0 до ${max}.`);
      return null;
    }
    return value;
  };

  const parseOptional = (raw: string, label: string, max: number): number | undefined => {
    if (!raw.trim()) return undefined;
    const value = Number(raw.trim());
    if (!Number.isFinite(value) || value < 0 || value > max) {
      errors.push(`${label}: число от 0 до ${max}.`);
      return undefined;
    }
    return value;
  };

  const kcal = mode === "create" ? parseRequired(form.kcal, "Калории", 1000) : parseOptional(form.kcal, "Калории", 1000);
  const protein = mode === "create" ? parseRequired(form.protein, "Белки", 100) : parseOptional(form.protein, "Белки", 100);
  const fat = mode === "create" ? parseRequired(form.fat, "Жиры", 100) : parseOptional(form.fat, "Жиры", 100);
  const carbs = mode === "create" ? parseRequired(form.carbs, "Углеводы", 100) : parseOptional(form.carbs, "Углеводы", 100);
  const fiber = parseOptional(form.fiber, "Клетчатка", 100);

  if (errors.length > 0) return { payload: null, errors };

  return {
    errors: [],
    payload: {
      name,
      brand: brand || null,
      category,
      ...(typeof kcal === "number" ? { kcal } : {}),
      ...(typeof protein === "number" ? { protein } : {}),
      ...(typeof fat === "number" ? { fat } : {}),
      ...(typeof carbs === "number" ? { carbs } : {}),
      ...(typeof fiber === "number" ? { fiber } : {}),
    },
  };
}

function resolutionLabel(action: AdminReportResolution): string {
  if (action === "no_action") return "Оставить объект и закрыть жалобу";
  if (action === "content_hidden") return "Скрыть объект и закрыть жалобу";
  if (action === "content_restored") return "Восстановить объект и закрыть жалобу";
  return "Отклонить объект и закрыть жалобу";
}

function resolutionValueLabel(value: string | null): string {
  if (value === "no_action") return "Объект оставлен";
  if (value === "content_hidden") return "Объект скрыт";
  if (value === "content_restored") return "Объект восстановлен";
  if (value === "content_rejected") return "Объект отклонён";
  return "Нерешённая";
}

function roleLabel(role: AdminUserItem["role"]): string {
  if (role === "superadmin") return "суперадминистратор";
  if (role === "admin") return "администратор";
  return "пользователь";
}

export function AdminPanelPage() {
  const location = useLocation();
  const { user: currentUser } = useAuth();
  const section = useMemo(() => sectionFromPath(location.pathname), [location.pathname]);
  const isSuperadmin = currentUser?.role === "superadmin";

  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [foods, setFoods] = useState<AdminFoodItem[]>([]);
  const [foodsLoading, setFoodsLoading] = useState(false);
  const [foodsError, setFoodsError] = useState<string | null>(null);
  const [foodsQuery, setFoodsQuery] = useState("");
  const [foodsOrigin, setFoodsOrigin] = useState<Exclude<AdminContentOrigin, "all">>("system");

  const [recipes, setRecipes] = useState<AdminRecipeItem[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [recipesError, setRecipesError] = useState<string | null>(null);
  const [recipesQuery, setRecipesQuery] = useState("");
  const [recipesOrigin, setRecipesOrigin] = useState<Exclude<AdminContentOrigin, "all">>("system");

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
  const [foodEditor, setFoodEditor] = useState<FoodEditorState>({
    open: false,
    mode: "create",
    target: null,
    form: EMPTY_FOOD_ADMIN_FORM,
    errors: [],
    loading: false,
  });

  const reportQueue = useMemo<AdminReportQueueItem[]>(
    () =>
      reports.map((report) => ({
        id: report.id,
        targetType: report.target_type,
        targetId: report.target_id,
        targetName: report.target_name,
      })),
    [reports],
  );

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
      const data = await listAdminFoods({ q: foodsQuery || undefined, origin: foodsOrigin, reportedOnly: false, limit: 200 });
      setFoods(data);
    } catch (error) {
      setFoodsError(error instanceof Error ? error.message : "Не удалось загрузить продукты.");
    } finally {
      setFoodsLoading(false);
    }
  }, [foodsOrigin, foodsQuery]);

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true);
    setRecipesError(null);
    try {
      const data = await listAdminRecipes({ q: recipesQuery || undefined, origin: recipesOrigin, reportedOnly: false, limit: 200 });
      setRecipes(data);
    } catch (error) {
      setRecipesError(error instanceof Error ? error.message : "Не удалось загрузить рецепты.");
    } finally {
      setRecipesLoading(false);
    }
  }, [recipesOrigin, recipesQuery]);

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

  const handleUpdateUserRole = (targetUser: AdminUserItem, role: AdminUserItem["role"]) => {
    openConfirm({
      title: "Изменить роль пользователя",
      message: `Пользователь ${targetUser.username} получит роль «${roleLabel(role)}».`,
      confirmText: "Изменить роль",
      loadingText: "Сохраняем роль...",
      action: async () => {
        await updateAdminUserRole(targetUser.id, role);
        await loadUsers();
      },
    });
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

  const openCreateFood = () => {
    setFoodEditor({
      open: true,
      mode: "create",
      target: null,
      form: EMPTY_FOOD_ADMIN_FORM,
      errors: [],
      loading: false,
    });
  };

  const openEditFood = (food: AdminFoodItem) => {
    setFoodEditor({
      open: true,
      mode: "edit",
      target: food,
      form: buildFoodFormFromItem(food),
      errors: [],
      loading: false,
    });
  };

  const updateFoodEditorField = (field: keyof FoodAdminForm, value: string) => {
    setFoodEditor((prev) => {
      if (field === "category") {
        if (!isFoodCategory(value)) return prev;
        return { ...prev, form: { ...prev.form, category: value }, errors: [] };
      }
      return { ...prev, form: { ...prev.form, [field]: value }, errors: [] };
    });
  };

  const submitFoodEditor = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = parseAdminFoodForm(foodEditor.form, foodEditor.mode);
    if (!parsed.payload) {
      setFoodEditor((prev) => ({ ...prev, errors: parsed.errors }));
      return;
    }

    setFoodEditor((prev) => ({ ...prev, loading: true, errors: [] }));
    try {
      if (foodEditor.mode === "edit" && foodEditor.target) {
        await updateAdminFood(foodEditor.target.id, parsed.payload as FoodItemUpdatePayload);
      } else {
        await createAdminFood(parsed.payload as FoodCreatePayload);
      }
      setFoodEditor((prev) => ({ ...prev, open: false, loading: false }));
      await loadFoods();
      await loadSummary();
    } catch (error) {
      setFoodEditor((prev) => ({
        ...prev,
        loading: false,
        errors: [error instanceof Error ? error.message : "Не удалось сохранить продукт."],
      }));
    }
  };

  const handleResolveReport = (report: AdminReportItem, resolution: AdminReportResolution) => {
    openConfirm({
      title: `${resolutionLabel(resolution)}`,
      message: `Жалоба на «${report.target_name}» будет закрыта с выбранным решением.`,
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
            Публичные рецепты
          </NavLink>
          <NavLink to="/admin/foods" className={({ isActive }) => `admin-tab ${isActive ? "is-active" : ""}`}>
            Публичные продукты
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
                <article className="admin-stat-card"><p>Необработанные жалобы</p><strong>{summary.open_food_reports + summary.open_recipe_reports}</strong></article>
              </>
            )}
          </div>
        )}

        {section === "reports" && (
          <>
            <div className="admin-toolbar">
              <label className="admin-field">
                <span>Тип жалоб</span>
                <CustomSelect
                  value={reportsTargetType}
                  options={REPORT_TARGET_TYPE_OPTIONS}
                  onChange={(nextValue) => setReportsTargetType(nextValue as "all" | "food" | "recipe")}
                  ariaLabel="Тип жалоб"
                  triggerClassName="admin-field-select"
                />
              </label>
              <label className="admin-checkbox">
                <input type="checkbox" checked={reportsOnlyOpen} onChange={(e) => setReportsOnlyOpen(e.target.checked)} />
                <span>Показать только необработанные жалобы</span>
              </label>
              <button type="button" className="btn btn-secondary" onClick={() => void loadReports()} disabled={reportsLoading}>Обновить</button>
            </div>
            {reportsLoading && <p className="admin-note">Загрузка жалоб...</p>}
            {reportsError && <p className="admin-error">{reportsError}</p>}
            {!reportsLoading && reports.length === 0 && <p className="admin-note">Жалобы не найдены.</p>}
            <div className="admin-list">
              {reports.map((report, reportIndex) => (
                <article key={`${report.target_type}-${report.id}`} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{report.target_name}</h3>
                    <p className="admin-meta-line">
                      Статус: {report.resolved_at ? "Закрыта" : "Нерешённая"} · Тип: {report.target_type === "food" ? "продукт" : "рецепт"} · Репортёр: {report.reporter?.username ?? "—"} · {formatDate(report.created_at)}
                    </p>
                    {report.reason && <p className="admin-text">Причина: {report.reason}</p>}
                    {report.comment && <p className="admin-text">Комментарий: {report.comment}</p>}
                    {report.resolved_at && (
                      <p className="admin-meta-line">
                        Закрыта: {formatDate(report.resolved_at)} · {resolutionValueLabel(report.resolution)}
                      </p>
                    )}
                  </div>
                  <div className="admin-actions">
                    <Link
                      to={report.target_type === "food" ? `/foods/${report.target_id}` : `/recipes/${report.target_id}`}
                      state={{
                        adminReturnTo: "/admin/reports",
                        adminReportId: report.id,
                        adminReportTargetType: report.target_type,
                        adminReportTargetName: report.target_name,
                        adminReportQueue: reportQueue,
                        adminReportQueueIndex: reportIndex,
                      }}
                      className="btn btn-secondary"
                    >
                      Открыть объект
                    </Link>
                    {!report.resolved_at && (
                      <>
                        <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "content_hidden")}>Скрыть объект и закрыть жалобу</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleResolveReport(report, "no_action")}>Оставить объект и закрыть жалобу</button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {section === "recipes" && (
          <>
            <div className="admin-subtabs" role="tablist" aria-label="Тип публичных рецептов">
              {RECIPES_ORIGIN_TABS.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  className={`admin-subtab ${recipesOrigin === tab.value ? "is-active" : ""}`}
                  onClick={() => setRecipesOrigin(tab.value)}
                  role="tab"
                  aria-selected={recipesOrigin === tab.value}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <form className="admin-toolbar" onSubmit={onRecipesFilterSubmit} noValidate>
              <label className="admin-field admin-field-grow">
                <span>Поиск</span>
                <input value={recipesQuery} onChange={(e) => setRecipesQuery(e.target.value)} placeholder="Название рецепта" />
              </label>
	              <button type="submit" className="btn btn-secondary" disabled={recipesLoading}>Найти</button>
	              {recipesOrigin === "system" && <Link to="/admin/recipes/new" className="btn btn-primary">Добавить публичный рецепт</Link>}
            </form>
            {recipesLoading && <p className="admin-note">Загрузка рецептов...</p>}
            {recipesError && <p className="admin-error">{recipesError}</p>}
            {!recipesLoading && recipes.length === 0 && (
              <p className="admin-note">
                {recipesOrigin === "system" ? "Рецепты приложения не найдены." : "Опубликованные рецепты пользователей не найдены."}
              </p>
            )}
            <div className="admin-list">
              {recipes.map((recipe) => (
                <article key={recipe.id} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{recipe.name}</h3>
                    <p className="admin-meta-line">
                      Статус: {statusLabel(recipe.status)} · Публикация: {recipe.is_listed ? "в каталоге" : "скрыт"} · Жалоб: {recipe.reports_count}
                    </p>
                    <p className="admin-meta-line">
                      Тип: {contentOriginLabel(recipe, "recipe")} · Источник: {sourceLabel(recipe.source)} · Обновлён: {formatDate(recipe.updated_at)}
                    </p>
                  </div>
                  <div className="admin-actions">
	                    <Link to={`/recipes/${recipe.id}`} state={{ adminReturnTo: "/admin/recipes" }} className="btn btn-secondary">Открыть рецепт</Link>
	                    {recipesOrigin === "system" && <Link to={`/admin/recipes/${recipe.id}/edit`} className="btn btn-secondary">Редактировать</Link>}
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "hide")}>Скрыть</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "restore")}>Восстановить</button>
                    {recipesOrigin === "user" && (
                      <>
                        <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "reject")}>Отклонить</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleModerateRecipe(recipe, "approve")}>Одобрить</button>
                      </>
                    )}
                    {recipesOrigin === "system" && (
                      <button
                        type="button"
                        className="btn btn-subtle"
                        onClick={() =>
                          openConfirm({
                            title: "Удалить рецепт",
                            message: `Рецепт «${recipe.name}» будет удалён без восстановления.`,
                            confirmText: "Удалить",
                            loadingText: "Удаляем...",
                            action: async () => {
                              await deleteAdminRecipe(recipe.id);
                              await loadRecipes();
                              await loadSummary();
                            },
                          })
                        }
                      >
                        Удалить
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {section === "foods" && (
          <>
            <div className="admin-subtabs" role="tablist" aria-label="Тип публичных продуктов">
              {FOODS_ORIGIN_TABS.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  className={`admin-subtab ${foodsOrigin === tab.value ? "is-active" : ""}`}
                  onClick={() => setFoodsOrigin(tab.value)}
                  role="tab"
                  aria-selected={foodsOrigin === tab.value}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <form className="admin-toolbar" onSubmit={onFoodsFilterSubmit} noValidate>
              <label className="admin-field admin-field-grow">
                <span>Поиск</span>
                <input value={foodsQuery} onChange={(e) => setFoodsQuery(e.target.value)} placeholder="Название продукта" />
              </label>
              <button type="submit" className="btn btn-secondary" disabled={foodsLoading}>Найти</button>
              {foodsOrigin === "system" && <button type="button" className="btn btn-primary" onClick={openCreateFood}>Создать системный продукт</button>}
            </form>
            {foodsLoading && <p className="admin-note">Загрузка продуктов...</p>}
            {foodsError && <p className="admin-error">{foodsError}</p>}
            {!foodsLoading && foods.length === 0 && (
              <p className="admin-note">
                {foodsOrigin === "system" ? "Продукты приложения не найдены." : "Опубликованные продукты пользователей не найдены."}
              </p>
            )}
            <div className="admin-list">
              {foods.map((food) => (
                <article key={food.id} className="admin-item-card">
                  <div className="admin-item-main">
                    <h3>{food.brand ? `${food.name} — ${food.brand}` : food.name}</h3>
                    <p className="admin-meta-line">
                      Статус: {statusLabel(food.status)} · Публикация: {food.is_listed ? "в каталоге" : "скрыт"} · Жалоб: {food.reports_count}
                    </p>
                    <p className="admin-meta-line">
                      Тип: {contentOriginLabel(food, "food")} · Источник: {sourceLabel(food.source)} · Обновлён: {formatDate(food.updated_at)}
                    </p>
                  </div>
                  <div className="admin-actions">
                    <Link to={`/foods/${food.id}`} state={{ adminReturnTo: "/admin/foods" }} className="btn btn-secondary">Открыть продукт</Link>
                    {foodsOrigin === "system" && <button type="button" className="btn btn-secondary" onClick={() => openEditFood(food)}>Редактировать</button>}
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "hide")}>Скрыть</button>
                    <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "restore")}>Восстановить</button>
                    {foodsOrigin === "user" && (
                      <>
                        <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "reject")}>Отклонить</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleModerateFood(food, "approve")}>Одобрить</button>
                      </>
                    )}
                    {foodsOrigin === "system" && (
                      <button
                        type="button"
                        className="btn btn-subtle"
                        onClick={() =>
                          openConfirm({
                            title: "Удалить продукт",
                            message: `Продукт «${food.name}» будет удалён без восстановления.`,
                            confirmText: "Удалить",
                            loadingText: "Удаляем...",
                            action: async () => {
                              await deleteAdminFood(food.id);
                              await loadFoods();
                              await loadSummary();
                            },
                          })
                        }
                      >
                        Удалить
                      </button>
                    )}
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
                      {user.username} {user.role !== "user" ? <span className="admin-badge">{roleLabel(user.role)}</span> : null}
                    </h3>
                    <p className="admin-meta-line">{user.email}</p>
                    <p className="admin-meta-line">
                      Роль: {roleLabel(user.role)} · Профилей: {user.profiles_count} · Рецептов: {user.recipes_count} · Планов: {user.plans_count}
                    </p>
                    <p className="admin-meta-line">Создан: {formatDate(user.created_at)}</p>
                  </div>
                  {isSuperadmin && (
                    <div className="admin-actions">
                      {user.role !== "admin" && (
                        <button type="button" className="btn btn-secondary" onClick={() => handleUpdateUserRole(user, "admin")}>
                          Назначить администратором
                        </button>
                      )}
                      {user.role !== "superadmin" && (
                        <button type="button" className="btn btn-secondary" onClick={() => handleUpdateUserRole(user, "superadmin")}>
                          Назначить superadmin
                        </button>
                      )}
                      {user.role !== "user" && (
                        <button type="button" className="btn btn-subtle" onClick={() => handleUpdateUserRole(user, "user")}>
                          Снять права администратора
                        </button>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
      </div>

      {foodEditor.open && (
        <div className="admin-modal-backdrop" role="presentation" onClick={() => !foodEditor.loading && setFoodEditor((prev) => ({ ...prev, open: false }))}>
          <div className="admin-modal" role="dialog" aria-modal="true" aria-label="Редактор продукта" onClick={(event) => event.stopPropagation()}>
            <header className="admin-modal-head">
              <h2>{foodEditor.mode === "create" ? "Создать системный продукт" : "Редактировать продукт"}</h2>
              <button type="button" className="btn btn-secondary" onClick={() => setFoodEditor((prev) => ({ ...prev, open: false }))} disabled={foodEditor.loading}>
                Закрыть
              </button>
            </header>
            <form className="admin-modal-form" onSubmit={submitFoodEditor} noValidate>
              {foodEditor.errors.length > 0 && (
                <div className="admin-form-errors" role="alert">
                  {foodEditor.errors.map((message) => <p key={message}>{message}</p>)}
                </div>
              )}
              <label className="admin-field">
                <span>Название</span>
                <input value={foodEditor.form.name} onChange={(event) => updateFoodEditorField("name", event.target.value)} disabled={foodEditor.loading} />
              </label>
              <label className="admin-field">
                <span>Бренд</span>
                <input value={foodEditor.form.brand} onChange={(event) => updateFoodEditorField("brand", event.target.value)} disabled={foodEditor.loading} />
              </label>
              <label className="admin-field">
                <span>Раздел магазина</span>
                <CustomSelect
                  value={foodEditor.form.category}
                  options={FOOD_CATEGORY_SELECT_OPTIONS}
                  onChange={(value) => updateFoodEditorField("category", value)}
                  disabled={foodEditor.loading}
                  ariaLabel="Раздел магазина"
                />
              </label>
              <div className="admin-form-grid">
                {(["kcal", "protein", "fat", "carbs", "fiber"] as const).map((field) => (
                  <label key={field} className="admin-field">
                    <span>{field === "kcal" ? "Ккал" : field === "protein" ? "Белки" : field === "fat" ? "Жиры" : field === "carbs" ? "Углеводы" : "Клетчатка"}</span>
                    <input
                      type="number"
                      min={0}
                      step="any"
                      value={foodEditor.form[field]}
                      onChange={(event) => updateFoodEditorField(field, event.target.value)}
                      disabled={foodEditor.loading}
                    />
                  </label>
                ))}
              </div>
              <div className="admin-modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setFoodEditor((prev) => ({ ...prev, open: false }))} disabled={foodEditor.loading}>Отмена</button>
                <button type="submit" className="btn btn-primary" disabled={foodEditor.loading}>
                  {foodEditor.loading ? "Сохраняем..." : "Сохранить"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
