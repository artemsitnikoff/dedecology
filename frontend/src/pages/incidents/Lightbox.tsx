import { Icon } from '@/components/ui/Icon';
import { fullAddr } from '@/lib/format';
import type { IncidentListItem } from '@/api/aliases';

type Props = {
  incident: IncidentListItem;
  /** Текущий индекс фото. */
  idx: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
};

/**
 * Полноэкранный просмотр фото. Стрелки ◀ ▶ и моно-счётчик «i / N» — только при >1 фото.
 * Подпись — полный адрес. Клик по фону / ✕ закрывает.
 */
export function Lightbox({ incident, idx, onClose, onPrev, onNext }: Props) {
  const srcs = incident.photo_urls;
  if (srcs.length === 0) return null;
  const i = Math.max(0, Math.min(idx, srcs.length - 1));
  const many = srcs.length > 1;

  return (
    <div className="de-inc-lb" onClick={onClose}>
      <button type="button" className="de-inc-lb-close" aria-label="Закрыть" onClick={onClose}>
        <Icon name="x" size={22} />
      </button>

      {many && (
        <button
          type="button"
          className="de-inc-lb-nav left"
          aria-label="Предыдущее фото"
          onClick={(e) => {
            e.stopPropagation();
            onPrev();
          }}
        >
          <Icon name="chevron-left" size={26} />
        </button>
      )}

      <div className="de-inc-lb-stage" onClick={(e) => e.stopPropagation()}>
        <div className="de-inc-lb-img" style={{ backgroundImage: `url("${srcs[i]}")` }} />
        <div className="de-inc-lb-caption">
          <span className="de-inc-lb-addr">{fullAddr(incident)}</span>
          {many && (
            <span className="de-inc-lb-counter">
              {i + 1} / {srcs.length}
            </span>
          )}
        </div>
      </div>

      {many && (
        <button
          type="button"
          className="de-inc-lb-nav right"
          aria-label="Следующее фото"
          onClick={(e) => {
            e.stopPropagation();
            onNext();
          }}
        >
          <Icon name="chevron-right" size={26} />
        </button>
      )}
    </div>
  );
}
