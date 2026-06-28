// Таблица инцидентов — Дата · время · фото в одном «замороженном» блоке (тень + sticky),
// сортировка по клику на заголовок столбца (как в Глафире). Клик по блоку → карточка + пульс-сердце.
const Check = ({ small }) => (
  <svg width={small ? 11 : 12} height={small ? 11 : 12} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-11" /></svg>
);

const HeartGlyph = ({ size, color }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color}><path d="M12 20.3l-1.6-1.5C5.4 14.2 2.5 11.6 2.5 8.3 2.5 5.7 4.6 3.7 7.2 3.7c1.5 0 2.9.7 3.8 1.8l1 1.2 1-1.2c.9-1.1 2.3-1.8 3.8-1.8 2.6 0 4.7 2 4.7 4.6 0 3.3-2.9 5.9-7.9 10.5L12 20.3z" /></svg>
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

function IncidentRow({ d, selected, pulse, onToggle, onOpen, onPhoto }) {
  const pp = de.photoParts(d.photoTime);
  const srcs = de.photoSrcs(d);
  const thumb = srcs[0];
  const isMax = d.source === 'max';
  const rowBg = selected ? '#EAF3FE' : '#fff';
  const frozen = { alignSelf: 'stretch', display: 'flex', alignItems: 'center', position: 'sticky', zIndex: 1, background: rowBg };
  return (
    <div className="de-row" onClick={() => onOpen(d.id)} style={{ display: 'flex', alignItems: 'center', minHeight: 58, cursor: 'pointer', borderBottom: '1px solid #ECEFF2', background: rowBg }}>
      {/* Чекбокс — заморожен слева */}
      <div className="de-frozen" style={{ ...frozen, width: 46, flex: 'none', justifyContent: 'center', left: 0 }}>
        <div onClick={(e) => { e.stopPropagation(); onToggle(d.id); }} style={de.checkStyle(selected)}>{selected && <Check small />}</div>
      </div>
      {/* Фото · дата · время · ID · телефон — единый замороженный блок с тенью */}
      <div className="de-frozen" onClick={() => onOpen(d.id)} style={{ ...frozen, width: 248, flex: 'none', gap: 11, padding: '0 12px', cursor: 'pointer', left: 46, boxShadow: '10px 0 10px -8px rgba(15,22,32,.12)' }}>
        <div onClick={(e) => { e.stopPropagation(); onPhoto(d.id); }} style={{ position: 'relative', width: 46, height: 34, borderRadius: 6, overflow: 'hidden', border: '1px solid #E6E9EC', cursor: 'zoom-in', background: '#EEF1F4', flex: 'none' }}>
          {thumb && <div style={{ position: 'absolute', inset: 0, backgroundImage: 'url("' + thumb + '")', backgroundSize: 'cover', backgroundPosition: 'center' }} />}
          {d.photos > 1 && <span style={{ position: 'absolute', right: 2, bottom: 2, background: 'rgba(15,22,32,.72)', color: '#fff', fontSize: 9, fontWeight: 600, padding: '0 4px', borderRadius: 4, lineHeight: '14px' }}>{d.photos}</span>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.3, minWidth: 0, gap: 2 }}>
          <span style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
            <span style={{ fontSize: 12.5, color: '#0F1620', fontWeight: 600 }}>{pp.date}</span>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, color: '#5B6573' }}>{pp.time}</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 600, color: '#5B6573', background: '#F4F6F8', padding: '1px 5px', borderRadius: 4, flex: 'none' }}>{d.id.toUpperCase()}</span>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#5B6573', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.phone}</span>
          </span>
        </div>
      </div>
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

function IncidentsTable({ rows, selected, pulseId, sortKey, sortDir, onSort, allSelected, onToggleAll, onToggleSelect, onOpen, onPhoto }) {
  const HEADS = [
    { key: 'date', label: 'Дата · время · ID', w: 248, sticky: 46, shadow: true },
    { key: 'region', label: 'Регион', w: 150 },
    { key: 'city', label: 'Город', w: 150 },
    { key: 'address', label: 'Адрес', flex: true },
    { key: 'coords', label: 'Координаты', w: 150, nosort: true },
    { key: 'status', label: 'Статус', w: 168 },
    { key: 'source', label: 'Источник', w: 108 },
    { key: 'link', label: 'Чат', w: 90, nosort: true },
  ];
  return (
    <div style={{ padding: 0, minWidth: 1288 }}>
      <div style={{ display: 'flex', alignItems: 'center', height: 40, background: '#F8F9FB', borderBottom: '1px solid #E6E9EC', position: 'sticky', top: 0, zIndex: 2, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', color: '#5B6573' }}>
        <div style={{ width: 46, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'sticky', left: 0, zIndex: 3, background: '#F8F9FB' }}>
          <div onClick={onToggleAll} style={de.checkStyle(allSelected)}>{allSelected && <Check small />}</div>
        </div>
        {HEADS.map(h => {
          const on = !h.nosort && sortKey === h.key;
          const style = { padding: '0 10px', cursor: h.nosort ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 6, height: '100%', color: on ? '#2A8AF0' : '#5B6573', whiteSpace: 'nowrap', userSelect: 'none', transition: 'color .12s ease' };
          if (h.flex) { style.flex = 1; style.minWidth = 200; } else { style.width = h.w; style.flex = 'none'; }
          if (h.sticky != null) { style.position = 'sticky'; style.left = h.sticky; style.zIndex = 3; style.background = '#F8F9FB'; }
          if (h.shadow) { style.boxShadow = '10px 0 10px -8px rgba(15,22,32,.12)'; }
          return (
            <div key={h.key} className="de-th" onClick={h.nosort ? undefined : () => onSort(h.key)} style={style}>
              {h.label}
              {!h.nosort && <SortArrows on={on} dir={sortDir} />}
            </div>
          );
        })}
      </div>
      {rows.map(d => (
        <IncidentRow key={d.id} d={d} selected={selected.includes(d.id)} pulse={pulseId === d.id} onToggle={onToggleSelect} onOpen={onOpen} onPhoto={onPhoto} />
      ))}
    </div>
  );
}
window.IncidentsTable = IncidentsTable;
