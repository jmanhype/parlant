// services/api.js

const BASE_URL = 'http://localhost:8000';

// A helper function to handle fetch requests
const request = async (url: string, options: RequestInit = {}) => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    if (options.method === 'PATCH') return;
    return await response.json();
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

// GET request
export const getData = async (endpoint:string) => {
  return request(`${BASE_URL}/${endpoint}`);
};

// POST request
export const postData = async (endpoint:string, data: object) => {
  return request(`${BASE_URL}/${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
};

// PUT request
export const patchData = async (endpoint: string, data: object) => {
  return request(`${BASE_URL}/${endpoint}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
};

// DELETE request
export const deleteData = async (endpoint: string) => {
  return request(`${BASE_URL}/${endpoint}`, {
    method: 'DELETE',
  });
};
