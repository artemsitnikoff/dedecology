import { Icon } from '@/components/ui/Icon';

/**
 * Окно номеров страниц вокруг текущей (как в ReportsPage/MnoPage) — до 7 страниц
 * показываем все; иначе первая · … · (тек-1, тек, тек+1) · … · последняя
 * ('gap' = многоточие).
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

type Props = {
  page: number;
  pages: number;
  onChange: (p: number) => void;
};

/**
 * Пагинатор списка «Инциденты» — та же визуальная логика, что у `de-rep-pager*`
 * на странице «Отчёты» (windowed-номера, ▲/▼-иконки, disabled на краях), но
 * живёт ВНУТРИ прокручиваемой `.de-inc-content` (под таблицей), а не отдельной
 * подвальной панелью.
 */
export function Pagination({ page, pages, onChange }: Props) {
  return (
    <div className="de-inc-pager">
      <div className="de-inc-pager-controls">
        <button
          type="button"
          className="de-inc-pager-btn"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <Icon name="chevron-left" size={15} />
          Назад
        </button>
        {pageWindow(page, pages).map((p, i) =>
          p === 'gap' ? (
            <span key={`gap-${i}`} className="de-inc-pager-gap">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              className={`de-inc-pager-num de-inc-mono ${p === page ? 'active' : ''}`}
              onClick={() => onChange(p)}
            >
              {p}
            </button>
          )
        )}
        <button
          type="button"
          className="de-inc-pager-btn"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Вперёд
          <Icon name="chevron-right" size={15} />
        </button>
      </div>
    </div>
  );
}
