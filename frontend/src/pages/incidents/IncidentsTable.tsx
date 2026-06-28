import { memo } from 'react';
import { Icon } from '@/components/ui/Icon';
import { STATUS, SOURCE } from '@/lib/status';
import { formatDate, formatTime, fullAddr, maxLink } from '@/lib/format';
import { thumbUrl } from '@/lib/photo';
import type { IncidentListItem } from '@/api/aliases';
import type { SortKey, SortOrder } from '@/api/hooks/useIncidents';

/** Описание колонки заголовка. */
type Head = {
  key: SortKey | 'coords' | 'link';
  label: string;
  /** Класс ячейки заголовка (ширина/flex задаётся в CSS на парных cell-классах). */
  thClass: string;
  /** Не сортируется (Координаты, Чат). */
  nosort?: boolean;
};

/**
 * Колонки после замороженного блока, в ТОЧНОМ порядке (BUILD-SPEC §7).
 * Первый «столбец» — единый замороженный блок (фото · дата · время · ID), он
 * рендерится отдельно и сортируется по ключу `date`. Здесь — остальные 7.
 */
const HEADS: Head[] = [
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
  // Превью в строке — уменьшенная версия (thumb) для быстрой загрузки списка.
  const thumb = d.photo_urls[0] ? thumbUrl(d.photo_urls[0]) : undefined;
  const link = maxLink(d.msg_url);
  // Короткий ID-чип (моно, uppercase); полный uuid — в title.
  const shortId = d.id.slice(0, 8).toUpperCase();

  return (
    <div
      className={`de-inc-row ${selected ? 'selected' : ''}`}
      onClick={() => onOpen(d.id)}
    >
      {/* Чекбокс — заморожен слева (left:0). */}
      <div className="de-inc-frozen de-inc-frozen-check">
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

      {/* Единый замороженный блок: фото · [дата+время] · [ID] (left:46, тень справа). */}
      <div className="de-inc-frozen de-inc-frozen-main">
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
        <div className="de-inc-frozen-text">
          <span className="de-inc-frozen-line1">
            <span className="de-inc-frozen-date">{formatDate(d.photo_time)}</span>
            <span className="de-inc-frozen-time de-inc-mono">{formatTime(d.photo_time)}</span>
          </span>
          <span className="de-inc-frozen-line2">
            <span className="de-inc-frozen-id de-inc-mono" title={d.id}>
              {shortId}
            </span>
          </span>
        </div>
      </div>

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
 * Таблица инцидентов с ЗАМОРОЖЕННЫМ левым блоком.
 *
 * Слева приклеены (sticky) две зоны: чекбокс-колонка (46px, left:0) и единый блок
 * «фото · дата · время · ID» (248px, left:46) с тенью справа — суммарно ровно 294px
 * (совпадает с DRAWER_LEFT_INSET карточки). Остальные 7 колонок (Регион · Город ·
 * Адрес · Координаты · Статус · Источник · Чат) скроллятся горизонтально под
 * замороженным блоком. Заголовок прилипает сверху, его левые зоны — слева.
 *
 * Клик по заголовку сортирует (первый клик — desc, повтор — asc), активная колонка
 * подсвечивается акцентом с индикатором ▲/▼. Замороженный блок сортирует по `date`.
 * Несортируемые: Координаты, Чат. Клик по строке открывает drawer.
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
  const frozenOn = sort === 'date';
  return (
    <div className="de-inc-table">
      <div className="de-inc-thead">
        {/* Чекбокс «выбрать всё» — заморожен слева (left:0). */}
        <div className="de-inc-th-checkbox">
          <div
            className={`de-inc-check ${allSelected ? 'checked' : ''}`}
            onClick={onToggleAll}
          >
            {allSelected && <CheckMark />}
          </div>
        </div>
        {/* Заголовок замороженного блока — сортирует по `date` (left:46, тень). */}
        <div
          className={`de-inc-th de-inc-th-frozen sortable ${frozenOn ? 'on' : ''}`}
          onClick={() => onSort('date')}
        >
          Дата · время · ID
          <SortArrows on={frozenOn} order={order} />
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
