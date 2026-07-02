/**
 * Загрузчик Yandex Maps JS API 2.1 (синглтон).
 *
 * Ключ — build-time env VITE_YANDEX_MAPS_KEY (тип ключа «JavaScript API и HTTP
 * Геокодер»). Ключ попадает в бандл — это нормально для JS-Карт (ограничивается по
 * домену в кабинете Яндекса). Если ключ пуст — карта честно показывает плашку
 * «Карта недоступна», см. компонент YandexMap.
 *
 * Полные типы (@types/yandex-maps) не устанавливаем — npm-реестр в этой среде
 * недоступен. Описываем только используемую поверхность API вручную (без any).
 */

const KEY = import.meta.env.VITE_YANDEX_MAPS_KEY as string | undefined;

/** GeoJSON-подобная фича для ObjectManager (Point + подпись). */
export interface YFeature {
  type: 'Feature';
  id: string;
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { balloonContent: string; hintContent: string };
}

/** Коллекция фич для ObjectManager.add. */
export interface YFeatureCollection {
  type: 'FeatureCollection';
  features: YFeature[];
}

/** Границы области [[юг, запад], [север, восток]] в порядке Яндекса [широта, долгота]. */
export type YBounds = [[number, number], [number, number]];

export interface YGeoObjects {
  add: (obj: unknown) => void;
  getBounds: () => YBounds | null;
}

/**
 * Менеджер событий карты (Yandex Maps 2.1). Используем только add/remove по имени
 * события ('boundschange'); объект события нам не нужен — текущую область берём из
 * map.getBounds().
 */
export interface YEventManager {
  add: (type: string, handler: (event?: unknown) => void) => void;
  remove: (type: string, handler: (event?: unknown) => void) => void;
}

export interface YMap {
  geoObjects: YGeoObjects;
  events: YEventManager;
  /** Текущая видимая область карты в порядке Яндекса [[юг,запад],[север,восток]]. */
  getBounds: () => YBounds | null;
  setBounds: (bounds: YBounds, opts?: { checkZoomRange?: boolean }) => void;
  destroy: () => void;
}

export interface YObjectManager {
  add: (obj: YFeatureCollection | YFeature) => void;
  removeAll: () => void;
}

interface YMapState {
  center: [number, number];
  zoom: number;
  controls?: string[];
}

interface YObjectManagerOptions {
  clusterize?: boolean;
  gridSize?: number;
  clusterDisableClickZoom?: boolean;
}

/** Минимальная поверхность глобального `ymaps`, которую использует приложение. */
export interface YMapsApi {
  Map: new (element: HTMLElement | string, state: YMapState) => YMap;
  ObjectManager: new (options: YObjectManagerOptions) => YObjectManager;
  ready: (callback: () => void) => void;
}

declare global {
  interface Window {
    ymaps?: YMapsApi;
  }
}

/** true — ключ Yandex Maps задан на этапе сборки (иначе рендерим честную плашку). */
export function isYandexKeyConfigured(): boolean {
  return !!KEY;
}

// Кэш промиса загрузки: скрипт инжектится один раз на всё приложение.
let loaderPromise: Promise<YMapsApi> | null = null;

/**
 * Один раз инжектит <script> Yandex Maps JS API и резолвит через ymaps.ready().
 * Промис кэшируется — повторные вызовы переиспользуют загруженный API.
 * Пустой ключ → reject('no-key'); ошибка загрузки скрипта → reject (кэш сбрасывается,
 * чтобы после восстановления сети можно было повторить).
 */
export function loadYmaps(): Promise<YMapsApi> {
  if (!KEY) return Promise.reject(new Error('no-key'));
  if (loaderPromise) return loaderPromise;

  loaderPromise = new Promise<YMapsApi>((resolve, reject) => {
    // API уже подгружен (например, скрипт остался от прошлого маунта) — переиспользуем.
    if (window.ymaps) {
      window.ymaps.ready(() => resolve(window.ymaps as YMapsApi));
      return;
    }
    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(KEY)}&lang=ru_RU`;
    script.async = true;
    script.onload = () => {
      if (!window.ymaps) {
        loaderPromise = null;
        reject(new Error('ymaps-missing'));
        return;
      }
      window.ymaps.ready(() => resolve(window.ymaps as YMapsApi));
    };
    script.onerror = () => {
      loaderPromise = null; // позволяем повторную попытку после сетевого сбоя
      reject(new Error('script-load-failed'));
    };
    document.head.appendChild(script);
  });

  return loaderPromise;
}
