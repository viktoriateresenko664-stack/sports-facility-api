const express = require('express');
const cors = require('cors');
const axios = require('axios');
const path = require('path');
const rateLimit = require('express-rate-limit');

const app = express();
const PORT = Number(process.env.PORT || 3000);
const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');
const APP_ENV = String(process.env.APP_ENV || process.env.NODE_ENV || 'development').toLowerCase();
const IS_PRODUCTION = APP_ENV === 'production';


const API_BASE = (process.env.API_BASE_URL || 'https://sports-facility-api.onrender.com').trim();
const PUBLIC_API_BASE = (process.env.PUBLIC_API_BASE_URL || '/bff/web').trim();


function validateEmail(email) {
  if (!email || typeof email !== 'string') return false;
  const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return regex.test(email) && email.length <= 100;
}

function validatePassword(password) {
  if (!password || typeof password !== 'string') return false;
  return password.length >= 6 && password.length <= 50;
}

function validateUsername(username) {
  if (!username || typeof username !== 'string') return false;
  const regex = /^[a-zA-Zа-яА-Я0-9_-]{2,50}$/;
  return regex.test(username);
}

function validatePhone(phone) {
  if (!phone) return true;
  if (typeof phone !== 'string') return false;
  const regex = /^[\+\d\s\-\(\)]{10,20}$/;
  return regex.test(phone);
}

