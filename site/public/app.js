const API_BASE_URL = String(
  window.__APP_CONFIG__?.apiBaseUrl || `${window.location.origin}/bff/web`
).replace(/\/+$/, '');
const MOCK_MODE = false;

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeImageUrl(url) {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('/')) return trimmed;
  try {
    const parsed = new URL(trimmed, window.location.origin);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href;
    }
  } catch (_) {
  }
  return '';
}

function validateClientInput(text, type = 'text') {
  if (!text) return false;
  if (type === 'username') {
    return text.length >= 2 && text.length <= 50 && /^[A-Za-z0-9_\-\u0400-\u04FF]+$/u.test(text);
  }
  if (type === 'email') {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text) && text.length <= 100;
  }
  if (type === 'password') {
    return text.length >= 6 && text.length <= 50;
  }
  if (type === 'description') {
    return text.length >= 10 && text.length <= 500 && !/[<>{}[\]`]/.test(text);
  }
  return text.length > 0 && text.length <= 500;
}

let facilitiesData = [];
let facilitiesById = new Map();

function showToast(message, type = 'error') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function getToken() {
  const token = localStorage.getItem('token');
  if (!token || token === 'null' || token === 'undefined' || token === '[object Object]') {
    return null;
  }
  return token;
}

function isAuthenticated() {
  return !!getToken();
}

function mapHttpError(status) {
  if (status === 401) return 'РќСѓР¶РЅРѕ РІРѕР№С‚Рё РІ СЃРёСЃС‚РµРјСѓ';
  if (status === 403) return 'РќРµС‚ РґРѕСЃС‚СѓРїР°';
  if (status === 404) return 'Р”Р°РЅРЅС‹Рµ РЅРµ РЅР°Р№РґРµРЅС‹';
  if (status === 409) return 'РљРѕРЅС„Р»РёРєС‚ РґР°РЅРЅС‹С…';
  if (status === 422) return 'РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё РґР°РЅРЅС‹С…';
  if (status >= 500) return 'РћС€РёР±РєР° СЃРµСЂРІРµСЂР°';
  return `РћС€РёР±РєР° ${status}`;
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;
    const data = await response.json().catch(() => ({}));
    if (!data?.access_token) return false;
    localStorage.setItem('token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refreshToken', data.refresh_token);
    return true;
  } catch (_) {
    return false;
  }
}

async function logoutFromServer() {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) return;
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch (_) {
  }
}

async function apiRequest(endpoint, options = {}) {
  if (MOCK_MODE) {
    await new Promise((r) => setTimeout(r, 200));
    return {};
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    ...options.headers,
  };

  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  let data;

  try {
    response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body,
    });

    data = await response.json().catch(() => ({}));

    if (!response.ok) {
      let message = data?.detail || data?.message || mapHttpError(response.status);
      if (
        response.status === 409 &&
        endpoint.includes('/reports') &&
        String(data?.detail || '').toLowerCase().includes('missing in storage')
      ) {
        message = 'Р¤Р°Р№Р» РѕС‚С‡РµС‚Р° РЅРµРґРѕСЃС‚СѓРїРµРЅ. Р—Р°РіСЂСѓР·РёС‚Рµ РѕС‚С‡РµС‚ Р·Р°РЅРѕРІРѕ.';
      }
      const error = new Error(message);
      error.status = response.status;
      error.payload = data;
      error.endpoint = endpoint;
      throw error;
    }

    return data;
  } catch (error) {
    const status = error.status || 0;
    const endpointPath = String(error.endpoint || endpoint || '');
    const isAuthEndpoint =
      endpointPath.includes('/auth/login') ||
      endpointPath.includes('/auth/register') ||
      endpointPath.includes('/auth/refresh') ||
      endpointPath.includes('/auth/logout');

    if (status === 401 && !options._retry && !isAuthEndpoint) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return apiRequest(endpoint, { ...options, _retry: true });
      }
    }

    const message = error.message || 'РЎРµС‚РµРІР°СЏ РѕС€РёР±РєР°';
    showToast(message, 'error');

    if (status === 401) {
      localStorage.clear();
      if (!window.location.pathname.endsWith('login.html')) {
        window.location.href = 'login.html';
      }
    }

    throw error;
  }
}

function mapFacility(item) {
  return {
    id: item.facility_id ?? item.id,
    name: item.name || `РћР±СЉРµРєС‚ #${item.facility_id ?? item.id ?? ''}`,
    type: item.facility_type || item.type || '',
    address: item.address || '',
    status: item.status || '',
    hours: item.hours || '09:00 - 18:00',
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    description: item.description ?? null,
    image_url: getFacilityImageUrl(item.facility_id ?? item.id)
  };
}

