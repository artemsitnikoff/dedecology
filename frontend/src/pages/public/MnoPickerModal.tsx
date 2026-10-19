import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { YandexMap } from '@/components/YandexMap';
import type { MapFocus, MapPoint } from '@/components/YandexMap';
import { isYandexKeyConfigured } from '@/lib/yandexMaps';
import { submitVolunteerMno } from '@/api/intake';
import type { AddressSuggestion } from '@/api/intake';
import type { MnoFormPoint } from '@/api/aliases';
import { compressImage } from '@/lib/image';
import { useAddressSuggest } from './useAddressSuggest';
import { useMnoFormPoints } from './useMnoFormPoints';
import './mno-picker.css';

// Модалка выбора места накопления отходов (МНО) на карте — для публичной формы.
// Два режима:
//  • «pick» — выбор существующей площадки: геолокация/поиск адреса (DaData) двигают
//    карту, клик по точке МНО подставляет в форму адрес + координаты + рег-номер;
//  • «create» — «моей площадки нет, добавить новую»: координаты берём из геолокации
//    браузера ИЛИ из выбранной DaData-подсказки адреса (или вводом вручную), поля
//    адрес(обяз)+название(необяз)+комментарий(необяз), фото необязательны (сжимаются
//    тем же compressImage). Сабмит → POST /intake/mno → новая площадка выбирается в
//    форму (onSelect) и модалка закрывается.
// Нет ключа карты → внутри YandexMap честная плашка (без фейков).

/** Данные выбранного МНО, которые модалка отдаёт форме. */
export type MnoPick = {
  /** UUID МНО — уходит в инцидент ссылкой на объект ТКО (Incident.mno_id). */
  id: string;
  reg: string;
  address: string;
  coords: string;
  region: string;
  city: string;
  /** Название площадки (для подписи, когда реестрового № нет — у волонтёрских МНО). */
  name: string;
};

type Props = {
  /** Клик по точке МНО (или создание новой площадки) → подстановка в форму (и закрытие модалки). */
  onSelect: (mno: MnoPick) => void;
  /** Закрыть модалку (крестик / фон / Esc). */
  onClose: () => void;
};

/** Статус запроса геолокации браузера. */
type GeoStatus = 'pending' | 'ok' | 'denied';

/** Режим модалки: выбор существующей площадки / добавление новой. */
type Mode = 'pick' | 'create';

const SUGGEST_MIN_LEN = 3;
// Лимиты фото новой площадки — те же, что на форме и на бэке (0..10, ≤20 МБ).
const MAX_PHOTOS = 10;
const MAX_PHOTO_BYTES = 20 * 1024 * 1024; // 20 МБ
const ACCEPTED = /\.(jpe?g|png|webp)$/i;

/** «lat, lon» текстом → [широта, долгота] или null (для координат из подсказки). */
function parseCoords(raw: string): [number, number] | null {
  const parts = raw.split(',');
  if (parts.length < 2) return null;
  const lat = Number(parts[0].trim());
  const lon = Number(parts[1].trim());
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lat, lon];
}

/** Человекочитаемое сообщение из конверта ошибки API. */
function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'error' in err) {
    const env = (err as { error?: { message?: string } }).error;
    if (env?.message) return env.message;
  }
  return 'Не удалось добавить площадку. Попробуйте ещё раз.';
}

