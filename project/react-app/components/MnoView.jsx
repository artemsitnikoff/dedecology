// ЭкоПульс — раздел «МНО» (места накопления отходов): список + карта + карточка + добавление
function MnoView({ mno, setMno, onToast }) {
  const { useState, useMemo } = React;
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [fRegion, setFRegion] = useState('');
  const [fSync, setFSync] = useState([]); // 'fgis' | 'manual'
  const [selected, setSelected] = useState([]);
  const [sub, setSub] = useState('list'); // 'list' | 'map'
  const [detailId, setDetailId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ name: '', reg: '', region: '63', city: '', address: '', coords: '' });

  const rn = de.regionName;
  const pill = (bg, fg) => ({ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap', background: bg, color: fg });
  const tab = (active) => ({ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 6, border: 0, cursor: 'pointer', font: 'inherit', fontSize: 12.5, fontWeight: 500, background: active ? '#fff' : 'transparent', color: active ? '#0F1620' : '#5B6573', boxShadow: active ? '0 1px 2px rgba(15,22,32,.08)' : 'none' });
  const field = { height: 38, width: '100%', border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 12px', font: 'inherit', fontSize: 13, color: '#0F1620', background: '#fff', outline: 'none', boxSizing: 'border-box' };
  const selectStyle = { height: 32, border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 10px', font: 'inherit', fontSize: 13, color: '#0F1620', background: '#fff', outline: 'none', minWidth: 210, cursor: 'pointer' };
  const mapGrid = "repeating-linear-gradient(0deg, transparent, transparent 47px, #E1E6EA 47px, #E1E6EA 48px), repeating-linear-gradient(90deg, transparent, transparent 47px, #E1E6EA 47px, #E1E6EA 48px)";

  const regionOpts = useMemo(() => {
    const codes = de.REGIONS.filter(r => mno.some(m => m.regionCode === r.code)).map(r => r.code);
    return codes.map(code => ({ code, label: rn(code) }));
  }, [mno]);

  const filtered = useMemo(() => {
    let list = mno.slice();
    const q = query.trim().toLowerCase();
    if (q) list = list.filter(m => (m.name + ' ' + m.reg + ' ' + rn(m.regionCode) + ' ' + m.city + ' ' + m.address + ' ' + m.coords + ' ' + (m.fgisId || '')).toLowerCase().includes(q));
    if (fRegion) list = list.filter(m => m.regionCode === fRegion);
    if (fSync.length) list = list.filter(m => fSync.includes(m.synced ? 'fgis' : 'manual'));
    const dir = sortDir === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      let av, bv;
      if (sortKey === 'reg') { av = a.reg; bv = b.reg; }
      else if (sortKey === 'region') { av = rn(a.regionCode); bv = rn(b.regionCode); }
      else if (sortKey === 'city') { av = a.city; bv = b.city; }
      else if (sortKey === 'address') { av = a.address; bv = b.address; }
      else { av = a.name; bv = b.name; }
      return av < bv ? -1 * dir : av > bv ? 1 * dir : 0;
    });
    return list;
  }, [mno, query, fRegion, fSync, sortKey, sortDir]);

  const map = useMemo(() => {
    if (!filtered.length) return { pins: [], bbox: '' };
    const lat = m => parseFloat(m.coords.split(',')[0]);
    const lng = m => parseFloat(m.coords.split(',')[1]);
    let minLat = Math.min(...filtered.map(lat)), maxLat = Math.max(...filtered.map(lat));
    let minLng = Math.min(...filtered.map(lng)), maxLng = Math.max(...filtered.map(lng));
    let latR = (maxLat - minLat) || 0.4, lngR = (maxLng - minLng) || 0.4;
    minLat -= latR * 0.16; maxLat += latR * 0.16; minLng -= lngR * 0.16; maxLng += lngR * 0.16;
    latR = maxLat - minLat; lngR = maxLng - minLng;
    const bbox = minLng.toFixed(4) + ', ' + minLat.toFixed(4) + ' … ' + maxLng.toFixed(4) + ', ' + maxLat.toFixed(4);
    const pins = filtered.map(m => ({ m, x: ((lng(m) - minLng) / lngR) * 100, y: (1 - (lat(m) - minLat) / latR) * 100, color: m.synced ? '#8D8D94' : '#1F8A5B' }));
    return { pins, bbox };
  }, [filtered]);

  const filterCount = (fRegion ? 1 : 0) + (fSync.length ? 1 : 0);
  const counterText = (filterCount || query) ? ('Показано ' + filtered.length + ' из ' + mno.length) : (mno.length + ' МНО · слой 5 ФГИС');
  const allSelected = filtered.length > 0 && filtered.every(m => selected.includes(m.id));
  const toggleSel = (id) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  const toggleSync = (v) => setFSync(prev => prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v]);
  const fmtDate = (s) => s ? s.slice(0, 10).split('-').reverse().join('.') : '—';

  const openDetail = (id) => { setDetailId(id); setDetailLoading(true); setTimeout(() => setDetailLoading(false), 620); };
  const doSync = () => {
    if (syncing) return;
    setSyncing(true);
    const total = mno.length, n = mno.filter(m => !m.synced).length;
    setTimeout(() => {
      const now = de.nowStr();
      setMno(prev => prev.map(m => ({ ...m, synced: true, syncDate: now })));
      setSyncing(false);
      onToast('Синхронизация с ФГИС завершена (слой 5). Получено ' + total + ' МНО' + (n ? ', новых отметок: ' + n : '') + '.');
    }, 1100);
  };
  const syncOne = (id) => setMno(prev => prev.map(m => m.id === id ? { ...m, synced: true, syncDate: de.nowStr() } : m));
  const submitAdd = () => {
    const name = form.name.trim(), coords = form.coords.trim();
    if (!name || !coords) { onToast('Укажите наименование и координаты МНО.'); return; }
    const m = { id: 'm' + Date.now(), reg: form.reg.trim() || '—', name, regionCode: form.region, city: form.city.trim(), address: form.address.trim() || '—', coords, synced: false, syncDate: '', incidents: 0, fgisId: '' };
    setMno(prev => [m, ...prev]);
    setAddOpen(false);
    setForm({ name: '', reg: '', region: '63', city: '', address: '', coords: '' });
    onToast('МНО добавлено вручную. Появится в ФГИС после синхронизации.');
  };

  const heads = [
    { key: 'reg', label: 'Реестровый №', w: 152 },
    { key: 'name', label: 'Наименование', flex: true },
    { key: 'region', label: 'Регион', w: 168 },
    { key: 'city', label: 'Город', w: 150 },
    { key: 'address', label: 'Адрес', w: 230 },
    { key: 'coords', label: 'Координаты', w: 150, nosort: true },
    { key: 'sync', label: 'Синхронизация', w: 146, nosort: true },
  ];
  const onSort = (key) => { setSortDir(prev => (sortKey === key && prev === 'asc') ? 'desc' : 'asc'); setSortKey(key); };
  const detail = detailId ? mno.find(m => m.id === detailId) : null;

  const Check = ({ on, onClick }) => (
    <div onClick={onClick} style={de.checkStyle(on)}>
      {on && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-11" /></svg>}
    </div>
  );
  const Pin = ({ width, color }) => (
    <svg width={width} height={width} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.4"><path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7z" fill={color || 'currentColor'} /><circle cx="12" cy="9" r="2.6" fill="#fff" stroke="none" /></svg>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Шапка */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 28px 9px', borderBottom: '1px solid #E6E9EC', flex: 'none' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, letterSpacing: '-0.015em' }}>Места накопления отходов</h1>
          <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 1 }}>{counterText}</div>
        </div>
        <div style={{ flex: 1 }} />
        <button className="de-btn" onClick={doSync} style={{ height: 34, padding: '0 14px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#0F1620', font: 'inherit', fontSize: 13, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer', opacity: syncing ? 0.65 : 1, pointerEvents: syncing ? 'none' : 'auto' }}>
          <svg className={syncing ? 'de-spin' : ''} width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7M21 4v4h-4" /></svg>
          {syncing ? 'Синхронизация…' : 'Синхронизировать с ФГИС'}
        </button>
        <button className="de-btn" onClick={() => setAddOpen(true)} style={{ height: 34, padding: '0 14px', borderRadius: 7, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
          Добавить МНО
        </button>
      </div>

      {/* Поиск + Список/Карта */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 28px', borderBottom: '1px solid #ECEFF2', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 11px', background: '#F8F9FB', border: '1px solid #E6E9EC', borderRadius: 8, width: 340 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#9AA3AE" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Поиск по наименованию, реестровому №, адресу…" style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: 'transparent', font: 'inherit', fontSize: 13, color: '#0F1620' }} />
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 3, padding: 3, background: '#F4F6F8', border: '1px solid #E6E9EC', borderRadius: 8 }}>
          <button className="de-btn" onClick={() => setSub('list')} style={tab(sub === 'list')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" /></svg>
            Список
          </button>
          <button className="de-btn" onClick={() => setSub('map')} style={tab(sub === 'map')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 4 3.6 5.8a1 1 0 0 0-.6.9V19a1 1 0 0 0 1.3 1L9 18.5l6 2 4.7-1.8a1 1 0 0 0 .6-.9V5a1 1 0 0 0-1.3-1L15 5.5z" /><path d="M9 4v14.5M15 5.5V20" /></svg>
            Карта
          </button>
        </div>
      </div>

      {/* Фильтры */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '8px 28px', borderBottom: '1px solid #ECEFF2', background: '#fff', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.04em', color: '#9AA3AE', fontWeight: 600 }}>Регион</span>
          <select value={fRegion} onChange={e => setFRegion(e.target.value)} style={selectStyle}>
            <option value="">Все регионы</option>
            {regionOpts.map(o => <option key={o.code} value={o.code}>{o.label}</option>)}
          </select>
        </div>
        <div style={{ width: 1, height: 20, background: '#ECEFF2' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.04em', color: '#9AA3AE', fontWeight: 600 }}>Синхронизация</span>
          {[{ v: 'fgis', label: 'ФГИС' }, { v: 'manual', label: 'Вручную' }].map(o => (
            <button key={o.v} className="de-chip" onClick={() => toggleSync(o.v)} style={de.chipStyle(fSync.includes(o.v))}>{o.label}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        {filterCount > 0 && (
          <button className="de-btn" onClick={() => { setFRegion(''); setFSync([]); }} style={{ height: 28, padding: '0 12px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#5B6573', font: 'inherit', fontSize: 12, cursor: 'pointer' }}>Сбросить</button>
        )}
      </div>

      {/* Bulk */}
      {selected.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 28px', background: '#EAF3FE', borderBottom: '1px solid #CFE2FB', flex: 'none', animation: 'deFade .12s ease' }}>
          <span style={{ fontSize: 13, color: '#1F7AE0', fontWeight: 600 }}>Выбрано: {selected.length}</span>
          <div style={{ width: 1, height: 16, background: '#CFE2FB' }} />
          <button className="de-btn" onClick={() => de.downloadMno(mno.filter(m => selected.includes(m.id)), 'МНО_ЭкоПульс_выбранные.csv')} style={{ height: 30, padding: '0 13px', borderRadius: 7, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 12.5, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
            Выгрузить в Excel
          </button>
          <div style={{ flex: 1 }} />
          <button className="de-btn" onClick={() => setSelected([])} style={{ height: 30, padding: '0 12px', borderRadius: 7, border: 0, background: 'transparent', color: '#5B6573', font: 'inherit', fontSize: 12.5, cursor: 'pointer' }}>Снять выделение</button>
        </div>
      )}

      {/* Контент: список */}
      {sub === 'list' && (
        <div className="de-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: '#fff' }}>
          {filtered.length > 0 ? (
            <div style={{ minWidth: 1282 }}>
              <div style={{ display: 'flex', alignItems: 'center', height: 40, background: '#F8F9FB', borderBottom: '1px solid #E6E9EC', position: 'sticky', top: 0, zIndex: 2, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', color: '#5B6573' }}>
                <div style={{ width: 46, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Check on={allSelected} onClick={() => setSelected(allSelected ? [] : filtered.map(m => m.id))} />
                </div>
                {heads.map(h => {
                  const on = !h.nosort && sortKey === h.key;
                  const st = { padding: '0 10px', cursor: h.nosort ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 6, height: '100%', color: on ? '#2A8AF0' : '#5B6573', whiteSpace: 'nowrap', userSelect: 'none' };
                  if (h.flex) { st.flex = 1; st.minWidth = 240; } else { st.width = h.w; st.flex = 'none'; }
                  return (
                    <div key={h.key} className="de-th" onClick={h.nosort ? undefined : () => onSort(h.key)} style={st}>
                      {h.label}
                      {!h.nosort && (
                        <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', lineHeight: 1 }}>
                          <span style={{ fontSize: 8, lineHeight: '8px', color: (on && sortDir === 'asc') ? '#2A8AF0' : '#C9CFD6' }}>▲</span>
                          <span style={{ fontSize: 8, lineHeight: '8px', color: (on && sortDir === 'desc') ? '#2A8AF0' : '#C9CFD6' }}>▼</span>
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
              {filtered.map(m => {
                const sel = selected.includes(m.id);
                return (
                  <div key={m.id} className="de-row" onClick={() => openDetail(m.id)} style={{ display: 'flex', alignItems: 'stretch', minHeight: 58, cursor: 'pointer', borderBottom: '1px solid #ECEFF2', background: sel ? '#EAF3FE' : (detailId === m.id ? '#F4F8FF' : '#fff') }}>
                    <div style={{ width: 46, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={e => { e.stopPropagation(); toggleSel(m.id); }}>
                      <Check on={sel} onClick={() => {}} />
                    </div>
                    <div style={{ width: 152, flex: 'none', padding: '0 10px', display: 'flex', alignItems: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, fontWeight: 600, color: '#5B6573' }}>{m.reg}</div>
                    <div style={{ flex: 1, minWidth: 240, padding: '0 10px', display: 'flex', alignItems: 'center', fontSize: 13, color: '#0F1620', fontWeight: 500, lineHeight: 1.35 }}>{m.name}</div>
                    <div style={{ width: 168, flex: 'none', padding: '0 10px', display: 'flex', alignItems: 'center', fontSize: 13, color: '#0F1620', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={rn(m.regionCode)}>{rn(m.regionCode)}</div>
                    <div style={{ width: 150, flex: 'none', padding: '0 10px', display: 'flex', alignItems: 'center', fontSize: 13, color: '#5B6573', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={m.city}>{m.city}</div>
                    <div style={{ width: 230, flex: 'none', padding: '0 10px', display: 'flex', alignItems: 'center', fontSize: 13, color: '#5B6573', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={m.address}>{m.address}</div>
                    <div style={{ width: 150, flex: 'none', padding: '0 10px', display: 'flex', alignItems: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, color: '#5B6573' }}>{m.coords}</div>
                    <div style={{ width: 146, flex: 'none', padding: '8px 10px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 3 }}>
                      <span style={pill(m.synced ? '#DEF5E5' : '#ECEFF2', m.synced ? '#128640' : '#5B6573')}><span style={de.dot(m.synced ? '#16A34A' : '#9AA3AE')} />{m.synced ? 'ФГИС' : 'Вручную'}</span>
                      <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10.5, color: '#9AA3AE' }}>{m.synced ? fmtDate(m.syncDate) : '—'}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: '80px 32px', textAlign: 'center' }}>
              <div style={{ width: 88, height: 88, borderRadius: '50%', background: '#DEF5E5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Pin width={40} color="#1F8A5B" /></div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>МНО не найдены</h3>
              <p style={{ margin: 0, maxWidth: 380, color: '#5B6573', fontSize: 13, lineHeight: 1.5 }}>Под заданные фильтры мест накопления отходов нет. Сбросьте фильтры или синхронизируйте список с ФГИС.</p>
              <button className="de-btn" onClick={() => { setFRegion(''); setFSync([]); }} style={{ height: 32, padding: '0 14px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', font: 'inherit', fontSize: 13, cursor: 'pointer' }}>Сбросить фильтры</button>
            </div>
          )}
        </div>
      )}

      {/* Контент: карта */}
      {sub === 'map' && (
        <div style={{ flex: 1, minHeight: 0, padding: '14px 28px 22px', display: 'flex' }}>
          <div style={{ flex: 1, position: 'relative', minHeight: 460, border: '1px solid #E6E9EC', borderRadius: 12, background: '#EEF2F5', backgroundImage: mapGrid, overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 12, top: 10, fontFamily: "'JetBrains Mono',monospace", fontSize: 10.5, color: '#9AA3AE', background: 'rgba(255,255,255,.7)', padding: '2px 7px', borderRadius: 6 }}>bbox · {map.bbox}</div>
            <div style={{ position: 'absolute', right: 12, top: 10, display: 'flex', gap: 6, zIndex: 6 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 26, padding: '0 10px', background: '#fff', border: '1px solid #E6E9EC', borderRadius: 7, fontSize: 11.5, fontWeight: 600, color: '#5B6573' }}><span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: '#2A8AF0' }} />Слой 5 · МНО</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', height: 26, padding: '0 10px', background: '#fff', border: '1px solid #E6E9EC', borderRadius: 7, fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, fontWeight: 600, color: '#5B6573' }}>z 8</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', height: 26, padding: '0 10px', background: '#0F1620', borderRadius: 7, fontSize: 11.5, fontWeight: 600, color: '#fff' }}>{filtered.length} точек</span>
            </div>
            <div style={{ position: 'absolute', left: 12, bottom: 12, display: 'flex', flexDirection: 'column', gap: 6, background: 'rgba(255,255,255,.85)', border: '1px solid #E6E9EC', borderRadius: 8, padding: '8px 11px', zIndex: 6 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 11.5, color: '#5B6573' }}><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: '#8D8D94' }} />Из ФГИС</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 11.5, color: '#5B6573' }}><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: '#1F8A5B' }} />Добавлено вручную</span>
            </div>
            {map.pins.map(p => (
              <div key={p.m.id} className="de-pin" onClick={() => openDetail(p.m.id)} style={{ position: 'absolute', left: p.x + '%', top: p.y + '%', transform: 'translate(-50%,-100%) scale(' + (detailId === p.m.id ? 1.22 : 1) + ')', color: p.color, zIndex: detailId === p.m.id ? 7 : 3 }}>
                <div className="de-pin-label" style={{ position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)', background: '#0F1620', color: '#fff', fontSize: 11, fontWeight: 500, padding: '3px 8px', borderRadius: 6, whiteSpace: 'nowrap', boxShadow: '0 4px 12px rgba(15,22,32,.2)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.m.name}</div>
                <Pin width={28} />
              </div>
            ))}
            {filtered.length === 0 && (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, textAlign: 'center', color: '#5B6573' }}>
                <Pin width={40} color="#9AA3AE" />
                <div style={{ fontSize: 14, fontWeight: 600, color: '#0F1620' }}>Нет точек на карте</div>
                <div style={{ fontSize: 12.5 }}>Сбросьте фильтры, чтобы увидеть все МНО.</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Карточка МНО */}
      {detail && (
        <div className="de-scroll de-mno-drawer" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 600, maxWidth: '92vw', zIndex: 70, background: '#fff', borderLeft: '1px solid #E6E9EC', boxShadow: '-18px 0 44px rgba(15,22,32,.16)', overflowY: 'auto' }}>
          {detailLoading ? (
            <div style={{ position: 'absolute', inset: 0, background: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, zIndex: 5 }}>
              <span className="de-mark-heart" style={{ fontSize: 48, lineHeight: 1 }}>💚</span>
              <span style={{ fontSize: 13.5, color: '#5B6573', fontWeight: 500 }}>Загрузка…</span>
            </div>
          ) : (
            <div style={{ animation: 'deFade .22s ease' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '20px 24px', borderBottom: '1px solid #ECEFF2', position: 'sticky', top: 0, background: '#fff', zIndex: 2 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: '#E7F7ED', color: '#128640' }}><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 6.5-9 12-9 12s-9-5.5-9-12a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="2.6" /></svg>МНО</span>
                    <span style={pill(detail.synced ? '#DEF5E5' : '#ECEFF2', detail.synced ? '#128640' : '#5B6573')}><span style={de.dot(detail.synced ? '#16A34A' : '#9AA3AE')} />{detail.synced ? 'Синхронизировано с ФГИС' : 'Добавлено вручную'}</span>
                    <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#5B6573', background: '#F4F6F8', padding: '2px 8px', borderRadius: 5 }}>№ {detail.reg}</span>
                  </div>
                  <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, lineHeight: 1.4 }}>{detail.name}</h2>
                  <div style={{ marginTop: 5, fontSize: 12.5, color: '#9AA3AE' }}>{rn(detail.regionCode)}</div>
                </div>
                <button onClick={() => setDetailId(null)} style={{ width: 32, height: 32, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
              </div>
              <div style={{ padding: '20px 24px' }}>
                <div style={{ position: 'relative', height: 132, borderRadius: 10, border: '1px solid #E6E9EC', background: '#EEF2F5', backgroundImage: mapGrid, overflow: 'hidden' }}>
                  <div style={{ position: 'absolute', left: '50%', top: '48%', transform: 'translate(-50%,-100%)', color: '#1F8A5B', filter: 'drop-shadow(0 4px 8px rgba(15,22,32,.22))' }}><Pin width={30} /></div>
                  <div style={{ position: 'absolute', left: 10, bottom: 9, display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#5B6573', background: 'rgba(255,255,255,.82)', padding: '3px 8px', borderRadius: 6 }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 6.5-9 12-9 12s-9-5.5-9-12a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="2.6" /></svg>{detail.coords}
                  </div>
                </div>
                <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column' }}>
                  {[
                    ['Наименование МНО', detail.name],
                    ['Реестровый номер', detail.reg],
                    ['Регион', rn(detail.regionCode)],
                    ['Город / н.п.', detail.city],
                    ['Адрес МНО', detail.address],
                    ['Координаты', detail.coords],
                    ['ID в ФГИС', detail.fgisId || '— (нет в ФГИС)'],
                    ['Синхронизация', detail.synced ? ('ФГИС, ' + detail.syncDate) : 'Добавлено вручную'],
                    ['Обращений по МНО', String(detail.incidents)],
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', gap: 14, padding: '11px 0', borderBottom: '1px dashed #ECEFF2' }}>
                      <div style={{ width: 180, flex: 'none', fontSize: 12.5, color: '#9AA3AE' }}>{f[0]}</div>
                      <div style={{ flex: 1, fontSize: 13.5, color: '#0F1620', fontWeight: 500, lineHeight: 1.45, wordBreak: 'break-word' }}>{f[1]}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 18, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  {!detail.synced && (
                    <button className="de-btn" onClick={() => syncOne(detail.id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, height: 38, padding: '0 16px', borderRadius: 8, border: '1px solid #B9E6C9', background: '#DEF5E5', color: '#128640', font: 'inherit', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7M21 4v4h-4" /></svg>
                      Синхронизировать с ФГИС
                    </button>
                  )}
                  {detail.incidents > 0 && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 38, padding: '0 14px', borderRadius: 8, background: '#FCE3E3', color: '#B83030', fontSize: 13, fontWeight: 600 }}>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" /></svg>
                      Обращений по МНО: {detail.incidents}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Модалка: добавить МНО */}
      {addOpen && (
        <div onClick={() => setAddOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(15,22,32,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'deFade .14s ease', padding: 24 }}>
          <div className="de-scroll" onClick={e => e.stopPropagation()} style={{ width: 560, maxWidth: '100%', maxHeight: '90vh', overflow: 'auto', background: '#fff', borderRadius: 12, boxShadow: '0 12px 32px rgba(15,22,32,.18)', animation: 'deUp .18s ease' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '18px 22px', borderBottom: '1px solid #ECEFF2', position: 'sticky', top: 0, background: '#fff', zIndex: 2 }}>
              <div style={{ flex: 1 }}>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Новое МНО</h2>
                <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 2 }}>Добавляется вручную, появится в ФГИС после синхронизации</div>
              </div>
              <button onClick={() => setAddOpen(false)} style={{ width: 30, height: 30, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
            </div>
            <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Field label="Наименование МНО"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Контейнерная площадка, ул. …" style={field} /></Field>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 180 }}><Field label="Реестровый номер"><input value={form.reg} onChange={e => setForm({ ...form, reg: e.target.value })} placeholder="63-04-000000" style={field} /></Field></div>
                <div style={{ flex: 1, minWidth: 180 }}><Field label="Регион"><select value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} style={field}>{de.REGIONS.filter(r => r.active).map(r => <option key={r.code} value={r.code}>{r.code} · {r.name}</option>)}</select></Field></div>
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 180 }}><Field label="Город / н.п."><input value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} placeholder="г. Кинель" style={field} /></Field></div>
                <div style={{ flex: 2, minWidth: 200 }}><Field label="Адрес МНО"><input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="ул. Маяковского, 41" style={field} /></Field></div>
              </div>
              <Field label="Координаты (широта, долгота)"><input value={form.coords} onChange={e => setForm({ ...form, coords: e.target.value })} placeholder="53.231410, 50.166820" style={field} /></Field>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', padding: '16px 22px', borderTop: '1px solid #ECEFF2', position: 'sticky', bottom: 0, background: '#fff' }}>
              <button className="de-btn" onClick={() => setAddOpen(false)} style={{ height: 38, padding: '0 16px', borderRadius: 8, border: '1px solid #E6E9EC', background: '#fff', color: '#5B6573', font: 'inherit', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>Отмена</button>
              <button className="de-btn" onClick={submitAdd} style={{ height: 38, padding: '0 18px', borderRadius: 8, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Добавить МНО</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  );
}
window.MnoView = MnoView;
