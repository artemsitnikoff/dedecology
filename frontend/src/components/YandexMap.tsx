import { useEffect, useRef, useState } from 'react';
import { isYandexKeyConfigured, loadYmaps } from '@/lib/yandexMaps';
import type { YFeature, YMap, YObjectManager } from '@/lib/yandexMaps';
import './YandexMap.css';

/** Точка на карте: id (уникальный), координаты «lat, lon» текстом, необязательная подпись. */
export type MapPoint = {
  id: string;
  coords: string;
  label?: string;
};

type Props = {
  points: MapPoint[];
  className?: string;
  /**
   * Вызывается при смене видимой области карты (с дебаунсом ~400мс) и один раз при
   * инициализации — чтобы страница узнала стартовый кадр. bbox в порядке
   * [minLat, minLon, maxLat, maxLon]. Наличие пропа включает «viewport-режим»:
   * страница догружает точки текущего кадра.
   */
  onBoundsChange?: (bbox: [number, number, number, number]) => void;
};

/**
 * Парсит строку координат «lat, lon» → [широта, долгота] (порядок Яндекса).
 * В БД coords хранится именно как «широта, долгота», поэтому берём как есть.
 * Некорректные/пустые значения → null (такие точки пропускаются).
 */
function parseCoords(raw: string): [number, number] | null {
  const parts = raw.split(',');
  if (parts.length < 2) return null;
  const lat = Number(parts[0].trim());
  const lon = Number(parts[1].trim());
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lat, lon];
}

/**
 * Настоящая Яндекс.Карта (JS API 2.1) с кластеризацией точек через ObjectManager.
 *
 * Если ключ Yandex Maps не задан на этапе сборки (VITE_YANDEX_MAPS_KEY) или скрипт
 * не загрузился — честно рендерит плашку «Карта недоступна…», без фейковых пинов.
 * Карта инициализируется один раз; при смене `points` ObjectManager пересобирается.
 */
export function YandexMap({ points, className, onBoundsChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<YMap | null>(null);
  const omRef = useRef<YObjectManager | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // Последний onBoundsChange держим в ref: слушатель события навешивается один раз при
  // инициализации карты, а проп меняется на каждом рендере страницы (стрелка).
  const onBoundsChangeRef = useRef(onBoundsChange);
  useEffect(() => {
    onBoundsChangeRef.current = onBoundsChange;
  });

  // Таймер дебаунса boundschange (чистится в cleanup и перед каждым новым событием).
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Авто-подгон вида под точки делаем ТОЛЬКО ОДИН РАЗ — иначе setBounds → boundschange →
  // refetch → снова подгон зациклится (в viewport-режиме).
  const fittedOnce = useRef(false);

  const configured = isYandexKeyConfigured();

  // Инициализация карты — один раз (ключ задаётся на этапе сборки, при рантайме не меняется).
  useEffect(() => {
    if (!configured) return;
    let cancelled = false;
    let mapInstance: YMap | null = null;

    // Отдаёт текущую область карты странице (порядок [minLat, minLon, maxLat, maxLon]).
    const emitBounds = (map: YMap) => {
      const cb = onBoundsChangeRef.current;
      if (!cb) return;
      const bounds = map.getBounds();
      if (!bounds) return;
      const [[minLat, minLon], [maxLat, maxLon]] = bounds;
      cb([minLat, minLon, maxLat, maxLon]);
    };
    // boundschange прилетает часто (во время зума/панорамы) — дебаунсим ~400мс.
    const handleBoundsChange = () => {
      const map = mapRef.current;
      if (!map) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => emitBounds(map), 400);
    };

    loadYmaps()
      .then((ymaps) => {
        if (cancelled || !containerRef.current) return;
        const map = new ymaps.Map(containerRef.current, {
          center: [61, 90], // примерный центр РФ
          zoom: 3,
          controls: ['zoomControl'],
        });
        const om = new ymaps.ObjectManager({
          clusterize: true,
          gridSize: 64,
          clusterDisableClickZoom: false,
        });
        map.geoObjects.add(om);
        mapRef.current = map;
        omRef.current = om;
        mapInstance = map;
        // Подписка на смену видимой области (догрузка точек по кадру).
        map.events.add('boundschange', handleBoundsChange);
        setReady(true);
        // Стартовый bbox — сразу (без дебаунса), чтобы страница узнала первый кадр.
        emitBounds(map);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      setReady(false);
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      if (mapInstance) mapInstance.events.remove('boundschange', handleBoundsChange);
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
        omRef.current = null;
      }
    };
  }, [configured]);

  // Пересборка точек ObjectManager при смене набора (или после готовности карты).
  useEffect(() => {
    const map = mapRef.current;
    const om = omRef.current;
    if (!ready || !map || !om) return;

    om.removeAll();
    const features: YFeature[] = [];
    for (const p of points) {
      const coordinates = parseCoords(p.coords);
      if (!coordinates) continue; // пропускаем некорректные/пустые координаты
      const label = p.label ?? '';
      features.push({
        type: 'Feature',
        id: p.id,
        geometry: { type: 'Point', coordinates },
        properties: { balloonContent: label, hintContent: label },
      });
    }
    om.add({ type: 'FeatureCollection', features });

    // Подгоняем вид под точки ТОЛЬКО ОДИН РАЗ — при первом непустом наборе. Дальше не
    // трогаем вид: иначе setBounds → boundschange → refetch → подгон зациклится.
    if (features.length > 0 && !fittedOnce.current) {
      const bounds = map.geoObjects.getBounds();
      if (bounds) {
        map.setBounds(bounds, { checkZoomRange: true });
        fittedOnce.current = true;
      }
    }
  }, [points, ready]);

  if (!configured || failed) {
    const text = !configured
      ? 'Карта недоступна: не задан ключ Yandex Maps (VITE_YANDEX_MAPS_KEY).'
      : 'Карта недоступна: не удалось загрузить Яндекс.Карты. Попробуйте обновить страницу.';
    return (
      <div className={`de-ymap-fallback ${className ?? ''}`}>
        <div className="de-ymap-fallback-inner">
          <div className="de-ymap-fallback-title">Карта недоступна</div>
          <div>{text}</div>
        </div>
      </div>
    );
  }

  return <div ref={containerRef} className={`de-ymap ${className ?? ''}`} />;
}
