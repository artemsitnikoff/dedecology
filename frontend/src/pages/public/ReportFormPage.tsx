import { useEffect, useMemo, useRef, useState } from 'react';
import { submitIntakeForm } from '@/api/intake';
import type { AddressSuggestion } from '@/api/intake';
import { useAddressSuggest } from './useAddressSuggest';
import './report-form.css';

// Публичная страница обращения о состоянии площадки ТКО. Открывается по ссылке
// без авторизации, без сайдбара (standalone). Дизайн адаптирован из публичного
// опроса Глафиры: центрированная карточка на мягком фоне + бренд-шапка.

const MAX_PHOTOS = 3;
const MAX_PHOTO_BYTES = 10 * 1024 * 1024; // 10 МБ
const ACCEPTED = /\.(jpe?g|png|webp)$/i;

type Bins = '' | 'yes' | 'no';

/** Текущее локальное время в формате datetime-local (YYYY-MM-DDTHH:mm). */
function nowLocalDatetime(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/** Достаём человекочитаемое сообщение из конверта ошибки API. */
function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'error' in err) {
    const env = (err as { error?: { message?: string } }).error;
    if (env?.message) return env.message;
  }
  return 'Не удалось отправить обращение. Попробуйте ещё раз.';
}

export default function ReportFormPage() {
  // --- Поля формы ---
  const [fio, setFio] = useState('');
  const [addr, setAddr] = useState('');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [street, setStreet] = useState('');
  const [coords, setCoords] = useState('');
  const [photoTime, setPhotoTime] = useState(nowLocalDatetime);
  const [bins, setBins] = useState<Bins>('');
  const [photos, setPhotos] = useState<File[]>([]);
  const [photoError, setPhotoError] = useState<string | null>(null);

  // --- Автодополнение адреса ---
  const [pickedValue, setPickedValue] = useState('');
  const [addrFocused, setAddrFocused] = useState(false);
  const suggestEnabled = addrFocused && addr !== pickedValue;
  const { suggestions, loading: suggestLoading } = useAddressSuggest(addr, suggestEnabled);
  const showDropdown = suggestEnabled && (suggestions.length > 0 || suggestLoading);

  // --- Ханипот (заполняют боты; человек не видит) ---
  const websiteRef = useRef<HTMLInputElement>(null);

  // --- Отправка ---
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Превью фото через object URL; чистим, когда набор файлов меняется.
  const previews = useMemo(() => photos.map((f) => URL.createObjectURL(f)), [photos]);
  useEffect(() => {
    return () => previews.forEach((url) => URL.revokeObjectURL(url));
  }, [previews]);

  const handlePickSuggestion = (s: AddressSuggestion) => {
    setAddr(s.value);
    setPickedValue(s.value);
    setRegion(s.region);
    setCity(s.city);
    setStreet(s.street);
    // Координаты собираем из geo_lat/geo_lon (если есть), иначе берём готовые.
    const fromGeo = s.geo_lat && s.geo_lon ? `${s.geo_lat}, ${s.geo_lon}` : '';
    setCoords(fromGeo || s.coords || '');
    setAddrFocused(false);
  };

  const handleFiles = (fileList: FileList | null, inputEl?: HTMLInputElement) => {
    setPhotoError(null);
    if (!fileList || fileList.length === 0) {
      setPhotos([]);
      return;
    }
    const next = Array.from(fileList);
    // При любой ошибке валидации сбрасываем набор и сам инпут — чтобы нельзя было
    // отправить ранее принятые фото при показанной ошибке.
    const fail = (msg: string) => {
      setPhotoError(msg);
      setPhotos([]);
      if (inputEl) inputEl.value = '';
    };
    if (next.length > MAX_PHOTOS) {
      fail(`Можно прикрепить не более ${MAX_PHOTOS} фотографий.`);
      return;
    }
    if (next.some((f) => f.size > MAX_PHOTO_BYTES)) {
      fail('Каждое фото должно быть не больше 10 МБ.');
      return;
    }
    if (next.some((f) => !ACCEPTED.test(f.name))) {
      fail('Допустимы только изображения: JPG, PNG или WEBP.');
      return;
    }
    setPhotos(next);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!fio.trim()) {
      setSubmitError('Пожалуйста, укажите ФИО.');
      return;
    }
    if (!addr.trim()) {
      setSubmitError('Пожалуйста, укажите адрес площадки.');
      return;
    }
    setSubmitError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('fio', fio.trim());
      fd.append('full_address', addr.trim());
      fd.append('region', region);
      fd.append('city', city);
      fd.append('street', street);
      fd.append('coords', coords.trim());
      fd.append('photo_time', photoTime || '');
      fd.append('bins', bins);
      // Ханипот: у человека всегда пусто. Если бот заполнил — бэк молча дропнет.
      fd.append('website', websiteRef.current?.value ?? '');
      for (const file of photos) fd.append('photos', file);

      await submitIntakeForm(fd);
      setDone(true);
    } catch (err) {
      setSubmitError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="de-rf-bg">
      <div className="de-rf-card">
        <div className="de-rf-brandbar" />
        {done ? (
          <div className="de-rf-thanks">
            <div className="de-rf-thanks-emoji">🌳</div>
            <h2>Спасибо!</h2>
            <p>Обращение принято и передано инспектору.</p>
          </div>
        ) : (
          <form className="de-rf-form" onSubmit={handleSubmit} noValidate>
            <div className="de-rf-header">
              <div className="de-rf-brand">
                <span className="de-rf-brand-emoji" aria-hidden>
                  👴
                </span>
                <span className="de-rf-brand-name">ДедЭколог</span>
              </div>
              <h1 className="de-rf-title">Сообщить о состоянии площадки ТКО</h1>
              <p className="de-rf-sub">
                Заполните форму — мы передадим обращение инспектору и проверим площадку.
              </p>
            </div>

            <div className="de-rf-fields">
              {/* ФИО */}
              <label className="de-rf-field">
                <span className="de-rf-label">
                  ФИО <span className="de-rf-req">*</span>
                </span>
                <input
                  type="text"
                  className="de-rf-input"
                  value={fio}
                  onChange={(e) => setFio(e.target.value)}
                  placeholder="Иванов Иван Иванович"
                  autoComplete="name"
                />
              </label>

              {/* Адрес с автодополнением */}
              <label className="de-rf-field de-rf-field-addr">
                <span className="de-rf-label">
                  Адрес площадки <span className="de-rf-req">*</span>
                </span>
                <input
                  type="text"
                  className="de-rf-input"
                  value={addr}
                  onChange={(e) => setAddr(e.target.value)}
                  onFocus={() => setAddrFocused(true)}
                  onBlur={() => setAddrFocused(false)}
                  placeholder="Начните вводить адрес…"
                  autoComplete="off"
                />
                {showDropdown && (
                  <div className="de-rf-dropdown">
                    {suggestLoading && suggestions.length === 0 ? (
                      <div className="de-rf-dropdown-empty">Поиск…</div>
                    ) : (
                      suggestions.map((s, i) => (
                        <button
                          key={`${s.value}-${i}`}
                          type="button"
                          className="de-rf-suggest"
                          // onMouseDown — чтобы клик сработал до blur инпута.
                          onMouseDown={(ev) => {
                            ev.preventDefault();
                            handlePickSuggestion(s);
                          }}
                        >
                          {s.value}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </label>

              {/* Координаты */}
              <label className="de-rf-field">
                <span className="de-rf-label">Координаты</span>
                <input
                  type="text"
                  className="de-rf-input de-rf-mono"
                  value={coords}
                  onChange={(e) => setCoords(e.target.value)}
                  placeholder="55.751244, 37.618423"
                  autoComplete="off"
                />
              </label>

              {/* Время фотофиксации */}
              <label className="de-rf-field">
                <span className="de-rf-label">Время фотофиксации</span>
                <input
                  type="datetime-local"
                  className="de-rf-input"
                  value={photoTime}
                  onChange={(e) => setPhotoTime(e.target.value)}
                />
              </label>

              {/* Баки раздельного сбора */}
              <div className="de-rf-field">
                <span className="de-rf-label">Баки раздельного сбора</span>
                <div className="de-rf-chips">
                  {([
                    { v: 'yes', label: 'Есть' },
                    { v: 'no', label: 'Нет' },
                  ] as const).map((o) => (
                    <button
                      key={o.v}
                      type="button"
                      className={`de-rf-chip ${bins === o.v ? 'active' : ''}`}
                      onClick={() => setBins((cur) => (cur === o.v ? '' : o.v))}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Фото */}
              <div className="de-rf-field">
                <span className="de-rf-label">Фото площадки (до 3, до 10 МБ)</span>
                <input
                  type="file"
                  className="de-rf-file"
                  accept="image/*"
                  multiple
                  onChange={(e) => handleFiles(e.target.files, e.target)}
                />
                {photoError && <span className="de-rf-inline-err">{photoError}</span>}
                {previews.length > 0 && (
                  <div className="de-rf-thumbs">
                    {previews.map((url, i) => (
                      <img key={url} className="de-rf-thumb" src={url} alt={`Фото ${i + 1}`} />
                    ))}
                  </div>
                )}
              </div>

              {/* Ханипот: скрыт от людей, ловит ботов */}
              <input
                ref={websiteRef}
                type="text"
                name="website"
                className="de-rf-hp"
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
              />
            </div>

            {submitError && <div className="de-rf-error">{submitError}</div>}

            <button type="submit" className="de-rf-submit" disabled={submitting}>
              {submitting ? 'Отправляем…' : 'Отправить'}
            </button>
            <div className="de-rf-foot">ДедЭколог · забота о чистоте</div>
          </form>
        )}
      </div>
    </div>
  );
}
