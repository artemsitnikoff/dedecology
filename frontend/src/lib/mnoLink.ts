/**
 * ЧПУ-URL карточки МНО. Волонтёрское МНО (source='volunteer') живёт в разделе «Новые МНО»
 * (/mno-new) — его нет в списке ФГИС, поэтому ссылка должна вести сразу туда; остальные — в /mno.
 * Путь копируется/вставляется (id в URL), карточка открывается при заходе по ссылке.
 */
export function mnoCardPath(id: string, source: string | null | undefined): string {
  return `${source === 'volunteer' ? '/mno-new' : '/mno'}/${id}`;
}
