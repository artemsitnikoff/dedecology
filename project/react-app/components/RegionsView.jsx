// ЭкоПульс — справочник «Регионы» (субъекты РФ) + карточка региона + добавление
function RegionsView({ regions, setRegions, mno, incidents, onToast }) {
  const { useState, useMemo } = React;
  const [query, setQuery] = useState('');
  const [fFed, setFFed] = useState([]);
  const [sortKey, setSortKey] = useState('code');
  const [sortDir, setSortDir] = useState('asc');
  const [detailCode, setDetailCode] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ code: '', name: '', fed: 5, operators: [], operatorInput: '' });

  const FED = de.FED;
  const pill = (bg, fg) => ({ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap', background: bg, color: fg });
  const field = { height: 38, width: '100%', border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 12px', font: 'inherit', fontSize: 13, color: '#0F1620', background: '#fff', outline: 'none', boxSizing: 'border-box' };
  const mnoCount = (code) => mno.filter(m => m.regionCode === code).length;
  const incCount = (name) => incidents.filter(d => d.region === name).length;
  const fmtDate = (s) => s ? s.slice(0, 10).split('-').reverse().join('.') : '—';

  const fedIds = useMemo(() => Array.from(new Set(regions.map(r => r.fed))).sort((a, b) => a - b), [regions]);
  const toggleFed = (id) => setFFed(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const filtered = useMemo(() => {
    let list = regions.slice();
    const q = query.trim().toLowerCase();
    if (q) list = list.filter(r => (r.code + ' ' + r.name + ' ' + r.operators.join(' ') + ' ' + (FED[r.fed] || {}).name).toLowerCase().includes(q));
    if (fFed.length) list = list.filter(r => fFed.includes(r.fed));
    const dir = sortDir === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      let av, bv;
      if (sortKey === 'name') { av = a.name; bv = b.name; }
      else if (sortKey === 'fed') { av = a.fed; bv = b.fed; }
      else if (sortKey === 'operator') { av = (a.operators[0] || ''); bv = (b.operators[0] || ''); }
      else if (sortKey === 'mno') { av = mnoCount(a.code); bv = mnoCount(b.code); }
      else if (sortKey === 'inc') { av = incCount(a.name); bv = incCount(b.name); }
      else { av = +a.code; bv = +b.code; }
      return av < bv ? -1 * dir : av > bv ? 1 * dir : 0;
    });
    return list;
  }, [regions, query, fFed, sortKey, sortDir, mno, incidents]);

  const heads = [
    { key: 'code', label: 'Код', w: 84 },
    { key: 'name', label: 'Субъект РФ', flex: true },
    { key: 'fed', label: 'Федеральный округ', w: 210 },
    { key: 'operator', label: 'Региональные операторы', w: 230 },
    { key: 'mno', label: 'МНО', w: 90 },
    { key: 'inc', label: 'Обращений', w: 116 },
    { key: 'status', label: 'Статус', w: 160, nosort: true },
  ];
  const onSort = (key) => { setSortDir(prev => (sortKey === key && prev === 'asc') ? 'desc' : 'asc'); setSortKey(key); };

  const detail = detailCode ? regions.find(r => r.code === detailCode) : null;

  const addOp = () => {
    const v = (form.operatorInput || '').replace(/,+$/, '').trim();
    if (v) setForm(f => ({ ...f, operators: [...f.operators, v], operatorInput: '' }));
  };
  const submitAdd = () => {
    const code = form.code.trim(), name = form.name.trim();
    if (!code || !name) { onToast('Укажите код и наименование субъекта РФ.'); return; }
    if (regions.some(r => r.code === code)) { onToast('Регион с кодом ' + code + ' уже есть в справочнике.'); return; }
    const ops = form.operators.slice();
    const tail = (form.operatorInput || '').trim();
    if (tail) ops.push(tail);
    setRegions(prev => [...prev, { code, name, fed: +form.fed, operators: ops, active: true, lastSync: '' }]);
    setAddOpen(false);
    setForm({ code: '', name: '', fed: 5, operators: [], operatorInput: '' });
    onToast('Регион «' + name + '» добавлен в справочник.');
  };

  const filterCount = fFed.length ? 1 : 0;
  const counterText = (filterCount || query) ? ('Показано ' + filtered.length + ' из ' + regions.length) : (regions.length + ' субъектов РФ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Шапка */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 28px 9px', borderBottom: '1px solid #E6E9EC', flex: 'none' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, letterSpacing: '-0.015em' }}>Регионы</h1>
          <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 1 }}>Справочник субъектов РФ · {counterText}</div>
        </div>
        <div style={{ flex: 1 }} />
        <button className="de-btn" onClick={() => setAddOpen(true)} style={{ height: 34, padding: '0 14px', borderRadius: 7, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
          Добавить регион
        </button>
      </div>

      {/* Контролы */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '8px 28px', borderBottom: '1px solid #ECEFF2', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 11px', background: '#F8F9FB', border: '1px solid #E6E9EC', borderRadius: 8, width: 300 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#9AA3AE" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Поиск по коду, субъекту, оператору…" style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: 'transparent', font: 'inherit', fontSize: 13, color: '#0F1620' }} />
        </div>
        <div style={{ width: 1, height: 20, background: '#ECEFF2' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.04em', color: '#9AA3AE', fontWeight: 600 }}>Округ</span>
          {fedIds.map(id => (
            <button key={id} className="de-chip" onClick={() => toggleFed(id)} style={de.chipStyle(fFed.includes(id))}>{(FED[id] || {}).code}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        {filterCount > 0 && (
          <button className="de-btn" onClick={() => setFFed([])} style={{ height: 28, padding: '0 12px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#5B6573', font: 'inherit', fontSize: 12, cursor: 'pointer' }}>Сбросить</button>
        )}
      </div>

      {/* Таблица */}
      <div className="de-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: '#fff' }}>
        {filtered.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: '80px 32px', textAlign: 'center', color: '#5B6573' }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#0F1620' }}>Регионы не найдены</h3>
            <p style={{ margin: 0, maxWidth: 360, fontSize: 13 }}>Под заданные фильтры субъектов нет.</p>
            <button className="de-btn" onClick={() => setFFed([])} style={{ height: 32, padding: '0 14px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', font: 'inherit', fontSize: 13, cursor: 'pointer' }}>Сбросить фильтры</button>
          </div>
        )}
        <div style={{ minWidth: 1116 }}>
          <div style={{ display: 'flex', alignItems: 'center', height: 40, background: '#F8F9FB', borderBottom: '1px solid #E6E9EC', position: 'sticky', top: 0, zIndex: 2, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', color: '#5B6573' }}>
            {heads.map(h => {
              const on = !h.nosort && sortKey === h.key;
              const st = { padding: '0 12px', cursor: h.nosort ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 6, height: '100%', color: on ? '#2A8AF0' : '#5B6573', whiteSpace: 'nowrap', userSelect: 'none' };
              if (h.flex) { st.flex = 1; st.minWidth = 220; } else { st.width = h.w; st.flex = 'none'; }
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
          {filtered.map(r => {
            const fed = FED[r.fed] || {};
            const more = r.operators.length > 1;
            return (
              <div key={r.code} className="de-row" onClick={() => setDetailCode(r.code)} style={{ display: 'flex', alignItems: 'center', minHeight: 52, borderBottom: '1px solid #ECEFF2', cursor: 'pointer', background: detailCode === r.code ? '#F4F8FF' : '#fff' }}>
                <div style={{ width: 84, flex: 'none', padding: '0 12px', display: 'flex', alignItems: 'center' }}>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: '#0F1620', background: '#F4F6F8', padding: '2px 8px', borderRadius: 5 }}>{r.code}</span>
                </div>
                <div style={{ flex: 1, minWidth: 220, padding: '0 12px', display: 'flex', alignItems: 'center', fontSize: 13.5, color: '#0F1620', fontWeight: 500 }}>{r.name}</div>
                <div style={{ width: 210, flex: 'none', padding: '8px 12px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 1, minWidth: 0 }}>
                  <span style={{ fontSize: 12.5, color: '#0F1620', fontWeight: 500 }}>{fed.code || '—'}</span>
                  <span style={{ fontSize: 11, color: '#9AA3AE', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fed.name || ''}</span>
                </div>
                <div style={{ width: 230, flex: 'none', padding: '0 12px', display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }} title={r.operators.join(', ') || '—'}>
                  <span style={{ fontSize: 13, color: '#5B6573', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.operators[0] || '—'}</span>
                  {more && <span style={{ flex: 'none', fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, color: '#1F7AE0', background: '#EAF3FE', padding: '1px 7px', borderRadius: 999 }}>+{r.operators.length - 1}</span>}
                </div>
                <div style={{ width: 90, flex: 'none', padding: '0 12px', display: 'flex', alignItems: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 600, color: '#128640' }}>{mnoCount(r.code)}</div>
                <div style={{ width: 116, flex: 'none', padding: '0 12px', display: 'flex', alignItems: 'center', fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: '#5B6573' }}>{incCount(r.name)}</div>
                <div style={{ width: 160, flex: 'none', padding: '8px 12px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 3 }}>
                  <span style={pill(r.active ? '#DEF5E5' : '#ECEFF2', r.active ? '#128640' : '#5B6573')}><span style={de.dot(r.active ? '#16A34A' : '#9AA3AE')} />{r.active ? 'Активен' : 'Не подключён'}</span>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10.5, color: '#9AA3AE' }}>синхр. {fmtDate(r.lastSync)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Карточка региона */}
      {detail && (
        <div className="de-scroll de-mno-drawer" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 560, maxWidth: '92vw', zIndex: 70, background: '#fff', borderLeft: '1px solid #E6E9EC', boxShadow: '-18px 0 44px rgba(15,22,32,.16)', overflowY: 'auto' }}>
          <div style={{ animation: 'deFade .2s ease' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '20px 24px', borderBottom: '1px solid #ECEFF2', position: 'sticky', top: 0, background: '#fff', zIndex: 2 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: '#0F1620', background: '#F4F6F8', padding: '2px 8px', borderRadius: 5 }}>Код {detail.code}</span>
                  <span style={pill(detail.active ? '#DEF5E5' : '#ECEFF2', detail.active ? '#128640' : '#5B6573')}><span style={de.dot(detail.active ? '#16A34A' : '#9AA3AE')} />{detail.active ? 'Активен' : 'Не подключён'}</span>
                </div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, lineHeight: 1.35 }}>{detail.name}</h2>
                <div style={{ marginTop: 5, fontSize: 12.5, color: '#9AA3AE' }}>{(FED[detail.fed] || {}).code} · {(FED[detail.fed] || {}).name} федеральный округ</div>
              </div>
              <button onClick={() => setDetailCode(null)} style={{ width: 32, height: 32, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
            </div>
            <div style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
                <div style={{ flex: 1, border: '1px solid #E6E9EC', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 700, color: '#128640' }}>{mnoCount(detail.code)}</div>
                  <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 2 }}>МНО в регионе</div>
                </div>
                <div style={{ flex: 1, border: '1px solid #E6E9EC', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 700, color: '#0F1620' }}>{incCount(detail.name)}</div>
                  <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 2 }}>Обращений</div>
                </div>
              </div>

              <div style={{ marginBottom: 8, display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>Региональные операторы</span>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, background: '#F4F6F8', color: '#5B6573', padding: '1px 7px', borderRadius: 999 }}>{detail.operators.length}</span>
              </div>
              {detail.operators.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
                  {detail.operators.map((op, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', border: '1px solid #E6E9EC', borderRadius: 8 }}>
                      <span style={{ width: 28, height: 28, borderRadius: 7, background: '#E7F7ED', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none', color: '#1F8A5B' }}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 21h18M5 21V8l7-4 7 4v13M9 21v-6h6v6" /></svg></span>
                      <span style={{ flex: 1, fontSize: 13.5, color: '#0F1620', fontWeight: 500 }}>{op}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: 14, border: '1px dashed #E6E9EC', borderRadius: 8, color: '#9AA3AE', fontSize: 12.5, marginBottom: 18 }}>Операторы пока не назначены.</div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {[
                  ['Код субъекта', detail.code],
                  ['Федеральный округ', (FED[detail.fed] || {}).code + ' · ' + (FED[detail.fed] || {}).name],
                  ['regionId в ФГИС', detail.code],
                  ['МНО в регионе', String(mnoCount(detail.code))],
                  ['Обращений', String(incCount(detail.name))],
                  ['Последняя синхронизация', fmtDate(detail.lastSync)],
                ].map((f, i) => (
                  <div key={i} style={{ display: 'flex', gap: 14, padding: '11px 0', borderBottom: '1px dashed #ECEFF2' }}>
                    <div style={{ width: 200, flex: 'none', fontSize: 12.5, color: '#9AA3AE' }}>{f[0]}</div>
                    <div style={{ flex: 1, fontSize: 13.5, color: '#0F1620', fontWeight: 500 }}>{f[1]}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Модалка: добавить регион */}
      {addOpen && (
        <div onClick={() => setAddOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(15,22,32,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'deFade .14s ease', padding: 24 }}>
          <div className="de-scroll" onClick={e => e.stopPropagation()} style={{ width: 520, maxWidth: '100%', maxHeight: '90vh', overflow: 'auto', background: '#fff', borderRadius: 12, boxShadow: '0 12px 32px rgba(15,22,32,.18)', animation: 'deUp .18s ease' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '18px 22px', borderBottom: '1px solid #ECEFF2' }}>
              <div style={{ flex: 1 }}>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Новый регион</h2>
                <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 2 }}>Субъект РФ в справочнике для сбора и синхронизации</div>
              </div>
              <button onClick={() => setAddOpen(false)} style={{ width: 30, height: 30, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
            </div>
            <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ width: 120, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>Код субъекта</label>
                  <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="63" style={field} />
                </div>
                <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>Федеральный округ</label>
                  <select value={form.fed} onChange={e => setForm({ ...form, fed: +e.target.value })} style={field}>
                    {Object.keys(FED).map(id => <option key={id} value={id}>{FED[id].code} · {FED[id].name}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>Субъект РФ</label>
                <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Самарская область" style={field} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>Региональные операторы по ТКО</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, minHeight: 38, border: '1px solid #E6E9EC', borderRadius: 7, padding: '5px 8px', background: '#fff' }}>
                  {form.operators.map((op, i) => (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 6px 3px 10px', borderRadius: 6, background: '#F4F6F8', fontSize: 12.5, color: '#0F1620' }}>{op}<button onClick={() => setForm(f => ({ ...f, operators: f.operators.filter((_, j) => j !== i) }))} style={{ border: 0, background: 'transparent', cursor: 'pointer', color: '#9AA3AE', display: 'flex', padding: 0 }}><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button></span>
                  ))}
                  <input value={form.operatorInput} onChange={e => setForm({ ...form, operatorInput: e.target.value })} onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addOp(); } }} placeholder="Оператор + Enter" style={{ flex: 1, minWidth: 140, border: 0, outline: 0, background: 'transparent', font: 'inherit', fontSize: 13, color: '#0F1620', padding: '3px 2px' }} />
                </div>
                <span style={{ fontSize: 11.5, color: '#9AA3AE' }}>В регионе может быть несколько операторов — добавьте по одному (Enter или запятая).</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', padding: '16px 22px', borderTop: '1px solid #ECEFF2' }}>
              <button className="de-btn" onClick={() => setAddOpen(false)} style={{ height: 38, padding: '0 16px', borderRadius: 8, border: '1px solid #E6E9EC', background: '#fff', color: '#5B6573', font: 'inherit', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>Отмена</button>
              <button className="de-btn" onClick={submitAdd} style={{ height: 38, padding: '0 18px', borderRadius: 8, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Добавить регион</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
window.RegionsView = RegionsView;
