import { useState, useEffect } from 'react';
// const baseUrl = process.env;
// console.log(baseUrl);

function objToUrlParams(obj: object) {
  const params = [];
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = encodeURIComponent(obj[key]);
      params.push(`${key}=${value}`);
    }
  }
  return `?${params.join('&')}`;
}

export default function useFetch(url: string, body?: object, dependencies: boolean[] = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const params = body ? objToUrlParams(body) : '';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(`http://localhost:8000/${url}${params}`);
        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }
        const result = await response.json();
        setData(result);
        setError(null)
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [url, ...dependencies]);

  return { data, loading, error };
}