// Инлайновые стили на ТОКЕНАХ дизайн-системы. Файл mno-picker.css вне зоны правки
// этого слоя (новые классы добавить нельзя), поэтому немногие новые элементы
// режима «создать» оформляем переменными --de-*/--ark-* инлайном — это допускает
// конвенция стилей (значения только через var(--…), без хардкода).
const createPanelStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--space-3)',
  padding: 'var(--space-4) var(--space-5) var(--space-2)',
  maxHeight: '46vh',
  overflowY: 'auto',
};
const fieldStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' };
const labelStyle: CSSProperties = { fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--fg-2)' };
const hintStyle: CSSProperties = { fontSize: 'var(--fs-12)', color: 'var(--fg-3)' };
const rowStyle: CSSProperties = { display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' };
const ghostBtnStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 'var(--space-2)',
  padding: 'var(--space-2) var(--space-3)',
  background: 'var(--brand-bg)',
  color: 'var(--brand-fg)',
  border: '1.5px solid var(--brand-border)',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--fs-13)',
  fontWeight: 600,
  cursor: 'pointer',
};
const switchBtnStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 'var(--space-2)',
  padding: 'var(--space-2) var(--space-3)',
  background: 'transparent',
  color: 'var(--de-brand)',
  border: '1px dashed var(--brand-border)',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--fs-13)',
  fontWeight: 600,
  cursor: 'pointer',
};
const primaryBtnStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 'var(--space-2)',
  padding: 'var(--space-3) var(--space-4)',
  background: 'var(--de-brand)',
  color: 'var(--ark-white)',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-sans)',
  fontSize: 'var(--fs-14)',
  fontWeight: 600,
  cursor: 'pointer',
};
const errStyle: CSSProperties = {
  margin: '0 var(--space-5) var(--space-2)',
  padding: 'var(--space-2) var(--space-3)',
  background: 'var(--error-bg)',
  border: '1px solid var(--error-border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--error-fg)',
  fontSize: 'var(--fs-13)',
};
const footActionsStyle: CSSProperties = {
  display: 'flex',
  gap: 'var(--space-3)',
  alignItems: 'center',
  padding: 'var(--space-3) var(--space-5) var(--space-5)',
};
const thumbsStyle: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' };
const thumbWrapStyle: CSSProperties = { position: 'relative', width: '64px', height: '64px' };
const thumbStyle: CSSProperties = {
  width: '64px',
  height: '64px',
  objectFit: 'cover',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-1)',
};
const thumbXStyle: CSSProperties = {
  position: 'absolute',
  top: '-6px',
  right: '-6px',
  width: '18px',
  height: '18px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 0,
  fontSize: 'var(--fs-11)',
  lineHeight: 1,
  color: 'var(--ark-white)',
  background: 'var(--ark-red-600)',
  border: 'none',
  borderRadius: 'var(--radius-full)',
  cursor: 'pointer',
};
const hpStyle: CSSProperties = {
  // fixed (не absolute): элемент за кадром не влияет на скролл панели «create».
  position: 'fixed',
  left: '-9999px',
  top: '-9999px',
  width: '1px',
  height: '1px',
  opacity: 0,
  pointerEvents: 'none',
};

