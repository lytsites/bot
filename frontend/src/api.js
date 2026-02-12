function baseDomainFromHost(hostname) {
  const host = String(hostname || '').trim().toLowerCase()
  if (!host || host === 'localhost' || host === '127.0.0.1') return ''
  // Works for most domains we use here (e.g. prok.services, e-qoldau.asia).
  const parts = host.split('.').filter(Boolean)
  if (parts.length < 2) return ''
  return parts.slice(-2).join('.')
}

const isBrowser = typeof window !== 'undefined' && typeof window.location !== 'undefined'
const host = isBrowser ? window.location.hostname : ''
const isLocalHost = host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local')
const baseDomain = baseDomainFromHost(host)

// Dev: local services. Prod: use per-domain subdomains behind Cloudflare tunnel.
const AUTH_API = isLocalHost || !baseDomain ? 'http://127.0.0.1:8001' : `https://auth.${baseDomain}`
const MAIN_API = isLocalHost || !baseDomain ? 'http://127.0.0.1:8000' : `https://api.${baseDomain}`

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
  const token = withAuth ? getAuthToken() : ''
  if (withAuth) {
    if (token) headers['X-Auth-Token'] = token
  }
  const res = await fetch(base + path, { ...options, headers })
  const text = await res.text()
  if (!res.ok) {
    let detail = ''
    if (text) {
      try {
        const parsed = JSON.parse(text)
        detail = String(parsed?.detail || parsed?.message || parsed?.error || '')
      } catch {
        detail = String(text)
      }
    }
    const code = (detail.split(':')[0] || '').trim() || detail.trim()

    if (withAuth && code === 'TG_SESSION_EXPIRED') {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('tg:session-expired', { detail: { code, message: detail } }))
      }
      throw new Error('TG_SESSION_EXPIRED')
    }

    // Only treat as "auth expired" when we actually sent a token and server says UNAUTHORIZED.
    if (res.status === 401 && withAuth && token && (code === 'UNAUTHORIZED' || !code)) {
      setAuthToken('')
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:expired'))
      }
      throw new Error('UNAUTHORIZED')
    }

    // Preserve the backend error code if provided.
    throw new Error(code || res.statusText || 'ERROR')
  }
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { ok: true, text }
  }
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
