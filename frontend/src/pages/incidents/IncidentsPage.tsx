import { useCallback, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { useIncidents } from '@/api/hooks/useIncidents';
import type { IncidentFilters, SortKey, SortOrder } from '@/api/hooks/useIncidents';
import { useIncidentPoints } from '@/api/hooks/useIncidentPoints';
import { useFunnelCounts } from '@/api/hooks/useFunnelCounts';
import { useRegions } from '@/api/hooks/useRegions';
import { useIncidentTypes } from '@/api/hooks/useIncidentTypes';
import { useBulkStatus, useBulkDelete } from '@/api/mutations/incidents';
import { useCreateIncidentsReport } from '@/api/mutations/reports';
import type { CreateIncidentsReportBody } from '@/api/mutations/reports';
import type { ApiError, Source, Status } from '@/api/aliases';
import { YandexMap } from '@/components/YandexMap';
import { Funnel } from './Funnel';
import { FilterBar } from './FilterBar';
import { IncidentsTable } from './IncidentsTable';
import { DetailDrawer } from './DetailDrawer';
import { Lightbox } from './Lightbox';
import './Incidents.css';

/** Допустимые ключи сортировки — для валидации значения из URL. */
const SORT_KEYS: SortKey[] = ['date', 'time', 'region', 'city', 'address', 'status', 'source'];

/**
 * Сдвиг левого края карточки внутри области таблицы: ширина ЗАМОРОЖЕННОГО левого
 * блока, который остаётся видимым при открытом drawer — чекбокс-колонка (46) +
 * единый блок «фото · дата · время · ID» (248) = ровно 294px. Карточка стартует
 * с колонки «Регион», ровно по правому краю замороженного блока (его тени).
 */
const DRAWER_LEFT_INSET = 46 + 248;

function parseSort(value: string | null): SortKey {
  return value && (SORT_KEYS as string[]).includes(value) ? (value as SortKey) : 'date';
}
function parseOrder(value: string | null): SortOrder {
  return value === 'asc' ? 'asc' : 'desc';
}
function parseStatus(value: string | null): Status | null {
  return value === 'new' || value === 'found' || value === 'none' || value === 'exported'
    ? value
    : null;
}
function parseSources(values: string[]): Source[] {
  return values.filter((v): v is Source => v === 'max' || v === 'form' || v === 'app');
}

/**
 * Экран «Инциденты» — оркестратор.
 * Фильтры/сортировка живут в URL (useSearchParams) → шарятся и переживают reload.
 * Выделение — локальный Set<string>; drawer и lightbox — локальный стейт.
 */
export function IncidentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Реконструируем типизированный объект фильтров из URL на каждый рендер.
  const search = searchParams.get('search') ?? '';
  const sources = parseSources(searchParams.getAll('source'));
  const region = searchParams.get('region') ?? '';
  const incidentType = searchParams.get('incident_type') ?? '';
  // Диплинк из карточки МНО: /incidents?mno_id=<id> — показать обращения одного объекта ТКО.
  const mnoId = searchParams.get('mno_id') ?? '';
  const status = parseStatus(searchParams.get('status'));
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const sort = parseSort(searchParams.get('sort'));
  const order = parseOrder(searchParams.get('order'));

  const filters: IncidentFilters = useMemo(
    () => ({
      search: search || undefined,
      source: sources.length ? sources : undefined,
      region: region || undefined,
      incident_type: incidentType || undefined,
      mno_id: mnoId || undefined,
      status: status ?? undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      sort,
      order,
    }),
    [search, sources, region, incidentType, mnoId, status, dateFrom, dateTo, sort, order]
  );

  // Стабильная ссылка на searchParams для use в колбэках без пересоздания.
  const spRef = useRef(searchParams);
  spRef.current = searchParams;

  /** Точечно правит один query-параметр (set/append/delete) и пишет в URL. */
  const patchParams = useCallback(
    (mutate: (p: URLSearchParams) => void) => {
      const next = new URLSearchParams(spRef.current);
      mutate(next);
      setSearchParams(next, { replace: true });
    },
    [setSearchParams]
  );

  const setSearch = useCallback(
    (v: string) => {
      patchParams((p) => {
        if (v.trim()) p.set('search', v);
        else p.delete('search');
      });
    },
    [patchParams]
  );

  const toggleSource = useCallback(
    (src: Source) => {
      patchParams((p) => {
        const current = p.getAll('source');
        p.delete('source');
        const nextSet = current.includes(src)
          ? current.filter((s) => s !== src)
          : [...current, src];
        for (const s of nextSet) p.append('source', s);
      });
    },
    [patchParams]
  );

  const setRegionParam = useCallback(
    (v: string) => {
      patchParams((p) => {
        if (v) p.set('region', v);
        else p.delete('region');
      });
    },
    [patchParams]
  );

  const setIncidentTypeParam = useCallback(
    (v: string) => {
      patchParams((p) => {
        if (v) p.set('incident_type', v);
        else p.delete('incident_type');
        p.delete('page'); // смена фильтра → на первую страницу
      });
    },
    [patchParams]
  );

  const setStatusParam = useCallback(
    (s: Status | null) => {
      patchParams((p) => {
        if (s) p.set('status', s);
        else p.delete('status');
      });
    },
    [patchParams]
  );

  const setDateFrom = useCallback(
    (v: string) => {
      patchParams((p) => {
        if (v) p.set('date_from', v);
        else p.delete('date_from');
      });
    },
    [patchParams]
  );
  const setDateTo = useCallback(
    (v: string) => {
      patchParams((p) => {
        if (v) p.set('date_to', v);
        else p.delete('date_to');
      });
    },
    [patchParams]
  );

  const handleSort = useCallback(
    (key: SortKey) => {
      patchParams((p) => {
        const curSort = parseSort(p.get('sort'));
        const curOrder = parseOrder(p.get('order'));
        const nextOrder: SortOrder =
          curSort === key ? (curOrder === 'desc' ? 'asc' : 'desc') : 'desc';
        p.set('sort', key);
        p.set('order', nextOrder);
      });
    },
    [patchParams]
  );

  const resetFilters = useCallback(() => {
    patchParams((p) => {
      p.delete('source');
      p.delete('region');
      p.delete('incident_type');
      p.delete('status');
      p.delete('date_from');
      p.delete('date_to');
    });
  }, [patchParams]);

  /** Снять привязку к объекту ТКО (баннер) — убрать mno_id из URL, страница на 1. */
  const clearMnoFilter = useCallback(() => {
    patchParams((p) => {
      p.delete('mno_id');
      p.delete('page');
    });
  }, [patchParams]);

  // ----- Данные -----
  const incidentsQuery = useIncidents(filters);
  const funnelQuery = useFunnelCounts(filters);
  const regionsQuery = useRegions();
  const incidentTypesQuery = useIncidentTypes();
  // Карта код→подпись типа инцидента для колонки «Тип» в таблице (стабильная ссылка —
  // чтобы memo строк не сбрасывался). Инцидент хранит код, подпись резолвим из справочника.
  const typeLabels = useMemo(() => {
    const m: Record<string, string> = {};
    for (const t of incidentTypesQuery.data ?? []) m[t.code] = t.label;
    return m;
  }, [incidentTypesQuery.data]);
  // Нефильтрованный общий итог («из N») — те же пустые фильтры, что и в Sidebar
  // (один queryKey → дедуп). all = grand total по всем обращениям.
  const grandTotalQuery = useFunnelCounts({});
  const bulkStatus = useBulkStatus();
  const bulkDelete = useBulkDelete();
  const createReport = useCreateIncidentsReport();
  const { message, showToast } = useToast();

  const rows = incidentsQuery.data?.items ?? [];
  const total = incidentsQuery.data?.total ?? 0;

  // ----- Локальный UI-стейт -----
  // Режим отображения: список (таблица) или настоящая Яндекс.Карта. Фильтры общие (из URL).
  const [view, setView] = useState<'list' | 'map'>('list');
  // Видимая область карты «minLat,minLon,maxLat,maxLon» — задаётся картой (boundschange
  // + стартовый кадр). Догружаем точки текущего кадра; undefined до инициализации карты.
  const [mapBbox, setMapBbox] = useState<string | undefined>(undefined);
  // Точки карты — отдельный лёгкий запрос /incidents/points, только в режиме «Карта».
  const pointsQuery = useIncidentPoints({ ...filters, bbox: mapBbox }, { enabled: view === 'map' });
  const points = pointsQuery.data?.points ?? [];
  const pointsTotal = pointsQuery.data?.total ?? points.length;
  const pointsCapped = pointsQuery.data?.capped ?? false;
  // Мемо — чтобы YandexMap не пересобирал маркеры на каждый ре-рендер страницы.
  const mapPoints = useMemo(
    () => points.map((p) => ({ id: p.id, coords: p.coords, label: p.address || p.status })),
    [points],
  );

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  // Координаты выезда карточки — считаются из скролл-контейнера таблицы при открытии.
  const [detailPos, setDetailPos] = useState<{ top: number; left: number }>({ top: 170, left: 0 });
  const [lb, setLb] = useState<{ id: string; idx: number } | null>(null);

  /** Скролл-контейнер таблицы — от его геометрии считаем top/left карточки. */
  const scrollRef = useRef<HTMLDivElement>(null);

  // Стабильная ссылка на выделение для колбэков (сохраняет React.memo строк).
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const toggleSelect = useCallback((id: string) => {
    setConfirmingDelete(false);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const toggleAll = useCallback(() => {
    setConfirmingDelete(false);
    setSelected((prev) => {
      const everySelected = rows.length > 0 && rows.every((r) => prev.has(r.id));
      return everySelected ? new Set<string>() : new Set(rows.map((r) => r.id));
    });
  }, [rows]);

  /** Снять всё выделение и сбросить состояние подтверждения удаления. */
  const clearSelection = useCallback(() => {
    setSelected(new Set());
    setConfirmingDelete(false);
  }, []);

  /**
   * Открыть карточку: считаем top (верх скролл-контейнера) и left (его левый край +
   * ширина видимых левых колонок) и запускаем drawer.
   */
  const openDetail = useCallback((id: string) => {
    const el = scrollRef.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      setDetailPos({
        top: Math.round(rect.top),
        left: Math.round(rect.left + DRAWER_LEFT_INSET),
      });
    }
    setDetailId(id);
  }, []);

  const openPhoto = useCallback((id: string) => setLb({ id, idx: 0 }), []);
  const openPhotoAt = useCallback((id: string, idx: number) => setLb({ id, idx }), []);

  // ----- Производные -----
  const filterCount =
    (sources.length ? 1 : 0) +
    (region ? 1 : 0) +
    (incidentType ? 1 : 0) +
    (status ? 1 : 0) +
    (dateFrom || dateTo ? 1 : 0);
  const hasFilters = filterCount > 0;
  const isFiltered = hasFilters || !!search || !!mnoId;

  const grandTotal = grandTotalQuery.data?.all ?? total;
  const counterText = isFiltered
    ? `Показано ${total} из ${grandTotal}`
    : `${grandTotal} обращений · обновлено сегодня`;

  // Карточка тянет деталь сама (useIncident по detailId). Лайтбокс берёт фото
  // из строки списка — он всегда открывается для видимой строки.
  const lbInc = lb ? rows.find((r) => r.id === lb.id) : undefined;

  const lbStep = useCallback(
    (delta: number) => {
      setLb((prev) => {
        if (!prev) return prev;
        const inc = rows.find((r) => r.id === prev.id);
        const n = inc?.photo_urls.length || 1;
        return { id: prev.id, idx: (prev.idx + delta + n) % n };
      });
    },
    [rows]
  );

  /** Достаёт человекочитаемое сообщение из конверта ошибки бэка, иначе — fallback. */
  const reportErrorMessage = useCallback((err: unknown, fallback: string): string => {
    const message = (err as Partial<ApiError>)?.error?.message;
    return message || fallback;
  }, []);

  const handleCreateReport = useCallback(() => {
    // Отчёт по текущему отфильтрованному набору (без ids — контракт /reports/incidents
    // трактует пустой ids как «по фильтрам»). incident_type/mno_id вне контракта отчёта.
    const body: CreateIncidentsReportBody = {
      search: filters.search,
      source: filters.source,
      status: filters.status ? [filters.status] : undefined,
      region: filters.region,
      date_from: filters.date_from,
      date_to: filters.date_to,
      sort: filters.sort,
      order: filters.order,
    };
    createReport.mutate(body, {
      onSuccess: () => showToast('Отчёт сформирован — доступен в разделе «Отчёты».'),
      onError: (err) => showToast(reportErrorMessage(err, 'Не удалось сформировать отчёт.')),
    });
  }, [createReport, filters, reportErrorMessage, showToast]);

  const handleCreateReportSelected = useCallback(() => {
    const ids = Array.from(selectedRef.current);
    if (ids.length === 0) return;
    createReport.mutate(
      { ids },
      {
        onSuccess: () => {
          showToast('Отчёт сформирован — доступен в разделе «Отчёты».');
          clearSelection();
        },
        onError: (err) => showToast(reportErrorMessage(err, 'Не удалось сформировать отчёт.')),
      }
    );
  }, [createReport, clearSelection, reportErrorMessage, showToast]);

  const handleMarkExported = useCallback(() => {
    const ids = Array.from(selectedRef.current);
    if (ids.length === 0) return;
    bulkStatus.mutate(
      { ids, status: 'exported' },
      { onSuccess: () => clearSelection() }
    );
  }, [bulkStatus, clearSelection]);

  /** Подтверждённое удаление: после успеха чистим выделение и закрываем drawer/lightbox удалённых. */
  const handleConfirmDelete = useCallback(() => {
    const ids = Array.from(selectedRef.current);
    if (ids.length === 0) return;
    bulkDelete.mutate(ids, {
      onSuccess: () => {
        const deletedSet = new Set(ids);
        setDetailId((cur) => (cur && deletedSet.has(cur) ? null : cur));
        setLb((cur) => (cur && deletedSet.has(cur.id) ? null : cur));
        clearSelection();
      },
    });
  }, [bulkDelete, clearSelection]);

  return (
    <div className="de-inc-wrap">
      {/* Шапка */}
      <div className="de-inc-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-inc-title">Инциденты</h1>
          <div className="de-inc-subtitle">{counterText}</div>
        </div>
        <div className="de-inc-spacer" />
        <button
          type="button"
          className="de-inc-btn de-inc-btn-outline"
          onClick={handleCreateReport}
          disabled={total === 0 || createReport.isPending}
        >
          <Icon name="download" size={15} />
          {createReport.isPending ? 'Формирование…' : 'Сформировать отчёт'}
        </button>
      </div>

      {/* Поиск */}
      <div className="de-inc-search-row">
        <div className="de-inc-search-box">
          <Icon name="search" size={15} color="var(--fg-3)" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по адресу, заявителю, координатам…"
          />
        </div>
        <div className="de-inc-spacer" />
        {view === 'list' && (
          <span className="de-inc-hint">Сортировка — по клику на заголовок столбца</span>
        )}
        <div className="de-inc-seg">
          <button
            type="button"
            className={`de-inc-seg-btn ${view === 'list' ? 'active' : ''}`}
            onClick={() => setView('list')}
          >
            <Icon name="list" size={15} />
            Список
          </button>
          <button
            type="button"
            className={`de-inc-seg-btn ${view === 'map' ? 'active' : ''}`}
            onClick={() => setView('map')}
          >
            <Icon name="map" size={15} />
            Карта
          </button>
        </div>
      </div>

      <Funnel status={status} counts={funnelQuery.data} onSelect={setStatusParam} />

      <FilterBar
        sources={sources}
        onToggleSource={toggleSource}
        region={region}
        regions={regionsQuery.data ?? []}
        onRegion={setRegionParam}
        incidentType={incidentType}
        incidentTypes={incidentTypesQuery.data ?? []}
        onIncidentType={setIncidentTypeParam}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        hasFilters={hasFilters}
        onReset={resetFilters}
      />

      {/* Баннер привязки к объекту ТКО: показываем только обращения выбранного МНО */}
      {mnoId && (
        <div className="de-inc-mno-banner">
          <Icon name="pin" size={15} color="var(--de-brand)" />
          <span className="de-inc-mno-banner-txt">Обращения по объекту ТКО</span>
          <button type="button" className="de-inc-mno-banner-reset" onClick={clearMnoFilter}>
            <Icon name="x" size={13} />
            Сбросить
          </button>
        </div>
      )}

      {/* Панель массовых действий */}
      {selected.size > 0 && (
        <div className="de-inc-bulkbar">
          <span className="de-inc-bulk-count">Выбрано: {selected.size}</span>
          <div className="de-inc-bulk-sep" />
          {confirmingDelete ? (
            <>
              <span className="de-inc-bulk-confirm">
                Удалить {selected.size}{' '}
                {selected.size === 1 ? 'обращение' : 'обращений'}? Действие необратимо.
              </span>
              <div className="de-inc-spacer" />
              <button
                type="button"
                className="de-inc-btn de-inc-btn-danger"
                onClick={handleConfirmDelete}
                disabled={bulkDelete.isPending}
              >
                {bulkDelete.isPending ? 'Удаление…' : 'Да, удалить'}
              </button>
              <button
                type="button"
                className="de-inc-btn de-inc-btn-ghost"
                onClick={() => setConfirmingDelete(false)}
                disabled={bulkDelete.isPending}
              >
                Отмена
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="de-inc-btn de-inc-btn-success"
                onClick={handleCreateReportSelected}
                disabled={createReport.isPending}
              >
                <Icon name="download" size={14} />
                {createReport.isPending ? 'Формирование…' : 'Сформировать отчёт'}
              </button>
              <button
                type="button"
                className="de-inc-btn de-inc-btn-bulk-outline"
                onClick={handleMarkExported}
                disabled={bulkStatus.isPending}
              >
                Пометить «Выгружен»
              </button>
              <button
                type="button"
                className="de-inc-btn de-inc-btn-danger-outline"
                onClick={() => setConfirmingDelete(true)}
              >
                <Icon name="trash" size={14} />
                Удалить
              </button>
              <div className="de-inc-spacer" />
              <button
                type="button"
                className="de-inc-btn de-inc-btn-ghost"
                onClick={clearSelection}
              >
                Снять выделение
              </button>
            </>
          )}
        </div>
      )}

      {/* Контент: список (таблица) */}
      {view === 'list' && (
        <div className="de-inc-content" ref={scrollRef}>
          {incidentsQuery.isLoading ? (
            <div className="de-inc-state">Загрузка…</div>
          ) : incidentsQuery.isError ? (
            <div className="de-inc-state error">Не удалось загрузить инциденты.</div>
          ) : rows.length > 0 ? (
            <IncidentsTable
              rows={rows}
              selected={selected}
              sort={sort}
              order={order}
              allSelected={allSelected}
              onSort={handleSort}
              onToggleAll={toggleAll}
              onToggleSelect={toggleSelect}
              onOpen={openDetail}
              onPhoto={openPhoto}
              typeLabels={typeLabels}
            />
          ) : (
            <div className="de-inc-empty">
              <div className="de-inc-empty-mark">💚</div>
              <h3>Ничего не найдено</h3>
              <p>Под заданные фильтры обращений нет. Попробуйте сбросить фильтры.</p>
              {hasFilters && (
                <button type="button" className="de-inc-empty-btn" onClick={resetFilters}>
                  Сбросить фильтры
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Контент: карта (настоящая Яндекс.Карта с кластеризацией) */}
      {view === 'map' && (
        <div className="de-inc-map-area">
          {/* Карта смонтирована ВСЕГДА — загрузку показываем подписью, НЕ заменой (иначе
              refetch по bbox размонтировал бы карту и сбрасывал вид → цикл). */}
          <div className="de-inc-map-wrap">
            <YandexMap
              className="de-inc-ymap"
              points={mapPoints}
              onBoundsChange={([a, b, c, d]) => setMapBbox(`${a},${b},${c},${d}`)}
            />
            <div className="de-inc-map-cap">
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
        <DetailDrawer
          id={detailId}
          top={detailPos.top}
          left={detailPos.left}
          onClose={() => setDetailId(null)}
          onPhoto={openPhotoAt}
        />
      )}
      {lbInc && lb && (
        <Lightbox
          incident={lbInc}
          idx={lb.idx}
          onClose={() => setLb(null)}
          onPrev={() => lbStep(-1)}
          onNext={() => lbStep(1)}
        />
      )}

      <Toast message={message} />
    </div>
  );
}
