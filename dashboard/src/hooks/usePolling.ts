import { useEffect, useRef, useCallback, useState } from "react";

const POLL_INTERVAL = 30_000;

interface UsePollingOptions {
  url: string;
  queryParams?: string;
  interval?: number;
}

export function usePolling<T>({ url, queryParams = "", interval = POLL_INTERVAL }: UsePollingOptions) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const fetchData = useCallback(async () => {
    try {
      const separator = queryParams ? "?" : "";
      const resp = await fetch(`/api/${url}${separator}${queryParams}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, [url, queryParams]);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, interval);
    return () => { clearInterval(timerRef.current); };
  }, [fetchData, interval]);

  return { data, loading, error, lastUpdated, refetch: fetchData };
}
