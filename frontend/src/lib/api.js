const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'hakk.token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body && !isForm) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent('hakk:unauthorised'));
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || d.message).join('. ')
          : `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return data;
}

export const api = {
  // meta
  config: () => request('/api/config'),
  setClock: (seconds_per_day, enabled = true) =>
    request('/api/config/clock', { method: 'POST', body: { seconds_per_day, enabled } }),
  news: () => request('/api/news'),
  notifications: () => request('/api/notifications'),
  markRead: (id) => request(`/api/notifications/${id}/read`, { method: 'POST' }),
  supportChat: (message) => request('/api/support/chat', { method: 'POST', body: { message } }),

  // auth
  authStart: (payload) => request('/api/auth/start', { method: 'POST', body: payload }),
  authVerify: (payload) => request('/api/auth/verify', { method: 'POST', body: payload }),
  authPassword: (password) => request('/api/auth/password', { method: 'POST', body: { password } }),
  authLogin: (payload) => request('/api/auth/login', { method: 'POST', body: payload }),
  me: () => request('/api/auth/me'),

  // cases
  intakeQuestions: () => request('/api/cases/intake/questions'),
  listCases: () => request('/api/cases'),
  createCase: (title) => request('/api/cases', { method: 'POST', body: { title } }),
  getCase: (id) => request(`/api/cases/${id}`),
  saveAnswers: (id, answers) =>
    request(`/api/cases/${id}/answers`, { method: 'PATCH', body: { answers } }),
  extractIntake: (id, text) =>
    request(`/api/cases/${id}/intake/extract`, { method: 'POST', body: { text } }),
  classify: (id) => request(`/api/cases/${id}/classify`, { method: 'POST' }),
  editDraft: (caseId, draftId, patch) =>
    request(`/api/cases/${caseId}/drafts/${draftId}`, { method: 'PATCH', body: patch }),
  approveDraft: (caseId, draftId) =>
    request(`/api/cases/${caseId}/drafts/${draftId}/approve`, { method: 'POST' }),
  activity: (id) => request(`/api/cases/${id}/activity`),
  caseNotifications: (id) => request(`/api/cases/${id}/notifications`),
  markUnresponsive: (id) => request(`/api/cases/${id}/mark-unresponsive`, { method: 'POST' }),
  recordAcknowledgement: (caseId, stageId, reference) =>
    request(`/api/cases/${caseId}/stages/${stageId}/acknowledge`, {
      method: 'POST',
      body: { reference },
    }),
  recordResponse: (caseId, stageId, outcome, note = '') =>
    request(`/api/cases/${caseId}/stages/${stageId}/response`, {
      method: 'POST',
      body: { outcome, note },
    }),

  // documents
  uploadDocument: (caseId, file) => {
    const form = new FormData();
    form.append('file', file);
    return request(`/api/cases/${caseId}/documents`, { method: 'POST', body: form, isForm: true });
  },
  confirmDocument: (caseId, docId, fields) =>
    request(`/api/cases/${caseId}/documents/${docId}/confirm`, {
      method: 'POST',
      body: { fields },
    }),
  deleteDocument: (caseId, docId) =>
    request(`/api/cases/${caseId}/documents/${docId}`, { method: 'DELETE' }),

  // payments
  paymentOptions: (caseId) => request(`/api/cases/${caseId}/payments/options`),
  pay: (caseId, payload) =>
    request(`/api/cases/${caseId}/payments`, { method: 'POST', body: payload }),
};

export const rupees = (paise) => `₹${(paise / 100).toFixed(0)}`;
