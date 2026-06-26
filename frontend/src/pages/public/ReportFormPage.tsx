import { useEffect, useMemo, useRef, useState } from 'react';
import { submitIntakeForm } from '@/api/intake';
import type { AddressSuggestion, SuggestOptions } from '@/api/intake';
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

/** Пропсы поля адреса с автодополнением (регион/город/улица). */
type AddressFieldProps = {
  label: string;
  required?: boolean;
  value: string;
  onChange: (value: string) => void;
  onPick: (s: AddressSuggestion) => void;
  opts: SuggestOptions;
  placeholder: string;
};

/**
 * Одно автодополняемое поле адреса. Хранит свой ввод (через value/onChange
 * родителя) + локальный «выбранный» текст: дропдаун показывается, только пока
 * поле в фокусе и текст отличается от уже выбранной подсказки. Свободный ввод
 * разрешён — пользователь может не выбирать подсказку (ручной ввод).
 */
function AddressField({ label, required, value, onChange, onPick, opts, placeholder }: AddressFieldProps) {
  const [picked, setPicked] = useState('');
  const [focused, setFocused] = useState(false);
  const enabled = focused && value !== picked;
  const { suggestions, loading } = useAddressSuggest(value, enabled, opts);
  const showDropdown = enabled && (suggestions.length > 0 || loading);

  const handlePick = (s: AddressSuggestion) => {
    setPicked(s.value);
    setFocused(false);
    onPick(s);
  };

  return (
    <label className="de-rf-field de-rf-field-addr">
      <span className="de-rf-label">
        {label} {required && <span className="de-rf-req">*</span>}
      </span>
      <input
        type="text"
        className="de-rf-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        autoComplete="off"
      />
      {showDropdown && (
        <div className="de-rf-dropdown">
          {loading && suggestions.length === 0 ? (
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
                  handlePick(s);
                }}
              >
                {s.value}
              </button>
            ))
          )}
        </div>
      )}
    </label>
  );
}

export default function ReportFormPage() {
  // --- Поля формы ---
  const [fio, setFio] = useState('');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [street, setStreet] = useState('');
  const [coords, setCoords] = useState('');
  const [photoTime, setPhotoTime] = useState(nowLocalDatetime);
  const [bins, setBins] = useState<Bins>('');
  const [photos, setPhotos] = useState<File[]>([]);
  const [photoError, setPhotoError] = useState<string | null>(null);

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

  // Выбор региона: при смене региона сбрасываем зависимые город/улицу.
  const handlePickRegion = (s: AddressSuggestion) => {
    if (s.value !== region) {
      setCity('');
      setStreet('');
    }
    setRegion(s.value);
  };

  const handlePickCity = (s: AddressSuggestion) => {
    setCity(s.value);
  };

  // Выбор улицы: подставляем координаты из geo (если есть), иначе готовые.
  const handlePickStreet = (s: AddressSuggestion) => {
    setStreet(s.value);
    const fromGeo = s.geo_lat && s.geo_lon ? `${s.geo_lat}, ${s.geo_lon}` : '';
    setCoords(fromGeo || s.coords || '');
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
    if (!region.trim()) {
      setSubmitError('Пожалуйста, укажите регион.');
      return;
    }
    if (!city.trim()) {
      setSubmitError('Пожалуйста, укажите город или населённый пункт.');
      return;
    }
    setSubmitError(null);
    setSubmitting(true);
    try {
      const fullAddress = [region.trim(), city.trim(), street.trim()]
        .filter(Boolean)
        .join(', ');
      const fd = new FormData();
      fd.append('fio', fio.trim());
      fd.append('full_address', fullAddress);
      fd.append('region', region.trim());
      fd.append('city', city.trim());
      fd.append('street', street.trim());
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

              {/* Регион с автодополнением */}
              <AddressField
                label="Регион"
                required
                value={region}
                onChange={setRegion}
                onPick={handlePickRegion}
                opts={{ kind: 'region' }}
                placeholder="Начните вводить регион…"
              />

              {/* Город / населённый пункт с автодополнением */}
              <AddressField
                label="Город / населённый пункт"
                required
                value={city}
                onChange={setCity}
                onPick={handlePickCity}
                opts={{ kind: 'city', region }}
                placeholder="Начните вводить город…"
              />

              {/* Улица, дом с автодополнением */}
              <AddressField
                label="Улица, дом"
                value={street}
                onChange={setStreet}
                onPick={handlePickStreet}
                opts={{ kind: 'street', region, city }}
                placeholder="Начните вводить улицу…"
              />

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
