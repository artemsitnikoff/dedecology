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
export function YandexMap({ points, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<YMap | null>(null);
  const omRef = useRef<YObjectManager | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  const configured = isYandexKeyConfigured();

  // Инициализация карты — один раз (ключ задаётся на этапе сборки, при рантайме не меняется).
  useEffect(() => {
    if (!configured) return;
    let cancelled = false;

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
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      setReady(false);
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

    // Подгоняем вид под точки (если они есть и границы посчитались).
    if (features.length > 0) {
      const bounds = map.geoObjects.getBounds();
      if (bounds) map.setBounds(bounds, { checkZoomRange: true });
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
