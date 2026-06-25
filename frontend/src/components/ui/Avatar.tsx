function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? '?';
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

interface AvatarProps {
  name: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  src?: string | null;
}

export function Avatar({ name, size = 'md', src }: AvatarProps) {
  const px = size === 'xs' ? 16 : size === 'sm' ? 22 : size === 'lg' ? 64 : 28;
  // Фиксированный фирменный зелёный фон (как в прототипе) — без палитры по имени.
  const bg = 'var(--de-brand)';

  if (src) {
    return (
      <img
        src={src}
        alt={name}
        style={{ width: px, height: px, borderRadius: '50%', objectFit: 'cover' }}
      />
    );
  }

  return (
    <div
      style={{
        width: px,
        height: px,
        borderRadius: '50%',
        background: bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontWeight: 600,
        fontSize: px * 0.4,
      }}
    >
      {initials(name)}
    </div>
  );
}
