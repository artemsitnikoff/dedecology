import { memo, useMemo, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate } from '@/lib/format';
import { useRegionsDirectory, useRegionDetail, useFederalDistricts } from '@/api/hooks/regions';
import type { RegionSortKey } from '@/api/hooks/regions';
import type { SortOrder } from '@/api/hooks/mno';
import { useCreateRegion } from '@/api/mutations/regions';
import type { FederalDistrict, RegionCreate, RegionListItem } from '@/api/aliases';
import './Regions.css';

/**
 * Справочник «Регионы» — это маленькая справочная таблица (8 субъектов в сидах) с
 * сортировкой по ВЫЧИСЛЯЕМЫМ колонкам (МНО/Обращений) и МНОЖЕСТВЕННЫМ выбором округа.
 * Поэтому фильтрация/сортировка делается на клиенте поверх полного GET /regions —
 * данные реальные, поведение 1:1 с прототипом, без зависимости от деталей бэк-сортировки.
 */

type HeadKey = RegionSortKey | 'status';
interface Head {
  key: HeadKey;
  label: string;
  cellClass: string;
  nosort?: boolean;
}
const HEADS: Head[] = [
  { key: 'code', label: 'Код', cellClass: 'de-reg-c-code' },
  { key: 'name', label: 'Субъект РФ', cellClass: 'de-reg-c-name' },
  { key: 'fed', label: 'Федеральный округ', cellClass: 'de-reg-c-fed' },
  { key: 'operator', label: 'Региональные операторы', cellClass: 'de-reg-c-ops' },
  { key: 'mno', label: 'МНО', cellClass: 'de-reg-c-mno' },
  { key: 'inc', label: 'Обращений', cellClass: 'de-reg-c-inc' },
  { key: 'status', label: 'Статус', cellClass: 'de-reg-c-status', nosort: true },
];

function SortArrows({ on, order }: { on: boolean; order: SortOrder }) {
  return (
    <span className="de-reg-sortarr">
      <span className={on && order === 'asc' ? 'lit' : ''}>▲</span>
      <span className={on && order === 'desc' ? 'lit' : ''}>▼</span>
    </span>
  );
}

/** Извлекает значение для сортировки (число или строка). */
function sortValue(r: RegionListItem, key: RegionSortKey): number | string {
  switch (key) {
    case 'name':
      return r.name;
    case 'fed':
      return r.fed;
    case 'operator':
      return r.operators[0] ?? '';
    case 'mno':
      return r.mno_count;
    case 'inc':
      return r.incidents_count;
    case 'code':
    default:
      return Number(r.code);
  }
}

