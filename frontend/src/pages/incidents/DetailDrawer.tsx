import { Icon } from '@/components/ui/Icon';
import { STATUS, SOURCE } from '@/lib/status';
import { formatDate, formatTime, fullAddr, maxLink } from '@/lib/format';
import { useSetStatus } from '@/api/mutations/incidents';
import type { IncidentListItem, Status } from '@/api/aliases';

type Props = {
  incident: IncidentListItem;
  onClose: () => void;
  /** Открыть фото в лайтбоксе по индексу. */
  onPhoto: (id: string, idx: number) => void;
};

/** Порядок статус-чипов смены статуса (все 4 статуса). */
const STATUS_KEYS: Status[] = ['new', 'found', 'none', 'exported'];

/**
 * Карточка инцидента — выезжает справа (560px) поверх затемнения.
 * Шапка: пилюли источник+статус, заголовок = полный адрес, ✕.
 * Фото → лайтбокс. Поля по контракту. Для Макса — ссылка на сообщение.
 * Чипы смены статуса (active = текущий) → useSetStatus с live-обновлением.
 */
export function DetailDrawer({ incident: d, onClose, onPhoto }: Props) {
  const setStatus = useSetStatus();
  const statusMeta = STATUS[d.status];
  const sourceMeta = SOURCE[d.source];
  const link = maxLink(d.msg);
  const addr = fullAddr(d);

  const fields: Array<[string, string]> = [
    ['ФИО', d.fio],
    ['Регион', d.region],
    ['Город / н.п.', d.city],
    ['Адрес', d.street],
    ['Координаты', d.coords],
    ['Дата фотофиксации', formatDate(d.photo_time)],
    ['Время фотофиксации', formatTime(d.photo_time)],
    ['Фотографий площадки', String(d.photos)],
    ['Источник', sourceMeta.label],
    ['Поступило', `${formatDate(d.received_at)} ${formatTime(d.received_at)}`.trim()],
  ];

  return (
    <div className="de-inc-overlay" onClick={onClose}>
      <div className="de-inc-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="de-inc-drawer-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="de-inc-drawer-pills">
              <span className="de-inc-pill" style={{ background: sourceMeta.bg, color: sourceMeta.fg }}>
                {sourceMeta.label}
              </span>
              <span className="de-inc-pill" style={{ background: statusMeta.bg, color: statusMeta.fg }}>
                <span className="de-inc-pill-dot" style={{ background: statusMeta.dot }} />
                {statusMeta.label}
              </span>
            </div>
            <h2 className="de-inc-drawer-title">{addr}</h2>
          </div>
          <button type="button" className="de-inc-drawer-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="de-inc-drawer-body">
          {d.photo_urls.length > 0 && (
            <div className="de-inc-drawer-photos">
              {d.photo_urls.map((src, i) => (
                <div
                  key={i}
                  className="de-inc-drawer-photo"
                  onClick={() => onPhoto(d.id, i)}
                >
                  <div className="de-inc-drawer-photo-img" style={{ backgroundImage: `url("${src}")` }} />
                  <span className="de-inc-drawer-photo-label">Фото {i + 1}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {fields.map(([k, v]) => (
              <div key={k} className="de-inc-field">
                <div className="de-inc-field-key">{k}</div>
                <div className="de-inc-field-val">{v}</div>
              </div>
            ))}
          </div>

          {link && (
            <a href={link} target="_blank" rel="noreferrer" className="de-inc-drawer-maxlink">
              <Icon name="external-link" size={16} />
              Открыть сообщение в Максе
            </a>
          )}

          <div className="de-inc-drawer-status-row">
            <span className="de-inc-drawer-status-label">Сменить статус:</span>
            {STATUS_KEYS.map((k) => {
              const meta = STATUS[k];
              const active = d.status === k;
              return (
                <button
                  key={k}
                  type="button"
                  className={`de-inc-schip ${active ? 'active' : ''}`}
                  disabled={setStatus.isPending}
                  onClick={() => {
                    if (!active) setStatus.mutate({ id: d.id, status: k });
                  }}
                >
                  <span className="de-inc-pill-dot" style={{ background: meta.dot }} />
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
