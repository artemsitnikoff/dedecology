// Карточка инцидента (выезжает справа)
function DetailDrawer({ incident, onClose, onSetStatus, onPhoto }) {
  if (!incident) return null;
  const d = incident;
  const srcs = de.photoSrcs(d);
  const pp = de.photoParts(d.photoTime);
  const isMax = d.source === 'max';
  const fields = [
    ['ФИО', d.fio],
    ['Регион', d.region],
    ['Город / н.п.', d.city],
    ['Адрес', d.street],
    ['Координаты', d.coords],
    ['Дата фотофиксации', pp.date],
    ['Время фотофиксации', pp.time],
    ['Фотографий площадки', String(d.photos)],
    ['Источник', de.SOURCE[d.source].label],
    ['Поступило', de.dateShort(d.dateRaw)],
  ];
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(15,22,32,.4)', animation: 'deFade .14s ease', display: 'flex', justifyContent: 'flex-end' }}>
      <div onClick={(e) => e.stopPropagation()} className="de-scroll" style={{ width: 560, maxWidth: '100%', height: '100%', background: '#fff', overflowY: 'auto', boxShadow: '-16px 0 40px rgba(15,22,32,.22)', animation: 'deSlide .24s cubic-bezier(.2,.8,.2,1)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '20px 24px', borderBottom: '1px solid #ECEFF2', position: 'sticky', top: 0, background: '#fff', zIndex: 2 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
              <span style={de.pillSource(d.source)}>{de.SOURCE[d.source].label}</span>
              <span style={de.pillStatus(d.status)}><span style={de.dot(de.STATUS[d.status].dot)} />{de.STATUS[d.status].label}</span>
            </div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, lineHeight: 1.4 }}>{de.fullAddr(d)}</h2>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        <div style={{ padding: '22px 24px' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {srcs.map((src, i) => (
              <div key={i} onClick={() => onPhoto(d.id, i)} style={{ flex: 1, height: 148, borderRadius: 9, overflow: 'hidden', border: '1px solid #E6E9EC', cursor: 'zoom-in', background: '#EEF1F4', position: 'relative' }}>
                <div style={{ position: 'absolute', inset: 0, backgroundImage: 'url("' + src + '")', backgroundSize: 'cover', backgroundPosition: 'center' }} />
                <span style={{ position: 'absolute', left: 8, bottom: 8, background: 'rgba(15,22,32,.62)', color: '#fff', fontSize: 10, padding: '2px 8px', borderRadius: 6 }}>Фото {i + 1}</span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {fields.map(([k, v], i) => (
              <div key={i} style={{ display: 'flex', gap: 14, padding: '11px 0', borderBottom: '1px dashed #ECEFF2' }}>
                <div style={{ width: 180, flex: 'none', fontSize: 12.5, color: '#9AA3AE' }}>{k}</div>
                <div style={{ flex: 1, fontSize: 13.5, color: '#0F1620', fontWeight: 500, lineHeight: 1.45 }}>{v}</div>
              </div>
            ))}
          </div>

          {isMax && (
            <a href={de.messageLink(d)} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 18, height: 38, padding: '0 16px', borderRadius: 8, background: '#ECE7FE', color: '#7E5CF0', textDecoration: 'none', fontSize: 13, fontWeight: 600 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a8 8 0 0 1-12.5 6.6L3 20l1.5-5A8 8 0 1 1 21 12z" /></svg>
              Открыть сообщение в Максе
            </a>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 24, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#9AA3AE', alignSelf: 'center', marginRight: 2 }}>Сменить статус:</span>
            {Object.keys(de.STATUS).map(k => (
              <button key={k} className="de-chip" onClick={() => onSetStatus(d.id, k)} style={de.chipStyle(d.status === k)}>
                <span style={de.dot(de.STATUS[k].dot)} />{de.STATUS[k].label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
window.DetailDrawer = DetailDrawer;
