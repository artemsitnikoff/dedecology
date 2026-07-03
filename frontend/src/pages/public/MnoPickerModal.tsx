import { useEffect, useMemo, useState } from 'react';
import { YandexMap } from '@/components/YandexMap';
import type { MapFocus, MapPoint } from '@/components/YandexMap';
import { isYandexKeyConfigured } from '@/lib/yandexMaps';
import type { AddressSuggestion } from '@/api/intake';
import type { MnoFormPoint } from '@/api/aliases';
import { useAddressSuggest } from './useAddressSuggest';
import { useMnoFormPoints } from './useMnoFormPoints';
import './mno-picker.css';

// Модалка выбора места накопления отходов (МНО) на карте — для публичной формы.
// Геолокация браузера центрирует карту рядом с пользователем и подгружает точки
// МНО текущего кадра; клик по точке подставляет в форму адрес + координаты +
// рег-номер. Без геолокации — поиск адреса (DaData) двигает карту на найденную
// точку. Нет ключа карты → внутри YandexMap честная плашка (без фейков).

/** Данные выбранного МНО, которые модалка отдаёт форме. */
export type MnoPick = {
  /** UUID МНО — уходит в инцидент ссылкой на объект ТКО (Incident.mno_id). */
  id: string;
  reg: string;
  address: string;
  coords: string;
  region: string;
  city: string;
};

type Props = {
  /** Клик по точке МНО → подстановка в форму (и закрытие модалки). */
  onSelect: (mno: MnoPick) => void;
  /** Закрыть модалку (крестик / фон / Esc). */
  onClose: () => void;
};

/** Статус запроса геолокации браузера. */
type GeoStatus = 'pending' | 'ok' | 'denied';

const SUGGEST_MIN_LEN = 3;

/** «lat, lon» текстом → [широта, долгота] или null (для координат из подсказки). */
function parseCoords(raw: string): [number, number] | null {
  const parts = raw.split(',');
  if (parts.length < 2) return null;
  const lat = Number(parts[0].trim());
  const lon = Number(parts[1].trim());
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lat, lon];
}

export function MnoPickerModal({ onSelect, onClose }: Props) {
  const keyConfigured = isYandexKeyConfigured();

  // Геолокацию спрашиваем только если карта вообще доступна (иначе прок нет — плашка).
  const [geoStatus, setGeoStatus] = useState<GeoStatus>(
    keyConfigured ? 'pending' : 'denied',
  );
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [bbox, setBbox] = useState<string | null>(null);
  // located — есть ли у нас точка отсчёта (геолокация ИЛИ выбранный адрес). До этого
  // не грузим точки: иначе первый (общероссийский) кадр даст лишний запрос.
  const [located, setLocated] = useState(false);

  // Поиск адреса (когда геолокация недоступна / для навигации по карте).
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const suggestEnabled = searchFocused && search.trim().length >= SUGGEST_MIN_LEN;
  const { suggestions, loading: suggestLoading } = useAddressSuggest(
    search,
    suggestEnabled,
    { kind: 'full', count: 6 },
  );
  const showDropdown = suggestEnabled && (suggestions.length > 0 || suggestLoading);

  // Точки МНО текущего кадра (публичный эндпоинт). Гасим, пока не определились с локацией.
  const { data: pointsData } = useMnoFormPoints(bbox, { enabled: located });

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

  // Смена видимого кадра карты → перезапрос точек (когда локация определена).
  const handleBounds = (b: [number, number, number, number]) => {
    setBbox(b.join(','));
  };

  // Клик по точке МНО → подстановка в форму + закрытие.
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
    });
    onClose();
  };

  // Выбор подсказки адреса → центрируем карту на её координатах и грузим МНО рядом.
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

  return (
    <div className="de-mnop-overlay" onMouseDown={onClose}>
      <div
        className="de-mnop-modal"
        role="dialog"
        aria-label="Выбор места накопления отходов"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="de-mnop-head">
          <h2 className="de-mnop-title">Выбор места накопления отходов</h2>
          <button
            type="button"
            className="de-mnop-close"
            aria-label="Закрыть"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

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

        {keyConfigured && geoStatus === 'pending' && (
          <div className="de-mnop-note">Определяем ваше местоположение…</div>
        )}
        {keyConfigured && geoStatus === 'denied' && !located && (
          <div className="de-mnop-note de-mnop-note-warn">
            Геолокация выключена — введите улицу в поиск выше, чтобы найти площадки рядом.
          </div>
        )}

        <div className="de-mnop-mapwrap">
          <YandexMap
            className="de-mnop-map"
            points={mapPoints}
            focus={focus}
            onBoundsChange={handleBounds}
            onPointClick={handlePointClick}
          />
        </div>

        <div className="de-mnop-foot">
          {keyConfigured ? (
            <>
              Нажмите на точку площадки на карте, чтобы выбрать её.
              {pointsData?.capped && ' Показаны не все площадки — приблизьте карту.'}
            </>
          ) : (
            'Карта недоступна — заполните адрес вручную в форме.'
          )}
        </div>
      </div>
    </div>
  );
}
