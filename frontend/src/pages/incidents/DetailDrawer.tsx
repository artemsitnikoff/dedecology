import { useNavigate } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { STATUS, SOURCE } from '@/lib/status';
import { formatDate, formatTime, fullAddr, maxLink } from '@/lib/format';
import { thumbUrl } from '@/lib/photo';
import { mnoCardPath } from '@/lib/mnoLink';
import { useIncident } from '@/api/hooks/useIncident';
import { useIncidentTypes } from '@/api/hooks/useIncidentTypes';
import { useSetStatus } from '@/api/mutations/incidents';
import type { Incident, Status } from '@/api/aliases';

type Props = {
  /** id открываемого инцидента — по нему делаем реальный GET /incidents/{id}. */
  id: string;
  /** Координаты выезда: top = верх скролл-контейнера таблицы, left = после левых колонок. */
  top: number;
  left: number;
  onClose: () => void;
  /** Открыть фото в лайтбоксе по индексу. */
  onPhoto: (id: string, idx: number) => void;
};

/**
 * Контекстные переходы статуса (из ТЗ): из текущего показываем только осмысленные.
 * new → [found, none] · found → [new, exported] · none → [new, found] · exported → [found, new].
 */
const TRANSITIONS: Record<Status, Status[]> = {
  new: ['found', 'none'],
  found: ['new', 'exported'],
  none: ['new', 'found'],
  exported: ['found', 'new'],
};

/**
 * Карточка инцидента — выезжает справа НАД областью таблицы (position:fixed),
 * не закрывая сайдбар, левые колонки (фото·дата·время), воронку и фильтры.
 * При открытии делает реальный запрос детали; пока isLoading — белый экран
 * с пульсом 💚. Контент: шапка (пилюли+ID+адрес) → контекстная смена статуса →
 * фото → дашед-поля → ссылка на Макс. Смена статуса — useSetStatus (live-обновление).
 */
export function DetailDrawer({ id, top, left, onClose, onPhoto }: Props) {
  const { data, isLoading, isError } = useIncident(id);

  return (
    <div className="de-inc-drawer" style={{ top, left }}>
      {isLoading ? (
        <div className="de-inc-drawer-loading">
          <span className="de-mark-heart de-inc-drawer-loading-mark">💚</span>
          <span className="de-inc-drawer-loading-text">Загрузка…</span>
        </div>
      ) : isError || !data ? (
        <div className="de-inc-drawer-loading">
          <span className="de-inc-drawer-error-text">Не удалось загрузить обращение.</span>
          <button type="button" className="de-inc-empty-btn" onClick={onClose}>
            Закрыть
          </button>
        </div>
      ) : (
        <DrawerContent d={data} onClose={onClose} onPhoto={onPhoto} />
      )}
    </div>
  );
}

type ContentProps = {
  d: Incident;
  onClose: () => void;
  onPhoto: (id: string, idx: number) => void;
};

