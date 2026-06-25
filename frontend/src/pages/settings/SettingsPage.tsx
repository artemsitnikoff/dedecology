import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Avatar } from '@/components/ui/Avatar';
import { useAuthStore } from '@/store/authStore';
import { useUsers } from '@/api/hooks/useUsers';
import { useUpdateProfile, useResetPassword } from '@/api/mutations/profile';
import { useCreateUser, useDeleteUser } from '@/api/mutations/users';
import type { Role, UserStatus } from '@/api/aliases';
import './Settings.css';

/** Мета бейджа роли (цвета — токены). */
const ROLE_META: Record<Role, { label: string; bg: string; fg: string }> = {
  admin: { label: 'Администратор', bg: 'var(--ark-violet-100)', fg: 'var(--ark-violet-500)' },
  user: { label: 'Пользователь', bg: 'var(--ark-gray-100)', fg: 'var(--ark-gray-600)' },
};

/** Мета бейджа статуса пользователя. */
const STATUS_META: Record<UserStatus, { label: string; bg: string; fg: string; dot: string }> = {
  active: {
    label: 'Активен',
    bg: 'var(--ark-green-100)',
    fg: 'var(--ark-green-600)',
    dot: 'var(--ark-green-500)',
  },
  invited: {
    label: 'Приглашён',
    bg: 'var(--ark-yellow-100)',
    fg: 'var(--ark-yellow-600)',
    dot: 'var(--ark-yellow-500)',
  },
};

type Banner = { kind: 'success' | 'error'; text: string } | null;

/**
 * Экран «Настройки»: профиль (ФИО + смена пароля) и — только для admin —
 * управление пользователями (список, приглашение с честным temp_password, удаление).
 */
