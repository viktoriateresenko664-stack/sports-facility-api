import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import { metrics } from '../utils/metrics';

export const API_BASE_URL = 'https://sports-facility-api.onrender.com';

console.log('API_BASE_URL:', API_BASE_URL);

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

let isRefreshing = false;
let failedQueue = [];
let tokenBlacklist = new Set();

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export function isTokenBlacklisted(token) {
  return tokenBlacklist.has(token);
}

const safeString = (value) => {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') {
    return value.token || value.refresh_token || JSON.stringify(value);
  }
  return String(value);
};

const refreshToken = async () => {
  let refreshTokenValue = await AsyncStorage.getItem('refresh_token');
  
  if (!refreshTokenValue) {
    throw new Error('Сессия истекла. Войдите снова.');
  }

  if (refreshTokenValue.startsWith('{')) {
    try {
      const parsed = JSON.parse(refreshTokenValue);
      refreshTokenValue = safeString(parsed);
    } catch (e) {
    }
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshTokenValue,
    });

    const access_token = response.data?.access_token;
    const newRefreshToken = safeString(response.data?.refresh_token);

    if (access_token) {
      await AsyncStorage.setItem('token', safeString(access_token));
      if (newRefreshToken) {
        await AsyncStorage.setItem('refresh_token', newRefreshToken);
      }
    }

    return access_token;
  } catch (error) {
    await logoutMobile();
    throw error;
  }
};

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

apiClient.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('token');
  if (token) {
    if (isTokenBlacklisted(token)) {
      throw new Error('Сессия истекла. Войдите снова.');
    }
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'] || 5;
      const waitTime = parseInt(retryAfter) * 1000;
      console.warn(`Rate limit hit, waiting ${waitTime}ms`);
      await delay(waitTime);
      return apiClient(originalRequest);
    }

    // 401 - пробуем refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch(err => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const newToken = await refreshToken();
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

function getErrorMessage(data) {
  if (!data) return null;
  if (typeof data === 'string') return data;
  if (typeof data === 'object') {
    if (data.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    if (data.message) return typeof data.message === 'string' ? data.message : JSON.stringify(data.message);
    if (data.error) return typeof data.error === 'string' ? data.error : JSON.stringify(data.error);
    return JSON.stringify(data);
  }
  return null;
}

function mapApiError(error) {
  if (!error.response && error.request) {
    return 'Нет подключения к интернету. Проверьте сеть.';
  }

  const status = error.response?.status || 0;
  const data = error.response?.data;

  // Обработка специфических статусов
  if (status === 401) return 'Неверный логин или пароль';
  if (status === 403) return 'Нет прав для выполнения действия';
  if (status === 404) return 'Данные не найдены';
  if (status === 409) return 'Недопустимый переход статуса задачи';
  if (status === 422) {
    const validationErrors = getErrorMessage(data);
    return validationErrors || 'Ошибка валидации данных';
  }
  if (status === 429) return 'Слишком много запросов. Подождите немного.';
  if (status >= 500) return 'Ошибка сервера. Попробуйте позже.';

  const errorMessage = getErrorMessage(data);
  if (errorMessage) return errorMessage;

  return 'Сетевая ошибка';
}

async function requestWithErrorHandling(requestFn, url, method) {
  const metricRequest = metrics.startRequest(url, method);

  try {
    const result = await requestFn();
    metrics.endRequest(metricRequest, 200, Date.now() - metricRequest.startTime);
    return result;
  } catch (error) {
    const errorMessage = getErrorMessage(error.response?.data) || error.message || 'Неизвестная ошибка';
    metrics.endRequestError(metricRequest, errorMessage);

    console.log('Mobile API error', {
      url: url,
      method: method,
      status: error.response?.status,
      data: error.response?.data,
    });

    const wrapped = new Error(mapApiError(error));
    wrapped.status = error.response?.status;
    wrapped.original = error;
    throw wrapped;
  }
}


export async function employeeLogin(employeeKey, password) {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.post('/auth/employee-login', {
      employee_key: employeeKey,
      password,
    });

    const token = safeString(response.data?.access_token);
    const refreshToken = safeString(response.data?.refresh_token);

    console.log('--- LOGIN TOKENS ---');
    console.log('Access token:', token ? '***' : 'EMPTY');
    console.log('Refresh token:', refreshToken ? '***' : 'EMPTY');
    console.log('------------------');

    if (token) {
      await AsyncStorage.setItem('token', token);
      await AsyncStorage.setItem('token_type', safeString(response.data?.token_type) || 'bearer');
      if (refreshToken) {
        await AsyncStorage.setItem('refresh_token', refreshToken);
      }
      if (response.data?.user_id != null) {
        await AsyncStorage.setItem('user_id', String(response.data.user_id));
      }
    }

    return {
      ...response.data,
      access_token: token,
      refresh_token: refreshToken,
    };
  }, '/auth/employee-login', 'POST');
}

