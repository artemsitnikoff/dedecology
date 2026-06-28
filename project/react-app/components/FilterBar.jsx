// Панель фильтров (Источник / Период) + сброс
function FilterBar({ fSources, setFSources, fFrom, setFFrom, fTo, setFTo, hasFilters, onReset }) {
  const toggle = (arr, setter, val) => {
    const a = arr.slice(); const i = a.indexOf(val);
    if (i >= 0) a.splice(i, 1); else a.push(val);
    setter(a);
  };
  const Label = ({ children }) => (
    <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.04em', color: '#9AA3AE', fontWeight: 600 }}>{children}</span>
  );
  const Sep = () => <div style={{ width: 1, height: 20, background: '#ECEFF2' }} />;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', padding: '8px 28px', borderBottom: '1px solid #ECEFF2', background: '#fff', flex: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Label>Источник</Label>
        {Object.keys(de.SOURCE).map(k => (
          <button key={k} className="de-chip" onClick={() => toggle(fSources, setFSources, k)} style={de.chipStyle(fSources.includes(k))}>{de.SOURCE[k].label}</button>
        ))}
      </div>
      <Sep />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Label>Период</Label>
        <input type="date" value={fFrom} onChange={e => setFFrom(e.target.value)} style={{ height: 30, border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 9px', font: 'inherit', fontSize: 12.5, color: '#0F1620', background: '#fff', outline: 'none', cursor: 'pointer' }} />
        <span style={{ color: '#9AA3AE', fontSize: 13 }}>—</span>
        <input type="date" value={fTo} onChange={e => setFTo(e.target.value)} style={{ height: 30, border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 9px', font: 'inherit', fontSize: 12.5, color: '#0F1620', background: '#fff', outline: 'none', cursor: 'pointer' }} />
        {(fFrom || fTo) && (
          <button className="de-btn" onClick={() => { setFFrom(''); setFTo(''); }} style={{ width: 28, height: 28, border: 0, background: 'transparent', borderRadius: 6, color: '#9AA3AE', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        )}
      </div>
      <div style={{ flex: 1 }} />
      {hasFilters && (
        <button className="de-btn" onClick={onReset} style={{ height: 28, padding: '0 12px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#5B6573', font: 'inherit', fontSize: 12, cursor: 'pointer' }}>Сбросить</button>
      )}
    </div>
  );
}
window.FilterBar = FilterBar;
