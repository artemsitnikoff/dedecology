import { memo, useMemo, useState } from 'react';
import type { AxiosError } from 'axios';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { useBlockedDomainsList } from '@/api/hooks/blockedDomains';
import { useCreateBlockedDomain, useDeleteBlockedDomain } from '@/api/mutations/blockedDomains';
import type { BlockedDomainItem } from '@/api/aliases';
// Переиспользуем стили справочника «Типы инцидентов» (.de-it-*): идентичная шапка/таблица/модалка.
import '@/pages/incident-types/IncidentTypes.css';

/**
 * Справочник «Стоп-лист почтовых доменов» — редактируемый список доменов (gmail.com,
 * icloud.com и т.п.), с которых ЗАПРЕЩЕНА регистрация волонтёра (проверка на бэке в
 * volunteer.register). Раздел только для админа (роут и API admin-only). Дизайн зеркалит
 * «Типы инцидентов»: шапка + таблица + модалки добавления/удаления.
 */

/** Текст ошибки из конверта бэка `{error:{message}}` (409 дубль / 400 невалидный домен). */
function errMessage(e: unknown, fallback: string): string {
  const msg = (e as AxiosError<{ error?: { message?: string } }>)?.response?.data?.error?.message;
  return msg || fallback;
}

/* ---------- Строка таблицы ---------- */
type RowProps = {
  d: BlockedDomainItem;
  busy: boolean;
  onDelete: (d: BlockedDomainItem) => void;
};
const DomainRow = memo(function DomainRow({ d, busy, onDelete }: RowProps) {
  return (
    <div className="de-it-row">
      <div className="de-it-cell de-it-c-label">
        <span className="de-it-code-badge" title={d.domain}>
          @{d.domain}
        </span>
      </div>
      <div className="de-it-cell de-it-c-actions">
        <button
          type="button"
          className="de-it-row-btn danger"
          disabled={busy}
          onClick={() => onDelete(d)}
        >
          <Icon name="trash" size={13} />
          Удалить
        </button>
      </div>
    </div>
  );
});

/* ============================================================
   Экран «Стоп-лист почтовых доменов»
   ============================================================ */