function mapRequest(item) {
  const facilityId = item.facility_id ?? null;
  const facility = facilitiesById.get(facilityId);

  return {
    id: item.id ?? item.request_id,
    facility_id: facilityId,
    facility_name: item.facility_name || facility?.name || (facilityId ? `РћР±СЉРµРєС‚ #${facilityId}` : 'РћР±СЉРµРєС‚'),
    description: item.description || item.title || 'Р‘РµР· РѕРїРёСЃР°РЅРёСЏ',
    status: item.status || 'CREATED',
    created_at: item.created_at || item.date || null,
  };
}

async function login(email, password) {
  if (!validateClientInput(email, 'email')) {
    showToast('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ email', 'error');
    return;
  }
  if (!validateClientInput(password, 'password')) {
    showToast('РџР°СЂРѕР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕС‚ 6 РґРѕ 50 СЃРёРјРІРѕР»РѕРІ', 'error');
    return;
  }
  
  try {
    const auth = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (!auth.access_token || typeof auth.access_token !== 'string') {
      showToast('РЎРµСЂРІРµСЂ РЅРµ РІРµСЂРЅСѓР» С‚РѕРєРµРЅ РґРѕСЃС‚СѓРїР°', 'error');
      return;
    }

    localStorage.setItem('token', auth.access_token);
    if (auth.refresh_token) {
      localStorage.setItem('refreshToken', auth.refresh_token);
    }
    localStorage.setItem('tokenType', auth.token_type || 'bearer');
    if (auth.user_id != null) localStorage.setItem('userId', String(auth.user_id));

    try {
      const me = await apiRequest('/auth/me');
      localStorage.setItem('userRole', (me.roles && me.roles[0]) || 'USER');
      localStorage.setItem('username', me.username || me.email || 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ');
    } catch (_) {
      localStorage.setItem('userRole', 'USER');
    }

    showToast('Р’С…РѕРґ РІС‹РїРѕР»РЅРµРЅ', 'success');
    window.location.href = 'index.html';
  } catch (_) {
  }
}

async function register(userData) {
  if (!validateClientInput(userData.username, 'username')) {
    showToast('РРјСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РѕС‚ 2 РґРѕ 50 СЃРёРјРІРѕР»РѕРІ (Р±СѓРєРІС‹, С†РёС„СЂС‹, _, -)', 'error');
    return;
  }
  if (!validateClientInput(userData.email, 'email')) {
    showToast('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ email', 'error');
    return;
  }
  if (!validateClientInput(userData.password, 'password')) {
    showToast('РџР°СЂРѕР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕС‚ 6 РґРѕ 50 СЃРёРјРІРѕР»РѕРІ', 'error');
    return;
  }
  
  try {
    await apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });

    showToast('Р РµРіРёСЃС‚СЂР°С†РёСЏ СѓСЃРїРµС€РЅР°. РўРµРїРµСЂСЊ РІРѕР№РґРёС‚Рµ.', 'success');
    setTimeout(() => (window.location.href = 'login.html'), 1200);
  } catch (err) {
    if (err.status === 409 && err.payload?.detail?.includes('phone')) {
      showToast('Р­С‚РѕС‚ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° СѓР¶Рµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ', 'error');
    }
  }
}

