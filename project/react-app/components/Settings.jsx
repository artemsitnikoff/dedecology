// Раздел «Настройки» — профиль, смена пароля, пользователи (с приглашением по email)
function Settings() {
  const { useState } = React;
  const [profileFio, setProfileFio] = useState('Администратор');
  const profileEmail = 'admin@dedekolog.ru';
  const [newPw, setNewPw] = useState('');
  const [users, setUsers] = useState([
    { id: 'u1', fio: 'Администратор', email: 'admin@dedekolog.ru', role: 'admin', status: 'active' },
    { id: 'u2', fio: 'Смирнов Олег Иванович', email: 'smirnov@dedekolog.ru', role: 'user', status: 'active' },
    { id: 'u3', fio: 'Климова Вера Павловна', email: 'klimova@dedekolog.ru', role: 'user', status: 'invited' },
  ]);
  const [nu, setNu] = useState({ fio: '', email: '', role: 'user' });
  const [notice, setNotice] = useState('');

  const fieldInput = { height: 38, width: '100%', border: '1px solid #E6E9EC', borderRadius: 7, padding: '0 12px', font: 'inherit', fontSize: 13, color: '#0F1620', background: '#fff', outline: 'none' };
  const roleMeta = { admin: { label: 'Администратор', bg: '#ECE7FE', fg: '#7E5CF0' }, user: { label: 'Пользователь', bg: '#F4F6F8', fg: '#5B6573' } };
  const statusMeta = { active: { label: 'Активен', bg: '#DEF5E5', fg: '#128640', dot: '#16A34A' }, invited: { label: 'Приглашён', bg: '#FFF1C8', fg: '#B5821A', dot: '#E0A21A' } };

  const initials = (n) => de.initials(n).toUpperCase();
  const saveProfile = () => setNotice('Профиль сохранён.');
  const changePassword = () => {
    if (!newPw.trim()) { setNotice('Введите новый пароль.'); return; }
    setNewPw(''); setNotice('Пароль сброшен — установлен новый.');
  };
  const addUser = () => {
    const fio = nu.fio.trim(), email = nu.email.trim();
    if (!fio || !email) { setNotice('Заполните ФИО и email — на него уйдёт приглашение.'); return; }
    setUsers(prev => prev.concat([{ id: 'u' + Date.now(), fio, email, role: nu.role, status: 'invited' }]));
    setNu({ fio: '', email: '', role: 'user' });
    setNotice('Приглашение отправлено на ' + email + ' — пользователь получит ссылку для входа.');
  };
  const removeUser = (id) => setUsers(prev => prev.filter(u => u.id !== id));

  const Field = ({ label, children }) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, color: '#5B6573', fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  );

  return (
    <div className="de-scroll" style={{ height: '100%', overflow: 'auto', background: '#fff' }}>
      <div style={{ padding: '16px 28px 14px', borderBottom: '1px solid #E6E9EC' }}>
        <h1 style={{ margin: 0, fontSize: 21, fontWeight: 600, letterSpacing: '-0.015em' }}>Настройки</h1>
        <div style={{ fontSize: 12, color: '#9AA3AE', marginTop: 3 }}>Профиль администратора и управление пользователями</div>
      </div>

      <div style={{ maxWidth: 780, padding: '22px 28px 48px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        {notice && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', background: '#DEF5E5', border: '1px solid #B9E6C9', borderRadius: 9, color: '#128640', fontSize: 13, fontWeight: 500 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }}><path d="M5 12l5 5 9-11" /></svg>
            <span style={{ flex: 1 }}>{notice}</span>
            <button onClick={() => setNotice('')} style={{ border: 0, background: 'transparent', cursor: 'pointer', color: '#128640', display: 'flex', padding: 2 }}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
          </div>
        )}

        {/* Профиль */}
        <div style={{ border: '1px solid #E6E9EC', borderRadius: 12, padding: '20px 22px' }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Профиль</div>
          <div style={{ fontSize: 12.5, color: '#9AA3AE', margin: '3px 0 16px' }}>Ваше имя и доступ к аккаунту</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Field label="ФИО"><input value={profileFio} onChange={e => setProfileFio(e.target.value)} style={fieldInput} /></Field>
            <Field label="Email для входа"><input value={profileEmail} disabled style={{ ...fieldInput, border: '1px solid #ECEFF2', color: '#9AA3AE', background: '#F8F9FB' }} /></Field>
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="de-btn" onClick={saveProfile} style={{ height: 36, padding: '0 16px', borderRadius: 7, border: 0, background: '#2A8AF0', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Сохранить</button>
          </div>
          <div style={{ height: 1, background: '#ECEFF2', margin: '20px 0' }} />
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>Смена пароля</div>
          <div style={{ fontSize: 12.5, color: '#9AA3AE', margin: '3px 0 14px' }}>Введите новый пароль и нажмите «Сбросить».</div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
            <div style={{ flex: 1, maxWidth: 320 }}>
              <Field label="Новый пароль"><input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="••••••" style={fieldInput} /></Field>
            </div>
            <button className="de-btn" onClick={changePassword} style={{ height: 38, padding: '0 18px', borderRadius: 7, border: '1px solid #E6E9EC', background: '#fff', color: '#0F1620', font: 'inherit', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>Сбросить</button>
          </div>
        </div>

        {/* Пользователи */}
        <div style={{ border: '1px solid #E6E9EC', borderRadius: 12, padding: '20px 22px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Пользователи и доступ</div>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, fontWeight: 600, background: '#F4F6F8', color: '#5B6573', padding: '1px 7px', borderRadius: 999 }}>{users.length}</span>
          </div>
          <div style={{ fontSize: 12.5, color: '#9AA3AE', margin: '3px 0 16px' }}>Добавьте сотрудника — на его email уйдёт приглашение со ссылкой для входа.</div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', padding: 14, background: '#F8F9FB', border: '1px solid #ECEFF2', borderRadius: 10 }}>
            <div style={{ flex: 1, minWidth: 180 }}><Field label="ФИО сотрудника"><input value={nu.fio} onChange={e => setNu({ ...nu, fio: e.target.value })} placeholder="Иванов Иван Иванович" style={fieldInput} /></Field></div>
            <div style={{ flex: 1, minWidth: 180 }}><Field label="Email"><input value={nu.email} onChange={e => setNu({ ...nu, email: e.target.value })} placeholder="ivanov@dedekolog.ru" style={fieldInput} /></Field></div>
            <Field label="Доступ">
              <div style={{ display: 'flex', gap: 6 }}>
                {['user', 'admin'].map(r => (
                  <button key={r} className="de-chip" onClick={() => setNu({ ...nu, role: r })} style={de.chipStyle(nu.role === r)}>{roleMeta[r].label}</button>
                ))}
              </div>
            </Field>
            <button className="de-btn" onClick={addUser} style={{ height: 38, padding: '0 16px', borderRadius: 7, border: 0, background: '#1F8A5B', color: '#fff', font: 'inherit', fontSize: 13, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5h18l-2 4M3 5l9 9 9-9M12 14v6" /></svg>
              Отправить приглашение
            </button>
          </div>

          <div style={{ marginTop: 18, border: '1px solid #ECEFF2', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', height: 38, background: '#F8F9FB', borderBottom: '1px solid #ECEFF2', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', color: '#5B6573' }}>
              <div style={{ flex: 1, padding: '0 14px' }}>Пользователь</div>
              <div style={{ width: 150, flex: 'none', padding: '0 14px' }}>Доступ</div>
              <div style={{ width: 140, flex: 'none', padding: '0 14px' }}>Статус</div>
              <div style={{ width: 44, flex: 'none' }} />
            </div>
            {users.map(u => (
              <div key={u.id} className="de-row" style={{ display: 'flex', alignItems: 'center', minHeight: 56, borderBottom: '1px solid #ECEFF2', background: '#fff' }}>
                <div style={{ flex: 1, padding: '0 14px', display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
                  <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#1F8A5B', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, flex: 'none' }}>{initials(u.fio)}</div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.fio}</div>
                    <div style={{ fontSize: 11.5, color: '#9AA3AE', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.email}</div>
                  </div>
                </div>
                <div style={{ width: 150, flex: 'none', padding: '0 14px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: roleMeta[u.role].bg, color: roleMeta[u.role].fg }}>{roleMeta[u.role].label}</span>
                </div>
                <div style={{ width: 140, flex: 'none', padding: '0 14px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600, background: statusMeta[u.status].bg, color: statusMeta[u.status].fg }}>
                    <span style={de.dot(statusMeta[u.status].dot)} />{statusMeta[u.status].label}
                  </span>
                </div>
                <div style={{ width: 44, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {u.role === 'admin' ? (
                    <span style={{ color: '#C9CFD6' }}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="4.5" y="10.5" width="15" height="10" rx="2" /><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" /></svg></span>
                  ) : (
                    <button className="de-btn" onClick={() => removeUser(u.id)} style={{ width: 28, height: 28, border: 0, background: 'transparent', borderRadius: 6, color: '#9AA3AE', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13h10l1-13" /></svg></button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
window.Settings = Settings;
