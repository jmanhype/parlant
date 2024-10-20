import { useState, useEffect, useCallback } from 'react';
// const baseUrl = process.env;
// console.log(baseUrl);

interface useFetchResponse<T> {
  data: T | null;
  loading: boolean;
  error: null | {message: string};
  setRefetch: React.Dispatch<React.SetStateAction<boolean>>;
}

function objToUrlParams(obj: any) {
  const params = [];
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = encodeURIComponent(obj[key]);
      params.push(`${key}=${value}`);
    }
  }
  return `?${params.join('&')}`;
}

export default function useFetch<T>(url: string, body?: object, dependencies: (boolean | number | string)[] = [], retry = false): useFetchResponse<T> {
  const [data, setData] = useState<null | any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<null | {message: string}>(null);
  const [refetch, setRefetch] = useState(false);
  const params = body ? objToUrlParams(body) : '';

  useEffect(() => {
    if (retry && error?.message) {
        setRefetch(r => !r);
        error.message = '';
    }
  }, [retry, error]);

  const fetchData = useCallback(() => {
    const controller = new AbortController(); // Create an AbortController
    const { signal } = controller; // Get the abort signal
    setLoading(true);

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
  }, [url, refetch, ...dependencies]);

  useEffect(() => {
    const abortFetch = fetchData();

    return () => {
      abortFetch();
    };
  }, [fetchData]);

  return { data, loading, error, setRefetch };
};