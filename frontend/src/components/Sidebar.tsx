import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useFunnelCounts } from '@/api/hooks/useFunnelCounts';
import { api } from '@/api/client';
import { Avatar } from './ui/Avatar';
import { Icon, type IconName } from './ui/Icon';
import { APP_VERSION } from '@/lib/version';
import './Sidebar.css';

interface NavItem {
  id: string;
  label: string;
  icon: IconName;
  /** Бейдж-счётчик (число) — рисуется только при заданном значении. */
  count?: number;
}

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.logout);

  // Реальный нефильтрованный итог инцидентов (тот же queryKey, что и на экране
  // «Инциденты» → дедуп). Пока грузится — число не задаём (без фейков).
  const incidentsCount = useFunnelCounts({}).data?.all;

  const handleLogout = async () => {
    // Гасим refresh-cookie на сервере; даже если запрос упал — разлогиниваем локально.
    try {
      await api.post('/auth/logout');
    } catch {
      // игнорируем — локальный logout всё равно выполняем
    }
    clearAuth();
    navigate('/login');
  };

  const getActiveSection = () => {
    const path = location.pathname;
    if (path.startsWith('/incidents') || path === '/') return 'incidents';
    if (path.startsWith('/settings')) return 'settings';
    return '';
  };

  const activeSection = getActiveSection();

  // Бейдж счётчика инцидентов — реальный нефильтрованный all из useFunnelCounts.
  // Пока грузится (incidentsCount === undefined) — бейдж не рисуется (без фейков).
  const nav: NavItem[] = [
    { id: 'incidents', label: 'Инциденты', icon: 'incidents', count: incidentsCount },
    { id: 'settings', label: 'Настройки', icon: 'settings' },
  ];

  const roleLabel = user?.role === 'admin' ? 'Администратор' : 'Пользователь';

  return (
    <aside className="sidebar-wide">
      <div className="brand-wide" onClick={() => navigate('/incidents')}>
        <div className="brand-mark">
          <span className="brand-emoji">👴</span>
        </div>
        <div className="brand-text">
          <span className="brand-name">
            ДедЭколог
            <span className="brand-version">v{APP_VERSION}</span>
          </span>
          <span className="brand-sub">сбор обращений</span>
        </div>
      </div>

      <div className="nav-wide">
        {nav.map((n) => {
          const isActive = activeSection === n.id;
          return (
            <button
              key={n.id}
              className={`nav-row ${isActive ? 'active' : ''}`}
              onClick={() => navigate(`/${n.id}`)}
            >
              <Icon name={n.icon} size={18} className="nav-row-icon" />
              <span className="nav-row-label">{n.label}</span>
              {typeof n.count === 'number' && <span className="nav-row-count">{n.count}</span>}
            </button>
          );
        })}
      </div>

      <div className="user-card-wide">
        {user && (
          <>
            <Avatar name={user.fio} size="sm" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="uc-name">{user.fio}</div>
              <div className="uc-role">{roleLabel}</div>
            </div>
            <button
              className="icon-btn"
              aria-label="Выйти"
              title="Выйти"
              onClick={handleLogout}
            >
              <Icon name="log-out" size={16} />
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
