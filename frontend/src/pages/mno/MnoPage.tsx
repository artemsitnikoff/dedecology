import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate } from '@/lib/format';
import { useMno, useMnoDetail, useMnoPoints } from '@/api/hooks/mno';
import type { MnoFilters, MnoSortKey, SortOrder } from '@/api/hooks/mno';
import { useRegionsDirectory } from '@/api/hooks/regions';
import { exportMno, useCreateMno, useSyncMno, useSyncMnoOne } from '@/api/mutations/mno';
import type { MnoCreate, MnoListItem, RegionListItem } from '@/api/aliases';
import { YandexMap } from '@/components/YandexMap';
import './Mno.css';

/** Размер страницы серверной пагинации реестра МНО (контракт GET /mno). */
const PAGE_SIZE = 100;

/**
 * Окно номеров страниц вокруг текущей. До 7 страниц — показываем все; иначе
 * первая · … · (тек-1, тек, тек+1) · … · последняя ('gap' = многоточие).
 */
function pageWindow(current: number, totalPages: number): Array<number | 'gap'> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const out: Array<number | 'gap'> = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(totalPages - 1, current + 1);
  if (start > 2) out.push('gap');
  for (let i = start; i <= end; i++) out.push(i);
  if (end < totalPages - 1) out.push('gap');
  out.push(totalPages);
  return out;
}

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
        {m.source === 'volunteer' ? (
          // МНО добавлено волонтёром на форме — помечаем, чтобы эколог проверил (source из контракта).
          <span className="de-mno-pill volunteer">
            <span className="de-mno-pill-dot" style={{ background: 'var(--ark-violet-500)' }} />
            Добавлен волонтёром
          </span>
        ) : (
          <span className={`de-mno-pill ${m.synced ? 'fgis' : 'manual'}`}>
            <span
              className="de-mno-pill-dot"
              style={{ background: m.synced ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
            />
            {m.synced ? 'ФГИС' : 'Вручную'}
          </span>
        )}
        <span className="de-mno-sync-date">{m.synced ? formatDate(m.sync_date) || '—' : '—'}</span>
      </div>
    </div>
  );
});

/* ============================================================
   Экран «МНО»
   ============================================================ */
