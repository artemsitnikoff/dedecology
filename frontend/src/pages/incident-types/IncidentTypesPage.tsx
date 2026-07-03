import { memo, useMemo, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { useAuthStore } from '@/store/authStore';
import { useIncidentTypesList } from '@/api/hooks/incidentTypes';
import {
  useCreateIncidentType,
  useDeleteIncidentType,
  useUpdateIncidentType,
} from '@/api/mutations/incidentTypes';
import type {
  IncidentTypeCreate,
  IncidentTypeItem,
  IncidentTypeUpdate,
} from '@/api/aliases';
import './IncidentTypes.css';

/**
 * Справочник «Типы инцидентов» — редактируемый список типов обращений (источник правды —
 * таблица incident_types в БД). admin может добавлять/изменять/удалять; user — только смотрит.
 * Дизайн зеркалит «Регионы» (шапка + таблица), модалка — как «Добавить МНО».
 */

/* ---------- Строка таблицы ---------- */
type RowProps = {
  t: IncidentTypeItem;
  isAdmin: boolean;
  busy: boolean;
  onEdit: (t: IncidentTypeItem) => void;
  onDelete: (t: IncidentTypeItem) => void;
};
const IncidentTypeRow = memo(function IncidentTypeRow({ t, isAdmin, busy, onEdit, onDelete }: RowProps) {
  return (
    <div className="de-it-row">
      <div className="de-it-cell de-it-c-code">
        <span className="de-it-code-badge" title={t.code}>
          {t.code}
        </span>
      </div>
      <div className="de-it-cell de-it-c-label">{t.label}</div>
      <div className="de-it-cell de-it-c-order">{t.sort_order}</div>
      {isAdmin && (
        <div className="de-it-cell de-it-c-actions">
          <button type="button" className="de-it-row-btn" disabled={busy} onClick={() => onEdit(t)}>
            Изменить
          </button>
          <button
            type="button"
            className="de-it-row-btn danger"
            disabled={busy}
            onClick={() => onDelete(t)}
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
   Экран «Типы инцидентов»
   ============================================================ */
export function IncidentTypesPage() {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === 'admin';

  const { message, showToast } = useToast();

  const listQuery = useIncidentTypesList();
  const createType = useCreateIncidentType();
  const updateType = useUpdateIncidentType();
  const deleteType = useDeleteIncidentType();

  const types = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  // Модалка: null — закрыта; 'new' — создание; иначе редактируем этот тип.
  const [modal, setModal] = useState<'new' | IncidentTypeItem | null>(null);
  // Подтверждение удаления — целевой тип или null.
  const [toDelete, setToDelete] = useState<IncidentTypeItem | null>(null);

  const rowBusy = createType.isPending || updateType.isPending || deleteType.isPending;

  const handleCreate = (payload: IncidentTypeCreate) => {
    createType.mutate(payload, {
      onSuccess: () => {
        setModal(null);
        showToast(`Тип «${payload.label}» добавлен в справочник.`);
      },
      onError: () => showToast('Не удалось добавить тип инцидента.'),
    });
  };

  const handleUpdate = (id: string, payload: IncidentTypeUpdate) => {
    updateType.mutate(
      { id, body: payload },
      {
        onSuccess: () => {
          setModal(null);
          showToast('Тип инцидента обновлён.');
        },
        onError: () => showToast('Не удалось обновить тип инцидента.'),
      }
    );
  };

  const handleDelete = () => {
    if (!toDelete) return;
    const label = toDelete.label;
    deleteType.mutate(toDelete.id, {
      onSuccess: () => {
        setToDelete(null);
        showToast(`Тип «${label}» удалён из справочника.`);
      },
      onError: () => showToast('Не удалось удалить тип инцидента.'),
    });
  };

  return (
    <div className="de-it-wrap">
      {/* Шапка */}
      <div className="de-it-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-it-title">Типы инцидентов</h1>
          <div className="de-it-subtitle">
            Справочник типов обращений · {types.length} типов
          </div>
        </div>
        <div className="de-it-spacer" />
        {isAdmin && (
          <button type="button" className="de-it-btn de-it-btn-primary" onClick={() => setModal('new')}>
            <Icon name="plus" size={15} />
            Добавить тип
          </button>
        )}
      </div>

      {/* Таблица */}
      <div className="de-it-content">
        {listQuery.isLoading ? (
          <div className="de-it-state">Загрузка…</div>
        ) : listQuery.isError ? (
          <div className="de-it-state error">Не удалось загрузить справочник типов инцидента.</div>
        ) : types.length === 0 ? (
          <div className="de-it-empty">
            <span className="de-it-empty-mark">💚</span>
            <h3>Типов инцидента пока нет</h3>
            <p>
              {isAdmin
                ? 'Добавьте первый тип обращения — он появится в форме приёма и фильтрах.'
                : 'Справочник пуст. Обратитесь к администратору для добавления типов.'}
            </p>
          </div>
        ) : (
          <div className="de-it-table">
            <div className="de-it-thead">
              <div className="de-it-th de-it-c-code">Код</div>
              <div className="de-it-th de-it-c-label">Название</div>
              <div className="de-it-th de-it-c-order">Порядок</div>
              {isAdmin && <div className="de-it-th de-it-c-actions">Действия</div>}
            </div>
            {types.map((t) => (
              <IncidentTypeRow
                key={t.id}
                t={t}
                isAdmin={isAdmin}
                busy={rowBusy}
                onEdit={setModal}
                onDelete={setToDelete}
              />
            ))}
          </div>
        )}
      </div>

      {modal && (
        <TypeModal
          editing={modal === 'new' ? null : modal}
          pending={createType.isPending || updateType.isPending}
          onClose={() => setModal(null)}
          onCreate={handleCreate}
          onUpdate={handleUpdate}
          notify={showToast}
        />
      )}

      {toDelete && (
        <ConfirmDeleteModal
          type={toDelete}
          pending={deleteType.isPending}
          onClose={() => setToDelete(null)}
          onConfirm={handleDelete}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Модалка добавления / правки ---------- */
type TypeModalProps = {
  /** null — режим создания; иначе редактируем этот тип (code readonly). */
  editing: IncidentTypeItem | null;
  pending: boolean;
  onClose: () => void;
  onCreate: (payload: IncidentTypeCreate) => void;
  onUpdate: (id: string, payload: IncidentTypeUpdate) => void;
  notify: (msg: string) => void;
};
function TypeModal({ editing, pending, onClose, onCreate, onUpdate, notify }: TypeModalProps) {
  const [label, setLabel] = useState(editing?.label ?? '');
  const [code, setCode] = useState(editing?.code ?? '');
  const [sortOrder, setSortOrder] = useState(
    editing ? String(editing.sort_order) : ''
  );

  const isEdit = editing !== null;

  const submit = () => {
    const l = label.trim();
    if (!l) {
      notify('Укажите название типа инцидента.');
      return;
    }
    // sort_order необязателен; если задан — валидное целое ≥ 0.
    const so = sortOrder.trim();
    let sortValue: number | undefined;
    if (so !== '') {
      const n = Number(so);
      if (!Number.isFinite(n) || !Number.isInteger(n) || n < 0) {
        notify('Порядок должен быть целым числом ≥ 0.');
        return;
      }
      sortValue = n;
    }

    if (isEdit && editing) {
      const payload: IncidentTypeUpdate = { label: l };
      if (sortValue !== undefined) payload.sort_order = sortValue;
      onUpdate(editing.id, payload);
    } else {
      const payload: IncidentTypeCreate = { label: l };
      const c = code.trim();
      if (c) payload.code = c;
      if (sortValue !== undefined) payload.sort_order = sortValue;
      onCreate(payload);
    }
  };

  return (
    <div className="de-it-modal-overlay" onClick={onClose}>
      <div className="de-it-modal" onClick={(e) => e.stopPropagation()}>
        <div className="de-it-modal-head">
          <div style={{ flex: 1 }}>
            <h2>{isEdit ? 'Изменить тип инцидента' : 'Новый тип инцидента'}</h2>
            <div className="de-it-modal-head-sub">
              {isEdit
                ? 'Код не меняется — на него ссылаются обращения'
                : 'Появится в форме приёма и фильтрах после сохранения'}
            </div>
          </div>
          <button type="button" className="de-it-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-it-modal-body">
          <div className="de-it-field-group">
            <label>Название</label>
            <input
              className="de-it-input"
              value={label}
              autoFocus
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Переполнение контейнера"
            />
          </div>
          <div className="de-it-modal-row">
            <div className="de-it-field-group" style={{ flex: 2, minWidth: 200 }}>
              <label>Код</label>
              <input
                className="de-it-input mono"
                value={editing ? editing.code : code}
                disabled={isEdit}
                onChange={(e) => setCode(e.target.value)}
                placeholder="необязательно — сгенерируется"
              />
              {!isEdit && (
                <span className="de-it-field-hint">
                  Оставьте пустым — код сгенерируется автоматически.
                </span>
              )}
            </div>
            <div className="de-it-field-group" style={{ flex: 1, minWidth: 120 }}>
              <label>Порядок</label>
              <input
                className="de-it-input mono"
                type="number"
                min={0}
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                placeholder="0"
              />
            </div>
          </div>
        </div>
        <div className="de-it-modal-foot">
          <button type="button" className="de-it-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="de-it-modal-submit" disabled={pending} onClick={submit}>
            {pending ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить тип'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Модалка подтверждения удаления ---------- */
type ConfirmProps = {
  type: IncidentTypeItem;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
};
function ConfirmDeleteModal({ type, pending, onClose, onConfirm }: ConfirmProps) {
  return (
    <div className="de-it-modal-overlay" onClick={onClose}>
      <div className="de-it-modal" style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <div className="de-it-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Удалить тип инцидента?</h2>
            <div className="de-it-modal-head-sub">Действие необратимо</div>
          </div>
          <button type="button" className="de-it-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-it-modal-body">
          <div className="de-it-confirm-text">
            Тип <b>«{type.label}»</b> будет удалён из справочника. Уже принятые обращения с этим
            кодом останутся, но тип у них перестанет отображаться (покажется «—»).
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
