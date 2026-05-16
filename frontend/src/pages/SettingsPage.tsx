import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateMe } from "../api/auth";
import { ApiError } from "../api/http";
import {
  createProfile,
  getProfiles,
  type Profile,
  type ProfileCreatePayload,
} from "../api/profiles";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { LogoutConfirmModal } from "../components/LogoutConfirmModal";
import { ProfileTargetsCard } from "../components/ProfileTargetsCard";
import "./SettingsPage.css";

type SettingsTab = "account" | "goals";

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

export function SettingsPage() {
  const navigate = useNavigate();
  const { user, logout, refreshMe } = useAuth();

  const [tab, setTab] = useState<SettingsTab>("goals");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [profilesError, setProfilesError] = useState<string | null>(null);
  const [profileMissing, setProfileMissing] = useState(false);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateProfileForm>(EMPTY_CREATE_FORM);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creatingProfile, setCreatingProfile] = useState(false);

  const [highlightedProfileId, setHighlightedProfileId] = useState<number | null>(null);
  const [accountUsername, setAccountUsername] = useState("");
  const [accountEmail, setAccountEmail] = useState("");
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountSuccess, setAccountSuccess] = useState<string | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);

  const defaultProfileId = useMemo(() => (profiles.length ? profiles[0].id : null), [profiles]);

  const forceLogin = useCallback(() => {
    logout();
    navigate("/login", { replace: true, state: { from: "/settings" } });
  }, [logout, navigate]);

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
    setCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    if (creatingProfile) return;
    setCreateModalOpen(false);
    setCreateError(null);
  };

  const updateCreateField = (field: keyof CreateProfileForm, value: string) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
    setCreateError(null);
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

  return (
    <section className="settings-page">
      <div className="settings-shell">
        <aside className="settings-sidebar">
          <h1 className="settings-title">Настройки</h1>
          <button
            type="button"
            className={`settings-tab-btn ${tab === "account" ? "is-active" : ""}`}
            onClick={() => setTab("account")}
          >
            Аккаунт
          </button>
          <button
            type="button"
            className={`settings-tab-btn ${tab === "goals" ? "is-active" : ""}`}
            onClick={() => setTab("goals")}
          >
            Цели
          </button>
        </aside>

        <article className="settings-panel">
          {tab === "account" && (
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
                    disabled={accountSaving}
                  >
                    Выйти
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={accountSaving}>
                    {accountSaving ? "Сохраняем..." : "Сохранить изменения"}
                  </button>
                </div>
              </form>
            </>
          )}

          {tab === "goals" && (
            <>
              <div className="settings-panel-head">
                <div>
                  <h2 className="settings-panel-title">Цели</h2>
                  <p className="settings-subtitle">Профили и цели редактируются на одной вкладке.</p>
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