/** Содержимое карточки (рендерится только когда деталь загружена). */
function DrawerContent({ d, onClose, onPhoto }: ContentProps) {
  const navigate = useNavigate();
  const setStatus = useSetStatus();
  const { data: incidentTypes = [] } = useIncidentTypes();
  const statusMeta = STATUS[d.status];
  const sourceMeta = SOURCE[d.source];
  const link = maxLink(d.msg_url);
  const addr = fullAddr(d);
  const shortId = d.id.slice(0, 8).toUpperCase();
  const single = d.photo_urls.length === 1;
  const actions = TRANSITIONS[d.status];

  // Резолвим код типа в подпись по справочнику; нет типа / неизвестный код → «—».
  const typeLabel =
    (d.incident_type && incidentTypes.find((t) => t.code === d.incident_type)?.label) || '—';

  const fields: Array<[string, string]> = [
    ['Заявитель', d.fio],
    ['Тип инцидента', typeLabel],
    ['Регион', d.region],
    ['Город / н.п.', d.city],
    ['Адрес', d.street],
    ['Координаты', d.coords],
    ['Дата фотофиксации', formatDate(d.photo_time)],
    ['Время фотофиксации', formatTime(d.photo_time)],
    ['Кол-во фото', String(d.photos)],
    ['Источник', sourceMeta.label],
    ['Поступило', `${formatDate(d.received_at)} ${formatTime(d.received_at)}`.trim()],
  ];

  return (
    <div className="de-inc-drawer-inner">
      {/* Шапка (sticky): сердце + пилюли + ID + полный адрес + крестик. */}
      <div className="de-inc-drawer-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="de-inc-drawer-pills">
            <span className="de-mark-heart de-inc-drawer-head-mark">💚</span>
            <span className="de-inc-pill" style={{ background: sourceMeta.bg, color: sourceMeta.fg }}>
              {sourceMeta.label}
            </span>
            <span className="de-inc-pill" style={{ background: statusMeta.bg, color: statusMeta.fg }}>
              <span className="de-inc-pill-dot" style={{ background: statusMeta.dot }} />
              {statusMeta.label}
            </span>
            <span className="de-inc-drawer-id" title={d.id}>
              ID {shortId}
            </span>
          </div>
          <h2 className="de-inc-drawer-title">{addr}</h2>
        </div>
        <button type="button" className="de-inc-drawer-close" aria-label="Закрыть" onClick={onClose}>
          <Icon name="x" size={18} />
        </button>
      </div>

      {/* Контекстная смена статуса — сразу под шапкой. */}
      {actions.length > 0 && (
        <div className="de-inc-drawer-status-row">
          <span className="de-inc-drawer-status-label">Сменить статус:</span>
          {actions.map((k) => {
            const meta = STATUS[k];
            return (
              <button
                key={k}
                type="button"
                className="de-inc-schip"
                disabled={setStatus.isPending}
                onClick={() => setStatus.mutate({ id: d.id, status: k })}
              >
                <span className="de-inc-pill-dot" style={{ background: meta.dot }} />
                {meta.label}
              </button>
            );
          })}
        </div>
      )}

      <div className="de-inc-drawer-body">
        {d.photo_urls.length > 0 && (
          <div className={`de-inc-drawer-photos ${single ? 'single' : ''}`}>
            {d.photo_urls.map((src, i) => (
              <div key={i} className="de-inc-drawer-photo" onClick={() => onPhoto(d.id, i)}>
                {/* Превью — thumb (быстро); клик открывает лайтбокс с FULL по индексу. */}
                <div
                  className="de-inc-drawer-photo-img"
                  style={{ backgroundImage: `url("${thumbUrl(src)}")` }}
                />
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
          {/* Объект ТКО — если инцидент привязан к МНО (есть mno_id), реестровый №
              кликабелен → ЧПУ-карточка МНО (/mno/<id>, а для волонтёрского МНО — /mno-new/<id>
              по mno_source). Без mno_id — просто текст рег-номера или «—». */}
          <div className="de-inc-field">
            <div className="de-inc-field-key">Объект ТКО</div>
            <div className="de-inc-field-val">
              {d.mno_id ? (
                <button
                  type="button"
                  className="de-inc-mno-link"
                  onClick={() => navigate(mnoCardPath(d.mno_id!, d.mno_source))}
                  title="Открыть карточку объекта ТКО"
                >
                  <Icon name="pin" size={13} />
                  {d.mno_reg || (d.mno_source === 'volunteer' ? 'Новый' : 'Открыть карточку МНО')}
                </button>
              ) : (
                d.mno_reg || '—'
              )}
            </div>
          </div>
          {/* Комментарий — поле показываем ВСЕГДА (пустое = «—»); многострочный текст переносится. */}
          <div className="de-inc-field">
            <div className="de-inc-field-key">Комментарий</div>
            <div
              className="de-inc-field-val"
              style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
            >
              {d.comment?.trim() || '—'}
            </div>
          </div>
        </div>

        {link && (
          <a href={link} target="_blank" rel="noreferrer" className="de-inc-drawer-maxlink">
            <Icon name="external-link" size={16} />
            Открыть сообщение в Максе
          </a>
        )}
      </div>
    </div>
  );
}
