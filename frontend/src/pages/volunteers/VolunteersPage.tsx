import { memo, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate, formatTime } from '@/lib/format';
import { useAuthStore } from '@/store/authStore';
import { useVolunteers } from '@/api/hooks/volunteers';
import {
  useDeleteVolunteer,
  useResetVolunteerPassword,
  useSetVolunteerActive,
} from '@/api/mutations/volunteers';
import type { Volunteer, VolunteerAdminResetResult } from '@/api/aliases';
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

/** «ДД.ММ.ГГГГ ЧЧ:ММ» или «—» — момент последней авторизации волонтёра (как в других таблицах). */
function fmtDateTime(iso: string | null | undefined): string {
  const d = formatDate(iso);
  return d ? `${d} ${formatTime(iso)}` : '—';
}

/* ---------- Строка таблицы ---------- */
type RowProps = {
  v: Volunteer;
  isAdmin: boolean;
  busy: boolean;
  onOpen: (id: string) => void;
  onToggleActive: (v: Volunteer) => void;
  onDelete: (v: Volunteer) => void;
  onResetPassword: (v: Volunteer) => void;
};
const VolunteerRow = memo(function VolunteerRow({
  v,
  isAdmin,
  busy,
  onOpen,
  onToggleActive,
  onDelete,
  onResetPassword,
}: RowProps) {
  return (
    <div className="de-vol-row de-vol-row-clickable" onClick={() => onOpen(v.id)}>
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
      <div className="de-vol-cell de-vol-c-seen">{fmtDateTime(v.last_seen_at)}</div>
      <div className="de-vol-cell de-vol-c-date">{formatDate(v.created_at) || '—'}</div>
      {isAdmin && (
        <div className="de-vol-cell de-vol-c-actions" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="de-vol-row-btn"
            disabled={busy}
            onClick={() => onResetPassword(v)}
          >
            <Icon name="key" size={13} />
            Сбросить пароль
          </button>
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
  const navigate = useNavigate();
  // ЧПУ-карточка волонтёра: id в пути (/volunteers/<id>) — открывается по клику на строку
  // и по диплинку из карточки инцидента (поле «Волонтёр»). Splat-параметр (*) = id.
  const routeParams = useParams();
  const openId = routeParams['*'] || null;

  const listQuery = useVolunteers();
  const setActive = useSetVolunteerActive();
  const deleteVolunteer = useDeleteVolunteer();
  const resetPassword = useResetVolunteerPassword();

  const volunteers = useMemo(() => listQuery.data ?? [], [listQuery.data]);
  // Открытый в карточке волонтёр (по id из URL) — берём из уже загруженного списка.
  const openVolunteer = useMemo(
    () => (openId ? volunteers.find((v) => v.id === openId) ?? null : null),
    [openId, volunteers]
  );

  // Подтверждение удаления — целевой волонтёр или null.
  const [toDelete, setToDelete] = useState<Volunteer | null>(null);

  // Сброс пароля: целевой волонтёр (модалка открыта) или null.
  const [toReset, setToReset] = useState<Volunteer | null>(null);
  // Результат сброса, когда SMTP не настроен (email_sent=false) — модалка переходит в
  // режим «передайте ссылку вручную». null — фаза подтверждения / письмо ушло.
  const [resetResult, setResetResult] = useState<VolunteerAdminResetResult | null>(null);

  const rowBusy = setActive.isPending || deleteVolunteer.isPending || resetPassword.isPending;

  const handleToggleActive = (v: Volunteer) => {
    const next = !v.is_active;
    setActive.mutate(
      { id: v.id, is_active: next },
      {
        onSuccess: () =>
          showToast(
            next ? `Волонтёр «${v.email}» разблокирован.` : `Волонтёр «${v.email}» заблокирован.`
          ),
        onError: () => showToast('Не удалось изменить статус волонтёра.'),
      }
    );
  };

  const handleDelete = () => {
    if (!toDelete) return;
    const email = toDelete.email;
    deleteVolunteer.mutate(toDelete.id, {
      onSuccess: () => {
        setToDelete(null);
        showToast(`Волонтёр «${email}» удалён из справочника.`);
      },
      onError: () => showToast('Не удалось удалить волонтёра.'),
    });
  };

  const handleResetPassword = () => {
    if (!toReset) return;
    const email = toReset.email;
    resetPassword.mutate(toReset.id, {
      onSuccess: (data) => {
        if (data.email_sent) {
          // Письмо ушло — закрываем модалку и подтверждаем тостом.
          closeReset();
          showToast(`Ссылка сброса отправлена на ${email}`);
        } else {
          // SMTP не настроен — письмо НЕ отправлено. Показываем ссылку/токен для
          // ручной передачи (без фейка «письмо отправлено»).
          setResetResult(data);
        }
      },
      onError: () => showToast('Не удалось отправить ссылку для сброса пароля.'),
    });
  };

  const closeReset = () => {
    setToReset(null);
    setResetResult(null);
  };

  // Копирование ссылки/токена в буфер обмена с честной обратной связью в тосте.
  const handleCopy = (text: string) => {
    if (!navigator.clipboard) {
      showToast('Копирование недоступно — выделите ссылку вручную.');
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => showToast('Скопировано в буфер обмена.'),
      () => showToast('Не удалось скопировать — выделите ссылку вручную.')
    );
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
              <div className="de-vol-th de-vol-c-email">Email</div>
              <div className="de-vol-th de-vol-c-phone">Телефон</div>
              <div className="de-vol-th de-vol-c-verified">Почта подтв.</div>
              <div className="de-vol-th de-vol-c-status">Статус</div>
              <div className="de-vol-th de-vol-c-seen">Посл. авторизация</div>
              <div className="de-vol-th de-vol-c-date">Дата регистрации</div>
              {isAdmin && <div className="de-vol-th de-vol-c-actions">Действия</div>}
            </div>
            {volunteers.map((v) => (
              <VolunteerRow
                key={v.id}
                v={v}
                isAdmin={isAdmin}
                busy={rowBusy}
                onOpen={(id) => navigate(`/volunteers/${id}`)}
                onToggleActive={handleToggleActive}
                onDelete={setToDelete}
                onResetPassword={setToReset}
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

      {toReset && (
        <ResetPasswordModal
          volunteer={toReset}
          result={resetResult}
          pending={resetPassword.isPending}
          onClose={closeReset}
          onConfirm={handleResetPassword}
          onCopy={handleCopy}
        />
      )}

      {openVolunteer && (
        <VolunteerCard
          v={openVolunteer}
          onClose={() => navigate('/volunteers')}
          onIncidents={() => navigate(`/incidents?volunteer_id=${openVolunteer.id}`)}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Карточка волонтёра (все данные + обращения) ---------- */
type VolunteerCardProps = {
  v: Volunteer;
  onClose: () => void;
  /** Переход к списку обращений этого волонтёра (/incidents?volunteer_id=<id>). */
  onIncidents: () => void;
};
function VolunteerCard({ v, onClose, onIncidents }: VolunteerCardProps) {
  const fields: Array<[string, React.ReactNode]> = [
    ['Email', v.email],
    ['Телефон', v.phone || '—'],
    ['Почта подтверждена', v.email_verified ? 'Да' : 'Нет'],
    ['Статус', v.is_active ? 'Активен' : 'Заблокирован'],
    ['Последняя авторизация', fmtDateTime(v.last_seen_at)],
    ['Дата регистрации', formatDate(v.created_at) || '—'],
    ['Обращений создано', String(v.incidents_count)],
  ];
  return (
    <div className="de-vol-modal-overlay" onClick={onClose}>
      <div className="de-vol-modal de-vol-card" onClick={(e) => e.stopPropagation()}>
        <div className="de-vol-modal-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="de-vol-card-title" title={v.email}>
              {v.email}
            </h2>
            <div className="de-vol-modal-head-sub">Карточка волонтёра</div>
          </div>
          <button type="button" className="de-vol-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-vol-modal-body">
          <div className="de-vol-card-fields">
            {fields.map(([k, val]) => (
              <div key={k} className="de-vol-card-field">
                <div className="de-vol-card-field-key">{k}</div>
                <div className="de-vol-card-field-val">{val}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="de-vol-modal-foot">
          <button type="button" className="de-vol-modal-cancel" onClick={onClose}>
            Закрыть
          </button>
          <button
            type="button"
            className="de-vol-modal-submit"
            disabled={v.incidents_count === 0}
            onClick={onIncidents}
            title={v.incidents_count === 0 ? 'У волонтёра нет обращений' : 'Открыть обращения волонтёра'}
          >
            <Icon name="incidents" size={15} />
            Обращения волонтёра ({v.incidents_count})
          </button>
        </div>
      </div>
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
            Волонтёр <b>«{volunteer.email}»</b> будет удалён из справочника. Учётная запись в
            мобильном приложении перестанет действовать. Если нужно временно ограничить доступ —
            используйте блокировку.
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

/* ---------- Модалка сброса пароля волонтёра ----------
   Две фазы в одной модалке:
   1) подтверждение (result == null) — «Отправить волонтёру ссылку для сброса?»;
   2) ручная передача (result?.email_sent === false) — SMTP не настроен, письмо НЕ
      ушло: показываем копируемую ссылку/токен с честной подписью.
   При email_sent === true модалка вообще не входит во 2-ю фазу — родитель её закрывает
   и показывает тост. */
type ResetProps = {
  volunteer: Volunteer;
  result: VolunteerAdminResetResult | null;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
  onCopy: (text: string) => void;
};
function ResetPasswordModal({
  volunteer,
  result,
  pending,
  onClose,
  onConfirm,
  onCopy,
}: ResetProps) {
  // Фаза ручной передачи: письмо не ушло (SMTP не настроен).
  const manual = result != null && !result.email_sent;

  return (
    <div className="de-vol-modal-overlay" onClick={onClose}>
      <div className="de-vol-modal" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <div className="de-vol-modal-head">
          <div style={{ flex: 1 }}>
            <h2>{manual ? 'Письмо не отправлено' : 'Сбросить пароль волонтёра?'}</h2>
            <div className="de-vol-modal-head-sub">
              {manual
                ? 'SMTP не настроен — передайте ссылку вручную'
                : 'Ссылка для сброса уйдёт на почту волонтёру'}
            </div>
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
          {manual ? (
            <>
              <div className="de-vol-confirm-text">
                Ссылка для сброса пароля создана, но <b>письмо НЕ отправлено</b> (SMTP не настроен).
                Передайте её волонтёру <b>«{volunteer.email}»</b> вручную — по ссылке он сам задаст
                новый пароль.
              </div>
              {result?.reset_url && (
                <ResetLinkField label="Ссылка для сброса" value={result.reset_url} onCopy={onCopy} />
              )}
              {result?.reset_token && (
                <ResetLinkField label="Токен" value={result.reset_token} onCopy={onCopy} />
              )}
            </>
          ) : (
            <div className="de-vol-confirm-text">
              Отправить волонтёру <b>«{volunteer.email}»</b> ссылку для сброса пароля? Прямую смену
              пароля мы не делаем — по ссылке волонтёр сам задаст новый пароль.
            </div>
          )}
        </div>

        <div className="de-vol-modal-foot">
          {manual ? (
            <button type="button" className="de-vol-modal-submit" onClick={onClose}>
              Готово
            </button>
          ) : (
            <>
              <button type="button" className="de-vol-modal-cancel" onClick={onClose}>
                Отмена
              </button>
              <button
                type="button"
                className="de-vol-modal-submit"
                disabled={pending}
                onClick={onConfirm}
              >
                {pending ? 'Отправка…' : 'Отправить ссылку'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Копируемое поле (ссылка/токен) для ручной передачи волонтёру ---------- */
type ResetLinkFieldProps = {
  label: string;
  value: string;
  onCopy: (text: string) => void;
};
function ResetLinkField({ label, value, onCopy }: ResetLinkFieldProps) {
  return (
    <div className="de-vol-reset-field">
      <div className="de-vol-reset-label">{label}</div>
      <div className="de-vol-reset-copyrow">
        <code className="de-vol-reset-code" title={value}>
          {value}
        </code>
        <button type="button" className="de-vol-reset-copy" onClick={() => onCopy(value)}>
          <Icon name="copy" size={13} />
          Копировать
        </button>
      </div>
    </div>
  );
}
