import { memo, useMemo, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate } from '@/lib/format';
import { useAuthStore } from '@/store/authStore';
import { useVolunteers } from '@/api/hooks/volunteers';
import { useDeleteVolunteer, useSetVolunteerActive } from '@/api/mutations/volunteers';
import type { Volunteer } from '@/api/aliases';
import './Volunteers.css';

/**
 * Справочник «Волонтёры» — просмотр волонтёров МОБИЛЬНОГО приложения (отдельная от
 * пользователей админки сущность: своя таблица volunteers, свой JWT). Волонтёры
 * регистрируются сами в приложении — админ здесь только смотрит и триажит:
 * admin может блокировать/разблокировать (is_active) и удалять; user — только смотрит.
 * Дизайн зеркалит «Типы инцидентов»/«Регионы» (шапка + таблица + модалка удаления).
 */

/** Русская форма слова «волонтёр» по числу (для счётчика в подзаголовке). */
function pluralVol(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'волонтёр';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'волонтёра';
  return 'волонтёров';
}

/* ---------- Строка таблицы ---------- */
type RowProps = {
  v: Volunteer;
  isAdmin: boolean;
  busy: boolean;
  onToggleActive: (v: Volunteer) => void;
  onDelete: (v: Volunteer) => void;
};
const VolunteerRow = memo(function VolunteerRow({
  v,
  isAdmin,
  busy,
  onToggleActive,
  onDelete,
}: RowProps) {
  return (
    <div className="de-vol-row">
      <div className="de-vol-cell de-vol-c-fio">{v.fio}</div>
      <div className="de-vol-cell de-vol-c-email" title={v.email}>
        {v.email}
      </div>
      <div className="de-vol-cell de-vol-c-phone">{v.phone || '—'}</div>
      <div className="de-vol-cell de-vol-c-verified">
        <span className={`de-vol-pill ${v.email_verified ? 'on' : 'off'}`}>
          <span
            className="de-vol-pill-dot"
            style={{
              background: v.email_verified ? 'var(--ark-green-500)' : 'var(--ark-gray-500)',
            }}
          />
          {v.email_verified ? 'Подтверждён' : 'Не подтверждён'}
        </span>
      </div>
      <div className="de-vol-cell de-vol-c-status">
        <span className={`de-vol-pill ${v.is_active ? 'on' : 'block'}`}>
          <span
            className="de-vol-pill-dot"
            style={{ background: v.is_active ? 'var(--ark-green-500)' : 'var(--ark-red-500)' }}
          />
          {v.is_active ? 'Активен' : 'Заблокирован'}
        </span>
      </div>
      <div className="de-vol-cell de-vol-c-date">{formatDate(v.created_at) || '—'}</div>
      {isAdmin && (
        <div className="de-vol-cell de-vol-c-actions">
          <button
            type="button"
            className="de-vol-row-btn"
            disabled={busy}
            onClick={() => onToggleActive(v)}
          >
            <Icon name={v.is_active ? 'lock' : 'check'} size={13} />
            {v.is_active ? 'Заблокировать' : 'Разблокировать'}
          </button>
          <button
            type="button"
            className="de-vol-row-btn danger"
            disabled={busy}
            onClick={() => onDelete(v)}
          >
            <Icon name="trash" size={13} />
            Удалить
          </button>
        </div>
      )}
    </div>
  );
});

/* ============================================================
   Экран «Волонтёры»
   ============================================================ */
