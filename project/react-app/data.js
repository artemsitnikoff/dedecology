// ЭкоПульс — данные и хелперы (общий модуль, грузится до компонентов)
(function () {
  const STATUS = {
    new:      { label: 'Новый',              bg: '#EAF3FE', fg: '#1F7AE0', dot: '#2A8AF0', order: 0 },
    found:    { label: 'Инцидент обнаружен', bg: '#FCE3E3', fg: '#B83030', dot: '#DC4646', order: 1 },
    none:     { label: 'Нет инцидента',      bg: '#ECEFF2', fg: '#5B6573', dot: '#9AA3AE', order: 2 },
    exported: { label: 'Выгружен',           bg: '#DEF5E5', fg: '#128640', dot: '#16A34A', order: 3 },
  };
  const SOURCE = {
    max:  { label: 'Макс',         bg: '#ECE7FE', fg: '#7E5CF0' },
    form: { label: 'Яндекс форма', bg: '#FFF1C8', fg: '#B5821A' },
  };
  const NOW = new Date('2026-04-26T19:00:00');

  const INCIDENTS = [
    { id:'i01', source:'max',  status:'found', fio:'Громов Сергей Петрович', region:'Самарская область', city:'пгт Усть-Кинельский', street:'Бульварная улица, 18 (Радар №116320)', coords:'53.231410, 50.166820', photoTime:'25.04.2026, 09:14', photos:2, msg:'max-msg-116320', dateRaw:'2026-04-26 08:42' },
    { id:'i02', source:'form', status:'new',   fio:'Андреева Мария Игоревна', region:'Новгородская область', city:'Великий Новгород', street:'ул. Радужная, 15', coords:'55.859624, 37.663597', photoTime:'26.04.2026, 11:30', photos:3, msg:'', dateRaw:'2026-04-26 11:48' },
    { id:'i03', source:'max',  status:'new',   fio:'Сидоров Иван Алексеевич', region:'Самарская область', city:'г. Кинель', street:'ул. Маяковского, 41 (Радар №118044)', coords:'53.222900, 50.629100', photoTime:'26.04.2026, 08:05', photos:1, msg:'max-msg-118044', dateRaw:'2026-04-26 08:11' },
    { id:'i04', source:'form', status:'found', fio:'Кузнецова Ольга Дмитриевна', region:'Москва', city:'Зеленоград', street:'корпус 1462', coords:'55.991400, 37.214700', photoTime:'25.04.2026, 17:22', photos:3, msg:'', dateRaw:'2026-04-25 17:40' },
    { id:'i05', source:'max',  status:'none',  fio:'Морозов Дмитрий Олегович', region:'Самарская область', city:'с. Сырейка', street:'ул. Центральная, 7 (Радар №115980)', coords:'53.301200, 50.420000', photoTime:'24.04.2026, 14:48', photos:2, msg:'max-msg-115980', dateRaw:'2026-04-24 15:02' },
    { id:'i06', source:'form', status:'exported', fio:'Петров Алексей Юрьевич', region:'Санкт-Петербург', city:'Санкт-Петербург', street:'пр. Космонавтов, 28', coords:'59.852300, 30.350100', photoTime:'22.04.2026, 10:05', photos:2, msg:'', dateRaw:'2026-04-22 10:20' },
    { id:'i07', source:'max',  status:'found', fio:'Васильева Наталья Сергеевна', region:'Самарская область', city:'пгт Усть-Кинельский', street:'Спортивная улица, 4 (Радар №116401)', coords:'53.232000, 50.170300', photoTime:'26.04.2026, 07:51', photos:3, msg:'max-msg-116401', dateRaw:'2026-04-26 07:55' },
    { id:'i08', source:'form', status:'new',   fio:'Орлов Михаил Викторович', region:'Республика Татарстан', city:'Казань', street:'ул. Чистопольская, 61А', coords:'55.821700, 49.111300', photoTime:'26.04.2026, 12:40', photos:1, msg:'', dateRaw:'2026-04-26 12:51' },
    { id:'i09', source:'max',  status:'exported', fio:'Зайцева Екатерина Павловна', region:'Самарская область', city:'г. Кинель', street:'ул. 27 Партсъезда, 1Б (Радар №117210)', coords:'53.220100, 50.638400', photoTime:'21.04.2026, 16:18', photos:2, msg:'max-msg-117210', dateRaw:'2026-04-21 16:30' },
    { id:'i10', source:'form', status:'none',  fio:'Лебедев Артём Романович', region:'Нижегородская область', city:'Нижний Новгород', street:'ул. Бекетова, 13', coords:'56.288800, 43.991200', photoTime:'23.04.2026, 09:36', photos:2, msg:'', dateRaw:'2026-04-23 09:50' },
    { id:'i11', source:'max',  status:'found', fio:'Соколова Анна Витальевна', region:'Самарская область', city:'пос. Алексеевка', street:'ул. Невская, 22 (Радар №116770)', coords:'53.181000, 50.020500', photoTime:'26.04.2026, 06:42', photos:3, msg:'max-msg-116770', dateRaw:'2026-04-26 06:48' },
    { id:'i12', source:'form', status:'new',   fio:'Никитин Павел Андреевич', region:'Свердловская область', city:'Екатеринбург', street:'ул. Сулимова, 38', coords:'56.851200, 60.617900', photoTime:'25.04.2026, 19:10', photos:2, msg:'', dateRaw:'2026-04-25 19:22' },
    { id:'i13', source:'max',  status:'exported', fio:'Фёдорова Юлия Олеговна', region:'Самарская область', city:'г. Кинель', street:'ул. Фестивальная, 9 (Радар №117905)', coords:'53.225600, 50.641000', photoTime:'20.04.2026, 13:27', photos:1, msg:'max-msg-117905', dateRaw:'2026-04-20 13:35' },
  ];

  function initials(name) { const p = name.split(/\s+/); return ((p[0] || '')[0] || '') + ((p[1] || '')[0] || ''); }
  function dateShort(raw) { const a = raw.split(' '); const d = a[0].split('-'); return d[2] + '.' + d[1] + ' · ' + a[1]; }
  function photoParts(pt) {
    const parts = pt.split(','); const date = (parts[0] || '').trim(); const time = (parts[1] || '').trim();
    const dm = date.split('.');
    const ts = dm.length === 3 ? new Date(+dm[2], +dm[1] - 1, +dm[0], +(time.split(':')[0] || 0), +(time.split(':')[1] || 0)).getTime() : 0;
    return { date, time, ts };
  }
  function inPeriod(raw, period) {
    if (period === 'all') return true;
    const dt = new Date(raw.replace(' ', 'T')); const days = (NOW - dt) / 86400000;
    if (period === 'today') return days < 1;
    if (period === 'week') return days < 7;
    if (period === 'month') return days < 31;
    return true;
  }
  function regionOf(a) { return (a.split(',')[0] || '').trim(); }
  function fullAddr(d) { return d.region + ', ' + d.city + ', ' + d.street; }
  function messageLink(d) { return d.source === 'max' ? ('https://max.ru/m/' + d.msg) : '#'; }
  function photoSrcs(d) {
    const imgs = (typeof window !== 'undefined' && window.__DE_IMGS) || [];
    if (!imgs.length) return [];
    const n = Math.max(1, Math.min(d.photos, 3));
    const off = (d.id.charCodeAt(2) || 0) % imgs.length;
    const arr = [];
    for (let i = 0; i < n; i++) arr.push(imgs[(off + i) % imgs.length]);
    return arr;
  }

  // ---- стили-хелперы ----
  function dot(color) { return { display: 'inline-block', width: '7px', height: '7px', borderRadius: '50%', background: color, flex: 'none' }; }
  function pill(meta) { return { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '3px 9px', borderRadius: '5px', fontSize: '11px', fontWeight: 600, whiteSpace: 'nowrap', background: meta.bg, color: meta.fg }; }
  function pillStatus(k) { return pill(STATUS[k]); }
  function pillSource(k) { return pill(SOURCE[k]); }
  function chipStyle(active) {
    return { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 11px', borderRadius: '999px', cursor: 'pointer', font: 'inherit', fontSize: '12.5px', fontWeight: active ? 600 : 500, background: active ? '#EAF3FE' : '#fff', border: '1px solid ' + (active ? '#CFE2FB' : '#E6E9EC'), color: active ? '#2A8AF0' : '#0F1620', transition: 'all .12s ease' };
  }
  function checkStyle(sel) {
    return { width: '18px', height: '18px', flex: 'none', borderRadius: '5px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', background: sel ? '#2A8AF0' : '#fff', border: '1.5px solid ' + (sel ? '#2A8AF0' : '#C9CFD6'), transition: 'all .1s ease' };
  }

  function toCsv(rows) {
    const cols = [
      ['ФИО', d => d.fio],
      ['Источник', d => SOURCE[d.source].label],
      ['Статус', d => STATUS[d.status].label],
      ['Регион', d => d.region],
      ['Город / н.п.', d => d.city],
      ['Адрес (улица)', d => d.street],
      ['Полный адрес', d => fullAddr(d)],
      ['Координаты', d => d.coords],
      ['Дата фотофиксации', d => photoParts(d.photoTime).date],
      ['Время фотофиксации', d => photoParts(d.photoTime).time],
      ['Кол-во фото', d => String(d.photos)],
      ['Ссылка на сообщение', d => d.source === 'max' ? ('https://max.ru/m/' + d.msg) : ''],
      ['Поступило', d => d.dateRaw],
    ];
    const esc = v => '"' + String(v).replace(/"/g, '""') + '"';
    const head = cols.map(c => esc(c[0])).join(';');
    const body = rows.map(r => cols.map(c => esc(c[1](r))).join(';')).join('\r\n');
    return '\uFEFF' + head + '\r\n' + body;
  }
  function download(rows, name) {
    if (!rows.length) return;
    const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    document.body.removeChild(a); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  window.de = {
    STATUS, SOURCE, INCIDENTS, NOW,
    initials, dateShort, photoParts, inPeriod, regionOf, fullAddr, messageLink, photoSrcs,
    dot, pillStatus, pillSource, chipStyle, checkStyle, download,
  };
})();
