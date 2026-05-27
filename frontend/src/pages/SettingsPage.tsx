import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { changePassword, updateMe } from "../api/auth";
import { searchFoods, type FoodItem } from "../api/foods";
import { ApiError } from "../api/http";
import { addPantryItem, deletePantryItem, listPantryItems, type PantryItem } from "../api/pantry";
import { getLatestProfileTargetCalculation } from "../api/profileTargetCalculations";
import {
  createProfile,
  getProfiles,
  type Profile,
  type ProfileCreatePayload,
} from "../api/profiles";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { FoodSearchSelect, type FoodSearchOption } from "../components/FoodSearchSelect";
import { InfoPopover } from "../components/InfoPopover";
import { LogoutConfirmModal } from "../components/LogoutConfirmModal";
import { ProfileTargetsCard } from "../components/ProfileTargetsCard";
import { ProfileTargetCalculatorPage } from "./ProfileTargetCalculatorPage";
import { PANTRY_PRESET_CATEGORIES, type PantryPresetItem } from "../config/pantryPresets";
import { FOOD_CATEGORY_LABELS } from "../types/foodCategory";
import "./SettingsPage.css";

type SettingsTab = "account" | "profiles" | "kbju_calculator" | "pantry";

type CreateProfileForm = {
  name: string;
  target_kcal: string;
  target_protein: string;
  target_fat: string;
  target_carbs: string;
  target_fiber: string;
};

const EMPTY_CREATE_FORM: CreateProfileForm = {
  name: "",
  target_kcal: "",
  target_protein: "",
  target_fat: "",
  target_carbs: "",
  target_fiber: "",
};

function sortProfilesWithDefaultFirst(items: Profile[]): Profile[] {
  if (!items.length) return [];
  const defaultProfile = items.find((item) => item.name === "Мой профиль") ?? items[0];
  return [defaultProfile, ...items.filter((item) => item.id !== defaultProfile.id)];
}

function parseNullableNonNegativeInt(value: string, label: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    throw new Error(`Поле "${label}" должно быть целым числом.`);
  }
  if (parsed < 0) {
    throw new Error(`Поле "${label}" не может быть отрицательным.`);
  }
  return parsed;
}

function parseNullableFiberInt(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    throw new Error("Поле \"Клетчатка\" должно быть целым числом.");
  }
  if (parsed < 0 || parsed > 100) {
    throw new Error("Поле \"Клетчатка\" должно быть в диапазоне от 0 до 100.");
  }
  return parsed;
}

function sortPantryItems(items: PantryItem[]): PantryItem[] {
  return [...items].sort((a, b) => a.food.name.localeCompare(b.food.name, "ru"));
}

function normalizeText(value: string): string {
  return value.trim().toLocaleLowerCase("ru");
}

function scorePresetMatch(food: FoodItem, alias: string): number {
  const normalizedAlias = normalizeText(alias);
  const normalizedName = normalizeText(food.name);
  if (normalizedName === normalizedAlias) return 120;
  if (normalizedName.startsWith(`${normalizedAlias} `)) return 100;
  if (normalizedName.startsWith(normalizedAlias)) return 90;
  if (normalizedName.includes(normalizedAlias)) return 70;
  return 0;
}

async function resolvePresetFood(item: PantryPresetItem): Promise<FoodItem | null> {
  let bestMatch: { food: FoodItem; score: number } | null = null;

  for (const alias of item.aliases) {
    const results = await searchFoods({ q: alias, limit: 25 });
    const verified = results.filter((food) => food.source === "verified");
    for (const food of verified) {
      const score = scorePresetMatch(food, alias);
      if (score <= 0) continue;
      if (!bestMatch || score > bestMatch.score) {
        bestMatch = { food, score };
      }
    }
    if (bestMatch && bestMatch.score >= 120) break;
  }

  return bestMatch?.food ?? null;
}