export function MnoPickerModal({ onSelect, onClose }: Props) {
  const keyConfigured = isYandexKeyConfigured();

  const [mode, setMode] = useState<Mode>('pick');

  // Геолокацию спрашиваем только если карта вообще доступна (иначе прок нет — плашка).
  const [geoStatus, setGeoStatus] = useState<GeoStatus>(
    keyConfigured ? 'pending' : 'denied',
  );
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [bbox, setBbox] = useState<string | null>(null);
  // located — есть ли у нас точка отсчёта (геолокация ИЛИ выбранный адрес). До этого
  // не грузим точки: иначе первый (общероссийский) кадр даст лишний запрос.
  const [located, setLocated] = useState(false);

  // Поиск адреса в режиме «pick» (когда геолокация недоступна / для навигации по карте).
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const suggestEnabled =
    mode === 'pick' && searchFocused && search.trim().length >= SUGGEST_MIN_LEN;
  const { suggestions, loading: suggestLoading } = useAddressSuggest(
    search,
    suggestEnabled,
    { kind: 'full', count: 6 },
  );
  const showDropdown = suggestEnabled && (suggestions.length > 0 || suggestLoading);

  // --- Поля режима «create» (добавление новой площадки) ---
  const [newAddress, setNewAddress] = useState('');
  const [newAddrFocused, setNewAddrFocused] = useState(false);
  const [newRegion, setNewRegion] = useState('');
  const [newCity, setNewCity] = useState('');
  const [newName, setNewName] = useState('');
  const [newComment, setNewComment] = useState('');
  const [newCoords, setNewCoords] = useState('');
  const [newPhotos, setNewPhotos] = useState<File[]>([]);
  const [newPhotoError, setNewPhotoError] = useState<string | null>(null);
  const [geoLocating, setGeoLocating] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const hpRef = useRef<HTMLInputElement>(null); // ханипот — у людей всегда пусто

  const newAddrEnabled =
    mode === 'create' && newAddrFocused && newAddress.trim().length >= SUGGEST_MIN_LEN;
  const { suggestions: newAddrSug, loading: newAddrLoading } = useAddressSuggest(
    newAddress,
    newAddrEnabled,
    { kind: 'full', count: 6 },
  );
  const showNewAddrDrop = newAddrEnabled && (newAddrSug.length > 0 || newAddrLoading);

  // Точки МНО текущего кадра (публичный эндпоинт). Только в режиме «pick» и после локации.
  const { data: pointsData } = useMnoFormPoints(bbox, {
    enabled: located && mode === 'pick',
  });

  // Превью фото новой площадки через object URL; чистим при смене набора.
  const newPreviews = useMemo(() => newPhotos.map((f) => URL.createObjectURL(f)), [newPhotos]);
  useEffect(() => {
    return () => newPreviews.forEach((url) => URL.revokeObjectURL(url));
  }, [newPreviews]);

  // Escape закрывает модалку + блокируем прокрутку фона на время открытия.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  // Запрос геолокации при открытии (успех → центрируем карту, отказ → поиск адреса).
  useEffect(() => {
    if (!keyConfigured) return;
    if (!('geolocation' in navigator)) {
      setGeoStatus('denied');
      return;
    }
    let cancelled = false;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (cancelled) return;
        setGeoStatus('ok');
        setFocus({ center: [pos.coords.latitude, pos.coords.longitude], zoom: 15 });
        setBbox(null); // ждём новый кадр после центрирования
        setLocated(true);
      },
      () => {
        if (!cancelled) setGeoStatus('denied');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
    return () => {
      cancelled = true;
    };
  }, [keyConfigured]);

  // Точки для карты (лёгкие) + индекс id→МНО для выбора по клику.
  const mapPoints: MapPoint[] = useMemo(
    () =>
      (pointsData?.points ?? []).map((p) => ({
        id: p.id,
        coords: p.coords,
        label: p.name || p.address,
      })),
    [pointsData?.points],
  );
  const byId = useMemo(() => {
    const map = new Map<string, MnoFormPoint>();
    for (const p of pointsData?.points ?? []) map.set(p.id, p);
    return map;
  }, [pointsData?.points]);

  // В режиме «create» на карте показываем ОДИН маркер — выбранную точку новой площадки.
  const createMarker: MapPoint[] = useMemo(
    () => (parseCoords(newCoords) ? [{ id: '__new__', coords: newCoords, label: 'Новая площадка' }] : []),
    [newCoords],
  );
  const displayPoints = mode === 'create' ? createMarker : mapPoints;

  // Смена видимого кадра карты → перезапрос точек (когда локация определена; в create — не нужен).
  const handleBounds = (b: [number, number, number, number]) => {
    setBbox(b.join(','));
  };

  // Клик по точке МНО → подстановка в форму + закрытие (режим «pick»).
  const handlePointClick = (id: string) => {
    const p = byId.get(id);
    if (!p) return;
    onSelect({
      id: p.id,
      reg: p.reg,
      address: p.address,
      coords: p.coords,
      region: p.region,
      city: p.city,
      name: p.name,
    });
    onClose();
  };

  // Выбор подсказки адреса (режим «pick») → центрируем карту на её координатах.
  const handlePickAddress = (s: AddressSuggestion) => {
    setSearch(s.value);
    setSearchFocused(false);
    const center =
      s.geo_lat && s.geo_lon
        ? ([Number(s.geo_lat), Number(s.geo_lon)] as [number, number])
        : parseCoords(s.coords || '');
    if (!center || !Number.isFinite(center[0]) || !Number.isFinite(center[1])) return;
    setFocus({ center, zoom: 16 });
    setBbox(null);
    setLocated(true);
  };

  // Выбор подсказки адреса (режим «create») → заполняем адрес/регион/город/координаты
  // новой площадки и центрируем карту на точке.
  const handlePickNewAddress = (s: AddressSuggestion) => {
    setNewAddress(s.value);
    setNewAddrFocused(false);
    setNewRegion(s.region || '');
    setNewCity(s.city || '');
    const center =
      s.geo_lat && s.geo_lon
        ? ([Number(s.geo_lat), Number(s.geo_lon)] as [number, number])
        : parseCoords(s.coords || '');
    if (center && Number.isFinite(center[0]) && Number.isFinite(center[1])) {
      setNewCoords(`${center[0]}, ${center[1]}`);
      setFocus({ center, zoom: 16 });
      setLocated(true);
    }
  };

  // «Моё местоположение» (режим «create») — координаты из геолокации браузера.
  const useMyLocation = () => {
    setCreateError(null);
    if (!('geolocation' in navigator)) {
      setCreateError('Геолокация недоступна в этом браузере — введите адрес или координаты вручную.');
      return;
    }
    setGeoLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoLocating(false);
        const center: [number, number] = [pos.coords.latitude, pos.coords.longitude];
        setNewCoords(`${center[0].toFixed(6)}, ${center[1].toFixed(6)}`);
        setFocus({ center, zoom: 16 });
        setLocated(true);
      },
      () => {
        setGeoLocating(false);
        setCreateError('Не удалось определить местоположение — разрешите доступ или введите адрес вручную.');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  };

  // Добавляет выбранные файлы к набору фото новой площадки (аддитивно, общий лимит).
  const handleNewFiles = (fileList: FileList | null, inputEl?: HTMLInputElement) => {
    setNewPhotoError(null);
    const resetInput = () => {
      if (inputEl) inputEl.value = '';
    };
    if (!fileList || fileList.length === 0) {
      resetInput();
      return;
    }
    const picked = Array.from(fileList);
    const fail = (msg: string) => {
      setNewPhotoError(msg);
      resetInput();
    };
    if (picked.some((f) => f.size > MAX_PHOTO_BYTES)) {
      fail('Каждое фото должно быть не больше 20 МБ.');
      return;
    }
    if (picked.some((f) => !ACCEPTED.test(f.name))) {
      fail('Допустимы только изображения: JPG, PNG или WEBP.');
      return;
    }
    if (newPhotos.length + picked.length > MAX_PHOTOS) {
      fail(`Можно прикрепить не более ${MAX_PHOTOS} фотографий.`);
      return;
    }
    setNewPhotos((cur) => [...cur, ...picked]);
    resetInput();
  };

  const removeNewAt = (index: number) => {
    setNewPhotoError(null);
    setNewPhotos((cur) => cur.filter((_, i) => i !== index));
  };

  // Сабмит новой площадки → POST /intake/mno → выбор созданного МНО в форму + закрытие.
  const handleCreateSubmit = async () => {
    if (creating) return;
    setCreateError(null);
    // Ханипот: заполнен → это бот. Тихо закрываем, ничего не создаём и не выбираем.
    if (hpRef.current?.value.trim()) {
      onClose();
      return;
    }
    const address = newAddress.trim();
    const coords = newCoords.trim();
    if (!address) {
      setCreateError('Укажите адрес площадки.');
      return;
    }
    if (!parseCoords(coords)) {
      setCreateError(
        'Укажите координаты: выберите адрес из подсказок, нажмите «Моё местоположение» или введите вручную «широта, долгота».',
      );
      return;
    }
    setCreating(true);
    try {
      const fd = new FormData();
      fd.append('address', address);
      fd.append('coords', coords);
      if (newName.trim()) fd.append('name', newName.trim());
      if (newCity.trim()) fd.append('city', newCity.trim());
      if (newComment.trim()) fd.append('comment', newComment.trim());
      // Ханипот: у человека всегда пусто (бэк молча дропнет при заполнении).
      fd.append('website', hpRef.current?.value ?? '');
      // Сжимаем фото в браузере перед отправкой (крупные телефонные фото иначе → 413).
      const prepared = await Promise.all(newPhotos.map((f) => compressImage(f)));
      for (const file of prepared) fd.append('photos', file);

      const created = await submitVolunteerMno(fd);
      onSelect({
        id: created.id,
        reg: created.reg,
        address: created.address,
        coords: created.coords,
        // region_name бэк резолвит по region_code; его у волонтёрской площадки нет,
        // поэтому для формы берём регион/город из выбранной DaData-подсказки.
        region: created.region_name || newRegion,
        city: created.city || newCity,
        name: created.name,
      });
      onClose();
    } catch (err) {
      setCreateError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  // Переключение в режим «создать»: сбрасываем ошибку, оставляем карту/фокус как есть.
  const goCreate = () => {
    setCreateError(null);
    setMode('create');
  };
  const goPick = () => {
    setCreateError(null);
    setMode('pick');
  };

  return (
    <div className="de-mnop-overlay" onMouseDown={onClose}>
      <div
        className="de-mnop-modal"
        role="dialog"
        aria-label="Выбор места накопления отходов"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="de-mnop-head">
          <h2 className="de-mnop-title">
            {mode === 'pick' ? 'Выбор места накопления отходов' : 'Новая площадка'}
          </h2>
          <button
            type="button"
            className="de-mnop-close"
            aria-label="Закрыть"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {mode === 'pick' ? (
          <div className="de-mnop-toolbar">
            <div className="de-mnop-search-wrap">
              <input
                type="text"
                className="de-mnop-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
                placeholder="Поиск по адресу — регион, город, улица…"
                autoComplete="off"
              />
              {showDropdown && (
                <div className="de-mnop-dropdown">
                  {suggestLoading && suggestions.length === 0 ? (
                    <div className="de-mnop-drop-empty">Поиск…</div>
                  ) : (
                    suggestions.map((s, i) => (
                      <button
                        key={`${s.value}-${i}`}
                        type="button"
                        className="de-mnop-suggest"
                        // onMouseDown — сработать до blur инпута (иначе список закроется).
                        onMouseDown={(ev) => {
                          ev.preventDefault();
                          handlePickAddress(s);
                        }}
                      >
                        {s.value}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={createPanelStyle}>
            {/* Адрес новой площадки (обязателен) — с DaData-подсказкой */}
            <div style={fieldStyle}>
              <span style={labelStyle}>Адрес площадки *</span>
              <div className="de-mnop-search-wrap">
                <input
                  type="text"
                  className="de-mnop-search"
                  value={newAddress}
                  onChange={(e) => setNewAddress(e.target.value)}
                  onFocus={() => setNewAddrFocused(true)}
                  onBlur={() => setNewAddrFocused(false)}
                  placeholder="Регион, город, улица, дом…"
                  autoComplete="off"
                />
                {showNewAddrDrop && (
                  <div className="de-mnop-dropdown">
                    {newAddrLoading && newAddrSug.length === 0 ? (
                      <div className="de-mnop-drop-empty">Поиск…</div>
                    ) : (
                      newAddrSug.map((s, i) => (
                        <button
                          key={`${s.value}-${i}`}
                          type="button"
                          className="de-mnop-suggest"
                          onMouseDown={(ev) => {
                            ev.preventDefault();
                            handlePickNewAddress(s);
                          }}
                        >
                          {s.value}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Координаты (обязательны): из подсказки / геолокации / вручную */}
            <div style={fieldStyle}>
              <span style={labelStyle}>Координаты *</span>
              <div style={rowStyle}>
                <input
                  type="text"
                  className="de-mnop-search"
                  style={{ flex: 1, minWidth: '180px' }}
                  value={newCoords}
                  onChange={(e) => setNewCoords(e.target.value)}
                  placeholder="55.751244, 37.618423"
                  autoComplete="off"
                />
                <button
                  type="button"
                  style={{ ...ghostBtnStyle, opacity: geoLocating ? 0.6 : 1 }}
                  onClick={useMyLocation}
                  disabled={geoLocating}
                >
                  <span aria-hidden>📍</span>
                  {geoLocating ? 'Определяем…' : 'Моё местоположение'}
                </button>
              </div>
              <span style={hintStyle}>
                Выберите адрес из подсказок или нажмите «Моё местоположение» — координаты подставятся.
              </span>
            </div>

            {/* Название (необязательно) */}
            <div style={fieldStyle}>
              <span style={labelStyle}>Название площадки</span>
              <input
                type="text"
                className="de-mnop-search"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Напр.: контейнерная площадка у дома 12"
                autoComplete="off"
              />
            </div>

            {/* Комментарий (необязательно) */}
            <div style={fieldStyle}>
              <span style={labelStyle}>Комментарий</span>
              <textarea
                className="de-mnop-search"
                style={{ resize: 'vertical', minHeight: '64px' }}
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Дополнительная информация о площадке"
                rows={2}
                maxLength={500}
              />
            </div>

            {/* Фото (необязательно) */}
            <div style={fieldStyle}>
              <span style={labelStyle}>Фото площадки (до 10, до 20 МБ)</span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => handleNewFiles(e.target.files, e.target)}
              />
              {newPhotoError && <span style={{ ...hintStyle, color: 'var(--error-fg)' }}>{newPhotoError}</span>}
              {newPreviews.length > 0 && (
                <div style={thumbsStyle}>
                  {newPreviews.map((url, i) => (
                    <div key={url} style={thumbWrapStyle}>
                      <img style={thumbStyle} src={url} alt={`Фото ${i + 1}`} />
                      <button
                        type="button"
                        style={thumbXStyle}
                        aria-label={`Удалить фото ${i + 1}`}
                        onClick={() => removeNewAt(i)}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Ханипот: скрыт от людей, ловит ботов */}
            <input
              ref={hpRef}
              type="text"
              name="website"
              style={hpStyle}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
            />
          </div>
        )}

        {mode === 'pick' && keyConfigured && geoStatus === 'pending' && (
          <div className="de-mnop-note">Определяем ваше местоположение…</div>
        )}
        {mode === 'pick' && keyConfigured && geoStatus === 'denied' && !located && (
          <div className="de-mnop-note de-mnop-note-warn">
            Геолокация выключена — введите улицу в поиск выше, чтобы найти площадки рядом.
          </div>
        )}

        <div className="de-mnop-mapwrap">
          <YandexMap
            className="de-mnop-map"
            points={displayPoints}
            focus={focus}
            onBoundsChange={handleBounds}
            onPointClick={handlePointClick}
          />
        </div>

        {mode === 'create' && createError && <div style={errStyle}>{createError}</div>}

        {mode === 'pick' ? (
          <div className="de-mnop-foot">
            {keyConfigured ? (
              <>
                Нажмите на точку площадки на карте, чтобы выбрать её.
                {pointsData?.capped && ' Показаны не все площадки — приблизьте карту.'}
              </>
            ) : (
              'Карта недоступна — заполните адрес вручную в форме.'
            )}
            <div style={{ marginTop: 'var(--space-3)' }}>
              <button type="button" style={switchBtnStyle} onClick={goCreate}>
                <span aria-hidden>➕</span> Моей площадки нет — добавить новую
              </button>
            </div>
          </div>
        ) : (
          <div style={footActionsStyle}>
            <button type="button" style={ghostBtnStyle} onClick={goPick} disabled={creating}>
              ← Назад к выбору
            </button>
            <button
              type="button"
              style={{ ...primaryBtnStyle, marginLeft: 'auto', opacity: creating ? 0.6 : 1 }}
              onClick={handleCreateSubmit}
              disabled={creating}
            >
              {creating ? 'Добавляем…' : 'Добавить площадку'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
