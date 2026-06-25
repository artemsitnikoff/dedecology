/**
 * Форматтеры ru-локали для ДедЭколог. Малые чистые функции.
 * Даты/время приходят с бэкенда ISO-строками (или null).
 */

/** Дата из ISO → «ДД.ММ.ГГГГ». Пустая строка для null/невалидного. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  // UTC-геттеры: рендерим настенные цифры из ISO без сдвига в локальную TZ браузера.
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = String(d.getUTCFullYear());
  return `${dd}.${mm}.${yyyy}`;
}

/** Время из ISO → «ЧЧ:ММ». Пустая строка для null/невалидного. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  // UTC-геттеры: 09:14(UTC) рендерится «09:14» вне зависимости от TZ браузера.
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hh}:${min}`;
}

/** Полный адрес: «регион, город, улица» (пустые части отбрасываются). */
export function fullAddr(parts: {
  region?: string;
  city?: string;
  street?: string;
}): string {
  return [parts.region, parts.city, parts.street]
    .map((p) => (p ?? '').trim())
    .filter(Boolean)
    .join(', ');
}

/** Ссылка на сообщение в Максе по msg id; null, если источник не Макс / нет msg. */
export function maxLink(msg: string | null | undefined): string | null {
  if (!msg) return null;
  return `https://max.ru/m/${msg}`;
}
