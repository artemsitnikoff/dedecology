import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { submitIntakeForm } from '@/api/intake';
import type { AddressSuggestion, SuggestOptions } from '@/api/intake';
import { useIncidentTypes } from '@/api/hooks/useIncidentTypes';
import { useAddressSuggest } from './useAddressSuggest';
import { MnoPickerModal } from './MnoPickerModal';
import type { MnoPick } from './MnoPickerModal';
import { compressImage } from '@/lib/image';
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
  // Справочник типов инцидента для дропдауна (публичный, без auth).
  const { data: incidentTypes = [] } = useIncidentTypes();

  // --- Поля формы ---
  const [fio, setFio] = useState('');
  const [incidentType, setIncidentType] = useState('');
  const [comment, setComment] = useState('');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [street, setStreet] = useState('');
  const [coords, setCoords] = useState('');
  // Рег-номер выбранного на карте МНО (необязательный) + флаг открытия модалки.
  const [mnoReg, setMnoReg] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  // Голые имена выбранного региона/города (без типа) — для фильтрации
  // следующего уровня в DaData (locations матчит "Самарская", а не "Самарская обл").
  const [regionPlain, setRegionPlain] = useState('');
  const [cityPlain, setCityPlain] = useState('');
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
  const [quote, setQuote] = useState('');

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
      setCityPlain('');
    }
    setRegion(s.value);
    setRegionPlain(s.region_plain || s.region || '');
  };

  const handlePickCity = (s: AddressSuggestion) => {
    setCity(s.value);
    setCityPlain(s.city_plain || s.city || '');
  };

  // Выбор улицы: подставляем координаты из geo (если есть), иначе готовые.
  const handlePickStreet = (s: AddressSuggestion) => {
    setStreet(s.value);
    const fromGeo = s.geo_lat && s.geo_lon ? `${s.geo_lat}, ${s.geo_lon}` : '';
    setCoords(fromGeo || s.coords || '');
  };

  // Выбор МНО на карте: адрес МНО → «Улица, дом», координаты и рег-номер — в форму.
  // Колбэки стабильны (useCallback) — модалка рендерится только пока открыта.
  const openPicker = useCallback(() => setPickerOpen(true), []);
  const closePicker = useCallback(() => setPickerOpen(false), []);
  const handleMnoSelect = useCallback((m: MnoPick) => {
    setStreet(m.address);
    setCoords(m.coords);
    setMnoReg(m.reg);
  }, []);
  const clearMno = () => setMnoReg('');

  // Добавляет только что выбранные файлы к уже набранным (аддитивно), с общим
  // лимитом MAX_PHOTOS. Это позволяет прикреплять фото по одному в несколько
  // заходов — без сброса предыдущего выбора. По завершении инпут очищается,
  // чтобы можно было снова выбрать тот же/новый файл в новом диалоге.
  const handleFiles = (fileList: FileList | null, inputEl?: HTMLInputElement) => {
    setPhotoError(null);
    // Очистить инпут в любом случае: набор файлов держим в state, а не в DOM.
    const resetInput = () => {
      if (inputEl) inputEl.value = '';
    };
    if (!fileList || fileList.length === 0) {
      resetInput();
      return;
    }
    const picked = Array.from(fileList);
    const fail = (msg: string) => {
      setPhotoError(msg);
      // Существующий набор НЕ трогаем — пользователь не теряет ранее добавленное.
      resetInput();
    };
    if (picked.some((f) => f.size > MAX_PHOTO_BYTES)) {
      fail('Каждое фото должно быть не больше 10 МБ.');
      return;
    }
    if (picked.some((f) => !ACCEPTED.test(f.name))) {
      fail('Допустимы только изображения: JPG, PNG или WEBP.');
      return;
    }
    if (photos.length + picked.length > MAX_PHOTOS) {
      fail(`Можно прикрепить не более ${MAX_PHOTOS} фотографий.`);
      return;
    }
    setPhotos((cur) => [...cur, ...picked]);
    resetInput();
  };

  // Удаляет одно фото из набора по индексу (иммутабельно).
  const removeAt = (index: number) => {
    setPhotoError(null);
    setPhotos((cur) => cur.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!fio.trim()) {
      setSubmitError('Пожалуйста, укажите заявителя.');
      return;
    }
    if (!incidentType) {
      setSubmitError('Пожалуйста, выберите тип инцидента.');
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
    if (!street.trim()) {
      setSubmitError('Пожалуйста, укажите улицу и дом.');
      return;
    }
    if (!coords.trim()) {
      setSubmitError('Пожалуйста, укажите координаты (подставятся при выборе улицы из подсказок).');
      return;
    }
    if (!comment.trim()) {
      setSubmitError('Пожалуйста, заполните комментарий.');
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
      fd.append('incident_type', incidentType);
      fd.append('comment', comment.trim());
      fd.append('full_address', fullAddress);
      fd.append('region', region.trim());
      fd.append('city', city.trim());
      fd.append('street', street.trim());
      fd.append('coords', coords.trim());
      // Рег-номер выбранного МНО (необязательный; пусто → бэк трактует как «не выбрано»).
      fd.append('mno_reg', mnoReg.trim());
      fd.append('photo_time', photoTime || '');
      fd.append('bins', bins);
      // Ханипот: у человека всегда пусто. Если бот заполнил — бэк молча дропнет.
      fd.append('website', websiteRef.current?.value ?? '');
      // Сжимаем фото в браузере перед отправкой (крупные телефонные фото иначе → 413).
      // Сервер всё равно делает финальный ресайз; при сбое сжатия шлём оригинал.
      const prepared = await Promise.all(photos.map((f) => compressImage(f)));
      for (const file of prepared) fd.append('photos', file);

      const res = await submitIntakeForm(fd);
      setQuote(res.quote ?? '');
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
            {quote && <p className="de-rf-quote">{quote}</p>}
          </div>
        ) : (
          <form className="de-rf-form" onSubmit={handleSubmit} noValidate>
            <div className="de-rf-header">
              <div className="de-rf-brand">
                <span className="de-rf-brand-emoji" aria-hidden>
                  💚
                </span>
                <span className="de-rf-brand-name">ЭкоПульс</span>
              </div>
              <h1 className="de-rf-title">Сообщить о состоянии площадки ТКО</h1>
              <p className="de-rf-sub">
                Заполните форму — мы передадим обращение инспектору и проверим площадку.
              </p>
            </div>

            <div className="de-rf-fields">
              {/* Заявитель */}
              <label className="de-rf-field">
                <span className="de-rf-label">
                  Заявитель <span className="de-rf-req">*</span>
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
                opts={{ kind: 'city', region: regionPlain }}
                placeholder="Начните вводить город…"
              />

              {/* Выбор МНО на карте (перед адресом): подставляет улицу + координаты + рег-номер */}
              <div className="de-rf-field">
                <button type="button" className="de-rf-mno-btn" onClick={openPicker}>
                  <span aria-hidden>📍</span> Выбрать МНО на карте
                </button>
                {mnoReg && (
                  <div className="de-rf-mno-chip">
                    <span className="de-rf-mno-chip-txt">
                      Выбрано МНО: <b className="de-rf-mono">{mnoReg}</b>
                    </span>
                    <button
                      type="button"
                      className="de-rf-mno-chip-x"
                      aria-label="Сбросить выбор МНО"
                      onClick={clearMno}
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>

              {/* Улица, дом с автодополнением */}
              <AddressField
                label="Улица, дом"
                required
                value={street}
                onChange={setStreet}
                onPick={handlePickStreet}
                opts={{ kind: 'street', region: regionPlain, city: cityPlain }}
                placeholder="Начните вводить улицу…"
              />

              {/* Координаты */}
              <label className="de-rf-field">
                <span className="de-rf-label">
                  Координаты <span className="de-rf-req">*</span>
                </span>
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

              {/* Тип инцидента — обязательный выбор из справочника (перед комментарием) */}
              <label className="de-rf-field">
                <span className="de-rf-label">
                  Тип инцидента <span className="de-rf-req">*</span>
                </span>
                <select
                  className="de-rf-input de-rf-select"
                  value={incidentType}
                  onChange={(e) => setIncidentType(e.target.value)}
                >
                  <option value="" disabled>
                    Выберите тип инцидента…
                  </option>
                  {incidentTypes.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>

              {/* Комментарий — обязательная прочая информация */}
              <label className="de-rf-field">
                <span className="de-rf-label">
                  Комментарий <span className="de-rf-req">*</span>
                </span>
                <textarea
                  className="de-rf-input de-rf-textarea"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Опишите проблему: что не так, ориентиры и т.п."
                  rows={3}
                />
              </label>

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
                <span className="de-rf-hint">Можно добавлять по одной, до 3</span>
                {photoError && <span className="de-rf-inline-err">{photoError}</span>}
                {previews.length > 0 && (
                  <div className="de-rf-thumbs">
                    {previews.map((url, i) => (
                      <div key={url} className="de-rf-thumb-wrap">
                        <img className="de-rf-thumb" src={url} alt={`Фото ${i + 1}`} />
                        <button
                          type="button"
                          className="de-rf-thumb-x"
                          aria-label={`Удалить фото ${i + 1}`}
                          onClick={() => removeAt(i)}
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
            <div className="de-rf-foot">ЭкоПульс · забота о чистоте</div>
          </form>
        )}
      </div>

      {/* Модалка выбора МНО на карте (оверлей поверх формы) */}
      {pickerOpen && (
        <MnoPickerModal onSelect={handleMnoSelect} onClose={closePicker} />
      )}
    </div>
  );
}
