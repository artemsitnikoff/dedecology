import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useFunnelCounts } from '@/api/hooks/useFunnelCounts';
import { useMno } from '@/api/hooks/mno';
import { useRegionsDirectory } from '@/api/hooks/regions';
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

  // Реальные нефильтрованные итоги (те же queryKey, что и на экранах → дедуп).
  // Пока грузится — count undefined, бейдж не рисуется (без фейков).
  const incidentsCount = useFunnelCounts({}).data?.all;
  const mnoCount = useMno({}).data?.total;
  const regionsCount = useRegionsDirectory({}).data?.length;

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
    if (path.startsWith('/reports')) return 'reports';
    // ВАЖНО: '/mno-new' проверяем ДО '/mno' (иначе startsWith('/mno') перехватит).
    if (path.startsWith('/mno-new')) return 'mno-new';
    if (path.startsWith('/mno')) return 'mno';
    if (path.startsWith('/regions')) return 'regions';
    if (path.startsWith('/incident-types')) return 'incident-types';
    if (path.startsWith('/blocked-domains')) return 'blocked-domains';
    if (path.startsWith('/errors')) return 'errors';
    if (path.startsWith('/volunteers')) return 'volunteers';
    if (path.startsWith('/integration')) return 'integration';
    if (path.startsWith('/settings')) return 'settings';
    return '';
  };

  const activeSection = getActiveSection();

  // Основная навигация (до группы «Справочники»).
  const mainNav: NavItem[] = [
    { id: 'incidents', label: 'Инциденты', icon: 'incidents', count: incidentsCount },
    { id: 'reports', label: 'Выгрузка УТКО', icon: 'download' },
    { id: 'mno', label: 'МНО', icon: 'pin', count: mnoCount },
    { id: 'mno-new', label: 'Новые МНО', icon: 'pin' },
  ];
  // Справочники.
  const refNav: NavItem[] = [
    { id: 'regions', label: 'Регионы', icon: 'map', count: regionsCount },
    { id: 'incident-types', label: 'Типы инцидентов', icon: 'file-text' },
    { id: 'volunteers', label: 'Волонтёры', icon: 'user' },
  ];

  const roleLabel = user?.role === 'admin' ? 'Администратор' : 'Пользователь';

  const renderNav = (n: NavItem) => {
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
  };

  return (
    <aside className="sidebar-wide">
      <div className="brand-wide" onClick={() => navigate('/incidents')}>
        <div className="brand-mark">
          <span className="brand-emoji">💚</span>
        </div>
        <div className="brand-text">
          <span className="brand-name">
            ЭкоПульс
            <span className="brand-version">v{APP_VERSION}</span>
          </span>
          <span className="brand-sub">сбор обращений</span>
        </div>
      </div>

      <div className="nav-wide">
        {mainNav.map(renderNav)}

        <div className="nav-group-label">Справочники</div>
        {refNav.map(renderNav)}

        {/* Стоп-лист почтовых доменов — только админ (раздел и API admin-only) */}
        {user?.role === 'admin' &&
          renderNav({ id: 'blocked-domains', label: 'Стоп-лист доменов', icon: 'shield' })}

        {/* Технические ошибки мобильного приложения — только админ */}
        {user?.role === 'admin' &&
          renderNav({ id: 'errors', label: 'Технические ошибки', icon: 'alert-circle' })}

        {/* Интеграция ФГИС — только супер-админ */}
        {user?.is_superadmin &&
          renderNav({ id: 'integration', label: 'Интеграция', icon: 'refresh-cw' })}

        <div className="nav-spacer" />

        {renderNav({ id: 'settings', label: 'Настройки', icon: 'settings' })}
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