export function BlockedDomainsPage() {
  const { message, showToast } = useToast();

  const listQuery = useBlockedDomainsList();
  const createDomain = useCreateBlockedDomain();
  const deleteDomain = useDeleteBlockedDomain();

  const domains = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  const [modalOpen, setModalOpen] = useState(false);
  const [toDelete, setToDelete] = useState<BlockedDomainItem | null>(null);

  const rowBusy = createDomain.isPending || deleteDomain.isPending;

  const handleCreate = (domain: string) => {
    createDomain.mutate(
      { domain },
      {
        onSuccess: (created) => {
          setModalOpen(false);
          showToast(`Домен «@${created.domain}» добавлен в стоп-лист.`);
        },
        onError: (e) => showToast(errMessage(e, 'Не удалось добавить домен.')),
      }
    );
  };

  const handleDelete = () => {
    if (!toDelete) return;
    const domain = toDelete.domain;
    deleteDomain.mutate(toDelete.id, {
      onSuccess: () => {
        setToDelete(null);
        showToast(`Домен «@${domain}» убран из стоп-листа.`);
      },
      onError: (e) => showToast(errMessage(e, 'Не удалось удалить домен.')),
    });
  };

  return (
    <div className="de-it-wrap">
      {/* Шапка */}
      <div className="de-it-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-it-title">Стоп-лист доменов</h1>
          <div className="de-it-subtitle">
            Регистрация с этих доменов запрещена · {domains.length} доменов
          </div>
        </div>
        <div className="de-it-spacer" />
        <button type="button" className="de-it-btn de-it-btn-primary" onClick={() => setModalOpen(true)}>
          <Icon name="plus" size={15} />
          Добавить домен
        </button>
      </div>

      {/* Таблица */}
      <div className="de-it-content">
        {listQuery.isLoading ? (
          <div className="de-it-state">Загрузка…</div>
        ) : listQuery.isError ? (
          <div className="de-it-state error">Не удалось загрузить стоп-лист доменов.</div>
        ) : domains.length === 0 ? (
          <div className="de-it-empty">
            <span className="de-it-empty-mark">💚</span>
            <h3>Стоп-лист пуст</h3>
            <p>Добавьте домен (например, gmail.com) — регистрация волонтёров с него будет запрещена.</p>
          </div>
        ) : (
          <div className="de-it-table">
            <div className="de-it-thead">
              <div className="de-it-th de-it-c-label">Домен</div>
              <div className="de-it-th de-it-c-actions">Действия</div>
            </div>
            {domains.map((d) => (
              <DomainRow key={d.id} d={d} busy={rowBusy} onDelete={setToDelete} />
            ))}
          </div>
        )}
      </div>

      {modalOpen && (
        <DomainModal
          pending={createDomain.isPending}
          onClose={() => setModalOpen(false)}
          onCreate={handleCreate}
          notify={showToast}
        />
      )}

      {toDelete && (
        <ConfirmDeleteModal
          domain={toDelete}
          pending={deleteDomain.isPending}
          onClose={() => setToDelete(null)}
          onConfirm={handleDelete}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Модалка добавления ---------- */
type DomainModalProps = {
  pending: boolean;
  onClose: () => void;
  onCreate: (domain: string) => void;
  notify: (msg: string) => void;
};
function DomainModal({ pending, onClose, onCreate, notify }: DomainModalProps) {
  const [domain, setDomain] = useState('');

  const submit = () => {
    // Нормализуем на клиенте так же, как бэк: срезаем «@» и регистр (бэк — источник правды).
    const d = domain.trim().toLowerCase().replace(/^@+/, '');
    if (!d || !d.includes('.')) {
      notify('Укажите корректный домен, например gmail.com');
      return;
    }
    onCreate(d);
  };

  return (
    <div className="de-it-modal-overlay" onClick={onClose}>
      <div className="de-it-modal" style={{ width: 440 }} onClick={(e) => e.stopPropagation()}>
        <div className="de-it-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Добавить домен в стоп-лист</h2>
            <div className="de-it-modal-head-sub">
              Регистрация волонтёров с этого домена будет запрещена
            </div>
          </div>
          <button type="button" className="de-it-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-it-modal-body">
          <div className="de-it-field-group">
            <label>Домен</label>
            <input
              className="de-it-input mono"
              value={domain}
              autoFocus
              onChange={(e) => setDomain(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submit();
              }}
              placeholder="gmail.com"
            />
            <span className="de-it-field-hint">
              Без «@» — только домен. Российские почты (mail.ru, yandex.ru) блокировать не нужно.
            </span>
          </div>
        </div>
        <div className="de-it-modal-foot">
          <button type="button" className="de-it-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="de-it-modal-submit" disabled={pending} onClick={submit}>
            {pending ? 'Сохранение…' : 'Добавить'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Модалка подтверждения удаления ---------- */
type ConfirmProps = {
  domain: BlockedDomainItem;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
};
function ConfirmDeleteModal({ domain, pending, onClose, onConfirm }: ConfirmProps) {
  return (
    <div className="de-it-modal-overlay" onClick={onClose}>
      <div className="de-it-modal" style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <div className="de-it-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Убрать домен из стоп-листа?</h2>
            <div className="de-it-modal-head-sub">Регистрация с этого домена снова станет возможной</div>
          </div>
          <button type="button" className="de-it-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-it-modal-body">
          <div className="de-it-confirm-text">
            Домен <b>«@{domain.domain}»</b> будет удалён из стоп-листа — волонтёры снова смогут
            регистрироваться с адресов на этом домене.
          </div>
        </div>
        <div className="de-it-modal-foot">
          <button type="button" className="de-it-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="de-it-modal-submit danger"
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
