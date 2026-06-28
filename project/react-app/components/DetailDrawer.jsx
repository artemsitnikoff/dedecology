// Карточка инцидента — выезжает справа над областью таблицы (Регион/Город/Адрес/Координаты…),
// не закрывая воронку и фильтры. При открытии — белый экран загрузки с пульсом 💚, затем контент (как у Глафиры).
function DetailDrawer({ incident, onClose, onSetStatus, onPhoto, top, loading }) {
  if (!incident) return null;
  const d = incident;
  const srcs = de.photoSrcs(d);
  const pp = de.photoParts(d.photoTime);
  const isMax = d.source === 'max';
  const idLabel = d.id.toUpperCase();
  const single = srcs.length === 1;
  const photoBox = single
    ? { flex: '0 0 220px', maxWidth: 220, height: 156, borderRadius: 9, overflow: 'hidden', border: '1px solid #E6E9EC', cursor: 'zoom-in', background: '#EEF1F4', position: 'relative' }
    : { flex: 1, height: 148, borderRadius: 9, overflow: 'hidden', border: '1px solid #E6E9EC', cursor: 'zoom-in', background: '#EEF1F4', position: 'relative' };
  const TRANSITIONS = { new: ['found', 'none'], found: ['new', 'exported'], none: ['new', 'found'], exported: ['found', 'new'] };
  const actions = (TRANSITIONS[d.status] || []);
  const actionStyle = (k) => {
    return { display: 'inline-flex', alignItems: 'center', gap: 6, height: 28, padding: '0 10px', borderRadius: 7, cursor: 'pointer', font: 'inherit', fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', border: '1px solid #E6E9EC', background: '#fff', color: '#0F1620', transition: 'all .12s ease' };
  };
  const fields = [
    ['ID обращения', idLabel],
    ['ФИО', d.fio],
    ['Телефон', d.phone],
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
    <div className="de-scroll" style={{ position: 'fixed', top: top != null ? top : 170, right: 0, bottom: 0, left: 494, zIndex: 60, background: '#fff', borderLeft: '1px solid #E6E9EC', boxShadow: '-18px 0 44px rgba(15,22,32,.16)', overflowY: 'auto', animation: 'deCardIn .24s ease-out' }}>
      {loading ? (
        <div style={{ position: 'absolute', inset: 0, background: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, zIndex: 5 }}>
          <span className="de-mark-heart" style={{ fontSize: 48, lineHeight: 1 }}>💚</span>
          <span style={{ fontSize: 13.5, color: '#5B6573', fontWeight: 500 }}>Загрузка…</span>
        </div>
      ) : (
      <div style={{ animation: 'deFade .22s ease' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '20px 24px', borderBottom: '1px solid #ECEFF2', position: 'sticky', top: 0, background: '#fff', zIndex: 2 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9, flexWrap: 'wrap' }}>
            <span className="de-mark-heart" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, lineHeight: 1, flex: 'none' }}>💚</span>
            <span style={de.pillSource(d.source)}>{de.SOURCE[d.source].label}</span>
            <span style={de.pillStatus(d.status)}><span style={de.dot(de.STATUS[d.status].dot)} />{de.STATUS[d.status].label}</span>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#5B6573', background: '#F4F6F8', padding: '2px 8px', borderRadius: 5 }}>ID {idLabel}</span>
          </div>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, lineHeight: 1.4 }}>{de.fullAddr(d)}</h2>
        </div>
        <button onClick={onClose} style={{ width: 32, height: 32, border: 0, background: '#F4F6F8', borderRadius: 8, cursor: 'pointer', color: '#5B6573', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
      </div>

      {actions.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', padding: '10px 24px', borderBottom: '1px solid #ECEFF2', background: '#F8F9FB' }}>
          <span style={{ fontSize: 11.5, color: '#9AA3AE', marginRight: 2 }}>Сменить статус:</span>
          {actions.map(k => (
            <button key={k} className="de-chip" onClick={() => onSetStatus(d.id, k)} style={actionStyle(k)}>
              <span style={de.dot(de.STATUS[k].dot)} />{de.STATUS[k].label}
            </button>
          ))}
        </div>
      )}

      <div style={{ padding: '22px 24px' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          {srcs.map((src, i) => (
            <div key={i} onClick={() => onPhoto(d.id, i)} style={photoBox}>
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
      </div>
      </div>
      )}
    </div>
  );
}
window.DetailDrawer = DetailDrawer;
