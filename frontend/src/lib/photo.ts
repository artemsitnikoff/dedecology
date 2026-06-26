/**
 * Хелперы для работы с URL фотографий инцидентов.
 *
 * Бэкенд отдаёт два варианта картинки по одному ресурсу:
 *   FULL  → /api/v1/intake/photo/<uuid>/<n>.jpg
 *   THUMB → /api/v1/intake/photo/<uuid>/<n>_thumb.jpg
 * Админка грузит THUMB для списков/превью (быстро), а FULL — в лайтбоксе.
 */

/** Матчит ресурс фото intake: .../photo/<uuid>/<n>.jpg (без _thumb). */
const INTAKE_PHOTO = /(\/api\/v1\/intake\/photo\/[0-9a-f-]+\/\d+)\.jpg$/i;

/**
 * Возвращает URL уменьшенной версии (thumb) для intake-фото.
 * Для совпавшего паттерна вставляет `_thumb` перед `.jpg`; для прочих URL
 * (seed/placeholder/внешние) возвращает исходную строку без изменений.
 */
export function thumbUrl(url: string): string {
  return url.replace(INTAKE_PHOTO, '$1_thumb.jpg');
}
