import { useCallback, useRef, useState } from 'react';
import './Toast.css';

/**
 * Минималистичный тост (как onToast в прототипе): одно сообщение снизу-по-центру,
 * авто-скрытие через timeout. Без внешних зависимостей, без фейков — показывает
 * реальный текст результата операции.
 */
export function useToast(timeout = 4200) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback(
    (msg: string) => {
      setMessage(msg);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setMessage(null), timeout);
    },
    [timeout]
  );

  return { message, showToast };
}

/** Рендер тоста: показывает сообщение, если оно задано. */
export function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="de-toast" role="status" aria-live="polite">
      <span className="de-toast-mark">💚</span>
      <span className="de-toast-text">{message}</span>
    </div>
  );
}