export function SettingsPage() {
  const me = useAuthStore((s) => s.user);
  const isAdmin = me?.role === 'admin';

  const [banner, setBanner] = useState<Banner>(null);

  // ----- Профиль -----
  const [fio, setFio] = useState(me?.fio ?? '');
  const [newPw, setNewPw] = useState('');
  const updateProfile = useUpdateProfile();
  const resetPassword = useResetPassword();

  const saveProfile = () => {
    const value = fio.trim();
    if (!value) {
      setBanner({ kind: 'error', text: 'Введите ФИО.' });
      return;
    }
    updateProfile.mutate(
      { fio: value },
      {
        onSuccess: () => setBanner({ kind: 'success', text: 'Профиль сохранён.' }),
        onError: () => setBanner({ kind: 'error', text: 'Не удалось сохранить профиль.' }),
      }
    );
  };

  const changePassword = () => {
    const value = newPw.trim();
    if (!value) {
      setBanner({ kind: 'error', text: 'Введите новый пароль.' });
      return;
    }
    resetPassword.mutate(
      { new_password: value },
      {
        onSuccess: () => {
          setNewPw('');
          setBanner({ kind: 'success', text: 'Пароль сброшен — установлен новый.' });
        },
        onError: () =>
          setBanner({ kind: 'error', text: 'Не удалось сменить пароль (минимум 6 символов).' }),
      }
    );
  };

  // ----- Пользователи (admin only) -----
  const usersQuery = useUsers();
  const users = usersQuery.data ?? [];
  const createUser = useCreateUser();
  const deleteUser = useDeleteUser();

  const [nuFio, setNuFio] = useState('');
  const [nuEmail, setNuEmail] = useState('');
  const [nuRole, setNuRole] = useState<Role>('user');

  const inviteUser = () => {
    const f = nuFio.trim();
    const e = nuEmail.trim();
    if (!f || !e) {
      setBanner({ kind: 'error', text: 'Заполните ФИО и email.' });
      return;
    }
    createUser.mutate(
      { fio: f, email: e, role: nuRole },
      {
        onSuccess: (res) => {
          setNuFio('');
          setNuEmail('');
          setNuRole('user');
          // Честно показываем временный пароль — письмо не отправляется (фаза позже).
          setBanner({
            kind: 'success',
            text: `Пользователь добавлен. Временный пароль: ${res.temp_password}`,
          });
        },
        onError: () =>
          setBanner({ kind: 'error', text: 'Не удалось создать пользователя (возможно, email занят).' }),
      }
    );
  };

  const removeUser = (id: string) => {
    deleteUser.mutate(id, {
      onSuccess: () => setBanner({ kind: 'success', text: 'Пользователь удалён.' }),
      onError: () => setBanner({ kind: 'error', text: 'Не удалось удалить пользователя.' }),
    });
  };

  return (
    <div className="de-set-wrap">
      <div className="de-set-header">
        <h1 className="de-set-title">Настройки</h1>
        <div className="de-set-subtitle">Профиль и управление пользователями</div>
      </div>

      <div className="de-set-body">
        {banner && (
          <div className={`de-set-banner ${banner.kind}`}>
            <Icon name={banner.kind === 'success' ? 'check' : 'alert-circle'} size={16} />
            <span>{banner.text}</span>
            <button
              type="button"
              className="de-set-banner-close"
              aria-label="Закрыть"
              onClick={() => setBanner(null)}
            >
              <Icon name="x" size={15} />
            </button>
          </div>
        )}

        {/* Профиль */}
        <div className="de-set-card">
          <div className="de-set-card-title">Профиль</div>
          <div className="de-set-card-sub">Ваше имя и доступ к аккаунту</div>
          <div className="de-set-stack">
            <div className="de-set-field">
              <label className="de-set-field-label">ФИО</label>
              <input
                className="de-set-input"
                value={fio}
                onChange={(e) => setFio(e.target.value)}
              />
            </div>
            <div className="de-set-field">
              <label className="de-set-field-label">Email для входа</label>
              <input className="de-set-input" value={me?.email ?? ''} disabled />
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button
              type="button"
              className="de-set-btn de-set-btn-primary"
              onClick={saveProfile}
              disabled={updateProfile.isPending}
            >
              Сохранить
            </button>
          </div>

          <div className="de-set-divider" />

          <div className="de-set-subhead">Смена пароля</div>
          <div className="de-set-card-sub">Введите новый пароль и нажмите «Сбросить».</div>
          <div className="de-set-pw-row">
            <div className="de-set-pw-field">
              <div className="de-set-field">
                <label className="de-set-field-label">Новый пароль</label>
                <input
                  className="de-set-input"
                  type="password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  placeholder="••••••"
                />
              </div>
            </div>
            <button
              type="button"
              className="de-set-btn de-set-btn-outline"
              onClick={changePassword}
              disabled={resetPassword.isPending}
            >
              Сбросить
            </button>
          </div>
        </div>

        {/* Пользователи — только для admin */}
        {isAdmin && (
          <div className="de-set-card">
            <div className="de-set-card-head">
              <div className="de-set-card-title">Пользователи и доступ</div>
              <span className="de-set-count">{users.length}</span>
            </div>
            <div className="de-set-card-sub">
              Добавьте сотрудника — временный пароль покажем здесь (письмо не отправляется).
            </div>

            <div className="de-set-invite">
              <div className="de-set-invite-grow">
                <div className="de-set-field">
                  <label className="de-set-field-label">ФИО сотрудника</label>
                  <input
                    className="de-set-input"
                    value={nuFio}
                    onChange={(e) => setNuFio(e.target.value)}
                    placeholder="Иванов Иван Иванович"
                  />
                </div>
              </div>
              <div className="de-set-invite-grow">
                <div className="de-set-field">
                  <label className="de-set-field-label">Email</label>
                  <input
                    className="de-set-input"
                    value={nuEmail}
                    onChange={(e) => setNuEmail(e.target.value)}
                    placeholder="ivanov@dedekolog.ru"
                  />
                </div>
              </div>
              <div className="de-set-field">
                <label className="de-set-field-label">Доступ</label>
                <div className="de-set-access-chips">
                  {(['user', 'admin'] as Role[]).map((r) => (
                    <button
                      key={r}
                      type="button"
                      className={`de-set-chip ${nuRole === r ? 'active' : ''}`}
                      onClick={() => setNuRole(r)}
                    >
                      {ROLE_META[r].label}
                    </button>
                  ))}
                </div>
              </div>
              <button
                type="button"
                className="de-set-btn de-set-btn-success"
                onClick={inviteUser}
                disabled={createUser.isPending}
              >
                <Icon name="plus" size={15} />
                Отправить приглашение
              </button>
            </div>

            <div className="de-set-table">
              <div className="de-set-thead">
                <div className="de-set-th-user">Пользователь</div>
                <div className="de-set-th-access">Доступ</div>
                <div className="de-set-th-status">Статус</div>
                <div className="de-set-th-action" />
              </div>
              {usersQuery.isLoading ? (
                <div className="de-set-row" style={{ justifyContent: 'center', color: 'var(--fg-2)' }}>
                  Загрузка…
                </div>
              ) : (
                users.map((u) => {
                  const roleMeta = ROLE_META[u.role];
                  const statusMeta = STATUS_META[u.status];
                  return (
                    <div key={u.id} className="de-set-row">
                      <div className="de-set-user-cell">
                        <Avatar name={u.fio} size="md" />
                        <div className="de-set-user-meta">
                          <div className="de-set-user-name">{u.fio}</div>
                          <div className="de-set-user-email">{u.email}</div>
                        </div>
                      </div>
                      <div className="de-set-cell-access">
                        <span
                          className="de-set-badge"
                          style={{ background: roleMeta.bg, color: roleMeta.fg }}
                        >
                          {roleMeta.label}
                        </span>
                      </div>
                      <div className="de-set-cell-status">
                        <span
                          className="de-set-badge"
                          style={{ background: statusMeta.bg, color: statusMeta.fg }}
                        >
                          <span className="de-set-badge-dot" style={{ background: statusMeta.dot }} />
                          {statusMeta.label}
                        </span>
                      </div>
                      <div className="de-set-cell-action">
                        {u.role === 'admin' ? (
                          <span className="de-set-lock" title="Администратора нельзя удалить">
                            <Icon name="lock" size={15} />
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="de-set-trash"
                            aria-label="Удалить пользователя"
                            onClick={() => removeUser(u.id)}
                            disabled={deleteUser.isPending}
                          >
                            <Icon name="trash" size={15} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
