/**
 * Публичные эндпоинты приёма обращений (intake) — без авторизации.
 * Контракт BUILD-SPEC: подсказки адреса (DaData) + отправка формы.
 * Используем общий `api` клиент: анонимно (без токена) — это нормально для
 * публичных роутов. Content-Type для multipart НЕ задаём руками — axios сам
 * проставит boundary.
 */
import { api } from '@/api/client';

/** Одна подсказка адреса из DaData (GET /intake/suggest/address). */
export interface AddressSuggestion {
  value: string;
  region: string;
  city: string;
  street: string;
  coords: string;
  geo_lat: string;
  geo_lon: string;
  /** Голые имена (без типа) — для фильтрации следующего уровня (DaData locations). */
  region_plain?: string;
  city_plain?: string;
}

interface SuggestResponse {
  suggestions: AddressSuggestion[];
}

/** Результат успешной отправки формы (POST /intake/form). */
export interface IntakeFormResult {
  ok: boolean;
  incident_id?: string;
  /** Короткая мотивирующая цитата о природе — показывается на экране «Спасибо». */
  quote?: string;
}

/** Вид подсказки: ограничивает выдачу DaData до региона/города/улицы/полного адреса. */
export type SuggestKind = 'region' | 'city' | 'street' | 'full';

/** Опции запроса подсказок: вид + контекст (регион/город) + размер выдачи. */
export interface SuggestOptions {
  kind?: SuggestKind;
  region?: string;
  city?: string;
  count?: number;
}

/**
 * GET /intake/suggest/address — подсказки адреса.
 * Пустой список, если нет DADATA_API_KEY или совпадений (graceful).
 * Минимальная длина запроса — 3 символа (короче не дёргаем сервер).
 * Через `opts` можно запросить ограниченную выдачу (kind=region|city|street)
 * с контекстом по уже выбранному региону/городу.
 */
export async function suggestAddress(
  q: string,
  opts: SuggestOptions = {},
  signal?: AbortSignal,
): Promise<AddressSuggestion[]> {
  if (q.trim().length < 3) return [];
  const { kind, region, city, count = 8 } = opts;
  const params = new URLSearchParams({ q: q.trim(), count: String(count) });
  if (kind) params.set('kind', kind);
  if (region) params.set('region', region);
  if (city) params.set('city', city);
  const res = await api.get<SuggestResponse>(`/intake/suggest/address?${params.toString()}`, {
    signal,
  });
  return res.data.suggestions ?? [];
}

/** POST /intake/form (multipart/form-data). Возвращает {ok, incident_id}. */
export async function submitIntakeForm(form: FormData): Promise<IntakeFormResult> {
  const res = await api.post<IntakeFormResult>('/intake/form', form);
  return res.data;
}