async function loadProfile() {
  try {
    const data = await apiRequest('/auth/me');
    const displayName = data.username || data.email || 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ';

    const usernameInput = document.getElementById('profileUsername');
    const emailInput = document.getElementById('profileEmail');
    const phoneInput = document.getElementById('profilePhone');

    if (usernameInput) usernameInput.value = displayName;
    if (emailInput) emailInput.value = data.email || '';
    if (phoneInput) phoneInput.value = data.phone || '';

    const userInfo = document.getElementById('userInfo');
    if (userInfo) {
      userInfo.textContent = '';
      const span = document.createElement('span');
      span.textContent = displayName;
      userInfo.appendChild(span);
    }
  } catch (err) {
  }
}

async function loadFacilities() {
  try {
    const facilities = await apiRequest('/sports-facilities');
    facilitiesData = (facilities || []).map(mapFacility);
    facilitiesById = new Map(facilitiesData.map((f) => [f.id, f]));
    renderFacilitiesList(facilitiesData);
    
  } catch (_) {
    renderFacilitiesList([]);
  }
}

function renderFacilitiesList(facilities) {
  const container = document.getElementById('facilitiesList');
  if (!container) return;
  container.textContent = '';
  if (!facilities || facilities.length === 0) {
    const emptyCard = document.createElement('div');
    emptyCard.className = 'facility-item';
    const emptyText = document.createElement('p');
    emptyText.textContent = 'No facilities data';
    emptyCard.appendChild(emptyText);
    container.appendChild(emptyCard);
    return;
  }
  const fragment = document.createDocumentFragment();
  facilities.forEach((f) => {
    const item = document.createElement('div');
    item.className = 'facility-item';
    if (f.id != null) {
      item.dataset.id = String(f.id);
    }
    const imageSrc = safeImageUrl(f.image_url);
    if (imageSrc) {
      const img = document.createElement('img');
      img.src = imageSrc;
      img.alt = f.name || 'Facility';
      img.className = 'facility-img';
      item.appendChild(img);
    }
    const title = document.createElement('h4');
    title.textContent = f.name || '';
    item.appendChild(title);
    const address = document.createElement('p');
    address.textContent = f.address || '';
    item.appendChild(address);
    const hours = document.createElement('div');
    hours.className = 'hours';
    hours.textContent = f.hours || '09:00 - 18:00';
    item.appendChild(hours);
    item.addEventListener('click', () => {
      const id = Number(f.id);
      if (!Number.isFinite(id)) return;
      openFacilityCard(id);
    });
    fragment.appendChild(item);
  });
  container.appendChild(fragment);
  if (typeof window.mapInitialized === 'undefined') {
    import('./map.js').then(module => {
      module.initMap(facilities);
      window.mapInitialized = true;
    }).catch(err => console.error('Map load error:', err));
  }
}

function openFacilityCard(id) {
  const facility = facilitiesData.find((f) => f.id === id);
  if (!facility) return;

  localStorage.setItem('selectedFacilityId', String(id));
  localStorage.setItem('selectedFacilityName', facility.name);
  localStorage.setItem('selectedFacilityAddress', facility.address);
  localStorage.setItem('selectedFacilityDescription', facility.description || '');
  localStorage.setItem('selectedFacilityImage', safeImageUrl(facility.image_url || ''));
  window.location.href = 'facility.html';

}

async function getFacilityDetails(facilityId) {
  try {
    const data = await apiRequest(`/facilities/${facilityId}/details`);
    return data;
  } catch (err) {
    return null;
  }
}

async function loadMyRequests() {
  try {
    if (!facilitiesData.length) {
      await loadFacilities();
    }
    const requests = await apiRequest('/user-requests/my');
    renderRequestsTable((requests || []).map(mapRequest));
  } catch (_) {
    renderRequestsTable([]);
  }
}

