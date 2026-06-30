import { memo, useCallback, useMemo, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate } from '@/lib/format';
import { useMno, useMnoDetail } from '@/api/hooks/mno';
import type { MnoFilters, MnoSortKey, SortOrder } from '@/api/hooks/mno';
import { useRegionsDirectory } from '@/api/hooks/regions';
import { exportMno, useCreateMno, useSyncMno, useSyncMnoOne } from '@/api/mutations/mno';
import type { MnoCreate, MnoListItem, RegionListItem } from '@/api/aliases';
import './Mno.css';

/** Заголовки таблицы МНО (порядок прототипа). coords/sync — без сортировки. */
type HeadKey = MnoSortKey | 'coords' | 'sync';
interface Head {
  key: HeadKey;
  label: string;
  cellClass: string;
  nosort?: boolean;
}
const HEADS: Head[] = [
  { key: 'reg', label: 'Реестровый №', cellClass: 'de-mno-c-reg' },
  { key: 'name', label: 'Наименование', cellClass: 'de-mno-c-name' },
  { key: 'region', label: 'Регион', cellClass: 'de-mno-c-region' },
  { key: 'city', label: 'Город', cellClass: 'de-mno-c-city' },
  { key: 'address', label: 'Адрес', cellClass: 'de-mno-c-address' },
  { key: 'coords', label: 'Координаты', cellClass: 'de-mno-c-coords', nosort: true },
  { key: 'sync', label: 'Синхронизация', cellClass: 'de-mno-c-sync', nosort: true },
];

function CheckMark() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--ark-white)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12l5 5 9-11" />
    </svg>
  );
}
function SortArrows({ on, order }: { on: boolean; order: SortOrder }) {
  return (
    <span className="de-mno-sortarr">
      <span className={on && order === 'asc' ? 'lit' : ''}>▲</span>
      <span className={on && order === 'desc' ? 'lit' : ''}>▼</span>
    </span>
  );
}
/** Схематичный маркер-пин (заливка currentColor, белый центр). */
function Pin({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="var(--ark-white)" strokeWidth="1.4">
      <path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7z" fill="currentColor" />
      <circle cx="12" cy="9" r="2.6" fill="var(--ark-white)" stroke="none" />
    </svg>
  );
}