export function MnoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<MnoSortKey>('name');
  const [sortDir, setSortDir] = useState<SortOrder>('asc');
  const [fRegion, setFRegion] = useState('');
  const [fSync, setFSync] = useState<Array<'fgis' | 'manual'>>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sub, setSub] = useState<'list' | 'map'>('list');
  // Видимая область карты «minLat,minLon,maxLat,maxLon» — задаётся картой (boundschange
  // + стартовый кадр). Догружаем точки текущего кадра; undefined до инициализации карты.
  const [mapBbox, setMapBbox] = useState<string | undefined>(undefined);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const { message, showToast } = useToast();

  // Текущая страница живёт в URL (?mpage=N) — шарится и переживает reload; 1 → без параметра.
  const page = Math.max(1, Number(searchParams.get('mpage')) || 1);
  const setPage = useCallback(
    (p: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (p <= 1) next.delete('mpage');
          else next.set('mpage', String(p));
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );
  // Любая смена фильтра/поиска/сортировки сбрасывает страницу на первую.
  const resetPage = useCallback(() => setPage(1), [setPage]);

  // Диплинк из карточки инцидента: /mno?open=<id> открывает drawer этого МНО при
  // загрузке. openParam входит в deps — переход по новой ссылке переоткрывает карточку.
  const openParam = searchParams.get('open');
  useEffect(() => {
    if (openParam) setDetailId(openParam);
  }, [openParam]);

  // Закрытие drawer: снимаем detailId и убираем ?open из URL (иначе эффект переоткроет).
  const closeDrawer = useCallback(() => {
    setDetailId(null);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('open');
        return next;
      },
      { replace: true }
    );
  }, [setSearchParams]);

  // Клик по счётчику обращений МНО → список инцидентов, отфильтрованный по этому объекту ТКО.
  const openIncidentsForMno = useCallback(
    (id: string) => navigate(`/incidents?mno_id=${id}`),
    [navigate]
  );

  // Серверная фильтрация/сортировка (как у incidents). synced: один чип → bool, оба/ни одного → all.
  const syncedFilter: boolean | undefined =
    fSync.length === 1 ? fSync[0] === 'fgis' : undefined;
  // Базовые фильтры (без пагинации) — для карты и экспорта (полный отфильтрованный набор).
  const baseFilters: MnoFilters = useMemo(
    () => ({
      search: query || undefined,
      region: fRegion || undefined,
      synced: syncedFilter,
      sort: sortKey,
      order: sortDir,
    }),
    [query, fRegion, syncedFilter, sortKey, sortDir]
  );
  // Фильтры списка = базовые + текущая страница.
  const listFilters: MnoFilters = useMemo(
    () => ({ ...baseFilters, page, page_size: PAGE_SIZE }),
    [baseFilters, page]
  );

  const listQuery = useMno(listFilters);
  const allQuery = useMno({}); // нефильтрованный итог (дедуп с Sidebar)
  // Точки карты — отдельный лёгкий запрос, только когда активен под-режим «Карта».
  const pointsQuery = useMnoPoints(
    { search: query || undefined, region: fRegion || undefined, synced: syncedFilter, bbox: mapBbox },
    { enabled: sub === 'map' }
  );
  const regionsQuery = useRegionsDirectory({});

  const syncMno = useSyncMno();
  const syncMnoOne = useSyncMnoOne();
  const createMno = useCreateMno();

  const rows = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const pages = listQuery.data?.pages ?? 0;
  const grandTotal = allQuery.data?.total ?? total;
  const regions = regionsQuery.data ?? [];

  const filterCount = (fRegion ? 1 : 0) + (fSync.length ? 1 : 0);
  const isFiltered = filterCount > 0 || !!query;
  const counterText = isFiltered
    ? `Показано ${total} из ${grandTotal}`
    : `${grandTotal} МНО · слой 5 ФГИС`;

  // Диапазон строк текущей страницы для подписи пагинатора («X–Y из N»).
  const rangeFrom = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeTo = Math.min(page * PAGE_SIZE, total);

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
  // «Выбрать всё» — по строкам ТЕКУЩЕЙ страницы (rows = items страницы).
  const toggleAll = () =>
    setSelected((prev) => (rows.length > 0 && rows.every((m) => prev.has(m.id)) ? new Set<string>() : new Set(rows.map((m) => m.id))));
  const toggleSync = (v: 'fgis' | 'manual') => {
    setFSync((prev) => (prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]));
    resetPage();
  };
  const resetFilters = () => {
    setFRegion('');
    setFSync([]);
    resetPage();
  };

  const onSort = (key: MnoSortKey) => {
    setSortDir((prev) => (sortKey === key && prev === 'asc' ? 'desc' : 'asc'));
    setSortKey(key);
    resetPage();
  };

  // Поиск/регион меняют выборку → страница на первую.
  const handleSearch = (v: string) => {
    setQuery(v);
    resetPage();
  };
  const handleRegion = (v: string) => {
    setFRegion(v);
    resetPage();
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
    // Экспорт = весь отфильтрованный реестр (без пагинации) — page/page_size не передаём.
    void exportMno(baseFilters);
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

  // Точки карты — из лёгкого /mno/points (id/coords/name), а НЕ из полного списка.
  const points = pointsQuery.data?.points ?? [];
  const pointsTotal = pointsQuery.data?.total ?? points.length;
  const pointsCapped = pointsQuery.data?.capped ?? false;
  // Мемо — чтобы YandexMap не пересобирал маркеры на каждый ре-рендер страницы.
  const mapPoints = useMemo(
    () => points.map((p) => ({ id: p.id, coords: p.coords, label: p.name })),
    [points],
  );

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
            onChange={(e) => handleSearch(e.target.value)}
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
          <select className="de-mno-select" value={fRegion} onChange={(e) => handleRegion(e.target.value)}>
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
        <>
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

        {/* Пагинатор (серверная пагинация по 100) */}
        {!listQuery.isLoading && !listQuery.isError && total > 0 && (
          <div className="de-mno-pager">
            <span className="de-mno-pager-info">
              Показано <span className="de-mno-mono">{rangeFrom}</span>–
              <span className="de-mno-mono">{rangeTo}</span> из{' '}
              <span className="de-mno-mono">{total}</span>
            </span>
            <div className="de-mno-spacer" />
            {pages > 1 && (
              <div className="de-mno-pager-controls">
                <button
                  type="button"
                  className="de-mno-pager-btn"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <Icon name="chevron-left" size={15} />
                  Назад
                </button>
                {pageWindow(page, pages).map((p, i) =>
                  p === 'gap' ? (
                    <span key={`gap-${i}`} className="de-mno-pager-gap">
                      …
                    </span>
                  ) : (
                    <button
                      key={p}
                      type="button"
                      className={`de-mno-pager-num de-mno-mono ${p === page ? 'active' : ''}`}
                      onClick={() => setPage(p)}
                    >
                      {p}
                    </button>
                  )
                )}
                <button
                  type="button"
                  className="de-mno-pager-btn"
                  disabled={page >= pages}
                  onClick={() => setPage(page + 1)}
                >
                  Вперёд
                  <Icon name="chevron-right" size={15} />
                </button>
              </div>
            )}
          </div>
        )}
        </>
      )}

      {/* Контент: карта (настоящая Яндекс.Карта с кластеризацией) */}
      {sub === 'map' && (
        <div className="de-mno-map-area">
          {/* Карта смонтирована ВСЕГДА — загрузку показываем подписью-оверлеем, НЕ заменой
              (иначе refetch по bbox размонтировал бы карту и сбрасывал вид → цикл). */}
          <div className="de-mno-map-wrap">
            <YandexMap
              className="de-mno-ymap"
              points={mapPoints}
              onBoundsChange={([a, b, c, d]) => setMapBbox(`${a},${b},${c},${d}`)}
            />
            <div className="de-mno-map-cap">
              {pointsQuery.isError
                ? 'не удалось загрузить точки'
                : pointsQuery.isFetching
                  ? 'обновление точек…'
                  : pointsCapped
                    ? `показано ${points.length} из ${pointsTotal} в этой области`
                    : `${points.length} точек`}
            </div>
          </div>
        </div>
      )}

      {detailId && (
        <MnoDrawer
          id={detailId}
          onClose={closeDrawer}
          onSyncOne={handleSyncOne}
          syncOnePending={syncMnoOne.isPending}
          onOpenIncidents={openIncidentsForMno}
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
  /** Клик по счётчику обращений → список инцидентов этого МНО (/incidents?mno_id=id). */
  onOpenIncidents: (id: string) => void;
};
function MnoDrawer({ id, onClose, onSyncOne, syncOnePending, onOpenIncidents }: DrawerProps) {
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
                {data.source === 'volunteer' ? (
                  // Добавлено волонтёром на публичной форме — бейдж-сигнал для проверки экологом.
                  <span className="de-mno-pill volunteer">
                    <span className="de-mno-pill-dot" style={{ background: 'var(--ark-violet-500)' }} />
                    Добавлен волонтёром
                  </span>
                ) : (
                  <span className={`de-mno-pill ${data.synced ? 'fgis' : 'manual'}`}>
                    <span
                      className="de-mno-pill-dot"
                      style={{ background: data.synced ? 'var(--ark-green-500)' : 'var(--ark-gray-500)' }}
                    />
                    {data.synced ? 'Синхронизировано с ФГИС' : 'Добавлено вручную'}
                  </span>
                )}
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
                  [
                    'Синхронизация',
                    data.source === 'volunteer'
                      ? 'Добавлено волонтёром'
                      : data.synced
                        ? `ФГИС, ${formatDate(data.sync_date) || '—'}`
                        : 'Добавлено вручную',
                  ],
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
                <button
                  type="button"
                  className="de-mno-inc-badge de-mno-inc-badge-link"
                  onClick={() => onOpenIncidents(data.id)}
                  title="Показать обращения по этому объекту ТКО"
                >
                  <Icon name="alert-circle" size={15} />
                  Обращений по МНО: {data.incidents}
                </button>
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
