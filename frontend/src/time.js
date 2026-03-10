const ALMATY_TZ = 'Asia/Almaty'
const OFFSET_SUFFIX = '+05:00'
const HAS_TZ_RE = /([zZ]|[+-]\d{2}:\d{2})$/

function normalizeIsoString(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (HAS_TZ_RE.test(raw)) return raw
  if (/^\d{4}-\d{2}-\d{2}T/.test(raw)) return `${raw}${OFFSET_SUFFIX}`
  return raw
}

export function toAlmatyDate(value) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const dt = new Date(normalizeIsoString(value))
  return Number.isNaN(dt.getTime()) ? null : dt
}

export function formatDateTime(value) {
  const dt = toAlmatyDate(value)
  if (!dt) return '\u2014'
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: ALMATY_TZ,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(dt)
}

export function formatTime(value) {
  const dt = toAlmatyDate(value)
  if (!dt) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: ALMATY_TZ,
    hour: '2-digit',
    minute: '2-digit',
  }).format(dt)
}

export function formatDateTimeRange(start, end) {
  const from = formatDateTime(start)
  if (!end) return from
  return `${from} -> ${formatDateTime(end)}`
}
