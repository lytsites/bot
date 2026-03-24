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

export function formatLastOnline(value, nowValue = new Date()) {
  const dt = toAlmatyDate(value)
  if (!dt) return 'Еще не входил'

  const now = toAlmatyDate(nowValue)
  if (!now) return formatDateTime(value)

  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: ALMATY_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(dt)
  const nowParts = new Intl.DateTimeFormat('en-CA', {
    timeZone: ALMATY_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)

  const makeDateKey = sourceParts => {
    const map = Object.fromEntries(sourceParts.map(part => [part.type, part.value]))
    return `${map.year}-${map.month}-${map.day}`
  }

  const parseDateKey = key => {
    const [year, month, day] = key.split('-').map(Number)
    return Date.UTC(year, month - 1, day)
  }

  const dayDiff = Math.round((parseDateKey(makeDateKey(nowParts)) - parseDateKey(makeDateKey(parts))) / 86400000)
  const time = formatTime(dt)

  if (dayDiff <= 0) return `Сегодня, ${time}`
  if (dayDiff === 1) return `Вчера, ${time}`
  if (dayDiff < 5) return `${dayDiff} дня назад, ${time}`
  return `${dayDiff} дней назад, ${time}`
}

export function formatDateTimeRange(start, end) {
  const from = formatDateTime(start)
  if (!end) return from
  return `${from} -> ${formatDateTime(end)}`
}