export function SettingsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, refreshMe } = useAuth();

  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [profilesError, setProfilesError] = useState<string | null>(null);
  const [profileMissing, setProfileMissing] = useState(false);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateProfileForm>(EMPTY_CREATE_FORM);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createInfo, setCreateInfo] = useState<string | null>(null);
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [applyingLatestToCreate, setApplyingLatestToCreate] = useState(false);

  const [highlightedProfileId, setHighlightedProfileId] = useState<number | null>(null);
  const [accountUsername, setAccountUsername] = useState("");
  const [accountEmail, setAccountEmail] = useState("");
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountSuccess, setAccountSuccess] = useState<string | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [passwordCurrent, setPasswordCurrent] = useState("");
  const [passwordNext, setPasswordNext] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const [pantryItems, setPantryItems] = useState<PantryItem[]>([]);
  const [loadingPantry, setLoadingPantry] = useState(false);
  const [pantryError, setPantryError] = useState<string | null>(null);
  const [pantrySaving, setPantrySaving] = useState(false);
  const [pantryInputKey, setPantryInputKey] = useState(0);
  const [manualPantrySelection, setManualPantrySelection] = useState<FoodSearchOption | null>(null);
  const [loadingPantryPresets, setLoadingPantryPresets] = useState(false);
  const [pantryPresetsError, setPantryPresetsError] = useState<string | null>(null);
  const [resolvedPantryPresets, setResolvedPantryPresets] = useState<Record<string, FoodItem>>({});
  const [pendingPresetFoodIds, setPendingPresetFoodIds] = useState<Set<number>>(new Set());

  const defaultProfileId = useMemo(() => (profiles.length ? profiles[0].id : null), [profiles]);
  const currentTab = useMemo<SettingsTab>(() => {
    if (location.pathname === "/settings/account") return "account";
    if (location.pathname === "/settings/pantry") return "pantry";
    if (location.pathname === "/settings/kbju-calculator") return "kbju_calculator";
    return "profiles";
  }, [location.pathname]);

  const forceLogin = useCallback(() => {
    logout();
    navigate("/login", { replace: true, state: { from: location.pathname } });
  }, [location.pathname, logout, navigate]);

  const handleUnauthorized = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) {
      forceLogin();
      return true;
    }
    return false;
  }, [forceLogin]);

  const loadProfiles = useCallback(async () => {
    setLoadingProfiles(true);
    setProfilesError(null);
    setProfileMissing(false);

    try {
      const items = await getProfiles();
      const ordered = sortProfilesWithDefaultFirst(items);
      setProfiles(ordered);

      if (!ordered.length) {
        setProfileMissing(true);
        setProfilesError("Профиль не найден");
      }
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setProfiles([]);
      setProfileMissing(false);
      setProfilesError(err instanceof Error ? err.message : "Не удалось загрузить профили.");
    } finally {
      setLoadingProfiles(false);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  useEffect(() => {
    if (!highlightedProfileId) return;

    const el = document.getElementById(`profile-card-${highlightedProfileId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });

    const timer = window.setTimeout(() => setHighlightedProfileId(null), 2200);
    return () => window.clearTimeout(timer);
  }, [highlightedProfileId, profiles.length]);

  useEffect(() => {
    setAccountUsername(user?.username ?? "");
    setAccountEmail(user?.email ?? "");
  }, [user?.username, user?.email]);

  useEffect(() => {
    if (!accountSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setAccountSuccess(null), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [accountSuccess]);

  useEffect(() => {
    if (!passwordSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setPasswordSuccess(null), 2600);
    return () => window.clearTimeout(timeoutId);
  }, [passwordSuccess]);

  const loadPantry = useCallback(async () => {
    setLoadingPantry(true);
    setPantryError(null);
    try {
      const items = await listPantryItems();
      setPantryItems(sortPantryItems(items));
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setPantryItems([]);
      setPantryError(err instanceof Error ? err.message : "Не удалось загрузить список «Есть дома».");
    } finally {
      setLoadingPantry(false);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    void loadPantry();
  }, [loadPantry]);

  useEffect(() => {
    let cancelled = false;
    setLoadingPantryPresets(true);
    setPantryPresetsError(null);

    const resolveAll = async () => {
      const entries = PANTRY_PRESET_CATEGORIES.flatMap((category) =>
        category.items.map(async (item) => {
          const food = await resolvePresetFood(item).catch(() => null);
          return { key: item.key, food };
        }),
      );

      const resolved = await Promise.all(entries);
      if (cancelled) return;

      const next: Record<string, FoodItem> = {};
      for (const entry of resolved) {
        if (entry.food) {
          next[entry.key] = entry.food;
        }
      }
      setResolvedPantryPresets(next);
      if (Object.keys(next).length === 0) {
        setPantryPresetsError("Не удалось загрузить быстрый выбор.");
      }
      setLoadingPantryPresets(false);
    };

    void resolveAll().catch((err) => {
      if (cancelled) return;
      setResolvedPantryPresets({});
      setLoadingPantryPresets(false);
      setPantryPresetsError(err instanceof Error ? err.message : "Не удалось загрузить быстрый выбор.");
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const onProfileSaved = (updatedProfile: Profile) => {
    setProfiles((prev) => sortProfilesWithDefaultFirst(prev.map((p) => (p.id === updatedProfile.id ? updatedProfile : p))));
  };

  const onProfileDeleted = (id: number) => {
    setProfiles((prev) => {
      const next = sortProfilesWithDefaultFirst(prev.filter((p) => p.id !== id));
      if (!next.length) {
        setProfileMissing(true);
        setProfilesError("Профиль не найден");
      }
      return next;
    });
  };

  const onAccountSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;

    const nextUsername = accountUsername.trim().toLowerCase();
    const nextEmail = accountEmail.trim().toLowerCase();
    if (!nextUsername) {
      setAccountError("Username не должен быть пустым.");
      return;
    }
    if (!nextEmail) {
      setAccountError("Email не должен быть пустым.");
      return;
    }

    const payload: { username?: string; email?: string } = {};
    if (nextUsername !== user.username) payload.username = nextUsername;
    if (nextEmail !== user.email) payload.email = nextEmail;

    if (Object.keys(payload).length === 0) {
      setAccountSuccess("Изменений нет.");
      setAccountError(null);
      return;
    }

    setAccountSaving(true);
    setAccountError(null);
    setAccountSuccess(null);
    try {
      await updateMe(payload);
      await refreshMe();
      setAccountSuccess("Данные аккаунта обновлены.");
    } catch (err) {
      if (handleUnauthorized(err)) return;
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setAccountError("Email или username уже заняты.");
        } else if (err.status === 422) {
          setAccountError("Проверьте корректность email и username.");
        } else {
          setAccountError("Не удалось сохранить изменения аккаунта.");
        }
      } else {
        setAccountError(err instanceof Error ? err.message : "Не удалось сохранить изменения аккаунта.");
      }
    } finally {
      setAccountSaving(false);
    }
  };

  const openLogoutConfirm = () => {
    setLogoutConfirmOpen(true);
  };

  const onPasswordSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!passwordCurrent) {
      setPasswordError("Введите текущий пароль.");
      return;
    }
    if (!passwordNext) {
      setPasswordError("Введите новый пароль.");
      return;
    }
    if (passwordNext !== passwordRepeat) {
      setPasswordError("Новый пароль и подтверждение не совпадают.");
      return;
    }

    setPasswordSaving(true);
    setPasswordError(null);
    setPasswordSuccess(null);
    try {
      await changePassword({
        current_password: passwordCurrent,
        new_password: passwordNext,
      });
      setPasswordCurrent("");
      setPasswordNext("");
      setPasswordRepeat("");
      setPasswordSuccess("Пароль обновлён.");
    } catch (err) {
      if (handleUnauthorized(err)) return;
      if (err instanceof ApiError) {
        if (err.status === 400 || err.status === 422) {
          setPasswordError(err.message);
        } else {
          setPasswordError("Не удалось изменить пароль.");
        }
      } else {
        setPasswordError(err instanceof Error ? err.message : "Не удалось изменить пароль.");
      }
    } finally {
      setPasswordSaving(false);
    }
  };

  const closeLogoutConfirm = () => {
    setLogoutConfirmOpen(false);
  };

  const confirmLogout = () => {
    setLogoutConfirmOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const openCreateModal = () => {
    setCreateForm(EMPTY_CREATE_FORM);
    setCreateError(null);
    setCreateInfo(null);
    setCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    if (creatingProfile) return;
    setCreateModalOpen(false);
    setCreateError(null);
    setCreateInfo(null);
  };

  const updateCreateField = (field: keyof CreateProfileForm, value: string) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
    setCreateError(null);
    setCreateInfo(null);
  };

  const applyLatestToCreateForm = async () => {
    if (creatingProfile || applyingLatestToCreate) return;
    setApplyingLatestToCreate(true);
    setCreateError(null);
    setCreateInfo(null);
    try {
      const latest = await getLatestProfileTargetCalculation();
      setCreateForm((prev) => ({
        ...prev,
        target_kcal: String(latest.target_kcal),
        target_protein: String(Math.round(latest.target_protein)),
        target_fat: String(Math.round(latest.target_fat)),
        target_carbs: String(Math.round(latest.target_carbs)),
        target_fiber: String(Math.round(latest.target_fiber)),
      }));
      setCreateInfo("Поля КБЖУ и клетчатки заполнены из последнего расчёта.");
    } catch (err) {
      if (handleUnauthorized(err)) return;
      if (err instanceof ApiError && err.status === 404) {
        setCreateError("Сначала выполните расчёт в калькуляторе КБЖУ.");
      } else {
        setCreateError(err instanceof Error ? err.message : "Не удалось подставить последний расчёт.");
      }
    } finally {
      setApplyingLatestToCreate(false);
    }
  };

  const onCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault();

    const name = createForm.name.trim();
    if (!name) {
      setCreateError("Введите название профиля.");
      return;
    }

    setCreateError(null);
    setCreatingProfile(true);

    try {
      const payload: ProfileCreatePayload = {
        name,
        target_kcal: parseNullableNonNegativeInt(createForm.target_kcal, "Калории"),
        target_protein: parseNullableNonNegativeInt(createForm.target_protein, "Белки"),
        target_fat: parseNullableNonNegativeInt(createForm.target_fat, "Жиры"),
        target_carbs: parseNullableNonNegativeInt(createForm.target_carbs, "Углеводы"),
        target_fiber: parseNullableFiberInt(createForm.target_fiber),
      };

      const created = await createProfile(payload);
      setProfiles((prev) => sortProfilesWithDefaultFirst([...prev, created]));
      setProfileMissing(false);
      setProfilesError(null);
      setCreateModalOpen(false);
      setCreateForm(EMPTY_CREATE_FORM);
      setHighlightedProfileId(created.id);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setCreateError(err instanceof Error ? err.message : "Не удалось создать профиль.");
    } finally {
      setCreatingProfile(false);
    }
  };

  const onAddPantryFood = async (foodId: number) => {
    if (pantrySaving) return;
    setPantrySaving(true);
    setPantryError(null);
    try {
      const created = await addPantryItem({ food_id: foodId });
      setPantryItems((prev) => {
        const existingIndex = prev.findIndex((item) => item.food_id === created.food_id);
        if (existingIndex >= 0) {
          const next = [...prev];
          next[existingIndex] = created;
          return sortPantryItems(next);
        }
        return sortPantryItems([...prev, created]);
      });
      setPantryInputKey((prev) => prev + 1);
      setManualPantrySelection(null);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      if (err instanceof ApiError && err.status === 404) {
        setPantryError("Продукт недоступен для добавления в список «Есть дома».");
      } else {
        setPantryError(err instanceof Error ? err.message : "Не удалось обновить список продуктов дома.");
      }
    } finally {
      setPantrySaving(false);
    }
  };

  const onRemovePantryFood = async (foodId: number) => {
    if (pantrySaving) return;
    setPantrySaving(true);
    setPantryError(null);
    try {
      await deletePantryItem(foodId);
      setPantryItems((prev) => prev.filter((item) => item.food_id !== foodId));
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setPantryError(err instanceof Error ? err.message : "Не удалось обновить список продуктов дома.");
    } finally {
      setPantrySaving(false);
    }
  };

  const togglePresetPantryItem = async (food: FoodItem, nextChecked: boolean) => {
    setPendingPresetFoodIds((prev) => new Set(prev).add(food.id));
    setPantryError(null);
    try {
      if (nextChecked) {
        await onAddPantryFood(food.id);
      } else {
        await onRemovePantryFood(food.id);
      }
    } finally {
      setPendingPresetFoodIds((prev) => {
        const next = new Set(prev);
        next.delete(food.id);
        return next;
      });
    }
  };

  const pantryFoodIds = useMemo(() => new Set(pantryItems.map((item) => item.food_id)), [pantryItems]);

  const resolvedPresetCategories = useMemo(
    () =>
      PANTRY_PRESET_CATEGORIES.map((category) => ({
        ...category,
        resolvedItems: category.items
          .map((item) => ({
            item,
            food: resolvedPantryPresets[item.key] ?? null,
          }))
          .filter((entry): entry is { item: PantryPresetItem; food: FoodItem } => entry.food !== null),
      })).filter((category) => category.resolvedItems.length > 0),
    [resolvedPantryPresets],
  );

  const navigateToSettingsTab = (next: SettingsTab) => {
    const pathByTab: Record<SettingsTab, string> = {
      account: "/settings/account",
      profiles: "/settings/profiles",
      kbju_calculator: "/settings/kbju-calculator",
      pantry: "/settings/pantry",
    };
    navigate(pathByTab[next]);
  };

  return (
    <section className="settings-page">
      <div className="settings-shell">
        <aside className="settings-sidebar">
          <h1 className="settings-title">Настройки</h1>
          <button
            type="button"
            className={`settings-tab-btn ${currentTab === "account" ? "is-active" : ""}`}
            onClick={() => navigateToSettingsTab("account")}
          >
            Аккаунт
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${currentTab === "profiles" ? "is-active" : ""}`}
            onClick={() => navigateToSettingsTab("profiles")}
          >
            Профили
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${currentTab === "kbju_calculator" ? "is-active" : ""}`}
            onClick={() => navigateToSettingsTab("kbju_calculator")}
          >
            Калькулятор КБЖУ
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${currentTab === "pantry" ? "is-active" : ""}`}
            onClick={() => navigateToSettingsTab("pantry")}
          >
            Есть дома
          </button>
        </aside>

        <article className="settings-panel">
          {currentTab === "account" && (
            <>
              <h2 className="settings-panel-title">Аккаунт</h2>
              <form className="settings-account-form" onSubmit={onAccountSave} noValidate>
                <label className="profile-name-field" htmlFor="settings-username">
                  <span className="profile-name-label">Username</span>
                  <input
                    id="settings-username"
                    className="profile-name-input"
                    type="text"
                    autoComplete="username"
                    value={accountUsername}
                    onChange={(event) => {
                      setAccountUsername(event.target.value);
                      setAccountError(null);
                    }}
                    disabled={accountSaving}
                  />
                </label>
                <label className="profile-name-field" htmlFor="settings-email">
                  <span className="profile-name-label">Email</span>
                  <input
                    id="settings-email"
                    className="profile-name-input"
                    type="email"
                    autoComplete="email"
                    value={accountEmail}
                    onChange={(event) => {
                      setAccountEmail(event.target.value);
                      setAccountError(null);
                    }}
                    disabled={accountSaving}
                  />
                </label>
                {accountError && <Alert text={accountError} />}
                {accountSuccess && <p className="settings-success">{accountSuccess}</p>}
                <div className="settings-account-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={openLogoutConfirm}
                    disabled={accountSaving || passwordSaving}
                  >
                    Выйти
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={accountSaving}>
                    {accountSaving ? "Сохраняем..." : "Сохранить изменения"}
                  </button>
                </div>
              </form>

              <form className="settings-account-form" onSubmit={onPasswordSave} noValidate>
                <h3 className="settings-profile-title">Сменить пароль</h3>
                <label className="profile-name-field" htmlFor="settings-current-password">
                  <span className="profile-name-label">Текущий пароль</span>
                  <input
                    id="settings-current-password"
                    className="profile-name-input"
                    type="password"
                    autoComplete="current-password"
                    value={passwordCurrent}
                    onChange={(event) => {
                      setPasswordCurrent(event.target.value);
                      setPasswordError(null);
                    }}
                    disabled={passwordSaving}
                  />
                </label>
                <label className="profile-name-field" htmlFor="settings-new-password">
                  <span className="profile-name-label">Новый пароль</span>
                  <input
                    id="settings-new-password"
                    className="profile-name-input"
                    type="password"
                    autoComplete="new-password"
                    value={passwordNext}
                    onChange={(event) => {
                      setPasswordNext(event.target.value);
                      setPasswordError(null);
                    }}
                    disabled={passwordSaving}
                  />
                </label>
                <label className="profile-name-field" htmlFor="settings-repeat-password">
                  <span className="profile-name-label">Повторите новый пароль</span>
                  <input
                    id="settings-repeat-password"
                    className="profile-name-input"
                    type="password"
                    autoComplete="new-password"
                    value={passwordRepeat}
                    onChange={(event) => {
                      setPasswordRepeat(event.target.value);
                      setPasswordError(null);
                    }}
                    disabled={passwordSaving}
                  />
                </label>
                {passwordError && <Alert text={passwordError} />}
                {passwordSuccess && <p className="settings-success">{passwordSuccess}</p>}
                <div className="settings-account-actions">
                  <button type="submit" className="btn btn-primary" disabled={passwordSaving}>
                    {passwordSaving ? "Сохраняем..." : "Обновить пароль"}
                  </button>
                </div>
              </form>
            </>
          )}

          {currentTab === "profiles" && (
            <>
              <div className="settings-panel-head">
                <div>
                  <h2 className="settings-panel-title">Профили</h2>
                  <p className="settings-subtitle">Настройте цели и ограничения для ваших профилей.</p>
                </div>

                <div className="settings-head-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={openCreateModal}
                    disabled={loadingProfiles || creatingProfile}
                  >
                    Добавить профиль
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void loadProfiles()}
                    disabled={loadingProfiles || creatingProfile}
                  >
                    Обновить
                  </button>
                </div>
              </div>

              {loadingProfiles && <div className="center-note settings-note">Загрузка профилей...</div>}

              {!loadingProfiles && profileMissing && (
                <div className="settings-state">
                  <Alert text="Профиль не найден" />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void loadProfiles()}
                    disabled={creatingProfile}
                  >
                    Обновить
                  </button>
                </div>
              )}

              {!loadingProfiles && !profileMissing && profilesError && (
                <div className="settings-state">
                  <Alert text={profilesError} />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void loadProfiles()}
                    disabled={creatingProfile}
                  >
                    Обновить
                  </button>
                </div>
              )}

              {!loadingProfiles && !profileMissing && !profilesError && (
                <div className="profiles-list">
                  {profiles.map((profile) => (
                    <ProfileTargetsCard
                      key={profile.id}
                      profile={profile}
                      isDefault={defaultProfileId === profile.id}
                      highlighted={highlightedProfileId === profile.id}
                      onSaved={onProfileSaved}
                      onDeleted={onProfileDeleted}
                      onUnauthorized={forceLogin}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {currentTab === "kbju_calculator" && (
            <ProfileTargetCalculatorPage embedded />
          )}

          {currentTab === "pantry" && (
            <>
              <div className="settings-panel-head">
                <div>
                  <h2 className="settings-panel-title">Что уже есть дома</h2>
                  <p className="settings-subtitle">
                    Эти продукты будут попадать в отдельный блок списка покупок «Проверьте дома».
                  </p>
                </div>
              </div>

              <section className="settings-pantry-quick">
                <span className="settings-pantry-title-row">
                  <h3 className="settings-pantry-section-title">Быстрый выбор</h3>
                  <InfoPopover
                    ariaLabel="Пояснение по быстрому выбору"
                    text="Отметьте продукты, которые обычно есть дома. При создании списка покупок они будут попадать в отдельный блок «Проверьте дома», чтобы не перегружать основной список."
                  />
                </span>

                {loadingPantryPresets && <p className="settings-note">Загрузка быстрого выбора...</p>}
                {!loadingPantryPresets && pantryPresetsError && <Alert text={pantryPresetsError} />}

                {!loadingPantryPresets && !pantryPresetsError && (
                  <div className="settings-pantry-categories-grid">
                    {resolvedPresetCategories.map((category) => (
                      <details key={category.key} className="settings-pantry-category" open={category.defaultOpen}>
                        <summary className="settings-pantry-category-summary">{category.title}</summary>
                        <div className="settings-pantry-check-list">
                          {category.resolvedItems.map(({ item, food }) => {
                            const checked = pantryFoodIds.has(food.id);
                            const pending = pendingPresetFoodIds.has(food.id);
                            return (
                              <label key={item.key} className={`settings-pantry-check-item ${checked ? "is-active" : ""}`}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  disabled={pending}
                                  onChange={(event) => {
                                    void togglePresetPantryItem(food, event.target.checked);
                                  }}
                                />
                                <span>{item.label}</span>
                              </label>
                            );
                          })}
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </section>

              <section className="settings-pantry-manual">
                <h3 className="settings-pantry-section-title">Добавить другой продукт</h3>
                <div className="settings-pantry-search">
                  <FoodSearchSelect
                    key={pantryInputKey}
                    value={manualPantrySelection}
                    onChange={(food) => {
                      setManualPantrySelection(food ? { id: food.id, name: food.name, brand: food.brand ?? null } : null);
                    }}
                    placeholder="Найти продукт"
                    disabled={pantrySaving}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={pantrySaving || !manualPantrySelection}
                    onClick={() => {
                      if (!manualPantrySelection) return;
                      void onAddPantryFood(manualPantrySelection.id);
                    }}
                  >
                    Добавить
                  </button>
                </div>
              </section>

              <div className="settings-pantry-selected">
                <p className="settings-pantry-selected-count">Выбрано: {pantryItems.length} продуктов</p>
                {pantryItems.length > 0 && (
                  <ul className="profile-chip-list">
                    {pantryItems.map((item) => (
                      <li key={item.food_id} className="profile-chip">
                        <span className="profile-chip-label">
                          {item.food.name}
                          {item.food.brand ? ` — ${item.food.brand}` : ""}
                          {` · ${FOOD_CATEGORY_LABELS[item.food.category] ?? item.food.category}`}
                        </span>
                        <button
                          type="button"
                          className="profile-chip-remove"
                          onClick={() => {
                            void onRemovePantryFood(item.food_id);
                          }}
                          disabled={pantrySaving}
                          aria-label={`Убрать ${item.food.name} из списка есть дома`}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {pantryError && <Alert text={pantryError} />}
              {loadingPantry && <p className="settings-note">Загрузка списка «Есть дома»...</p>}

              {!loadingPantry && pantryItems.length === 0 && (
                <p className="settings-note">Пока ничего не выбрано. Отметьте продукты в быстром выборе или добавьте через поиск.</p>
              )}
            </>
          )}
        </article>
      </div>

      {createModalOpen && (
        <div className="settings-modal-backdrop" role="presentation" onClick={closeCreateModal}>
          <div
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-profile-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="new-profile-title" className="settings-modal-title">
              Новый профиль
            </h3>
            <p className="settings-subtitle">Название обязательно. Цели можно оставить пустыми.</p>

            {createError && <Alert text={createError} />}
            {createInfo && <p className="settings-success">{createInfo}</p>}

            <form className="create-profile-form" onSubmit={onCreateProfile}>
              <label className="profile-name-field" htmlFor="create_profile_name">
                <span className="profile-name-label">Название профиля</span>
                <input
                  id="create_profile_name"
                  className="profile-name-input"
                  type="text"
                  value={createForm.name}
                  onChange={(e) => updateCreateField("name", e.target.value)}
                  placeholder="Например, День тренировки"
                  autoFocus
                />
              </label>

              <div className="create-goals-grid">
                <label className="profile-name-field" htmlFor="create_target_kcal">
                  <span className="profile-name-label">Калории (ккал)</span>
                  <input
                    id="create_target_kcal"
                    className="profile-name-input"
                    type="number"
                    min={0}
                    value={createForm.target_kcal}
                    onChange={(e) => updateCreateField("target_kcal", e.target.value)}
                    placeholder="Опционально"
                  />
                </label>
                <label className="profile-name-field" htmlFor="create_target_protein">
                  <span className="profile-name-label">Белки (г)</span>
                  <input
                    id="create_target_protein"
                    className="profile-name-input"
                    type="number"
                    min={0}
                    value={createForm.target_protein}
                    onChange={(e) => updateCreateField("target_protein", e.target.value)}
                    placeholder="Опционально"
                  />
                </label>
                <label className="profile-name-field" htmlFor="create_target_fat">
                  <span className="profile-name-label">Жиры (г)</span>
                  <input
                    id="create_target_fat"
                    className="profile-name-input"
                    type="number"
                    min={0}
                    value={createForm.target_fat}
                    onChange={(e) => updateCreateField("target_fat", e.target.value)}
                    placeholder="Опционально"
                  />
                </label>
                <label className="profile-name-field" htmlFor="create_target_carbs">
                  <span className="profile-name-label">Углеводы (г)</span>
                  <input
                    id="create_target_carbs"
                    className="profile-name-input"
                    type="number"
                    min={0}
                    value={createForm.target_carbs}
                    onChange={(e) => updateCreateField("target_carbs", e.target.value)}
                    placeholder="Опционально"
                  />
                </label>
                <label className="profile-name-field" htmlFor="create_target_fiber">
                  <span className="profile-name-label">Клетчатка (г)</span>
                  <input
                    id="create_target_fiber"
                    className="profile-name-input"
                    type="number"
                    min={0}
                    value={createForm.target_fiber}
                    onChange={(e) => updateCreateField("target_fiber", e.target.value)}
                    placeholder="Опционально"
                  />
                </label>
              </div>

              <div className="create-profile-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void applyLatestToCreateForm()}
                  disabled={creatingProfile || applyingLatestToCreate}
                >
                  {applyingLatestToCreate ? "Подставляем..." : "Подставить последний расчёт"}
                </button>
                <button type="button" className="btn btn-secondary" onClick={closeCreateModal} disabled={creatingProfile}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={creatingProfile}>
                  {creatingProfile ? "Создаём..." : "Создать профиль"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <LogoutConfirmModal
        open={logoutConfirmOpen}
        onCancel={closeLogoutConfirm}
        onConfirm={confirmLogout}
      />
    </section>
  );
}
