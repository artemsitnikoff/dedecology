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
    { id:'i01', source:'max',  status:'found', fio:'Громов Сергей Петрович', phone:'+7 927 614-22-08', region:'Самарская область', city:'пгт Усть-Кинельский', street:'Бульварная улица, 18 (Радар №116320)', coords:'53.231410, 50.166820', photoTime:'25.04.2026, 09:14', photos:2, msg:'max-msg-116320', dateRaw:'2026-04-26 08:42' },
    { id:'i02', source:'form', status:'new',   fio:'Андреева Мария Игоревна', phone:'+7 911 700-31-45', region:'Новгородская область', city:'Великий Новгород', street:'ул. Радужная, 15', coords:'55.859624, 37.663597', photoTime:'26.04.2026, 11:30', photos:3, msg:'', dateRaw:'2026-04-26 11:48' },
    { id:'i03', source:'max',  status:'new',   fio:'Сидоров Иван Алексеевич', phone:'+7 927 330-18-72', region:'Самарская область', city:'г. Кинель', street:'ул. Маяковского, 41 (Радар №118044)', coords:'53.222900, 50.629100', photoTime:'26.04.2026, 08:05', photos:1, msg:'max-msg-118044', dateRaw:'2026-04-26 08:11' },
    { id:'i04', source:'form', status:'found', fio:'Кузнецова Ольга Дмитриевна', phone:'+7 916 245-09-63', region:'Москва', city:'Зеленоград', street:'корпус 1462', coords:'55.991400, 37.214700', photoTime:'25.04.2026, 17:22', photos:3, msg:'', dateRaw:'2026-04-25 17:40' },
    { id:'i05', source:'max',  status:'none',  fio:'Морозов Дмитрий Олегович', phone:'+7 937 512-44-19', region:'Самарская область', city:'с. Сырейка', street:'ул. Центральная, 7 (Радар №115980)', coords:'53.301200, 50.420000', photoTime:'24.04.2026, 14:48', photos:2, msg:'max-msg-115980', dateRaw:'2026-04-24 15:02' },
    { id:'i06', source:'form', status:'exported', fio:'Петров Алексей Юрьевич', phone:'+7 921 158-77-30', region:'Санкт-Петербург', city:'Санкт-Петербург', street:'пр. Космонавтов, 28', coords:'59.852300, 30.350100', photoTime:'22.04.2026, 10:05', photos:2, msg:'', dateRaw:'2026-04-22 10:20' },
    { id:'i07', source:'max',  status:'found', fio:'Васильева Наталья Сергеевна', phone:'+7 927 880-15-26', region:'Самарская область', city:'пгт Усть-Кинельский', street:'Спортивная улица, 4 (Радар №116401)', coords:'53.232000, 50.170300', photoTime:'26.04.2026, 07:51', photos:3, msg:'max-msg-116401', dateRaw:'2026-04-26 07:55' },
    { id:'i08', source:'form', status:'new',   fio:'Орлов Михаил Викторович', phone:'+7 917 390-62-51', region:'Республика Татарстан', city:'Казань', street:'ул. Чистопольская, 61А', coords:'55.821700, 49.111300', photoTime:'26.04.2026, 12:40', photos:1, msg:'', dateRaw:'2026-04-26 12:51' },
    { id:'i09', source:'max',  status:'exported', fio:'Зайцева Екатерина Павловна', phone:'+7 937 204-88-13', region:'Самарская область', city:'г. Кинель', street:'ул. 27 Партсъезда, 1Б (Радар №117210)', coords:'53.220100, 50.638400', photoTime:'21.04.2026, 16:18', photos:2, msg:'max-msg-117210', dateRaw:'2026-04-21 16:30' },
    { id:'i10', source:'form', status:'none',  fio:'Лебедев Артём Романович', phone:'+7 920 611-47-95', region:'Нижегородская область', city:'Нижний Новгород', street:'ул. Бекетова, 13', coords:'56.288800, 43.991200', photoTime:'23.04.2026, 09:36', photos:2, msg:'', dateRaw:'2026-04-23 09:50' },
    { id:'i11', source:'max',  status:'found', fio:'Соколова Анна Витальевна', phone:'+7 927 145-53-67', region:'Самарская область', city:'пос. Алексеевка', street:'ул. Невская, 22 (Радар №116770)', coords:'53.181000, 50.020500', photoTime:'26.04.2026, 06:42', photos:3, msg:'max-msg-116770', dateRaw:'2026-04-26 06:48' },
    { id:'i12', source:'form', status:'new',   fio:'Никитин Павел Андреевич', phone:'+7 922 776-20-44', region:'Свердловская область', city:'Екатеринбург', street:'ул. Сулимова, 38', coords:'56.851200, 60.617900', photoTime:'25.04.2026, 19:10', photos:2, msg:'', dateRaw:'2026-04-25 19:22' },
    { id:'i13', source:'max',  status:'exported', fio:'Фёдорова Юлия Олеговна', phone:'+7 937 901-36-58', region:'Самарская область', city:'г. Кинель', street:'ул. Фестивальная, 9 (Радар №117905)', coords:'53.225600, 50.641000', photoTime:'20.04.2026, 13:27', photos:1, msg:'max-msg-117905', dateRaw:'2026-04-20 13:35' },
  ];

  // ===== Справочник: федеральные округа (нумерация как в ФГИС) =====
  const FED = {
    1: { code: 'ЦФО',  name: 'Центральный' },
    2: { code: 'СЗФО', name: 'Северо-Западный' },
    3: { code: 'ЮФО',  name: 'Южный' },
    4: { code: 'СКФО', name: 'Северо-Кавказский' },
    5: { code: 'ПФО',  name: 'Приволжский' },
    6: { code: 'УФО',  name: 'Уральский' },
    7: { code: 'СФО',  name: 'Сибирский' },
    8: { code: 'ДФО',  name: 'Дальневосточный' },
  };

  // ===== Справочник: Регионы (субъекты РФ). code = код субъекта = regionId в ФГИС =====
  const REGIONS = [
    { code:'63', name:'Самарская область',    fed:5, operators:['ЭкоСтройРесурс'], active:true, lastSync:'2026-04-26 06:30' },
    { code:'77', name:'Москва',               fed:1, operators:['ГБУ «Экотехпром»','МКМ-Логистика','Хартия','МСК-НТ'], active:true, lastSync:'2026-04-25 07:00' },
    { code:'78', name:'Санкт-Петербург',      fed:2, operators:['Невский экологический оператор'], active:true, lastSync:'2026-04-22 09:00' },
    { code:'16', name:'Республика Татарстан', fed:5, operators:['УК «ПЖКХ»','Гринта'], active:true, lastSync:'2026-04-24 08:00' },
    { code:'52', name:'Нижегородская область',fed:5, operators:['«Нижэкология-НН»','Реал-Кстово','МСК-НТ'], active:true, lastSync:'2026-04-23 08:00' },
    { code:'66', name:'Свердловская область', fed:6, operators:['«Спецавтобаза»','Рифей','ТБО «Экосервис»'], active:true, lastSync:'2026-04-25 10:00' },
    { code:'53', name:'Новгородская область', fed:2, operators:['«Спецавтохозяйство»'], active:true, lastSync:'2026-04-20 06:00' },
    { code:'73', name:'Ульяновская область',  fed:5, operators:[], active:false, lastSync:'' },
  ];

  // ===== МНО — места накопления отходов (слой 5 ФГИС) =====
  const MNO = [
    { id:'m01', reg:'63-04-001162', name:'Контейнерная площадка, ул. Бульварная, 18',    regionCode:'63', city:'пгт Усть-Кинельский', address:'Бульварная улица, 18',    coords:'53.231410, 50.166820', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'02e29deb-1aa8-4949-a1c2-8db71252acb6' },
    { id:'m02', reg:'63-04-001180', name:'Контейнерная площадка, ул. Маяковского, 41',    regionCode:'63', city:'г. Кинель',          address:'ул. Маяковского, 41',    coords:'53.222900, 50.629100', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'1b6f3c20-7d11-4a8e-9f02-2c44a1e6b730' },
    { id:'m03', reg:'63-04-000159', name:'Контейнерная площадка, ул. Центральная, 7',     regionCode:'63', city:'с. Сырейка',         address:'ул. Центральная, 7',     coords:'53.301200, 50.420000', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'9c7a44e1-0b53-4f6d-8a21-6e9d0c12fa84' },
    { id:'m04', reg:'63-04-001164', name:'Контейнерная площадка, ул. Спортивная, 4',      regionCode:'63', city:'пгт Усть-Кинельский', address:'Спортивная улица, 4',    coords:'53.232000, 50.170300', synced:false, syncDate:'',                 incidents:1, fgisId:'4d2e8810-5a6b-4c3d-b1f7-7a0e9d551c22' },
    { id:'m05', reg:'63-04-001172', name:'Контейнерная площадка, ул. 27 Партсъезда, 1Б',  regionCode:'63', city:'г. Кинель',          address:'ул. 27 Партсъезда, 1Б',  coords:'53.220100, 50.638400', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'7f10a3b9-2c84-49e1-a6d3-0b5f8e44d910' },
    { id:'m06', reg:'63-04-001167', name:'Контейнерная площадка, ул. Невская, 22',        regionCode:'63', city:'пос. Алексеевка',    address:'ул. Невская, 22',        coords:'53.181000, 50.020500', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'a3c91f57-6d20-4b8a-9e14-3f7c2d60ab85' },
    { id:'m07', reg:'63-04-001179', name:'Контейнерная площадка, ул. Фестивальная, 9',    regionCode:'63', city:'г. Кинель',          address:'ул. Фестивальная, 9',    coords:'53.225600, 50.641000', synced:true,  syncDate:'2026-04-26 06:30', incidents:1, fgisId:'c5e07b42-8a19-4d63-b2f0-1e9a4c87d536' },
    { id:'m08', reg:'63-04-001181', name:'Контейнерная площадка, ул. Украинская, 3',      regionCode:'63', city:'г. Кинель',          address:'ул. Украинская, 3',      coords:'53.228000, 50.632000', synced:true,  syncDate:'2026-04-26 06:30', incidents:0, fgisId:'e81d2a64-3f57-4c90-a7b1-5d0e6b29f413' },
    { id:'m09', reg:'63-04-001165', name:'Контейнерная площадка, ул. Шоссейная, 12',      regionCode:'63', city:'пгт Усть-Кинельский', address:'Шоссейная улица, 12',    coords:'53.236000, 50.158000', synced:true,  syncDate:'2026-04-26 06:30', incidents:0, fgisId:'6b4f9c07-1e83-42da-90c5-8a2d7f015e6b' },
    { id:'m10', reg:'77-18-004521', name:'Контейнерная площадка, корпус 1462',            regionCode:'77', city:'Зеленоград',         address:'корпус 1462',            coords:'55.991400, 37.214700', synced:true,  syncDate:'2026-04-25 07:00', incidents:1, fgisId:'d7a3e510-9b26-4f81-8c04-2e6b1a93c7d8' },
    { id:'m11', reg:'78-06-002210', name:'Контейнерная площадка, пр. Космонавтов, 28',    regionCode:'78', city:'Санкт-Петербург',    address:'пр. Космонавтов, 28',    coords:'59.852300, 30.350100', synced:true,  syncDate:'2026-04-22 09:00', incidents:1, fgisId:'0f5c8b21-7a40-4e63-9d12-4b8e0a6f3c95' },
    { id:'m12', reg:'16-01-003344', name:'Контейнерная площадка, ул. Чистопольская, 61А', regionCode:'16', city:'Казань',            address:'ул. Чистопольская, 61А', coords:'55.821700, 49.111300', synced:false, syncDate:'',                 incidents:1, fgisId:'b29d4e76-5c81-403a-8f25-7a1c6d09e482' },
    { id:'m13', reg:'52-01-002901', name:'Контейнерная площадка, ул. Бекетова, 13',       regionCode:'52', city:'Нижний Новгород',    address:'ул. Бекетова, 13',       coords:'56.288800, 43.991200', synced:true,  syncDate:'2026-04-23 08:00', incidents:1, fgisId:'38e1c9a0-6b47-4d52-91f8-0c5a2e74b613' },
    { id:'m14', reg:'66-01-005012', name:'Контейнерная площадка, ул. Сулимова, 38',       regionCode:'66', city:'Екатеринбург',      address:'ул. Сулимова, 38',       coords:'56.851200, 60.617900', synced:true,  syncDate:'2026-04-25 10:00', incidents:1, fgisId:'5a0b7f33-2d68-4c19-a8e4-9f1d6037b285' },
    { id:'m15', reg:'53-01-000412', name:'Контейнерная площадка, ул. Радужная, 15',       regionCode:'53', city:'Великий Новгород',   address:'ул. Радужная, 15',       coords:'58.521800, 31.275000', synced:false, syncDate:'',                 incidents:1, fgisId:'91c46de8-0a72-4b35-86f1-3d8e2a5c049b' },
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
      ['ID', d => d.id.toUpperCase()],
      ['ФИО', d => d.fio],
      ['Телефон', d => d.phone],
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

  // ---- МНО / регионы ----
  function regionName(code) { const r = REGIONS.find(x => x.code === code); return r ? r.name : code; }
  function mnoToCsv(rows) {
    const cols = [
      ['Реестровый номер', m => m.reg],
      ['Наименование', m => m.name],
      ['Регион', m => regionName(m.regionCode)],
      ['Город / н.п.', m => m.city],
      ['Адрес', m => m.address],
      ['Координаты', m => m.coords],
      ['ФГИС-ID', m => m.fgisId || ''],
      ['Синхронизация', m => m.synced ? ('ФГИС, ' + m.syncDate) : 'Добавлено вручную'],
      ['Обращений по МНО', m => String(m.incidents)],
    ];
    const esc = v => '"' + String(v).replace(/"/g, '""') + '"';
    const head = cols.map(c => esc(c[0])).join(';');
    const body = rows.map(r => cols.map(c => esc(c[1](r))).join(';')).join('\r\n');
    return '\uFEFF' + head + '\r\n' + body;
  }
  function downloadMno(rows, name) {
    if (!rows.length) return;
    const blob = new Blob([mnoToCsv(rows)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    document.body.removeChild(a); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function nowStr() {
    const d = NOW, p = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  window.de = {
    STATUS, SOURCE, INCIDENTS, NOW, FED, REGIONS, MNO,
    initials, dateShort, photoParts, inPeriod, regionOf, fullAddr, messageLink, photoSrcs,
    regionName, nowStr,
    dot, pillStatus, pillSource, chipStyle, checkStyle, download, mnoToCsv, downloadMno,
  };
})();
