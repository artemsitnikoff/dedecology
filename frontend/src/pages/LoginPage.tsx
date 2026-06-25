import { useState, type FormEvent } from 'react';
import { useLogin } from '@/api/mutations/useLogin';
import type { ApiError } from '@/api/aliases';
import './LoginPage.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const login = useLogin();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password });
  };

  const apiError = login.error as ApiError | null;
  const errCode = apiError?.error?.code;
  // Показываем ошибку ТОЛЬКО после реальной неудачной попытки входа.
  const errMsg = !apiError
    ? null
    : errCode === 'INVALID_CREDENTIALS'
      ? 'Неверный email или пароль'
      : errCode === 'ACCOUNT_LOCKED'
        ? 'Слишком много попыток. Попробуйте позже'
        : errCode === 'USER_INACTIVE'
          ? 'Пользователь деактивирован'
          : (apiError.error?.message ?? 'Ошибка входа');

  return (
    <div className="login-page">
      <div className="login-brand">
        <span className="login-brand-mark">👴</span>
        <div className="login-brand-text">
          <span className="login-brand-name">ДедЭколог</span>
          <span className="login-brand-sub">сбор обращений</span>
        </div>
      </div>

      <form onSubmit={onSubmit} className="login-form">
        <h1>Вход в систему</h1>

        <label className="login-field">
          <span>Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your.email@example.com"
          />
        </label>

        <label className="login-field">
          <span>Пароль</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Введите пароль"
          />
        </label>

        {errMsg && <div className="login-error">{errMsg}</div>}

        <button type="submit" disabled={login.isPending} className="login-submit">
          {login.isPending ? 'Вход…' : 'Войти'}
        </button>
      </form>
    </div>
  );
}