type RowProps = {
  r: RegionListItem;
  active: boolean;
  onOpen: (code: string) => void;
};
const RegionRow = memo(function RegionRow({ r, active, onOpen }: RowProps) {
  const more = r.operators.length > 1;
  return (
    <div className={`de-reg-row ${active ? 'active' : ''}`} onClick={() => onOpen(r.code)}>
      <div className="de-reg-cell de-reg-c-code">
        <span className="de-reg-code-badge">{r.code}</span>
      </div>
      <div className="de-reg-cell de-reg-c-name">{r.name}</div>
      <div className="de-reg-c-fed">
        <span className="de-reg-fed-code">{r.fed_code || '—'}</span>
        <span className="de-reg-fed-name">{r.fed_name || ''}</span>
      </div>
      <div className="de-reg-cell de-reg-c-ops" title={r.operators.join(', ') || '—'}>
        <span className="de-reg-ops-first">{r.operators[0] || '—'}</span>
        {more && <span className="de-reg-ops-more">+{r.operators.length - 1}</span>}
      </div>
      <div className="de-reg-cell de-reg-c-mno">{r.mno_count}</div>
      <div className="de-reg-cell de-reg-c-inc">{r.incidents_count}</div>
      <div className="de-reg-c-status">
        <span className={`de-reg-pill ${r.active ? 'on' : 'off'}`}>
          <span
            className="de-reg-pill-dot"
            style={{ background: r.active ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
          />
          {r.active ? 'Активен' : 'Не подключён'}
        </span>
        <span className="de-reg-sync-date">синхр. {formatDate(r.last_sync) || '—'}</span>
      </div>
    </div>
  );
});

/* ============================================================
   Экран «Регионы»
   ============================================================ */
export function RegionsPage() {
  const [query, setQuery] = useState('');
  const [fFed, setFFed] = useState<string>(''); // '' = все округа (одиночный выбор)
  const [sortKey, setSortKey] = useState<RegionSortKey>('code');
  const [sortDir, setSortDir] = useState<SortOrder>('asc');
  const [detailCode, setDetailCode] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const { message, showToast } = useToast();

  const regionsQuery = useRegionsDirectory({});
  const districtsQuery = useFederalDistricts();
  const createRegion = useCreateRegion();

  const regions = useMemo(() => regionsQuery.data ?? [], [regionsQuery.data]);
  const districts = districtsQuery.data ?? [];

  const filtered = useMemo(() => {
    let list = regions.slice();
    const q = query.trim().toLowerCase();
    if (q)
      list = list.filter((r) =>
        `${r.code} ${r.name} ${r.operators.join(' ')} ${r.fed_name}`.toLowerCase().includes(q)
      );
    if (fFed) list = list.filter((r) => String(r.fed) === fFed);
    const dir = sortDir === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    return list;
  }, [regions, query, fFed, sortKey, sortDir]);

  const onSort = (key: RegionSortKey) => {
    setSortDir((prev) => (sortKey === key && prev === 'asc' ? 'desc' : 'asc'));
    setSortKey(key);
  };

  const filterCount = fFed ? 1 : 0;
  const isFiltered = filterCount > 0 || !!query;
  const counterText = isFiltered
    ? `Показано ${filtered.length} из ${regions.length}`
    : `${regions.length} субъектов РФ`;

  const handleCreate = (payload: RegionCreate) => {
    if (regions.some((r) => r.code === payload.code)) {
      showToast(`Регион с кодом ${payload.code} уже есть в справочнике.`);
      return;
    }
    createRegion.mutate(payload, {
      onSuccess: () => {
        setAddOpen(false);
        showToast(`Регион «${payload.name}» добавлен в справочник.`);
      },
      onError: () => showToast('Не удалось добавить регион.'),
    });
  };

  return (
    <div className="de-reg-wrap">
      {/* Шапка */}
      <div className="de-reg-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-reg-title">Регионы</h1>
          <div className="de-reg-subtitle">Справочник субъектов РФ · {counterText}</div>
        </div>
        <div className="de-reg-spacer" />
        <button type="button" className="de-reg-btn de-reg-btn-primary" onClick={() => setAddOpen(true)}>
          <Icon name="plus" size={15} />
          Добавить регион
        </button>
      </div>

      {/* Контролы */}
      <div className="de-reg-controls">
        <div className="de-reg-search-box">
          <Icon name="search" size={15} color="var(--fg-3)" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по коду, субъекту, оператору…"
          />
        </div>
        <div className="de-reg-filter-sep" />
        <div className="de-reg-filter-group">
          <span className="de-reg-filter-label">Округ</span>
          <select
            className="de-reg-select"
            value={fFed}
            onChange={(e) => setFFed(e.target.value)}
          >
            <option value="">Все округа</option>
            {districts.map((d) => (
              <option key={d.id} value={String(d.id)}>
                {d.code} · {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="de-reg-spacer" />
        {filterCount > 0 && (
          <button type="button" className="de-reg-btn de-reg-btn-reset" onClick={() => setFFed('')}>
            Сбросить
          </button>
        )}
      </div>

      {/* Таблица */}
      <div className="de-reg-content">
        {regionsQuery.isLoading ? (
          <div className="de-reg-state">Загрузка…</div>
        ) : regionsQuery.isError ? (
          <div className="de-reg-state error">Не удалось загрузить справочник регионов.</div>
        ) : filtered.length === 0 ? (
          <div className="de-reg-empty">
            <h3>Регионы не найдены</h3>
            <p>Под заданные фильтры субъектов нет.</p>
            {filterCount > 0 && (
              <button type="button" className="de-reg-empty-btn" onClick={() => setFFed('')}>
                Сбросить фильтры
              </button>
            )}
          </div>
        ) : (
          <div className="de-reg-table">
            <div className="de-reg-thead">
              {HEADS.map((h) => {
                const on = !h.nosort && sortKey === h.key;
                return (
                  <div
                    key={h.key}
                    className={`de-reg-th ${h.cellClass} ${h.nosort ? '' : 'sortable'} ${on ? 'on' : ''}`}
                    onClick={h.nosort ? undefined : () => onSort(h.key as RegionSortKey)}
                  >
                    {h.label}
                    {!h.nosort && <SortArrows on={on} order={sortDir} />}
                  </div>
                );
              })}
            </div>
            {filtered.map((r) => (
              <RegionRow key={r.code} r={r} active={detailCode === r.code} onOpen={setDetailCode} />
            ))}
          </div>
        )}
      </div>

      {detailCode && <RegionDrawer code={detailCode} onClose={() => setDetailCode(null)} />}

      {addOpen && (
        <AddRegionModal
          districts={districts}
          pending={createRegion.isPending}
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
          notify={showToast}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Карточка-drawer региона ---------- */
function RegionDrawer({ code, onClose }: { code: string; onClose: () => void }) {
  const { data, isLoading, isError } = useRegionDetail(code);

  return (
    <div className="de-reg-drawer">
      {isLoading ? (
        <div className="de-reg-drawer-loading">
          <span className="de-reg-heart de-reg-drawer-loading-mark">💚</span>
          <span className="de-reg-drawer-loading-text">Загрузка…</span>
        </div>
      ) : isError || !data ? (
        <div className="de-reg-drawer-loading">
          <span className="de-reg-drawer-error-text">Не удалось загрузить регион.</span>
          <button type="button" className="de-reg-empty-btn" onClick={onClose}>
            Закрыть
          </button>
        </div>
      ) : (
        <div className="de-reg-drawer-inner">
          <div className="de-reg-drawer-head">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="de-reg-drawer-pills">
                <span className="de-reg-drawer-code">Код {data.code}</span>
                <span className={`de-reg-pill ${data.active ? 'on' : 'off'}`}>
                  <span
                    className="de-reg-pill-dot"
                    style={{ background: data.active ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
                  />
                  {data.active ? 'Активен' : 'Не подключён'}
                </span>
              </div>
              <h2 className="de-reg-drawer-title">{data.name}</h2>
              <div className="de-reg-drawer-sub">
                {data.fed_code} · {data.fed_name} федеральный округ
              </div>
            </div>
            <button type="button" className="de-reg-drawer-close" aria-label="Закрыть" onClick={onClose}>
              <Icon name="x" size={18} />
            </button>
          </div>

          <div className="de-reg-drawer-body">
            <div className="de-reg-tiles">
              <div className="de-reg-tile">
                <div className="de-reg-tile-num green">{data.mno_count}</div>
                <div className="de-reg-tile-label">МНО в регионе</div>
              </div>
              <div className="de-reg-tile">
                <div className="de-reg-tile-num dark">{data.incidents_count}</div>
                <div className="de-reg-tile-label">Обращений</div>
              </div>
            </div>

            <div className="de-reg-ops-head">
              <span className="de-reg-ops-head-title">Региональные операторы</span>
              <span className="de-reg-ops-count">{data.operators.length}</span>
            </div>
            {data.operators.length > 0 ? (
              <div className="de-reg-ops-list">
                {data.operators.map((op, i) => (
                  <div key={i} className="de-reg-op-item">
                    <span className="de-reg-op-icon">
                      <Icon name="building" size={15} />
                    </span>
                    <span className="de-reg-op-name">{op}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="de-reg-ops-empty">Операторы пока не назначены.</div>
            )}

            <div className="de-reg-fields">
              {(
                [
                  ['Код субъекта', data.code],
                  ['Федеральный округ', `${data.fed_code} · ${data.fed_name}`],
                  ['regionId в ФГИС', data.code],
                  ['МНО в регионе', String(data.mno_count)],
                  ['Обращений', String(data.incidents_count)],
                  ['Последняя синхронизация', formatDate(data.last_sync) || '—'],
                ] as Array<[string, string]>
              ).map(([k, v]) => (
                <div key={k} className="de-reg-field">
                  <div className="de-reg-field-key">{k}</div>
                  <div className="de-reg-field-val">{v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Модалка «Добавить регион» ---------- */
type AddModalProps = {
  districts: FederalDistrict[];
  pending: boolean;
  onClose: () => void;
  onSubmit: (payload: RegionCreate) => void;
  notify: (msg: string) => void;
};
function AddRegionModal({ districts, pending, onClose, onSubmit, notify }: AddModalProps) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [fed, setFed] = useState<number>(districts.find((d) => d.id === 5)?.id ?? districts[0]?.id ?? 1);
  const [operators, setOperators] = useState<string[]>([]);
  const [operatorInput, setOperatorInput] = useState('');

  const addOp = () => {
    const v = operatorInput.replace(/,+$/, '').trim();
    if (v) {
      setOperators((prev) => [...prev, v]);
      setOperatorInput('');
    }
  };

  const submit = () => {
    const c = code.trim();
    const n = name.trim();
    if (!c || !n) {
      notify('Укажите код и наименование субъекта РФ.');
      return;
    }
    const ops = operators.slice();
    const tail = operatorInput.trim();
    if (tail) ops.push(tail);
    onSubmit({ code: c, name: n, fed, operators: ops });
  };

  return (
    <div className="de-reg-modal-overlay" onClick={onClose}>
      <div className="de-reg-modal" onClick={(e) => e.stopPropagation()}>
        <div className="de-reg-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Новый регион</h2>
            <div className="de-reg-modal-head-sub">Субъект РФ в справочнике для сбора и синхронизации</div>
          </div>
          <button type="button" className="de-reg-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-reg-modal-body">
          <div className="de-reg-modal-row">
            <div className="de-reg-field-group" style={{ width: 120 }}>
              <label>Код субъекта</label>
              <input
                className="de-reg-input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="63"
              />
            </div>
            <div className="de-reg-field-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Федеральный округ</label>
              <select
                className="de-reg-input"
                value={fed}
                onChange={(e) => setFed(Number(e.target.value))}
              >
                {districts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code} · {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="de-reg-field-group">
            <label>Субъект РФ</label>
            <input
              className="de-reg-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Самарская область"
            />
          </div>
          <div className="de-reg-field-group">
            <label>Региональные операторы по ТКО</label>
            <div className="de-reg-tagbox">
              {operators.map((op, i) => (
                <span key={i} className="de-reg-tag">
                  {op}
                  <button
                    type="button"
                    aria-label="Удалить оператора"
                    onClick={() => setOperators((prev) => prev.filter((_, j) => j !== i))}
                  >
                    <Icon name="x" size={13} />
                  </button>
                </span>
              ))}
              <input
                className="de-reg-tag-input"
                value={operatorInput}
                onChange={(e) => setOperatorInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    addOp();
                  }
                }}
                placeholder="Оператор + Enter"
              />
            </div>
            <span className="de-reg-tag-hint">
              В регионе может быть несколько операторов — добавьте по одному (Enter или запятая).
            </span>
          </div>
        </div>
        <div className="de-reg-modal-foot">
          <button type="button" className="de-reg-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="de-reg-modal-submit" disabled={pending} onClick={submit}>
            {pending ? 'Добавление…' : 'Добавить регион'}
          </button>
        </div>
      </div>
    </div>
  );
}
