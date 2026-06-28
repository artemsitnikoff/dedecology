import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { useIncidents } from '@/api/hooks/useIncidents';
import type { IncidentFilters, SortKey, SortOrder } from '@/api/hooks/useIncidents';
import { useFunnelCounts } from '@/api/hooks/useFunnelCounts';
import { useRegions } from '@/api/hooks/useRegions';
import { exportAll, exportSelected, useBulkStatus, useBulkDelete } from '@/api/mutations/incidents';
import type { Source, Status } from '@/api/aliases';
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
  return values.filter((v): v is Source => v === 'max' || v === 'form');
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
      status: status ?? undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      sort,
      order,
    }),
    [search, sources, region, status, dateFrom, dateTo, sort, order]
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
      p.delete('status');
      p.delete('date_from');
      p.delete('date_to');
    });
  }, [patchParams]);

  // ----- Данные -----
  const incidentsQuery = useIncidents(filters);
  const funnelQuery = useFunnelCounts(filters);
  const regionsQuery = useRegions();
  // Нефильтрованный общий итог («из N») — те же пустые фильтры, что и в Sidebar
  // (один queryKey → дедуп). all = grand total по всем обращениям.
  const grandTotalQuery = useFunnelCounts({});
  const bulkStatus = useBulkStatus();
  const bulkDelete = useBulkDelete();

  const rows = incidentsQuery.data?.items ?? [];
  const total = incidentsQuery.data?.total ?? 0;

  // ----- Локальный UI-стейт -----
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  // Координаты выезда карточки — считаются из скролл-контейнера таблицы при открытии.
  const [detailPos, setDetailPos] = useState<{ top: number; left: number }>({ top: 170, left: 0 });
  // Подсветка кликнутой строки (пульс-сердце) на короткое время.
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [lb, setLb] = useState<{ id: string; idx: number } | null>(null);

  /** Скролл-контейнер таблицы — от его геометрии считаем top/left карточки. */
  const scrollRef = useRef<HTMLDivElement>(null);
  /** Таймер сброса пульса (чистим при повторном открытии/размонтировании). */
  const pulseTimer = useRef<number | null>(null);

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
   * ширина видимых левых колонок), запускаем drawer и короткий пульс кликнутой строки.
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
    setPulseId(id);
    if (pulseTimer.current != null) window.clearTimeout(pulseTimer.current);
    pulseTimer.current = window.setTimeout(() => {
      setPulseId((p) => (p === id ? null : p));
    }, 850);
  }, []);

  // Чистим таймер пульса при размонтировании страницы.
  useEffect(() => {
    return () => {
      if (pulseTimer.current != null) window.clearTimeout(pulseTimer.current);
    };
  }, []);

  const openPhoto = useCallback((id: string) => setLb({ id, idx: 0 }), []);
  const openPhotoAt = useCallback((id: string, idx: number) => setLb({ id, idx }), []);

  // ----- Производные -----
  const filterCount =
    (sources.length ? 1 : 0) +
    (region ? 1 : 0) +
    (status ? 1 : 0) +
    (dateFrom || dateTo ? 1 : 0);
  const hasFilters = filterCount > 0;
  const isFiltered = hasFilters || !!search;

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

  const handleExportAll = useCallback(() => {
    void exportAll(filters);
  }, [filters]);

  const handleExportSelected = useCallback(() => {
    void exportSelected(Array.from(selectedRef.current));
  }, []);

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
          onClick={handleExportAll}
          disabled={total === 0}
        >
          <Icon name="download" size={15} />
          Выгрузить всё
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
        <span className="de-inc-hint">Сортировка — по клику на заголовок столбца</span>
      </div>

      <Funnel status={status} counts={funnelQuery.data} onSelect={setStatusParam} />

      <FilterBar
        sources={sources}
        onToggleSource={toggleSource}
        region={region}
        regions={regionsQuery.data ?? []}
        onRegion={setRegionParam}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        hasFilters={hasFilters}
        onReset={resetFilters}
      />

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
                onClick={handleExportSelected}
              >
                <Icon name="download" size={14} />
                Выгрузить в Excel
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

      {/* Контент */}
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
            pulseId={pulseId}
            onSort={handleSort}
            onToggleAll={toggleAll}
            onToggleSelect={toggleSelect}
            onOpen={openDetail}
            onPhoto={openPhoto}
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
    </div>
  );
}
