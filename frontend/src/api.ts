import { useCallback, useEffect, useState } from 'react';

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string,string> = options.body instanceof FormData ? {} : {'Content-Type':'application/json'};
  const response = await fetch('/api' + path, {credentials:'same-origin', ...options, headers:{...headers,...options.headers}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : response.status === 422 ? 'Проверьте заполнение полей' : 'Не удалось выполнить запрос';
    throw new Error(detail);
  }
  return body as T;
}

export function useResource<T>(path: string, interval = 5000) {
  const [data,setData] = useState<T | null>(null);
  const [error,setError] = useState('');
  const [tick,setTick] = useState(0);
  const refresh = useCallback(() => setTick(value => value + 1),[]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    async function load() {
      try { const value = await api<T>(path,{signal:controller.signal}); if(active){setData(value);setError('');} }
      catch(err){if(active && !controller.signal.aborted)setError((err as Error).message);}
    }
    void load();
    const timer = interval ? setInterval(() => void load(), interval) : undefined;
    return () => {active=false;controller.abort();if(timer)clearInterval(timer);};
  },[path,interval,tick]);
  return {data,error,refresh};
}