function renderRequestsTable(requests) {
  const tbody = document.getElementById('requestsBody');
  if (!tbody) return;
  const statusMap = {
    CREATED: { text: 'Created', class: 'status-created' },
    IN_PROGRESS: { text: 'In progress', class: 'status-in-progress' },
    ACTIVE: { text: 'In progress', class: 'status-assigned' },
    COMPLETED: { text: 'Completed', class: 'status-completed' },
    RESOLVED: { text: 'Completed', class: 'status-completed' },
    CANCELLED: { text: 'Cancelled', class: 'status-created' },
    REJECTED: { text: 'Rejected', class: 'status-created' },
  };
  tbody.textContent = '';
  if (!requests || requests.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.style.textAlign = 'center';
    cell.style.padding = '20px';
    cell.textContent = 'No requests';
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }
  requests.forEach((req, index) => {
    const status = statusMap[req.status] || statusMap.CREATED;
    const row = document.createElement('tr');
    const idCell = document.createElement('td');
    idCell.textContent = String(index + 1);
    const facilityCell = document.createElement('td');
    facilityCell.textContent = req.facility_name || '';
    const descriptionCell = document.createElement('td');
    descriptionCell.textContent = req.description || '';
    const dateCell = document.createElement('td');
    dateCell.textContent = req.created_at ? new Date(req.created_at).toLocaleDateString('ru-RU') : '-';
    const statusCell = document.createElement('td');
    const statusSpan = document.createElement('span');
    statusSpan.className = `status ${status.class}`;
    statusSpan.textContent = status.text;
    statusCell.appendChild(statusSpan);
    row.appendChild(idCell);
    row.appendChild(facilityCell);
    row.appendChild(descriptionCell);
    row.appendChild(dateCell);
    row.appendChild(statusCell);
    tbody.appendChild(row);
  });
}

async function submitRequest(title, description) {
  const facilityId = localStorage.getItem('selectedFacilityId');

  if (!facilityId) {
    showToast('РћС€РёР±РєР°: РѕР±СЉРµРєС‚ РЅРµ РІС‹Р±СЂР°РЅ', 'error');
    return;
  }

  if (!description || !description.trim()) {
    showToast('РћРїРёС€РёС‚Рµ РїСЂРѕР±Р»РµРјСѓ', 'error');
    return;
  }

  if (!validateClientInput(description, 'description')) {
    showToast('РћРїРёСЃР°РЅРёРµ РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РѕС‚ 10 РґРѕ 500 СЃРёРјРІРѕР»РѕРІ Рё РЅРµ СЃРѕРґРµСЂР¶Р°С‚СЊ HTML С‚РµРіРё', 'error');
    return;
  }

  try {
    await apiRequest('/user-requests', {
      method: 'POST',
      body: JSON.stringify({
        facility_id: Number(facilityId),
        title: title || 'Р—Р°СЏРІРєР° СЃ СЃР°Р№С‚Р°',
        description: description.trim(),
      }),
    });

    showToast('Р—Р°СЏРІРєР° РѕС‚РїСЂР°РІР»РµРЅР°', 'success');
    setTimeout(() => (window.location.href = 'profile.html'), 800);
  } catch (_) {
  }
}

async function updateProfile(phone, username, email) {
  try {
    const updateData = {};
    if (phone !== undefined) updateData.phone = phone || '';
    if (username !== undefined) updateData.username = username;
    if (email !== undefined) updateData.email = email;
    
    const phoneRegex = /^[\+\d\s\-\(\)]{10,20}$/;
    if (phone !== undefined && phone && !phoneRegex.test(phone)) {
      showToast('РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР°', 'error');
      return false;
    }
    
    const response = await apiRequest('/auth/me', {
      method: 'POST',
      body: JSON.stringify(updateData)
  });
    
    showToast('РџСЂРѕС„РёР»СЊ РѕР±РЅРѕРІР»С‘РЅ', 'success');
    
    if (response.username) localStorage.setItem('username', response.username);
    if (response.phone) localStorage.setItem('phone', response.phone);
    
    await loadProfile();
    return true;
  } catch (err) {
    if (err.status === 409 && err.payload?.detail?.includes('phone')) {
      showToast('Р­С‚РѕС‚ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° СѓР¶Рµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РґСЂСѓРіРёРј РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј', 'error');
    } else {
      showToast(err.message || 'РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ', 'error');
    }
    return false;
  }
}

