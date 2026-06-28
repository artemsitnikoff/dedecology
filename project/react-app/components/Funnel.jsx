// Воронка статусов (как в Глафире) + быстрый фильтр по статусу
function Funnel({ fStatuses, setFStatuses, incidents }) {
  const list = incidents || de.INCIDENTS;
  const allActive = fStatuses.length === 0;
  const countByStatus = k => list.filter(d => d.status === k).length;
  const isActive = k => fStatuses.length === 1 && fStatuses[0] === k;
  const setOne = k => setFStatuses(isActive(k) ? [] : [k]);

  const baseChip = (active, variant) => {
    const s = { display: 'inline-flex', alignItems: 'center', gap: 7, height: 32, padding: '0 12px', borderRadius: 7, cursor: 'pointer', font: 'inherit', fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', flex: 'none', border: '1px solid #E6E9EC', background: '#fff', color: '#0F1620', transition: 'all .12s ease' };
    if (variant === 'hired') { s.borderColor = active ? '#16A34A' : '#A7DDB9'; s.color = active ? '#fff' : '#128640'; s.background = active ? '#16A34A' : '#fff'; }
    else if (variant === 'rejected') { s.borderColor = active ? '#DC4646' : '#EFB4B4'; s.color = active ? '#fff' : '#B83030'; s.background = active ? '#DC4646' : '#fff'; }
    else if (active) { s.background = '#0F1620'; s.color = '#fff'; s.borderColor = '#0F1620'; }
    return s;
  };
  const cnt = (active) => ({ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, color: active ? 'rgba(255,255,255,.82)' : '#9AA3AE' });
  const Chip = ({ k, variant }) => {
    const active = isActive(k); const m = de.STATUS[k];
    return (
      <button className="de-chip" onClick={() => setOne(k)} style={baseChip(active, variant)}>
        <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', flex: 'none', background: active ? '#fff' : m.dot }} />
        {m.label}
        <span style={cnt(active)}>{countByStatus(k)}</span>
      </button>
    );
  };
  const gap = (extra) => <span style={{ width: 14, borderLeft: '1px dashed #C9CFD6', height: 20, flex: 'none', margin: extra ? '0 5px' : '0 3px' }} />;

  return (
    <div className="de-scroll" style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '8px 28px', borderBottom: '1px solid #E6E9EC', background: '#F8F9FB', flex: 'none', overflowX: 'auto' }}>
      <button className="de-chip" onClick={() => setFStatuses([])} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 32, padding: '0 13px', borderRadius: 7, cursor: 'pointer', font: 'inherit', fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap', flex: 'none', border: '1px solid ' + (allActive ? '#2A8AF0' : 'transparent'), background: allActive ? '#2A8AF0' : '#EAF3FE', color: allActive ? '#fff' : '#2A8AF0', transition: 'all .12s ease' }}>
        Все<span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, color: allActive ? 'rgba(255,255,255,.82)' : '#2A8AF0' }}>{list.length}</span>
      </button>
      {gap(false)}
      <Chip k="new" variant="pipe" />
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C9CFD6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }}><path d="M5 12h13M13 6l6 6-6 6" /></svg>
      <Chip k="found" variant="pipe" />
      {gap(true)}
      <Chip k="exported" variant="hired" />
      <Chip k="none" variant="rejected" />
    </div>
  );
}
window.Funnel = Funnel;
