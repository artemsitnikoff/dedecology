// Боковая панель
function Sidebar({ total, view, onNav }) {
  const navStyle = (active) => ({ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 11px', borderRadius: 7, border: 0, width: '100%', textAlign: 'left', font: 'inherit', fontSize: 13, cursor: 'pointer', background: active ? '#fff' : 'transparent', color: active ? '#2A8AF0' : '#3A4452', fontWeight: active ? 600 : 500, boxShadow: active ? '0 1px 2px rgba(15,22,32,.06)' : 'none' });
  return (
    <aside style={{ width: 248, flex: 'none', background: '#F4F6F8', borderRight: '1px solid #E6E9EC', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="de-brand" style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '17px 18px 15px', borderBottom: '1px solid #E6E9EC' }}>
        <div className="de-mark de-mark-heart" style={{ width: 34, height: 34, borderRadius: 9, background: '#E7F7ED', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, lineHeight: 1, flex: 'none' }}>💚</div>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span style={{ fontWeight: 700, fontSize: 15.5, letterSpacing: '-0.01em' }}>ЭкоПульс</span>
          <span style={{ fontSize: 11, color: '#9AA3AE', marginTop: 2 }}>сбор обращений</span>
        </div>
      </div>

      <div style={{ padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minHeight: 0, overflowY: 'auto' }} className="de-scroll">
        <button className="de-navrow" onClick={() => onNav('incidents')} style={navStyle(view === 'incidents')}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" /></svg>
          <span style={{ flex: 1 }}>Инциденты</span>
          <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, background: '#EAF3FE', color: '#2A8AF0', padding: '1px 7px', borderRadius: 999 }}>{total}</span>
        </button>
        <button className="de-navrow" onClick={() => onNav('settings')} style={navStyle(view === 'settings')}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 2.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H7a1.6 1.6 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V7a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" /></svg>
          <span style={{ flex: 1 }}>Настройки</span>
        </button>
        <div style={{ marginTop: 14, padding: '10px 11px', fontSize: 11.5, color: '#9AA3AE', lineHeight: 1.5 }}>
          Обращения из мессенджера Макс и Яндекс-формы. Статусы — на панели воронки.
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderTop: '1px solid #E6E9EC' }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#1F8A5B', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 12, flex: 'none' }}>АД</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Администратор</div>
          <div style={{ fontSize: 11, color: '#9AA3AE' }}>ЭкоПульс · смена</div>
        </div>
      </div>
    </aside>
  );
}
window.Sidebar = Sidebar;