function validateDescription(description) {
  if (!description || typeof description !== 'string') return false;
  if (description.length < 10 || description.length > 500) return false;
  const dangerous = /[<>{}[\]`]/;
  return !dangerous.test(description);
}

function validateFacilityId(id) {
  const num = parseInt(id);
  return !isNaN(num) && num > 0;
}

function sanitizeString(str) {
  if (!str || typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;');
}

function hasSqlInjection(str) {
  if (!str || typeof str !== 'string') return false;
  const patterns = [
    /(\bSELECT\b.*\bFROM\b)/i,
    /(\bINSERT\b.*\bINTO\b)/i,
    /(\bUPDATE\b.*\bSET\b)/i,
    /(\bDELETE\b.*\bFROM\b)/i,
    /(\bDROP\b.*\bTABLE\b)/i,
    /(\bUNION\b.*\bSELECT\b)/i,
    /(--)/,
    /(;)/,
    /('.*OR.*'=')/i
  ];
  return patterns.some(pattern => pattern.test(str));
}

const globalLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 1000,
  message: { detail: 'Слишком много запросов. Подождите минуту.' },
  standardHeaders: true,
  legacyHeaders: false
});

const authLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  message: { detail: 'Слишком много попыток входа. Подождите минуту.' },
  skipSuccessfulRequests: true,
  standardHeaders: true,
  legacyHeaders: false
});

const requestLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  message: { detail: 'Слишком много заявок. Подождите минуту.' },
  standardHeaders: true,
  legacyHeaders: false
});

function normalizeOrigin(origin) {
  if (typeof origin !== 'string') return '';
  return origin.trim().replace(/\/+$/, '');
}

function parseCorsOrigins(rawValue) {
  const raw = String(rawValue || '').trim();
  if (!raw) return [];
  if (raw.startsWith('[')) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed
          .filter((item) => typeof item === 'string')
          .map(normalizeOrigin)
          .filter(Boolean);
      }
    } catch (_err) {
    }
  }
  return raw
    .split(',')
    .map(normalizeOrigin)
    .filter(Boolean);
}

function tryGetOrigin(value) {
  try {
    return new URL(value).origin;
  } catch (_err) {
    return null;
  }
}


const defaultOrigins = ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:5500'];
const envOrigins = parseCorsOrigins(process.env.CORS_ORIGINS);
const allowedOrigins = IS_PRODUCTION
  ? envOrigins.filter((origin) => origin !== '*')
  : (envOrigins.length ? envOrigins : defaultOrigins);
const allowAnyOrigin = !IS_PRODUCTION && allowedOrigins.includes('*');
const allowedOriginSet = new Set(allowedOrigins.map(normalizeOrigin));

const corsOptions = {
  origin(origin, callback) {
    if (!origin) return callback(null, true);
    if (allowAnyOrigin) return callback(null, true);
    if (allowedOriginSet.has(normalizeOrigin(origin))) return callback(null, true);
    return callback(null, false);
  },
  credentials: true,
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'ngrok-skip-browser-warning'],
  optionsSuccessStatus: 200
};


app.disable('x-powered-by');
app.set('trust proxy', 1);
app.use(cors(corsOptions));
app.use(express.json({ limit: '10kb' }));
app.use(globalLimiter);

const connectSrcOrigins = new Set(["'self'"]);
const apiBaseOrigin = tryGetOrigin(API_BASE);
const publicApiBaseOrigin = tryGetOrigin(PUBLIC_API_BASE);
if (apiBaseOrigin) connectSrcOrigins.add(apiBaseOrigin);
if (publicApiBaseOrigin) connectSrcOrigins.add(publicApiBaseOrigin);

const cspPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "script-src 'self' https://unpkg.com 'unsafe-inline'",
  "style-src 'self' https://unpkg.com 'unsafe-inline'",
  "img-src 'self' https: data:",
  "font-src 'self' https: data:",
  `connect-src ${Array.from(connectSrcOrigins).join(' ')}`,
].join('; ');

app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  res.setHeader('Content-Security-Policy', cspPolicy);
  const requestIsSecure = req.secure || req.headers['x-forwarded-proto'] === 'https';
  if (requestIsSecure) {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
  next();
});

function buildHeaders(authHeader = null) {
  const headers = {};
  if (authHeader) headers.Authorization = authHeader;
  return headers;
}

function proxyError(res, error, fallbackMessage) {
  const statusCode = error.response?.status || 500;
  const payload = error.response?.data || { detail: fallbackMessage };
  return res.status(statusCode).json(payload);
}

async function apiGet(url, authHeader = null) {
  return axios.get(url, { headers: buildHeaders(authHeader), timeout: 10000 });
}

async function apiPost(url, data, authHeader = null) {
  return axios.post(url, data, { headers: buildHeaders(authHeader), timeout: 10000 });
}

async function apiPut(url, data, authHeader = null) {
  return axios.put(url, data, { headers: buildHeaders(authHeader), timeout: 10000 });
}

async function apiPatch(url, data, authHeader = null) {
  return axios.patch(url, data, { headers: buildHeaders(authHeader), timeout: 10000 });
}

app.get('/config.js', (_req, res) => {
  res.type('application/javascript');
  res.send(`window.__APP_CONFIG__ = ${JSON.stringify({ apiBaseUrl: PUBLIC_API_BASE })};`);
});

app.post('/bff/web/auth/register', authLimiter, async (req, res) => {
  const { username, email, password, phone } = req.body;
  
  if (!validateUsername(username)) {
    return res.status(400).json({ detail: 'Имя пользователя от 2 до 50 символов' });
  }
  if (!validateEmail(email)) {
    return res.status(400).json({ detail: 'Некорректный email' });
  }
  if (!validatePassword(password)) {
    return res.status(400).json({ detail: 'Пароль от 6 до 50 символов' });
  }
  
  try {
    const response = await apiPost(`${API_BASE}/auth/register`, {
      username: sanitizeString(username),
      email: email.toLowerCase().trim(),
      password,
      phone: phone || ''
    });
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Registration failed');
  }
});

app.post('/bff/web/auth/login', authLimiter, async (req, res) => {
  const { email, password } = req.body;
  
  if (!validateEmail(email)) {
    return res.status(400).json({ detail: 'Некорректный email' });
  }
  
  try {
    const response = await apiPost(`${API_BASE}/auth/login`, {
      email: email.toLowerCase().trim(),
      password
    });
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Login failed');
  }
});

app.post('/bff/web/auth/refresh', authLimiter, async (req, res) => {
  const { refresh_token } = req.body || {};
  if (!refresh_token || typeof refresh_token !== 'string') {
    return res.status(422).json({ detail: 'refresh_token is required' });
  }
  try {
    const response = await apiPost(`${API_BASE}/auth/refresh`, { refresh_token: refresh_token.trim() });
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Refresh failed');
  }
});

app.post('/bff/web/auth/logout', async (req, res) => {
  const { refresh_token } = req.body || {};
  if (!refresh_token || typeof refresh_token !== 'string') {
    return res.status(422).json({ detail: 'refresh_token is required' });
  }
  try {
    await apiPost(`${API_BASE}/auth/logout`, { refresh_token: refresh_token.trim() });
    res.status(204).send();
  } catch (error) {
    proxyError(res, error, 'Logout failed');
  }
});

app.get('/bff/web/auth/me', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  try {
    const response = await apiGet(`${API_BASE}/auth/me`, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Profile request failed');
  }
});

app.post('/bff/web/auth/change-password', async (req, res) => {
  
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Требуется авторизация' });
  }
  
  const { current_password, new_password, new_password_confirm } = req.body;
  
  if (!current_password || !new_password || !new_password_confirm) {
    return res.status(422).json({ detail: 'Заполните все поля' });
  }
  if (new_password !== new_password_confirm) {
    return res.status(422).json({ detail: 'Пароли не совпадают' });
  }
  if (new_password.length < 6) {
    return res.status(422).json({ detail: 'Пароль минимум 6 символов' });
  }
  
  try {
    const response = await apiPost(`${API_BASE}/auth/change-password`, {
      current_password,
      new_password,
      new_password_confirm
    }, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Change password failed');
  }
});

app.post('/bff/web/auth/me', async (req, res) => {
  
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Требуется авторизация' });
  }
  
  const { phone, username, email } = req.body;

  if (phone !== undefined && !validatePhone(phone)) {
    return res.status(400).json({ detail: 'Некорректный номер телефона' });
  }

  if (username !== undefined && !validateUsername(username)) {
    return res.status(400).json({ detail: 'Имя пользователя от 2 до 50 символов' });
  }

  if (email !== undefined && !validateEmail(email)) {
    return res.status(400).json({ detail: 'Некорректный email' });
  }

  const updateData = {};
  if (phone !== undefined) updateData.phone = phone;
  if (username !== undefined) updateData.username = username;
  if (email !== undefined) updateData.email = email;
  
  try {
    const response = await apiPost(`${API_BASE}/auth/me`, updateData, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Update profile failed');
  }
});


app.get('/bff/web/sports-facilities/:facilityId', async (req, res) => {
  const facilityId = parseInt(req.params.facilityId);
  
  if (!validateFacilityId(facilityId)) {
    return res.status(400).json({ detail: 'Некорректный ID объекта' });
  }
  try {
    const response = await apiGet(`${API_BASE}/sports-facilities/${facilityId}`, req.headers.authorization);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Sports facility request failed');
  }
});

app.get('/bff/web/sports-facilities', async (req, res) => {
  try {
    const response = await apiGet(`${API_BASE}/sports-facilities`, req.headers.authorization);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Sports facilities request failed');
  }
});

app.get('/bff/web/facilities/:facilityId/details', async (req, res) => {
  const facilityId = req.params.facilityId;
  
  if (!validateFacilityId(facilityId)) {
    return res.status(400).json({ detail: 'Некорректный ID объекта' });
  }
  
  try {
    const response = await apiGet(`${API_BASE}/facilities/${facilityId}/details`, req.headers.authorization);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Facility details request failed');
  }
});


app.get('/bff/web/user-requests/my', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Требуется авторизация' });
  }
  try {
    const response = await apiGet(`${API_BASE}/bff/web/user-requests/my`, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'User requests request failed');
  }
});

app.post('/bff/web/user-requests', requestLimiter, async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Требуется авторизация' });
  }
  
  const { facility_id, title, description } = req.body;
  
  if (!validateFacilityId(facility_id)) {
    return res.status(400).json({ detail: 'Некорректный ID объекта' });
  }
  if (!validateDescription(description)) {
    return res.status(400).json({ detail: 'Описание от 10 до 500 символов, без HTML тегов' });
  }
  
  try {
    const response = await apiPost(`${API_BASE}/user-requests`, {
      facility_id: parseInt(facility_id),
      title: sanitizeString(title || 'Заявка с сайта'),
      description: sanitizeString(description)
    }, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Create request failed');
  }
});

app.post('/bff/mobile/auth/login', authLimiter, async (req, res) => {
  const { employee_key, password } = req.body || {};
  if (!employee_key || !password) {
    return res.status(422).json({ detail: 'employee_key and password are required' });
  }
  try {
    const response = await apiPost(`${API_BASE}/auth/employee-login`, {
      employee_key: String(employee_key).trim(),
      password,
    });
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Employee login failed');
  }
});

app.get('/bff/mobile/tasks', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  try {
    const response = await apiGet(`${API_BASE}/bff/mobile/tasks`, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Mobile tasks request failed');
  }
});

app.post('/bff/mobile/engineer-tasks/:taskId/start', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  const taskId = Number(req.params.taskId);
  if (!Number.isInteger(taskId) || taskId <= 0) {
    return res.status(400).json({ detail: 'Invalid task_id' });
  }
  try {
    const response = await apiPost(`${API_BASE}/engineer-tasks/${taskId}/start`, {}, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Start task failed');
  }
});

app.post('/bff/mobile/engineer-tasks/:taskId/finish', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  const taskId = Number(req.params.taskId);
  if (!Number.isInteger(taskId) || taskId <= 0) {
    return res.status(400).json({ detail: 'Invalid task_id' });
  }
  try {
    const response = await apiPost(`${API_BASE}/engineer-tasks/${taskId}/finish`, {}, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Finish task failed');
  }
});

app.post('/bff/mobile/reports/generate-delayed', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  try {
    const response = await apiPost(`${API_BASE}/reports/generate-delayed`, req.body || {}, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Generate delayed report failed');
  }
});

app.get('/bff/mobile/reports/jobs/:jobId', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ detail: 'Missing Authorization header' });
  }
  const jobId = req.params.jobId;
  if (!jobId) {
    return res.status(400).json({ detail: 'job_id is required' });
  }
  try {
    const response = await apiGet(`${API_BASE}/reports/jobs/${jobId}`, authHeader);
    res.json(response.data);
  } catch (error) {
    proxyError(res, error, 'Report job status request failed');
  }
});



app.use(express.static(PUBLIC_DIR));

app.get('/', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`BFF started on port ${PORT}`);
  console.log(`Proxy target configured: ${Boolean(API_BASE)}`);
  console.log(`Proxy target host: ${apiBaseOrigin || 'invalid'}`);
  console.log(`Public API base: ${PUBLIC_API_BASE}`);
});
