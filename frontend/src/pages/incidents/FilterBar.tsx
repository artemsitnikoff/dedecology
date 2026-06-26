import { Icon } from '@/components/ui/Icon';
import { SOURCE } from '@/lib/status';
import type { Source } from '@/api/aliases';

type Props = {
  /** Выбранные источники (multi-select). */
  sources: Source[];
  onToggleSource: (source: Source) => void;
  /** Выбранный регион (точное совпадение); '' — все регионы. */
  region: string;
  /** Справочник регионов для дропдауна (А→Я). */
  regions: string[];
  onRegion: (region: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateFrom: (v: string) => void;
  onDateTo: (v: string) => void;
  /** Активен ли хоть один фильтр (источник/период) — показывает «Сбросить». */
  hasFilters: boolean;
  onReset: () => void;
};

/** Порядок чипов источника (как в прототипе: Макс, Яндекс форма). */
const SOURCE_KEYS: Source[] = ['max', 'form'];

/**
 * Панель фильтров: множественный выбор Источника + период (два native date input
 * «с — по» с ✕-сбросом). Кнопка «Сбросить» — когда активен любой фильтр.
 */
export function FilterBar({
  sources,
  onToggleSource,
  region,
  regions,
  onRegion,
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
  hasFilters,
  onReset,
}: Props) {
  const periodSet = !!dateFrom || !!dateTo;

  return (
    <div className="de-inc-filterbar">
      <div className="de-inc-filter-group">
        <span className="de-inc-filter-label">Источник</span>
        {SOURCE_KEYS.map((k) => (
          <button
            key={k}
            type="button"
            className={`de-inc-fchip ${sources.includes(k) ? 'active' : ''}`}
            onClick={() => onToggleSource(k)}
          >
            {SOURCE[k].label}
          </button>
        ))}
      </div>

      <div className="de-inc-filter-sep" />

      <div className="de-inc-filter-group">
        <span className="de-inc-filter-label">Регион</span>
        <select
          className="de-inc-select"
          value={region}
          onChange={(e) => onRegion(e.target.value)}
        >
          <option value="">Все регионы</option>
          {regions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      <div className="de-inc-filter-sep" />

      <div className="de-inc-filter-group">
        <span className="de-inc-filter-label">Период</span>
        <input
          type="date"
          className="de-inc-date"
          value={dateFrom}
          onChange={(e) => onDateFrom(e.target.value)}
        />
        <span className="de-inc-date-dash">—</span>
        <input
          type="date"
          className="de-inc-date"
          value={dateTo}
          onChange={(e) => onDateTo(e.target.value)}
        />
        {periodSet && (
          <button
            type="button"
            className="de-inc-date-clear"
            aria-label="Очистить период"
            onClick={() => {
              onDateFrom('');
              onDateTo('');
            }}
          >
            <Icon name="x" size={15} />
          </button>
        )}
      </div>

      <div className="de-inc-spacer" />

      {hasFilters && (
        <button type="button" className="de-inc-btn de-inc-btn-reset" onClick={onReset}>
          Сбросить
        </button>
      )}
    </div>
  );
}
