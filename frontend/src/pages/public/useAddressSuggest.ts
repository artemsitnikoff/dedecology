/**
 * Хук автодополнения адреса (DaData) для публичной формы.
 * Дебаунс ~300мс + отмена прошлого запроса через AbortController, чтобы
 * не было гонки ответов. Пустой список — это валидное состояние (нет токена
 * DaData или нет совпадений): пользователь тогда вводит адрес вручную.
 */
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { suggestAddress } from '@/api/intake';
import type { AddressSuggestion } from '@/api/intake';

const DEBOUNCE_MS = 300;
const MIN_LEN = 3;

interface UseAddressSuggest {
  suggestions: AddressSuggestion[];
  loading: boolean;
}

export function useAddressSuggest(query: string, enabled: boolean): UseAddressSuggest {
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled || query.trim().length < MIN_LEN) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = window.setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const list = await suggestAddress(query, 8, controller.signal);
        setSuggestions(list);
      } catch (err) {
        // Отмена запроса — не ошибка; прочие сбои подсказок гасим тихо
        // (форму всё равно можно отправить с введённым вручную адресом).
        if (!axios.isCancel(err)) setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [query, enabled]);

  // Чистим висящий запрос при размонтировании.
  useEffect(() => () => abortRef.current?.abort(), []);

  return { suggestions, loading };
}
