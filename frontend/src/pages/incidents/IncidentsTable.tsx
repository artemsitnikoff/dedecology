import { memo } from 'react';
import { Icon } from '@/components/ui/Icon';
import { STATUS, SOURCE } from '@/lib/status';
import { formatDate, formatTime, fullAddr, maxLink } from '@/lib/format';
import type { IncidentListItem } from '@/api/aliases';
import type { SortKey, SortOrder } from '@/api/hooks/useIncidents';

/** Описание колонки заголовка. */
type Head = {
  key: SortKey | 'photo' | 'coords' | 'link';
  label: string;
  /** Класс ячейки заголовка (ширина/flex задаётся в CSS на парных cell-классах). */
  thClass: string;
  /** Не сортируется (Фото, Координаты, Чат). */
  nosort?: boolean;
};

/** 10 колонок в ТОЧНОМ порядке (BUILD-SPEC §7). */
const HEADS: Head[] = [
  { key: 'photo', label: 'Фото', thClass: 'de-inc-cell-photo', nosort: true },
  { key: 'date', label: 'Дата', thClass: 'de-inc-cell-date' },
  { key: 'time', label: 'Время', thClass: 'de-inc-cell-time' },
  { key: 'region', label: 'Регион', thClass: 'de-inc-cell-region' },
  { key: 'city', label: 'Город', thClass: 'de-inc-cell-city' },
  { key: 'address', label: 'Адрес', thClass: 'de-inc-cell-address' },
  { key: 'coords', label: 'Координаты', thClass: 'de-inc-cell-coords', nosort: true },
  { key: 'status', label: 'Статус', thClass: 'de-inc-cell-status' },
  { key: 'source', label: 'Источник', thClass: 'de-inc-cell-source' },
  { key: 'link', label: 'Чат', thClass: 'de-inc-cell-chat', nosort: true },
];

function CheckMark() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--ark-white)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12l5 5 9-11" />
    </svg>
  );
}

function SortArrows({ on, order }: { on: boolean; order: SortOrder }) {
  return (
    <span className="de-inc-sortarr">
      <span className={on && order === 'asc' ? 'lit' : ''}>▲</span>
      <span className={on && order === 'desc' ? 'lit' : ''}>▼</span>
    </span>
  );
}

type RowProps = {
  d: IncidentListItem;
  selected: boolean;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
  onPhoto: (id: string) => void;
};

/** Строка таблицы — мемоизирована, чтобы не перерисовывать весь список при выделении одной. */
const IncidentRow = memo(function IncidentRow({ d, selected, onToggle, onOpen, onPhoto }: RowProps) {
  const statusMeta = STATUS[d.status];
  const sourceMeta = SOURCE[d.source];
  const thumb = d.photo_urls[0];
  const link = maxLink(d.msg);

  return (
    <div
      className={`de-inc-row ${selected ? 'selected' : ''}`}
      onClick={() => onOpen(d.id)}
    >
      <div className="de-inc-row-checkbox">
        <div
          className={`de-inc-check ${selected ? 'checked' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(d.id);
          }}
        >
          {selected && <CheckMark />}
        </div>
      </div>

      <div className="de-inc-cell de-inc-cell-photo">
        <div
          className="de-inc-thumb"
          onClick={(e) => {
            e.stopPropagation();
            onPhoto(d.id);
          }}
        >
          {thumb && (
            <div className="de-inc-thumb-img" style={{ backgroundImage: `url("${thumb}")` }} />
          )}
          {d.photos > 1 && <span className="de-inc-thumb-badge de-inc-mono">{d.photos}</span>}
        </div>
      </div>

      <div className="de-inc-cell de-inc-cell-date">{formatDate(d.photo_time)}</div>
      <div className="de-inc-cell de-inc-cell-time de-inc-mono">{formatTime(d.photo_time)}</div>
      <div className="de-inc-cell de-inc-cell-region" title={d.region}>
        {d.region}
      </div>
      <div className="de-inc-cell de-inc-cell-city" title={d.city}>
        {d.city}
      </div>
      <div className="de-inc-cell-address" title={fullAddr(d)}>
        {d.street}
      </div>
      <div className="de-inc-cell de-inc-cell-coords de-inc-mono">{d.coords}</div>
      <div className="de-inc-cell de-inc-cell-status">
        <span
          className="de-inc-pill"
          style={{ background: statusMeta.bg, color: statusMeta.fg }}
        >
          <span className="de-inc-pill-dot" style={{ background: statusMeta.dot }} />
          {statusMeta.label}
        </span>
      </div>
      <div className="de-inc-cell de-inc-cell-source">
        <span className="de-inc-pill" style={{ background: sourceMeta.bg, color: sourceMeta.fg }}>
          {sourceMeta.label}
        </span>
      </div>
      <div className="de-inc-cell de-inc-cell-chat">
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="de-inc-chat-link"
            onClick={(e) => e.stopPropagation()}
          >
            <Icon name="external-link" size={13} />
            Макс
          </a>
        )}
      </div>
    </div>
  );
});

type Props = {
  rows: IncidentListItem[];
  selected: Set<string>;
  sort: SortKey;
  order: SortOrder;
  allSelected: boolean;
  onSort: (key: SortKey) => void;
  onToggleAll: () => void;
  onToggleSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onPhoto: (id: string) => void;
};

/**
 * Таблица инцидентов. 10 колонок в фиксированном порядке + чекбокс-колонка.
 * Клик по заголовку сортирует (первый клик — desc, повтор — asc), активная
 * колонка подсвечивается акцентом с индикатором ▲/▼. Несортируемые: Фото,
 * Координаты, Чат. Клик по строке открывает drawer.
 */
export function IncidentsTable({
  rows,
  selected,
  sort,
  order,
  allSelected,
  onSort,
  onToggleAll,
  onToggleSelect,
  onOpen,
  onPhoto,
}: Props) {
  return (
    <div className="de-inc-table">
      <div className="de-inc-thead">
        <div className="de-inc-th-checkbox">
          <div
            className={`de-inc-check ${allSelected ? 'checked' : ''}`}
            onClick={onToggleAll}
          >
            {allSelected && <CheckMark />}
          </div>
        </div>
        {HEADS.map((h) => {
          const on = !h.nosort && sort === h.key;
          return (
            <div
              key={h.key}
              className={`de-inc-th ${h.thClass} ${h.nosort ? '' : 'sortable'} ${on ? 'on' : ''}`}
              onClick={h.nosort ? undefined : () => onSort(h.key as SortKey)}
            >
              {h.label}
              {!h.nosort && <SortArrows on={on} order={order} />}
            </div>
          );
        })}
      </div>
      {rows.map((d) => (
        <IncidentRow
          key={d.id}
          d={d}
          selected={selected.has(d.id)}
          onToggle={onToggleSelect}
          onOpen={onOpen}
          onPhoto={onPhoto}
        />
      ))}
    </div>
  );
}
