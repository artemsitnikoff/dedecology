// Лайтбокс — листалка фото
function Lightbox({ incident, idx, onClose, onPrev, onNext }) {
  if (!incident) return null;
  const srcs = de.photoSrcs(incident);
  const i = Math.max(0, Math.min(idx, srcs.length - 1));
  const many = srcs.length > 1;
  const navBtn = (side) => ({ position: 'absolute', [side]: 24, top: '50%', transform: 'translateY(-50%)', width: 48, height: 48, border: 0, borderRadius: '50%', background: 'rgba(255,255,255,.14)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' });
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15,22,32,.84)', display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'deFade .14s ease' }}>
      <button onClick={onClose} style={{ position: 'absolute', top: 20, right: 24, width: 40, height: 40, border: 0, borderRadius: 10, background: 'rgba(255,255,255,.12)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
      </button>
      {many && (
        <button onClick={(e) => { e.stopPropagation(); onPrev(); }} style={navBtn('left')}>
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6l-6 6 6 6" /></svg>
        </button>
      )}
      <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, maxWidth: '86vw' }}>
        <div style={{ width: '86vw', maxWidth: 1080, height: '72vh', backgroundImage: 'url("' + srcs[i] + '")', backgroundSize: 'contain', backgroundPosition: 'center', backgroundRepeat: 'no-repeat', borderRadius: 12 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#fff' }}>
          <span style={{ fontSize: 13, opacity: .85, textAlign: 'center' }}>{de.fullAddr(incident)}</span>
          {many && <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, background: 'rgba(255,255,255,.15)', padding: '2px 9px', borderRadius: 999 }}>{i + 1} / {srcs.length}</span>}
        </div>
      </div>
      {many && (
        <button onClick={(e) => { e.stopPropagation(); onNext(); }} style={navBtn('right')}>
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
        </button>
      )}
    </div>
  );
}
window.Lightbox = Lightbox;
