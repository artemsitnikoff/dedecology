/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  /** Ключ Yandex Maps JS API (build-time). Пусто → карта рендерит честную плашку. */
  readonly VITE_YANDEX_MAPS_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