export async function logoutMobile() {
  const token = await AsyncStorage.getItem('token');
  
  try {
    const refreshToken = await AsyncStorage.getItem('refresh_token');
    if (refreshToken && refreshToken.length > 0 && !refreshToken.startsWith('[')) {
      await apiClient.post('/auth/logout', { refresh_token: refreshToken });
    }
  } catch (error) {
    console.warn('Logout API error:', error.message);
  }

  if (token) {
    tokenBlacklist.add(token);
  }
  
  await AsyncStorage.multiRemove(['token', 'refresh_token', 'token_type', 'user_id']);
}

export async function getMe() {
  return requestWithErrorHandling(async () => {
    try {
      const response = await apiClient.get('/auth/me');
      return response.data;
    } catch (error) {
      if (error.response?.status === 401) {
        await logoutMobile();
        throw new Error('Сессия истекла. Войдите снова.');
      }
      throw error;
    }
  }, '/auth/me', 'GET');
}

export async function getEngineerTasks() {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.get('/bff/mobile/tasks');
    return response.data || [];
  }, '/bff/mobile/tasks', 'GET');
}

export async function getEngineerTask(taskId) {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.get(`/engineer-tasks/${taskId}`);
    return response.data;
  }, `/engineer-tasks/${taskId}`, 'GET');
}

export async function startEngineerTask(taskId) {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.post(`/engineer-tasks/${taskId}/start`);
    return response.data;
  }, `/engineer-tasks/${taskId}/start`, 'POST');
}

export async function finishEngineerTask(taskId) {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.post(`/engineer-tasks/${taskId}/finish`);
    return response.data;
  }, `/engineer-tasks/${taskId}/finish`, 'POST');
}

export async function cancelEngineerTask(taskId) {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.post(`/engineer-tasks/${taskId}/cancel`);
    return response.data;
  }, `/engineer-tasks/${taskId}/cancel`, 'POST');
}

export async function downloadReportTemplate() {
  return requestWithErrorHandling(async () => {
    const token = await AsyncStorage.getItem('token');
    
    const response = await fetch(`${API_BASE_URL}/reports/template`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to download template: ${response.status}`);
    }
    
    const blob = await response.blob();
    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    
    return { blob, contentType };
  }, '/reports/template', 'GET');
}

export async function uploadReport(taskId, file, notes = null, idempotencyKey = null) {
  return requestWithErrorHandling(async () => {
    const token = await AsyncStorage.getItem('token');
    const formData = new FormData();

    formData.append('task_id', String(taskId));
    formData.append('report_file', {
      uri: file.uri,
      name: file.name,
      type: file.mimeType || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    
    if (notes) {
      formData.append('notes', notes);
    }

    const headers = {
      'Authorization': `Bearer ${token}`,
    };
    
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }

    const response = await fetch(`${API_BASE_URL}/reports/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      const errorMsg = getErrorMessage(data) || 'Upload failed';
      throw new Error(errorMsg);
    }

    return data;
  }, '/reports/upload', 'POST');
}

export async function getMyReports() {
  return requestWithErrorHandling(async () => {
    const response = await apiClient.get('/reports/my');
    return response.data;
  }, '/reports/my', 'GET');
}


export function createRealtimeConnection(onEvent, onError) {
  console.log('Realtime: using polling fallback (SSE not available in this environment)');
  
  return {
    close: () => {
      console.log('Realtime: connection closed (no-op)');
    },
  };
}

export const createSSEConnection = createRealtimeConnection;
export const createWebSocketConnection = createRealtimeConnection;


export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export default apiClient;