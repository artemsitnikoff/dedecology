// Таблица инцидентов — сортировка по клику на заголовок (как в Глафире)
const Check = ({ small }) => (
  <svg width={small ? 11 : 12} height={small ? 11 : 12} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-11" /></svg>
);

function SortArrows({ on, dir }) {
  const up = on && dir === 'asc', down = on && dir === 'desc';
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', lineHeight: 1 }}>
      <span style={{ fontSize: 8, lineHeight: '8px', color: up ? '#2A8AF0' : '#C9CFD6' }}>▲</span>
      <span style={{ fontSize: 8, lineHeight: '8px', color: down ? '#2A8AF0' : '#C9CFD6' }}>▼</span>
    </span>
  );
}

function IncidentRow({ d, selected, onToggle, onOpen, onPhoto }) {
  const pp = de.photoParts(d.photoTime);
  const srcs = de.photoSrcs(d);
  const thumb = srcs[0];
  const isMax = d.source === 'max';
  return (
    <div className="de-row" onClick={() => onOpen(d.id)} style={{ display: 'flex', alignItems: 'center', minHeight: 58, cursor: 'pointer', borderBottom: '1px solid #ECEFF2', background: selected ? '#EAF3FE' : '#fff' }}>
      <div style={{ width: 46, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div onClick={(e) => { e.stopPropagation(); onToggle(d.id); }} style={de.checkStyle(selected)}>{selected && <Check small />}</div>
      </div>
      <div style={{ width: 64, flex: 'none', padding: '0 10px' }}>
        <div onClick={(e) => { e.stopPropagation(); onPhoto(d.id); }} style={{ position: 'relative', width: 46, height: 34, borderRadius: 6, overflow: 'hidden', border: '1px solid #E6E9EC', cursor: 'zoom-in', background: '#EEF1F4' }}>
          {thumb && <div style={{ position: 'absolute', inset: 0, backgroundImage: 'url("' + thumb + '")', backgroundSize: 'cover', backgroundPosition: 'center' }} />}
          {d.photos > 1 && <span style={{ position: 'absolute', right: 2, bottom: 2, background: 'rgba(15,22,32,.72)', color: '#fff', fontSize: 9, fontWeight: 600, padding: '0 4px', borderRadius: 4, lineHeight: '14px' }}>{d.photos}</span>}
        </div>
      </div>
      <div style={{ width: 104, flex: 'none', padding: '0 10px', fontSize: 12.5, color: '#0F1620' }}>{pp.date}</div>
      <div style={{ width: 80, flex: 'none', padding: '0 10px', fontFamily: "'JetBrains Mono',monospace", fontSize: 12.5, color: '#5B6573' }}>{pp.time}</div>
      <div style={{ width: 150, flex: 'none', padding: '0 10px', fontSize: 13, color: '#0F1620', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={d.region}>{d.region}</div>
      <div style={{ width: 150, flex: 'none', padding: '0 10px', fontSize: 13, color: '#0F1620', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={d.city}>{d.city}</div>
      <div style={{ flex: 1, minWidth: 190, padding: '0 10px', fontSize: 13, color: '#5B6573', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={de.fullAddr(d)}>{d.street}</div>
      <div style={{ width: 150, flex: 'none', padding: '0 10px', fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, color: '#5B6573' }}>{d.coords}</div>
      <div style={{ width: 168, flex: 'none', padding: '0 10px' }}>
        <span style={de.pillStatus(d.status)}><span style={de.dot(de.STATUS[d.status].dot)} />{de.STATUS[d.status].label}</span>
      </div>
      <div style={{ width: 108, flex: 'none', padding: '0 10px' }}>
        <span style={de.pillSource(d.source)}>{de.SOURCE[d.source].label}</span>
      </div>
      <div style={{ width: 90, flex: 'none', padding: '0 10px' }}>
        {isMax && (
          <a href={de.messageLink(d)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, fontWeight: 600, color: '#7E5CF0', textDecoration: 'none' }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 15l6-6" /><path d="M11 6l1-1a4 4 0 0 1 6 6l-1 1M13 18l-1 1a4 4 0 0 1-6-6l1-1" /></svg>
            Макс
          </a>
        )}
      </div>
    </div>
  );
}

function IncidentsTable({ rows, selected, sortKey, sortDir, onSort, allSelected, onToggleAll, onToggleSelect, onOpen, onPhoto }) {
  const HEADS = [
    { key: 'photo', label: 'Фото', w: 64, nosort: true },
    { key: 'date', label: 'Дата', w: 104 },
    { key: 'time', label: 'Время', w: 80 },
    { key: 'region', label: 'Регион', w: 150 },
    { key: 'city', label: 'Город', w: 150 },
    { key: 'address', label: 'Адрес', flex: true },
    { key: 'coords', label: 'Координаты', w: 150, nosort: true },
    { key: 'status', label: 'Статус', w: 168 },
    { key: 'source', label: 'Источник', w: 108 },
    { key: 'link', label: 'Чат', w: 90, nosort: true },
  ];
  return (
    <div style={{ padding: 0, minWidth: 1300 }}>
      <div style={{ display: 'flex', alignItems: 'center', height: 40, background: '#F8F9FB', borderBottom: '1px solid #E6E9EC', position: 'sticky', top: 0, zIndex: 2, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', color: '#5B6573' }}>
        <div style={{ width: 46, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={onToggleAll} style={de.checkStyle(allSelected)}>{allSelected && <Check small />}</div>
        </div>
        {HEADS.map(h => {
          const on = !h.nosort && sortKey === h.key;
          const style = { padding: '0 10px', cursor: h.nosort ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 6, height: '100%', color: on ? '#2A8AF0' : '#5B6573', whiteSpace: 'nowrap', userSelect: 'none', transition: 'color .12s ease' };
          if (h.flex) { style.flex = 1; style.minWidth = 200; } else { style.width = h.w; style.flex = 'none'; }
          return (
            <div key={h.key} className="de-th" onClick={h.nosort ? undefined : () => onSort(h.key)} style={style}>
              {h.label}
              {!h.nosort && <SortArrows on={on} dir={sortDir} />}
            </div>
          );
        })}
      </div>
      {rows.map(d => (
        <IncidentRow key={d.id} d={d} selected={selected.includes(d.id)} onToggle={onToggleSelect} onOpen={onOpen} onPhoto={onPhoto} />
      ))}
    </div>
  );
}
window.IncidentsTable = IncidentsTable;
