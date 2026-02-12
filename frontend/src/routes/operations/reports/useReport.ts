import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface UseReportResult<T> {
  data: T | null;
  loading: boolean;
  error: string;
  refresh: () => void;
}

export function useReport<T>(
  endpoint: string,
  params: Record<string, string>,
  { enabled = true }: { enabled?: boolean } = {},
): UseReportResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const paramKey = JSON.stringify(params);

  const fetchReport = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError('');
    try {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) {
        if (v) qs.set(k, v);
      }
      const url = `${endpoint}${qs.toString() ? '?' + qs.toString() : ''}`;
      const result = await api.get<T>(url);
      setData(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? (err as { detail?: string }).detail ?? err.message : 'Report failed to load.';
      setError(message);
      setData(null);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, paramKey, enabled]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  return { data, loading, error, refresh: fetchReport };
}
