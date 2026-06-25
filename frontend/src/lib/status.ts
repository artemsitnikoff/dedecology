/**
 * Мета статусов и источников инцидентов — лейбл + CSS-токены (BUILD-SPEC §5).
 * Цвета задаются ТОЛЬКО через токены палитры ark (никакого хардкода hex).
 */
import type { Status, Source } from '@/api/aliases';

interface StatusMeta {
  /** Русский лейбл. */
  label: string;
  /** Фон пилюли (CSS var). */
  bg: string;
  /** Цвет текста пилюли (CSS var). */
  fg: string;
  /** Цвет точки-индикатора (CSS var). */
  dot: string;
  /** Порядок сортировки: new < found < none < exported. */
  order: number;
}

interface SourceMeta {
  /** Русский лейбл. */
  label: string;
  /** Фон пилюли (CSS var). */
  bg: string;
  /** Цвет текста пилюли (CSS var). */
  fg: string;
}

export const STATUS: Record<Status, StatusMeta> = {
  new: {
    label: 'Новый',
    bg: 'var(--ark-blue-50)',
    fg: 'var(--ark-blue-600)',
    dot: 'var(--accent)',
    order: 0,
  },
  found: {
    label: 'Инцидент обнаружен',
    bg: 'var(--ark-red-100)',
    fg: 'var(--ark-red-600)',
    dot: 'var(--ark-red-500)',
    order: 1,
  },
  none: {
    label: 'Нет инцидента',
    bg: 'var(--ark-gray-200)',
    fg: 'var(--ark-gray-600)',
    dot: 'var(--ark-gray-500)',
    order: 2,
  },
  exported: {
    label: 'Выгружен',
    bg: 'var(--ark-green-100)',
    fg: 'var(--ark-green-600)',
    dot: 'var(--ark-green-500)',
    order: 3,
  },
};

export const SOURCE: Record<Source, SourceMeta> = {
  max: {
    label: 'Макс',
    bg: 'var(--ark-violet-100)',
    fg: 'var(--ark-violet-500)',
  },
  form: {
    label: 'Яндекс форма',
    bg: 'var(--ark-yellow-100)',
    fg: 'var(--ark-yellow-600)',
  },
};