async function getFacilityById(facilityId) {
  try {
    const data = await apiRequest(`/sports-facilities/${facilityId}`);
    return data;
  } catch (err) {
    return null;
  }
}

window.getFacilityById = getFacilityById;

async function changePassword(currentPassword, newPassword, confirmPassword) {
  // Р’РђР›РР”РђР¦РРЇ
  if (!currentPassword || !newPassword || !confirmPassword) {
    showToast('Р—Р°РїРѕР»РЅРёС‚Рµ РІСЃРµ РїРѕР»СЏ', 'error');
    return false;
  }
  
  if (newPassword !== confirmPassword) {
    showToast('РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ Рё РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РЅРµ СЃРѕРІРїР°РґР°СЋС‚', 'error');
    return false;
  }
  
  if (newPassword.length < 6) {
    showToast('РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РјРёРЅРёРјСѓРј 6 СЃРёРјРІРѕР»РѕРІ', 'error');
    return false;
  }
  
  if (currentPassword === newPassword) {
    showToast('РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ РґРѕР»Р¶РµРЅ РѕС‚Р»РёС‡Р°С‚СЊСЃСЏ РѕС‚ С‚РµРєСѓС‰РµРіРѕ', 'error');
    return false;
  }
  
  try {
    const response = await apiRequest('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ 
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: confirmPassword
      })
    });

    const message = response.message || 'РџР°СЂРѕР»СЊ СѓСЃРїРµС€РЅРѕ РёР·РјРµРЅС‘РЅ';
    showToast(message, 'success');

    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmNewPassword').value = '';

    setTimeout(() => {
      showToast('Р”Р»СЏ РїСЂРѕРґРѕР»Р¶РµРЅРёСЏ СЂР°Р±РѕС‚С‹ РІРѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ', 'info');
    }, 14 * 60 * 1000); // С‡РµСЂРµР· 14 РјРёРЅСѓС‚
    
    return true;
  } catch (err) {
    if (err.status === 401) {
      showToast('РќРµРІРµСЂРЅС‹Р№ С‚РµРєСѓС‰РёР№ РїР°СЂРѕР»СЊ', 'error');
    } else if (err.status === 400) {
      showToast('РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ СЃРѕРІРїР°РґР°РµС‚ СЃРѕ СЃС‚Р°СЂС‹Рј', 'error');
    } else if (err.status === 422) {
      showToast('РџР°СЂРѕР»СЊ РЅРµ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ С‚СЂРµР±РѕРІР°РЅРёСЏРј РёР»Рё РїР°СЂРѕР»Рё РЅРµ СЃРѕРІРїР°РґР°СЋС‚', 'error');
    } else {
      showToast(err.message || 'РћС€РёР±РєР° СЃРјРµРЅС‹ РїР°СЂРѕР»СЏ', 'error');
    }
    return false;
  }
}

function getFacilityImageUrl(facilityId) {
    return `/images/facilities/${facilityId}.jpg`;
}

document.addEventListener('DOMContentLoaded', () => {
  if (isAuthenticated()) {
    loadProfile();
  }

  if (document.getElementById('facilitiesList')) loadFacilities();
  if (document.getElementById('requestsBody')) {
    loadMyRequests();
    setInterval(loadMyRequests, 15000);
  }

  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await logoutFromServer();
      localStorage.clear();
      window.location.href = 'login.html';
    });
  }
});

window.login = login;
window.register = register;
window.showToast = showToast;
window.changePassword = changePassword;
window.getFacilityDetails = getFacilityDetails;
window.safeImageUrl = safeImageUrl;

