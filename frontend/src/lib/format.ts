/**
 * Форматтеры ru-локали для ЭкоПульс. Малые чистые функции.
 * Даты/время приходят с бэкенда ISO-строками (UTC) — вся админка показывает их в МСК.
 */

// Вся админка рендерит даты/время в поясе МСК (Europe/Moscow = UTC+3, без летнего времени).
// Форматтеры создаём один раз на модуль и переиспользуем (Intl.DateTimeFormat дорог в конструкции).
const MSK_DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});
const MSK_TIME_FMT = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

/** Дата из ISO (UTC) → «ДД.ММ.ГГГГ» в МСК. Пустая строка для null/невалидного. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  // МСК: сдвигаем UTC-момент в пояс Europe/Moscow (ru-RU даёт разделители-точки «ДД.ММ.ГГГГ»).
  return MSK_DATE_FMT.format(d);
}

/** Время из ISO (UTC) → «ЧЧ:ММ» в МСК. Пустая строка для null/невалидного. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  // МСК: 09:14(UTC) рендерится «12:14» (UTC+3), полночь — «00:00» (24-часовой формат).
  return MSK_TIME_FMT.format(d);
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

/**
 * Ссылка на сообщение в Максе — приходит готовой в поле msg_url (полный https-URL).
 * Возвращаем как есть, только если непустая и начинается с http(s); иначе null
 * (ссылку не показываем — никаких битых конструкций на FE не строим).
 */
export function maxLink(msgUrl: string | null | undefined): string | null {
  if (!msgUrl) return null;
  return /^https?:\/\//i.test(msgUrl) ? msgUrl : null;
}
