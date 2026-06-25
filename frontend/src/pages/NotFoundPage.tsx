import { Link } from 'react-router-dom';

/** Страница 404 — несуществующий маршрут. */
export function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-4)',
        textAlign: 'center',
        padding: 'var(--space-8)',
      }}
    >
      <div style={{ fontSize: 'var(--fs-32)', fontWeight: 700, color: 'var(--fg-1)' }}>404</div>
      <p style={{ color: 'var(--fg-2)' }}>Страница не найдена</p>
      <Link to="/incidents" style={{ color: 'var(--accent)', fontWeight: 500 }}>
        Вернуться к инцидентам
      </Link>
    </div>
  );
}
