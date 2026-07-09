import { useCallback, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '@/components/ui/Icon';
import { Toast, useToast } from '@/components/ui/Toast';
import { formatDate, formatTime } from '@/lib/format';
import { useReports } from '@/api/hooks/useReports';
import type { ReportListItem } from '@/api/hooks/useReports';
import { downloadReport, useDeleteReport } from '@/api/mutations/reports';
import type { ApiError } from '@/api/aliases';
import './Reports.css';

/** Размер страницы серверной пагинации истории отчётов (контракт GET /reports). */
const PAGE_SIZE = 50;

/**
 * Окно номеров страниц вокруг текущей (как в MnoPage) — до 7 страниц показываем все;
 * иначе первая · … · (тек-1, тек, тек+1) · … · последняя ('gap' = многоточие).
 */
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

/** Байты → человекочитаемый размер (Б/КБ/МБ). */
function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} КБ`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb < 10 ? 1 : 0)} МБ`;
}

/** Достаёт человекочитаемое сообщение из конверта ошибки бэка, иначе — fallback. */
function apiErrorMessage(err: unknown, fallback: string): string {
  const message = (err as Partial<ApiError>)?.error?.message;
  return message || fallback;
}

/* ---------- Строка таблицы ---------- */
type RowProps = {
  r: ReportListItem;
  confirming: boolean;
  deletePending: boolean;
  onDownload: (r: ReportListItem) => void;
  onDeleteClick: (id: string) => void;
  onConfirmDelete: (id: string) => void;
  onCancelDelete: () => void;
};
function ReportRow({
  r,
  confirming,
  deletePending,
  onDownload,
  onDeleteClick,
  onConfirmDelete,
  onCancelDelete,
}: RowProps) {
  return (
    <div className="de-rep-row">
      <div className="de-rep-cell de-rep-c-date">
        <span className="de-rep-mono">{formatDate(r.created_at) || '—'}</span>
        <span className="de-rep-mono de-rep-time">{formatTime(r.created_at)}</span>
      </div>
      <div className="de-rep-cell de-rep-c-rows">
        <span className="de-rep-mono">{r.row_count}</span>
      </div>
      <div className="de-rep-cell de-rep-c-size">
        <span className="de-rep-mono">{humanSize(r.size_bytes)}</span>
      </div>
      <div className="de-rep-cell de-rep-c-author" title={r.created_by_fio || undefined}>
        {r.created_by_fio || '—'}
      </div>
      <div className="de-rep-cell de-rep-c-actions">
        {confirming ? (
          <div className="de-rep-confirm">
            <span>Удалить?</span>
            <button
              type="button"
              className="de-rep-btn de-rep-btn-danger"
              disabled={deletePending}
              onClick={() => onConfirmDelete(r.id)}
            >
              {deletePending ? 'Удаление…' : 'Да'}
            </button>
            <button
              type="button"
              className="de-rep-btn de-rep-btn-ghost"
              disabled={deletePending}
              onClick={onCancelDelete}
            >
              Отмена
            </button>
          </div>
        ) : (
          <>
            <button
              type="button"
              className="de-rep-icon-btn"
              title="Скачать"
              aria-label="Скачать отчёт"
              onClick={() => onDownload(r)}
            >
              <Icon name="download" size={15} />
            </button>
            <button
              type="button"
              className="de-rep-icon-btn danger"
              title="Удалить"
              aria-label="Удалить отчёт"
              onClick={() => onDeleteClick(r.id)}
            >
              <Icon name="trash" size={15} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Экран «Отчёты» — история сформированных .xlsx-выгрузок обращений.
   ============================================================ */
export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const { message, showToast } = useToast();

  // Текущая страница живёт в URL (?rpage=N) — шарится и переживает reload; 1 → без параметра.
  const page = Math.max(1, Number(searchParams.get('rpage')) || 1);
  const setPage = useCallback(
    (p: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (p <= 1) next.delete('rpage');
          else next.set('rpage', String(p));
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const reportsQuery = useReports({ page, page_size: PAGE_SIZE });
  const deleteReport = useDeleteReport();

  const rows = reportsQuery.data?.items ?? [];
  const total = reportsQuery.data?.total ?? 0;
  const pages = reportsQuery.data?.pages ?? 0;

  const rangeFrom = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeTo = Math.min(page * PAGE_SIZE, total);

  const handleDownload = useCallback(
    async (r: ReportListItem) => {
      showToast('Отчёт скачивается…');
      try {
        await downloadReport(r.id, r.filename);
      } catch (err) {
        showToast(apiErrorMessage(err, 'Не удалось скачать отчёт.'));
      }
    },
    [showToast]
  );

  const handleDeleteClick = useCallback((id: string) => setConfirmingId(id), []);
  const handleCancelDelete = useCallback(() => setConfirmingId(null), []);
  const handleConfirmDelete = useCallback(
    (id: string) => {
      deleteReport.mutate(id, {
        onSuccess: () => {
          setConfirmingId(null);
          showToast('Отчёт удалён.');
        },
        onError: (err) => {
          setConfirmingId(null);
          showToast(apiErrorMessage(err, 'Не удалось удалить отчёт.'));
        },
      });
    },
    [deleteReport, showToast]
  );

  return (
    <div className="de-rep-wrap">
      {/* Шапка */}
      <div className="de-rep-header">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="de-rep-title">Выгрузка УТКО</h1>
          <div className="de-rep-subtitle">{total} отчётов</div>
        </div>
      </div>

      {/* Контент: таблица */}
      <div className="de-rep-content">
        {reportsQuery.isLoading ? (
          <div className="de-rep-state">Загрузка…</div>
        ) : reportsQuery.isError ? (
          <div className="de-rep-state error">Не удалось загрузить отчёты.</div>
        ) : rows.length > 0 ? (
          <div className="de-rep-table">
            <div className="de-rep-thead">
              <div className="de-rep-th de-rep-c-date">Дата и время</div>
              <div className="de-rep-th de-rep-c-rows">Строк</div>
              <div className="de-rep-th de-rep-c-size">Размер</div>
              <div className="de-rep-th de-rep-c-author">Сформировал</div>
              <div className="de-rep-th de-rep-c-actions">Действия</div>
            </div>
            {rows.map((r) => (
              <ReportRow
                key={r.id}
                r={r}
                confirming={confirmingId === r.id}
                deletePending={deleteReport.isPending && deleteReport.variables === r.id}
                onDownload={handleDownload}
                onDeleteClick={handleDeleteClick}
                onConfirmDelete={handleConfirmDelete}
                onCancelDelete={handleCancelDelete}
              />
            ))}
          </div>
        ) : (
          <div className="de-rep-empty">
            <div className="de-rep-empty-mark">💚</div>
            <h3>Выгрузок пока нет</h3>
            <p>Выгрузок пока нет — сформируйте на странице «Инциденты» кнопкой «Выгрузить в УТКО».</p>
          </div>
        )}
      </div>

      {/* Пагинатор (серверная пагинация по PAGE_SIZE) */}
      {!reportsQuery.isLoading && !reportsQuery.isError && total > 0 && (
        <div className="de-rep-pager">
          <span className="de-rep-pager-info">
            Показано <span className="de-rep-mono">{rangeFrom}</span>–
            <span className="de-rep-mono">{rangeTo}</span> из{' '}
            <span className="de-rep-mono">{total}</span>
          </span>
          <div className="de-rep-spacer" />
          {pages > 1 && (
            <div className="de-rep-pager-controls">
              <button
                type="button"
                className="de-rep-pager-btn"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                <Icon name="chevron-left" size={15} />
                Назад
              </button>
              {pageWindow(page, pages).map((p, i) =>
                p === 'gap' ? (
                  <span key={`gap-${i}`} className="de-rep-pager-gap">
                    …
                  </span>
                ) : (
                  <button
                    key={p}
                    type="button"
                    className={`de-rep-pager-num de-rep-mono ${p === page ? 'active' : ''}`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                )
              )}
              <button
                type="button"
                className="de-rep-pager-btn"
                disabled={page >= pages}
                onClick={() => setPage(page + 1)}
              >
                Вперёд
                <Icon name="chevron-right" size={15} />
              </button>
            </div>
          )}
        </div>
      )}

      <Toast message={message} />
    </div>
  );
}
