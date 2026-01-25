const isProd = typeof window !== 'undefined' && window.location.hostname.endsWith('e-qoldau.asia')
const AUTH_API = isProd ? 'https://api.e-qoldau.asia' : 'http://127.0.0.1:8001'
const MAIN_API = isProd ? 'https://api.e-qoldau.asia' : 'http://127.0.0.1:8000'

const TOKEN_KEY = 'local_auth_token'

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

async function request(base, path, options = {}, withAuth = true) {
  const headers = { ...(options.headers || {}) }
  if (withAuth) {
    const token = getAuthToken()
    if (token) headers['X-Auth-Token'] = token
  }
  const res = await fetch(base + path, { ...options, headers })
  const text = await res.text()
  if (!res.ok) throw new Error(text || res.statusText)
  return text ? JSON.parse(text) : {}
}

export async function authPost(path, payload) {
  return request(AUTH_API, path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function authGet(path) {
  return request(AUTH_API, path)
}

export async function mainGet(path) {
  return request(MAIN_API, path)
}

export async function mainPost(path, payload, withAuth = true) {
  return request(MAIN_API, path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, withAuth)
}

export async function mainPatch(path, payload) {
  return request(MAIN_API, path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function mainDelete(path) {
  return request(MAIN_API, path, { method: 'DELETE' })
}
