import { Icon } from '@/components/ui/Icon';
import { STATUS } from '@/lib/status';
import type { FunnelCounts } from '@/api/aliases';
import type { Status } from '@/api/aliases';

type Props = {
  /** Текущий выбранный статус (single-select) или null = «Все». */
  status: Status | null;
  /** Счётчики воронки с бэкенда (учитывают search/source/period, не status). */
  counts: FunnelCounts | undefined;
  /** Клик по чипу: выбрать статус или, если он уже активен, снять (вернуть к «Все»). */
  onSelect: (status: Status | null) => void;
};

/** Соответствие ключа статуса полю счётчиков FunnelCounts. */
const COUNT_KEY: Record<Status, keyof FunnelCounts> = {
  new: 'new',
  found: 'found',
  none: 'none',
  exported: 'exported',
};

/**
 * Воронка статусов: single-select чипы.
 * Порядок: Все | Новый → Инцидент обнаружен | Выгружен | Нет инцидента.
 * Счётчики моно-шрифтом из useFunnelCounts. Клик по активному чипу сбрасывает статус.
 */
export function Funnel({ status, counts, onSelect }: Props) {
  const allActive = status === null;

  const renderChip = (k: Status, variant: 'pipe' | 'exported' | 'none') => {
    const active = status === k;
    const meta = STATUS[k];
    const count = counts ? counts[COUNT_KEY[k]] : 0;
    return (
      <button
        type="button"
        className={`de-inc-chip ${variant} ${active ? 'active' : ''}`}
        onClick={() => onSelect(active ? null : k)}
      >
        <span
          className="de-inc-chip-dot"
          style={{ background: active ? 'var(--ark-white)' : meta.dot }}
        />
        {meta.label}
        <span className="de-inc-chip-count">{count}</span>
      </button>
    );
  };

  return (
    <div className="de-inc-funnel">
      <button
        type="button"
        className={`de-inc-chip de-inc-chip-all ${allActive ? 'active' : ''}`}
        onClick={() => onSelect(null)}
      >
        Все
        <span className="de-inc-chip-count">{counts ? counts.all : 0}</span>
      </button>

      <span className="de-inc-funnel-gap" />
      {renderChip('new', 'pipe')}
      <Icon name="arrow-right" size={16} className="de-inc-funnel-arrow" />
      {renderChip('found', 'pipe')}
      <span className="de-inc-funnel-gap wide" />
      {renderChip('exported', 'exported')}
      {renderChip('none', 'none')}
    </div>
  );
}