export function VolunteersPage() {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === 'admin';

  const { message, showToast } = useToast();

  const listQuery = useVolunteers();
  const setActive = useSetVolunteerActive();
  const deleteVolunteer = useDeleteVolunteer();

  const volunteers = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  // Подтверждение удаления — целевой волонтёр или null.
  const [toDelete, setToDelete] = useState<Volunteer | null>(null);

  const rowBusy = setActive.isPending || deleteVolunteer.isPending;

  const handleToggleActive = (v: Volunteer) => {
    const next = !v.is_active;
    setActive.mutate(
      { id: v.id, is_active: next },
      {
        onSuccess: () =>
          showToast(
            next ? `Волонтёр «${v.fio}» разблокирован.` : `Волонтёр «${v.fio}» заблокирован.`
          ),
        onError: () => showToast('Не удалось изменить статус волонтёра.'),
      }
    );
  };

  const handleDelete = () => {
    if (!toDelete) return;
    const fio = toDelete.fio;
    deleteVolunteer.mutate(toDelete.id, {
      onSuccess: () => {
        setToDelete(null);
        showToast(`Волонтёр «${fio}» удалён из справочника.`);
      },
      onError: () => showToast('Не удалось удалить волонтёра.'),
    });
  };

  return (
    <div className="de-vol-wrap">
      {/* Шапка */}
      <div className="de-vol-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-vol-title">Волонтёры</h1>
          <div className="de-vol-subtitle">
            Справочник мобильного приложения · {volunteers.length} {pluralVol(volunteers.length)}
          </div>
        </div>
        <div className="de-vol-spacer" />
      </div>

      {/* Таблица */}
      <div className="de-vol-content">
        {listQuery.isLoading ? (
          <div className="de-vol-state">Загрузка…</div>
        ) : listQuery.isError ? (
          <div className="de-vol-state error">Не удалось загрузить справочник волонтёров.</div>
        ) : volunteers.length === 0 ? (
          <div className="de-vol-empty">
            <span className="de-vol-empty-mark">💚</span>
            <h3>Волонтёров пока нет</h3>
            <p>Волонтёры появятся в справочнике после регистрации в мобильном приложении.</p>
          </div>
        ) : (
          <div className="de-vol-table">
            <div className="de-vol-thead">
              <div className="de-vol-th de-vol-c-fio">Заявитель</div>
              <div className="de-vol-th de-vol-c-email">Email</div>
              <div className="de-vol-th de-vol-c-phone">Телефон</div>
              <div className="de-vol-th de-vol-c-verified">Почта подтв.</div>
              <div className="de-vol-th de-vol-c-status">Статус</div>
              <div className="de-vol-th de-vol-c-date">Дата</div>
              {isAdmin && <div className="de-vol-th de-vol-c-actions">Действия</div>}
            </div>
            {volunteers.map((v) => (
              <VolunteerRow
                key={v.id}
                v={v}
                isAdmin={isAdmin}
                busy={rowBusy}
                onToggleActive={handleToggleActive}
                onDelete={setToDelete}
              />
            ))}
          </div>
        )}
      </div>

      {toDelete && (
        <ConfirmDeleteModal
          volunteer={toDelete}
          pending={deleteVolunteer.isPending}
          onClose={() => setToDelete(null)}
          onConfirm={handleDelete}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Модалка подтверждения удаления ---------- */
type ConfirmProps = {
  volunteer: Volunteer;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
};
function ConfirmDeleteModal({ volunteer, pending, onClose, onConfirm }: ConfirmProps) {
  return (
    <div className="de-vol-modal-overlay" onClick={onClose}>
      <div className="de-vol-modal" style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <div className="de-vol-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Удалить волонтёра?</h2>
            <div className="de-vol-modal-head-sub">Действие необратимо</div>
          </div>
          <button
            type="button"
            className="de-vol-modal-close"
            aria-label="Закрыть"
            onClick={onClose}
          >
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-vol-modal-body">
          <div className="de-vol-confirm-text">
            Волонтёр <b>«{volunteer.fio}»</b> ({volunteer.email}) будет удалён из справочника.
            Учётная запись в мобильном приложении перестанет действовать. Если нужно временно
            ограничить доступ — используйте блокировку.
          </div>
        </div>
        <div className="de-vol-modal-foot">
          <button type="button" className="de-vol-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="de-vol-modal-submit danger"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? 'Удаление…' : 'Удалить'}
          </button>
        </div>
      </div>
    </div>
  );
}
