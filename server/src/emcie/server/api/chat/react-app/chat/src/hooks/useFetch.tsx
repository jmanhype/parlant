import { useState, useEffect, useCallback, ReactElement } from 'react';

interface useFetchResponse<T> {
  data: T | null;
  loading: boolean;
  error: null | {message: string};
  refetch: () => void;
  ErrorTemplate: (() => ReactElement) | null;
}

function objToUrlParams(obj: Record<string, unknown>) {
  const params = [];
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = encodeURIComponent(`${obj[key]}`);
      params.push(`${key}=${value}`);
    }
  }
  return `?${params.join('&')}`;
}

export default function useFetch<T>(url: string, body?: Record<string, unknown>, dependencies: unknown[] = [], retry = false): useFetchResponse<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<null | {message: string}>(null);
  const [refetchData, setRefetchData] = useState(false);
  const params = body ? objToUrlParams(body) : '';
  

  const ErrorTemplate = () => {
    return (
      <div>
        <div>Something went wrong</div>
        <div role='button' onClick={() => setRefetchData(r => !r)} className='underline cursor-pointer'>Click to retry</div>
      </div>
    );
  };

  const refetch = () => setRefetchData(r => !r);

  useEffect(() => {
    if (retry && error?.message) {
      setRefetchData(r => !r);
        error.message = '';
    }
  }, [retry, error]);

  const fetchData = useCallback(() => {
    const controller = new AbortController(); // Create an AbortController
    const { signal } = controller; // Get the abort signal
    setLoading(true);
    setError(null);

    fetch(`http://localhost:8000/${url}${params}`, { signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Error: ${response.statusText}`);
        }
        const result = await response.json(); // or response.text() / response.blob() based on your API
        setData(result);
      })
      .catch((err) => {
        if (err.name === 'AbortError') {
          console.log('Fetch aborted');
        } else {
          setError({message: err.message});
        }
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, refetchData, ...dependencies]);

  useEffect(() => {
    const abortFetch = fetchData();

    return () => {
      abortFetch();
    };
  }, [fetchData]);

  return { data, loading, error, refetch, ErrorTemplate: error && ErrorTemplate };
};