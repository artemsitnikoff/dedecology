// ЭкоПульс — корневой компонент (классический React + ReactDOM.createRoot)
function App() {
  const { useState, useMemo, useRef } = React;

  const [data, setData] = useState(de.INCIDENTS.map(d => ({ ...d })));
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [view, setView] = useState('incidents');
  const [fSources, setFSources] = useState([]);
  const [fStatuses, setFStatuses] = useState([]);
  const [fFrom, setFFrom] = useState('');
  const [fTo, setFTo] = useState('');
  const [selected, setSelected] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [pulseId, setPulseId] = useState(null);
  const [detailTop, setDetailTop] = useState(170);
  const [detailLoading, setDetailLoading] = useState(false);
  const scrollRef = useRef(null);
  const [lb, setLb] = useState(null); // { id, idx }

  const openDetail = (id) => {
    const top = scrollRef.current ? Math.round(scrollRef.current.getBoundingClientRect().top) : 170;
    setDetailTop(top);
    setDetailLoading(true);
    setDetailId(id);
    setPulseId(id);
    setTimeout(() => setPulseId(p => (p === id ? null : p)), 850);
    setTimeout(() => setDetailLoading(false), 720);
  };

  const onSort = (key) => {
    setSortDir(prev => (sortKey === key && prev === 'desc') ? 'asc' : 'desc');
    setSortKey(key);
  };
  const toggleSelect = (id) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  const setStatus = (id, status) => setData(prev => prev.map(d => d.id === id ? { ...d, status } : d));

  const filtered = useMemo(() => {
    let list = data.slice();
    const q = query.trim().toLowerCase();
    if (q) list = list.filter(d => (d.fio + ' ' + d.region + ' ' + d.city + ' ' + d.street + ' ' + d.coords + ' ' + d.msg).toLowerCase().includes(q));
    if (fSources.length) list = list.filter(d => fSources.includes(d.source));
    if (fStatuses.length) list = list.filter(d => fStatuses.includes(d.status));
    if (fFrom) { const from = new Date(fFrom + 'T00:00:00').getTime(); list = list.filter(d => de.photoParts(d.photoTime).ts >= from); }
    if (fTo) { const to = new Date(fTo + 'T23:59:59').getTime(); list = list.filter(d => de.photoParts(d.photoTime).ts <= to); }
    const dir = sortDir === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      let av, bv;
      if (sortKey === 'region') { av = a.region; bv = b.region; }
      else if (sortKey === 'city') { av = a.city; bv = b.city; }
      else if (sortKey === 'address') { av = a.street; bv = b.street; }
      else if (sortKey === 'source') { av = de.SOURCE[a.source].label; bv = de.SOURCE[b.source].label; }
      else if (sortKey === 'status') { av = de.STATUS[a.status].order; bv = de.STATUS[b.status].order; }
      else { av = de.photoParts(a.photoTime).ts; bv = de.photoParts(b.photoTime).ts; } // date | time
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    return list;
  }, [data, query, fSources, fStatuses, fFrom, fTo, sortKey, sortDir]);

  const filterCount = (fSources.length ? 1 : 0) + (fStatuses.length ? 1 : 0) + ((fFrom || fTo) ? 1 : 0);
  const hasFilters = filterCount > 0;
  const allSelected = filtered.length > 0 && filtered.every(d => selected.includes(d.id));
  const resetFilters = () => { setFSources([]); setFStatuses([]); setFFrom(''); setFTo(''); };
  const detail = detailId ? data.find(d => d.id === detailId) : null;
  const lbInc = lb ? data.find(d => d.id === lb.id) : null;

  const exportSelected = () => de.download(data.filter(d => selected.includes(d.id)), 'Инциденты_ЭкоПульс_выбранные.csv');
  const exportAll = () => de.download(filtered, 'Инциденты_ЭкоПульс.csv');
  const markExported = () => { setData(prev => prev.map(d => selected.includes(d.id) ? { ...d, status: 'exported' } : d)); setSelected([]); };

  const lbStep = (delta) => setLb(prev => {
    if (!prev) return prev;
    const inc = data.find(d => d.id === prev.id);
    const n = de.photoSrcs(inc).length || 1;
    return { id: prev.id, idx: (prev.idx + delta + n) % n };
  });

  const counterText = (filterCount || query)
    ? ('Показано ' + filtered.length + ' из ' + data.length)
    : (data.length + ' обращений · обновлено сегодня');

  return (
    <div style={{ display: 'flex', height: '100vh', minWidth: 1100, overflow: 'hidden', background: '#fff' }}>
      <Sidebar total={data.length} view={view} onNav={setView} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
        {view === 'settings' ? <Settings /> : <React.Fragment>
        {/* Шапка */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 28px 9px', borderBottom: '1px solid #E6E9EC', flex: 'none' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, letterSpacing: '-0.015em' }}>Инциденты</h1>
            <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 1 }}>{counterText}</div>
          </div>
          <div style={{ flex: 1 }} />
          <button className="de-btn" onClick={exportAll} style={{ height: 34, padding: '0 14px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#0F1620', font: 'inherit', fontSize: 13, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
            Выгрузить всё
          </button>
        </div>

        {/* Поиск */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 28px', borderBottom: '1px solid #ECEFF2', flex: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 11px', background: '#F8F9FB', border: '1px solid #E6E9EC', borderRadius: 8, width: 300 }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#9AA3AE" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Поиск по адресу, ФИО, координатам…" style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: 'transparent', font: 'inherit', fontSize: 13, color: '#0F1620' }} />
          </div>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: '#9AA3AE' }}>Сортировка — по клику на заголовок столбца</span>
        </div>

        <Funnel fStatuses={fStatuses} setFStatuses={setFStatuses} incidents={data} />
        <FilterBar fSources={fSources} setFSources={setFSources} fFrom={fFrom} setFFrom={setFFrom} fTo={fTo} setFTo={setFTo} hasFilters={hasFilters} onReset={resetFilters} />

        {/* Панель массовых действий */}
        {selected.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 28px', background: '#EAF3FE', borderBottom: '1px solid #CFE2FB', flex: 'none', animation: 'deFade .12s ease' }}>
            <span style={{ fontSize: 13, color: '#1F7AE0', fontWeight: 600 }}>Выбрано: {selected.length}</span>
            <div style={{ width: 1, height: 16, background: '#CFE2FB' }} />
            <button className="de-btn" onClick={exportSelected} style={{ height: 30, padding: '0 13px', borderRadius: 7, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 12.5, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
              Выгрузить в Excel
            </button>
            <button className="de-btn" onClick={markExported} style={{ height: 30, padding: '0 12px', borderRadius: 7, border: '1px solid #CFE2FB', background: '#fff', color: '#1F7AE0', font: 'inherit', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>Пометить «Выгружен»</button>
            <div style={{ flex: 1 }} />
            <button className="de-btn" onClick={() => setSelected([])} style={{ height: 30, padding: '0 12px', borderRadius: 7, border: 0, background: 'transparent', color: '#5B6573', font: 'inherit', fontSize: 12.5, cursor: 'pointer' }}>Снять выделение</button>
          </div>
        )}

        {/* Контент */}
        <div ref={scrollRef} className="de-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: '#fff' }}>
          {filtered.length > 0 ? (
            <IncidentsTable
              rows={filtered}
              selected={selected}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={onSort}
              allSelected={allSelected}
              onToggleAll={() => setSelected(allSelected ? [] : filtered.map(d => d.id))}
              onToggleSelect={toggleSelect}
              onOpen={openDetail}
              pulseId={pulseId}
              onPhoto={(id) => setLb({ id, idx: 0 })}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: '80px 32px', textAlign: 'center' }}>
              <div style={{ width: 88, height: 88, borderRadius: '50%', background: '#DEF5E5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44 }}>💚</div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Ничего не найдено</h3>
              <p style={{ margin: 0, maxWidth: 360, color: '#5B6573', fontSize: 13, lineHeight: 1.5 }}>Под заданные фильтры обращений нет. Попробуйте сбросить фильтры.</p>
              <button className="de-btn" onClick={resetFilters} style={{ height: 32, padding: '0 14px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', font: 'inherit', fontSize: 13, cursor: 'pointer' }}>Сбросить фильтры</button>
            </div>
          )}
        </div>
        </React.Fragment>}
      </div>

      {detail && (
        <DetailDrawer
          incident={detail}
          top={detailTop}
          loading={detailLoading}
          onClose={() => { setDetailId(null); setDetailLoading(false); }}
          onSetStatus={setStatus}
          onPhoto={(id, idx) => setLb({ id, idx })}
        />
      )}
      {lbInc && (
        <Lightbox
          incident={lbInc}
          idx={lb.idx}
          onClose={() => setLb(null)}
          onPrev={() => lbStep(-1)}
          onNext={() => lbStep(1)}
        />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