/* ---------- Строка таблицы ---------- */
type RowProps = {
  m: MnoListItem;
  selected: boolean;
  active: boolean;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
};
const MnoRow = memo(function MnoRow({ m, selected, active, onToggle, onOpen }: RowProps) {
  return (
    <div
      className={`de-mno-row ${selected ? 'selected' : active ? 'active' : ''}`}
      onClick={() => onOpen(m.id)}
    >
      <div
        className="de-mno-cell de-mno-check-col"
        onClick={(e) => {
          e.stopPropagation();
          onToggle(m.id);
        }}
      >
        <div className={`de-mno-check ${selected ? 'checked' : ''}`}>{selected && <CheckMark />}</div>
      </div>
      <div className="de-mno-cell de-mno-c-reg">{m.reg}</div>
      <div className="de-mno-cell de-mno-c-name">{m.name}</div>
      <div className="de-mno-cell de-mno-c-region" title={m.region_name}>
        {m.region_name}
      </div>
      <div className="de-mno-cell de-mno-c-city" title={m.city}>
        {m.city}
      </div>
      <div className="de-mno-cell de-mno-c-address" title={m.address}>
        {m.address}
      </div>
      <div className="de-mno-cell de-mno-c-coords">{m.coords}</div>
      <div className="de-mno-cell de-mno-c-sync">
        <span className={`de-mno-pill ${m.synced ? 'fgis' : 'manual'}`}>
          <span
            className="de-mno-pill-dot"
            style={{ background: m.synced ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
          />
          {m.synced ? 'ФГИС' : 'Вручную'}
        </span>
        <span className="de-mno-sync-date">{m.synced ? formatDate(m.sync_date) || '—' : '—'}</span>
      </div>
    </div>
  );
});

/* ============================================================
   Экран «МНО»
   ============================================================ */
export function MnoPage() {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<MnoSortKey>('name');
  const [sortDir, setSortDir] = useState<SortOrder>('asc');
  const [fRegion, setFRegion] = useState('');
  const [fSync, setFSync] = useState<Array<'fgis' | 'manual'>>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sub, setSub] = useState<'list' | 'map'>('list');
  const [detailId, setDetailId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const { message, showToast } = useToast();

  // Серверная фильтрация/сортировка (как у incidents). synced: один чип → bool, оба/ни одного → all.
  const syncedFilter: boolean | undefined =
    fSync.length === 1 ? fSync[0] === 'fgis' : undefined;
  const filters: MnoFilters = useMemo(
    () => ({
      search: query || undefined,
      region: fRegion || undefined,
      synced: syncedFilter,
      sort: sortKey,
      order: sortDir,
    }),
    [query, fRegion, syncedFilter, sortKey, sortDir]
  );

  const listQuery = useMno(filters);
  const allQuery = useMno({}); // нефильтрованный итог (дедуп с Sidebar)
  const regionsQuery = useRegionsDirectory({});

  const syncMno = useSyncMno();
  const syncMnoOne = useSyncMnoOne();
  const createMno = useCreateMno();

  const rows = listQuery.data ?? [];
  const grandTotal = allQuery.data?.length ?? rows.length;
  const regions = regionsQuery.data ?? [];

  const filterCount = (fRegion ? 1 : 0) + (fSync.length ? 1 : 0);
  const isFiltered = filterCount > 0 || !!query;
  const counterText = isFiltered
    ? `Показано ${rows.length} из ${grandTotal}`
    : `${grandTotal} МНО · слой 5 ФГИС`;

  const allSelected = rows.length > 0 && rows.every((m) => selected.has(m.id));
  // Стабильная ссылка — чтобы memo строк не сбрасывался на каждом рендере.
  const toggleSel = useCallback(
    (id: string) =>
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    []
  );
  const toggleAll = () =>
    setSelected((prev) => (rows.length > 0 && rows.every((m) => prev.has(m.id)) ? new Set<string>() : new Set(rows.map((m) => m.id))));
  const toggleSync = (v: 'fgis' | 'manual') =>
    setFSync((prev) => (prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]));
  const resetFilters = () => {
    setFRegion('');
    setFSync([]);
  };

  const onSort = (key: MnoSortKey) => {
    setSortDir((prev) => (sortKey === key && prev === 'asc' ? 'desc' : 'asc'));
    setSortKey(key);
  };

  const handleSyncAll = () => {
    if (syncMno.isPending) return;
    syncMno.mutate(undefined, {
      onSuccess: (res) =>
        showToast(
          `Синхронизация с ФГИС завершена (слой 5). Обработано ${res.total} МНО` +
            (res.synced ? `, новых отметок: ${res.synced}.` : '.')
        ),
      onError: () => showToast('Не удалось синхронизировать с ФГИС. Попробуйте ещё раз.'),
    });
  };
  const handleSyncOne = (id: string) =>
    syncMnoOne.mutate(id, {
      onSuccess: () => showToast('МНО синхронизировано с ФГИС.'),
      onError: () => showToast('Не удалось синхронизировать МНО.'),
    });

  const handleExport = () => {
    void exportMno(filters);
  };

  const handleCreate = (payload: MnoCreate) => {
    createMno.mutate(payload, {
      onSuccess: () => {
        setAddOpen(false);
        showToast('МНО добавлено вручную. Появится в ФГИС после синхронизации.');
      },
      onError: () => showToast('Не удалось добавить МНО.'),
    });
  };

  // Проекция координат в проценты для схематичной карты (как в прототипе).
  const map = useMemo(() => {
    if (!rows.length) return { pins: [] as Array<{ m: MnoListItem; x: number; y: number }>, bbox: '' };
    const lat = (m: MnoListItem) => parseFloat(m.coords.split(',')[0]);
    const lng = (m: MnoListItem) => parseFloat(m.coords.split(',')[1]);
    let minLat = Math.min(...rows.map(lat));
    let maxLat = Math.max(...rows.map(lat));
    let minLng = Math.min(...rows.map(lng));
    let maxLng = Math.max(...rows.map(lng));
    let latR = maxLat - minLat || 0.4;
    let lngR = maxLng - minLng || 0.4;
    minLat -= latR * 0.16;
    maxLat += latR * 0.16;
    minLng -= lngR * 0.16;
    maxLng += lngR * 0.16;
    latR = maxLat - minLat;
    lngR = maxLng - minLng;
    const bbox = `${minLng.toFixed(4)}, ${minLat.toFixed(4)} … ${maxLng.toFixed(4)}, ${maxLat.toFixed(4)}`;
    const pins = rows.map((m) => ({
      m,
      x: ((lng(m) - minLng) / lngR) * 100,
      y: (1 - (lat(m) - minLat) / latR) * 100,
    }));
    return { pins, bbox };
  }, [rows]);

  return (
    <div className="de-mno-wrap">
      {/* Шапка */}
      <div className="de-mno-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-mno-title">Места накопления отходов</h1>
          <div className="de-mno-subtitle">{counterText}</div>
        </div>
        <div className="de-mno-spacer" />
        <button
          type="button"
          className="de-mno-btn de-mno-btn-outline"
          onClick={handleSyncAll}
          disabled={syncMno.isPending}
        >
          <Icon name="refresh" size={15} className={syncMno.isPending ? 'de-spin' : ''} />
          {syncMno.isPending ? 'Синхронизация…' : 'Синхронизировать с ФГИС'}
        </button>
        <button type="button" className="de-mno-btn de-mno-btn-primary" onClick={() => setAddOpen(true)}>
          <Icon name="plus" size={15} />
          Добавить МНО
        </button>
      </div>

      {/* Поиск + Список/Карта */}
      <div className="de-mno-toolbar">
        <div className="de-mno-search-box">
          <Icon name="search" size={15} color="var(--fg-3)" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по наименованию, реестровому №, адресу…"
          />
        </div>
        <div className="de-mno-spacer" />
        <div className="de-mno-seg">
          <button
            type="button"
            className={`de-mno-seg-btn ${sub === 'list' ? 'active' : ''}`}
            onClick={() => setSub('list')}
          >
            <Icon name="list" size={15} />
            Список
          </button>
          <button
            type="button"
            className={`de-mno-seg-btn ${sub === 'map' ? 'active' : ''}`}
            onClick={() => setSub('map')}
          >
            <Icon name="map" size={15} />
            Карта
          </button>
        </div>
      </div>

      {/* Фильтры */}
      <div className="de-mno-filterbar">
        <div className="de-mno-filter-group">
          <span className="de-mno-filter-label">Регион</span>
          <select className="de-mno-select" value={fRegion} onChange={(e) => setFRegion(e.target.value)}>
            <option value="">Все регионы</option>
            {regions.map((r) => (
              <option key={r.code} value={r.code}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <div className="de-mno-filter-sep" />
        <div className="de-mno-filter-group">
          <span className="de-mno-filter-label">Синхронизация</span>
          <button
            type="button"
            className={`de-mno-fchip ${fSync.includes('fgis') ? 'active' : ''}`}
            onClick={() => toggleSync('fgis')}
          >
            ФГИС
          </button>
          <button
            type="button"
            className={`de-mno-fchip ${fSync.includes('manual') ? 'active' : ''}`}
            onClick={() => toggleSync('manual')}
          >
            Вручную
          </button>
        </div>
        <div className="de-mno-spacer" />
        {filterCount > 0 && (
          <button type="button" className="de-mno-btn de-mno-btn-reset" onClick={resetFilters}>
            Сбросить
          </button>
        )}
      </div>

      {/* Bulk */}
      {selected.size > 0 && (
        <div className="de-mno-bulkbar">
          <span className="de-mno-bulk-count">Выбрано: {selected.size}</span>
          <div className="de-mno-bulk-sep" />
          <button type="button" className="de-mno-btn de-mno-btn-success" onClick={handleExport}>
            <Icon name="download" size={14} />
            Выгрузить в Excel
          </button>
          <div className="de-mno-spacer" />
          <button type="button" className="de-mno-btn de-mno-btn-ghost" onClick={() => setSelected(new Set())}>
            Снять выделение
          </button>
        </div>
      )}

      {/* Контент: список */}
      {sub === 'list' && (
        <div className="de-mno-content">
          {listQuery.isLoading ? (
            <div className="de-mno-state">Загрузка…</div>
          ) : listQuery.isError ? (
            <div className="de-mno-state error">Не удалось загрузить реестр МНО.</div>
          ) : rows.length > 0 ? (
            <div className="de-mno-table">
              <div className="de-mno-thead">
                <div className="de-mno-check-col">
                  <div
                    className={`de-mno-check ${allSelected ? 'checked' : ''}`}
                    onClick={toggleAll}
                  >
                    {allSelected && <CheckMark />}
                  </div>
                </div>
                {HEADS.map((h) => {
                  const on = !h.nosort && sortKey === h.key;
                  return (
                    <div
                      key={h.key}
                      className={`de-mno-th ${h.cellClass} ${h.nosort ? '' : 'sortable'} ${on ? 'on' : ''}`}
                      onClick={h.nosort ? undefined : () => onSort(h.key as MnoSortKey)}
                    >
                      {h.label}
                      {!h.nosort && <SortArrows on={on} order={sortDir} />}
                    </div>
                  );
                })}
              </div>
              {rows.map((m) => (
                <MnoRow
                  key={m.id}
                  m={m}
                  selected={selected.has(m.id)}
                  active={detailId === m.id}
                  onToggle={toggleSel}
                  onOpen={setDetailId}
                />
              ))}
            </div>
          ) : (
            <div className="de-mno-empty">
              <div className="de-mno-empty-mark">
                <Pin size={40} />
              </div>
              <h3>МНО не найдены</h3>
              <p>
                Под заданные фильтры мест накопления отходов нет. Сбросьте фильтры или синхронизируйте список с
                ФГИС.
              </p>
              {filterCount > 0 && (
                <button type="button" className="de-mno-empty-btn" onClick={resetFilters}>
                  Сбросить фильтры
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Контент: карта */}
      {sub === 'map' && (
        <div className="de-mno-map-area">
          <div className="de-mno-map">
            <div className="de-mno-map-bbox">bbox · {map.bbox || '—'}</div>
            <div className="de-mno-map-chips">
              <span className="de-mno-map-chip">
                <span className="de-mno-map-chip-dot" />
                Слой 5 · МНО
              </span>
              <span className="de-mno-map-chip mono">z 8</span>
              <span className="de-mno-map-chip dark">{rows.length} точек</span>
            </div>
            <div className="de-mno-map-legend">
              <span>
                <span className="de-mno-map-legend-dot" style={{ background: 'var(--ark-gray-500)' }} />
                Из ФГИС
              </span>
              <span>
                <span className="de-mno-map-legend-dot" style={{ background: 'var(--de-brand)' }} />
                Добавлено вручную
              </span>
            </div>
            {map.pins.map((p) => {
              const isActive = detailId === p.m.id;
              return (
                <div
                  key={p.m.id}
                  className={`de-mno-pin ${isActive ? 'active' : ''}`}
                  onClick={() => setDetailId(p.m.id)}
                  style={{
                    left: `${p.x}%`,
                    top: `${p.y}%`,
                    transform: `translate(-50%,-100%) scale(${isActive ? 1.22 : 1})`,
                    color: p.m.synced ? 'var(--ark-gray-500)' : 'var(--de-brand)',
                  }}
                >
                  <div className="de-mno-pin-label">{p.m.name}</div>
                  <Pin size={28} />
                </div>
              );
            })}
            {rows.length === 0 && (
              <div className="de-mno-map-empty">
                <Pin size={40} />
                <div className="de-mno-map-empty-title">Нет точек на карте</div>
                <div>Сбросьте фильтры, чтобы увидеть все МНО.</div>
              </div>
            )}
          </div>
        </div>
      )}

      {detailId && (
        <MnoDrawer
          id={detailId}
          onClose={() => setDetailId(null)}
          onSyncOne={handleSyncOne}
          syncOnePending={syncMnoOne.isPending}
        />
      )}

      {addOpen && (
        <AddMnoModal
          regions={regions.filter((r) => r.active)}
          pending={createMno.isPending}
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
          notify={showToast}
        />
      )}

      <Toast message={message} />
    </div>
  );
}

/* ---------- Карточка-drawer МНО ---------- */
type DrawerProps = {
  id: string;
  onClose: () => void;
  onSyncOne: (id: string) => void;
  syncOnePending: boolean;
};
function MnoDrawer({ id, onClose, onSyncOne, syncOnePending }: DrawerProps) {
  const { data, isLoading, isError } = useMnoDetail(id);

  return (
    <div className="de-mno-drawer">
      {isLoading ? (
        <div className="de-mno-drawer-loading">
          <span className="de-mno-heart de-mno-drawer-loading-mark">💚</span>
          <span className="de-mno-drawer-loading-text">Загрузка…</span>
        </div>
      ) : isError || !data ? (
        <div className="de-mno-drawer-loading">
          <span className="de-mno-drawer-error-text">Не удалось загрузить МНО.</span>
          <button type="button" className="de-mno-empty-btn" onClick={onClose}>
            Закрыть
          </button>
        </div>
      ) : (
        <div className="de-mno-drawer-inner">
          <div className="de-mno-drawer-head">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="de-mno-drawer-pills">
                <span className="de-mno-drawer-type">
                  <Icon name="pin" size={12} />
                  МНО
                </span>
                <span className={`de-mno-pill ${data.synced ? 'fgis' : 'manual'}`}>
                  <span
                    className="de-mno-pill-dot"
                    style={{ background: data.synced ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
                  />
                  {data.synced ? 'Синхронизировано с ФГИС' : 'Добавлено вручную'}
                </span>
                <span className="de-mno-drawer-reg">№ {data.reg}</span>
              </div>
              <h2 className="de-mno-drawer-title">{data.name}</h2>
              <div className="de-mno-drawer-sub">{data.region_name}</div>
            </div>
            <button type="button" className="de-mno-drawer-close" aria-label="Закрыть" onClick={onClose}>
              <Icon name="x" size={18} />
            </button>
          </div>

          <div className="de-mno-drawer-body">
            <div className="de-mno-minimap">
              <div className="de-mno-minimap-pin">
                <Pin size={30} />
              </div>
              <div className="de-mno-minimap-coords">
                <Icon name="pin" size={12} />
                {data.coords}
              </div>
            </div>

            <div className="de-mno-fields">
              {(
                [
                  ['Наименование МНО', data.name],
                  ['Реестровый номер', data.reg || '—'],
                  ['Регион', data.region_name],
                  ['Город / н.п.', data.city || '—'],
                  ['Адрес МНО', data.address || '—'],
                  ['Координаты', data.coords],
                  ['ID в ФГИС', data.fgis_id || '— (нет в ФГИС)'],
                  ['Синхронизация', data.synced ? `ФГИС, ${formatDate(data.sync_date) || '—'}` : 'Добавлено вручную'],
                  ['Обращений по МНО', String(data.incidents)],
                ] as Array<[string, string]>
              ).map(([k, v]) => (
                <div key={k} className="de-mno-field">
                  <div className="de-mno-field-key">{k}</div>
                  <div className="de-mno-field-val">{v}</div>
                </div>
              ))}
            </div>

            <div className="de-mno-drawer-actions">
              {!data.synced && (
                <button
                  type="button"
                  className="de-mno-sync-one"
                  disabled={syncOnePending}
                  onClick={() => onSyncOne(data.id)}
                >
                  <Icon name="refresh" size={15} className={syncOnePending ? 'de-spin' : ''} />
                  Синхронизировать с ФГИС
                </button>
              )}
              {data.incidents > 0 && (
                <span className="de-mno-inc-badge">
                  <Icon name="alert-circle" size={15} />
                  Обращений по МНО: {data.incidents}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Модалка «Добавить МНО» ---------- */
type AddModalProps = {
  regions: RegionListItem[];
  pending: boolean;
  onClose: () => void;
  onSubmit: (payload: MnoCreate) => void;
  notify: (msg: string) => void;
};
function AddMnoModal({ regions, pending, onClose, onSubmit, notify }: AddModalProps) {
  const [name, setName] = useState('');
  const [reg, setReg] = useState('');
  const [region, setRegion] = useState(regions[0]?.code ?? '');
  const [city, setCity] = useState('');
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState('');

  const submit = () => {
    const n = name.trim();
    const c = coords.trim();
    if (!n || !c) {
      notify('Укажите наименование и координаты МНО.');
      return;
    }
    onSubmit({
      name: n,
      reg: reg.trim(),
      region_code: region,
      city: city.trim(),
      address: address.trim(),
      coords: c,
    });
  };

  return (
    <div className="de-mno-modal-overlay" onClick={onClose}>
      <div className="de-mno-modal" onClick={(e) => e.stopPropagation()}>
        <div className="de-mno-modal-head">
          <div style={{ flex: 1 }}>
            <h2>Новое МНО</h2>
            <div className="de-mno-modal-head-sub">
              Добавляется вручную, появится в ФГИС после синхронизации
            </div>
          </div>
          <button type="button" className="de-mno-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-mno-modal-body">
          <div className="de-mno-field-group">
            <label>Наименование МНО</label>
            <input
              className="de-mno-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Контейнерная площадка, ул. …"
            />
          </div>
          <div className="de-mno-modal-row">
            <div className="de-mno-field-group" style={{ flex: 1, minWidth: 180 }}>
              <label>Реестровый номер</label>
              <input
                className="de-mno-input"
                value={reg}
                onChange={(e) => setReg(e.target.value)}
                placeholder="63-04-000000"
              />
            </div>
            <div className="de-mno-field-group" style={{ flex: 1, minWidth: 180 }}>
              <label>Регион</label>
              <select className="de-mno-input" value={region} onChange={(e) => setRegion(e.target.value)}>
                {regions.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.code} · {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="de-mno-modal-row">
            <div className="de-mno-field-group" style={{ flex: 1, minWidth: 180 }}>
              <label>Город / н.п.</label>
              <input
                className="de-mno-input"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="г. Кинель"
              />
            </div>
            <div className="de-mno-field-group" style={{ flex: 2, minWidth: 200 }}>
              <label>Адрес МНО</label>
              <input
                className="de-mno-input"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="ул. Маяковского, 41"
              />
            </div>
          </div>
          <div className="de-mno-field-group">
            <label>Координаты (широта, долгота)</label>
            <input
              className="de-mno-input"
              value={coords}
              onChange={(e) => setCoords(e.target.value)}
              placeholder="53.231410, 50.166820"
            />
          </div>
        </div>
        <div className="de-mno-modal-foot">
          <button type="button" className="de-mno-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="de-mno-modal-submit" disabled={pending} onClick={submit}>
            {pending ? 'Добавление…' : 'Добавить МНО'}
          </button>
        </div>
      </div>
    </div>
  );
}
