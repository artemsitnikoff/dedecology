import { memo, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { formatDate, formatTime } from '@/lib/format';
import {
  ERROR_TYPE_LABELS,
  useErrorReport,
  useErrorReports,
} from '@/api/hooks/useErrorReports';
import type { ErrorReportItem } from '@/api/hooks/useErrorReports';
import './Errors.css';

/** Размер страницы серверной пагинации списка ошибок. */
const PAGE_SIZE = 50;

/** «ДД.ММ.ГГГГ ЧЧ:ММ» или «—». */
function fmtDateTime(iso: string | null | undefined): string {
  const d = formatDate(iso);
  return d ? `${d} ${formatTime(iso)}` : '—';
}

function typeLabel(code: string): string {
  return ERROR_TYPE_LABELS[code] || code;
}

/** Окно номеров страниц вокруг текущей (как в отчётах). */
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

/* ---------- Строка таблицы ---------- */
type RowProps = { e: ErrorReportItem; onOpen: (id: string) => void };
const ErrorRow = memo(function ErrorRow({ e, onOpen }: RowProps) {
  return (
    <div className="de-err-row" onClick={() => onOpen(e.id)}>
      <div className="de-err-cell de-err-c-code" title={e.code}>
        {e.code}
      </div>
      <div className="de-err-cell de-err-c-type">{typeLabel(e.error_type)}</div>
      <div className="de-err-cell de-err-c-msg" title={e.message || ''}>
        {e.message || '—'}
      </div>
      <div className="de-err-cell de-err-c-app">{e.app_version || '—'}</div>
      <div className="de-err-cell de-err-c-platform">{e.platform || '—'}</div>
      <div className="de-err-cell de-err-c-email" title={e.volunteer_email || ''}>
        {e.volunteer_email || '—'}
      </div>
      <div className="de-err-cell de-err-c-occurred">{fmtDateTime(e.occurred_at)}</div>
      <div className="de-err-cell de-err-c-created">{fmtDateTime(e.created_at)}</div>
      <div className="de-err-cell de-err-c-mail">
        <span className={`de-err-pill ${e.emailed ? 'ok' : 'off'}`}>
          <span
            className="de-err-pill-dot"
            style={{ background: e.emailed ? 'var(--ark-green-500)' : 'var(--ark-red-500)' }}
          />
          {e.emailed ? 'Отправлено' : 'Не ушло'}
        </span>
      </div>
    </div>
  );
});

/* ============================================================
   Экран «Технические ошибки» (admin)
   ============================================================ */
export function ErrorsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get('epage')) || 1);

  const setPage = (p: number) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (p <= 1) next.delete('epage');
        else next.set('epage', String(p));
        return next;
      },
      { replace: true }
    );

  const listQuery = useErrorReports(page, PAGE_SIZE);
  const items = useMemo(() => listQuery.data?.items ?? [], [listQuery.data]);
  const total = listQuery.data?.total ?? 0;
  const totalPages = listQuery.data?.pages ?? 0;

  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="de-err-wrap">
      {/* Шапка */}
      <div className="de-err-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-err-title">Технические ошибки</h1>
          <div className="de-err-subtitle">
            Обращения об ошибках из мобильного приложения · {total}
          </div>
        </div>
      </div>

      {/* Таблица */}
      <div className="de-err-content">
        {listQuery.isLoading ? (
          <div className="de-err-state">Загрузка…</div>
        ) : listQuery.isError ? (
          <div className="de-err-state error">Не удалось загрузить список ошибок.</div>
        ) : items.length === 0 ? (
          <div className="de-err-empty">
            <span className="de-err-empty-mark">💚</span>
            <h3>Ошибок пока нет</h3>
            <p>Здесь появятся технические ошибки, о которых сообщило мобильное приложение.</p>
          </div>
        ) : (
          <div className="de-err-table">
            <div className="de-err-thead">
              <div className="de-err-th de-err-c-code">Код</div>
              <div className="de-err-th de-err-c-type">Тип</div>
              <div className="de-err-th de-err-c-msg">Описание</div>
              <div className="de-err-th de-err-c-app">Версия</div>
              <div className="de-err-th de-err-c-platform">Платформа</div>
              <div className="de-err-th de-err-c-email">Email волонтёра</div>
              <div className="de-err-th de-err-c-occurred">Время сбоя</div>
              <div className="de-err-th de-err-c-created">Зарегистрировано</div>
              <div className="de-err-th de-err-c-mail">Письмо в ТП</div>
            </div>
            {items.map((e) => (
              <ErrorRow key={e.id} e={e} onOpen={setOpenId} />
            ))}
          </div>
        )}
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div className="de-err-pager">
          <button
            type="button"
            className="de-err-pager-btn"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            <Icon name="chevron-left" size={15} />
          </button>
          {pageWindow(page, totalPages).map((p, i) =>
            p === 'gap' ? (
              <span key={`gap${i}`} className="de-err-pager-gap">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                className={`de-err-pager-btn ${p === page ? 'on' : ''}`}
                onClick={() => setPage(p)}
              >
                {p}
              </button>
            )
          )}
          <button
            type="button"
            className="de-err-pager-btn"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            <Icon name="chevron-right" size={15} />
          </button>
        </div>
      )}

      {openId && <ErrorDetailModal id={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}

/* ---------- Модалка детальной карточки ошибки ---------- */
function ErrorDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, isLoading, isError } = useErrorReport(id);

  const rows: Array<[string, string]> = data
    ? [
        ['Код', data.code],
        ['Тип', typeLabel(data.error_type)],
        ['Описание', data.message || '—'],
        ['Версия приложения', data.app_version || '—'],
        ['Платформа', data.platform || '—'],
        ['Email волонтёра', data.volunteer_email || '—'],
        ['Действие пользователя', data.user_action || '—'],
        ['Время сбоя', fmtDateTime(data.occurred_at)],
        ['Зарегистрировано', fmtDateTime(data.created_at)],
        [
          'Письмо в поддержку',
          data.emailed ? 'Отправлено (ecopulse@reo.ru)' : `Не отправлено${data.email_error ? `: ${data.email_error}` : ''}`,
        ],
      ]
    : [];

  return (
    <div className="de-err-modal-overlay" onClick={onClose}>
      <div className="de-err-modal" onClick={(ev) => ev.stopPropagation()}>
        <div className="de-err-modal-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="de-err-modal-title">{data ? data.code : 'Ошибка'}</h2>
            <div className="de-err-modal-sub">Карточка технической ошибки</div>
          </div>
          <button type="button" className="de-err-modal-close" aria-label="Закрыть" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="de-err-modal-body">
          {isLoading ? (
            <div className="de-err-state">Загрузка…</div>
          ) : isError || !data ? (
            <div className="de-err-state error">Не удалось загрузить карточку ошибки.</div>
          ) : (
            <>
              <div className="de-err-fields">
                {rows.map(([k, v]) => (
                  <div key={k} className="de-err-field">
                    <div className="de-err-field-key">{k}</div>
                    <div className="de-err-field-val">{v}</div>
                  </div>
                ))}
              </div>
              <div className="de-err-tech">
                <div className="de-err-field-key">Технические данные</div>
                <pre className="de-err-tech-pre">
                  {data.technical && Object.keys(data.technical).length > 0
                    ? JSON.stringify(data.technical, null, 2)
                    : '—'}
                </pre>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
