import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  authPost,
  getAuthToken,
  mainDelete,
  mainGet,
  mainPatch,
  mainPost,
  setAuthToken,
} from './api'
import HomeTab from './tabs/HomeTab'
import MonitoringTab from './tabs/MonitoringTab'
import SettingsTab from './tabs/SettingsTab'
import KeywordHighlight from './components/KeywordHighlight'
import SupportWidget from './components/SupportWidget'
import { formatDateTime, toAlmatyDate } from './time'
import { RefreshCw, ShieldX } from 'lucide-react'
import './styles.css'

export default function App() {
  const [password, setPassword] = useState('')
  const [qrAuthId, setQrAuthId] = useState('')
  const [qrStatus, setQrStatus] = useState('')
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [qrExpiresAt, setQrExpiresAt] = useState('')
  const [qrRefreshAfter, setQrRefreshAfter] = useState('')
  const [qrErr, setQrErr] = useState('')
  const [qrSubmitting, setQrSubmitting] = useState(false)

  const [accounts, setAccounts] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [activeAccountId, setActiveAccountId] = useState(null)
  const [aiStatus, setAiStatus] = useState({ ok: null, provider: '', deepseek_ok: null, deepseek_error: '', error: '' })

  const [uiErr, setUiErr] = useState('')
  const [toasts, setToasts] = useState([])
  const toastIdRef = useRef(1)
  const toastTimersRef = useRef(new Map())
  const [loggedIn, setLoggedIn] = useState(!!getAuthToken())
  const [login, setLogin] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginErr, setLoginErr] = useState('')
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [tgSessionExpiredOpen, setTgSessionExpiredOpen] = useState(false)
  const [tgSessionExpiredText, setTgSessionExpiredText] = useState('')
  const [activeTopTab, setActiveTopTab] = useState(() => {
    try {
      const saved = localStorage.getItem('activeTopTab')
      return saved || 'home'
    } catch {
      return 'home'
    }
  })
  const [homeSideTab, setHomeSideTab] = useState(() => {
    try {
      const saved = localStorage.getItem('homeSideTab')
      return saved || 'listening'
    } catch {
      return 'listening'
    }
  })
  const [monitorSideTab, setMonitorSideTab] = useState(() => {
    try {
      const saved = localStorage.getItem('monitorSideTab')
      return saved || 'listening'
    } catch {
      return 'listening'
    }
  })
  const [settingsSideTab, setSettingsSideTab] = useState(() => {
    try {
      const saved = localStorage.getItem('settingsSideTab')
      return saved || 'main'
    } catch {
      return 'main'
    }
  })
  const [isAdmin, setIsAdmin] = useState(false)
  const [isSuperAdmin, setIsSuperAdmin] = useState(false)
  const [isAdminChecked, setIsAdminChecked] = useState(false)
  const [meLogin, setMeLogin] = useState('')
  const [meRole, setMeRole] = useState('user')
  const [serviceEnabledChecked, setServiceEnabledChecked] = useState(false)
  const [serviceEnabled, setServiceEnabled] = useState(true)
  const [featureGroupReadingEnabled, setFeatureGroupReadingEnabled] = useState(true)
  const [featureAutoDialogsEnabled, setFeatureAutoDialogsEnabled] = useState(true)
  const [disabledComment, setDisabledComment] = useState('')
  const [keywords, setKeywords] = useState('')
  const [settingsActive, setSettingsActive] = useState(true)
  const [settingsErr, setSettingsErr] = useState('')
  const [groups, setGroups] = useState([])
  const [groupsErr, setGroupsErr] = useState('')
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [selectedGroupId, setSelectedGroupId] = useState(null)
  const [groupMatchCounts, setGroupMatchCounts] = useState({})
  const [groupWorkerId, setGroupWorkerId] = useState(null)
  const [groupWorkers, setGroupWorkers] = useState([])
  const [showMatchesModal, setShowMatchesModal] = useState(false)
  const [matchesLoading, setMatchesLoading] = useState(false)
  const [matchesErr, setMatchesErr] = useState('')
  const [matches, setMatches] = useState([])
  const [matchesGroup, setMatchesGroup] = useState(null)
  const [monitoringListeningMatches, setMonitoringListeningMatches] = useState([])
  const [monitoringListeningMatchesOffset, setMonitoringListeningMatchesOffset] = useState(0)
  const [monitoringListeningMatchesLimit, setMonitoringListeningMatchesLimit] = useState(20)

  const [adminUsers, setAdminUsers] = useState([])
  const [adminAccounts, setAdminAccounts] = useState([])
  const [adminWorkers, setAdminWorkers] = useState([])
  const [adminErrors, setAdminErrors] = useState([])
  const [adminErrorsOffset, setAdminErrorsOffset] = useState(0)
  const [adminErrorsLimit] = useState(20)
  const [adminErrorsTotal, setAdminErrorsTotal] = useState(0)
  const [adminErrorsErr, setAdminErrorsErr] = useState('')
  const [adminErrorsLoading, setAdminErrorsLoading] = useState(false)
  const [resolvingIncidentKey, setResolvingIncidentKey] = useState('')
  const [resolvingAllIncidents, setResolvingAllIncidents] = useState(false)
  const [adminMatches, setAdminMatches] = useState([])
  const [adminMatchesOffset, setAdminMatchesOffset] = useState(0)
  const [adminMatchesLimit, setAdminMatchesLimit] = useState(10)
  const [adminAutoChatDialogs, setAdminAutoChatDialogs] = useState([])
  const [adminAutoChatDialogsMeta, setAdminAutoChatDialogsMeta] = useState({ account_id: null, limit: 10, active_count: 0 })
  const [adminAutoChatDialogsErr, setAdminAutoChatDialogsErr] = useState('')
  const [adminAutoChatDialogsLoading, setAdminAutoChatDialogsLoading] = useState(false)
  const [adminAutoChatHistoryActive, setAdminAutoChatHistoryActive] = useState(null)
  const [adminAutoChatHistoryMessages, setAdminAutoChatHistoryMessages] = useState([])
  const [adminAutoChatHistoryMessagesErr, setAdminAutoChatHistoryMessagesErr] = useState('')
  const [adminAutoChatHistoryMessagesLoading, setAdminAutoChatHistoryMessagesLoading] = useState(false)
  const [adminRequisites, setAdminRequisites] = useState([])
  const [adminRequisitesErr, setAdminRequisitesErr] = useState('')
  const [adminRequisitesLoading, setAdminRequisitesLoading] = useState(false)
  const [adminLogin, setAdminLogin] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [adminIsAdmin, setAdminIsAdmin] = useState(false)
  const [adminIsActive, setAdminIsActive] = useState(true)
  const [adminAccessMode, setAdminAccessMode] = useState('both') // both | no_groups | no_auto | disabled
  const [adminErr, setAdminErr] = useState('')
  const [serviceRestartItems, setServiceRestartItems] = useState([])
  const [serviceRestartErr, setServiceRestartErr] = useState('')
  const [serviceRestartLoading, setServiceRestartLoading] = useState(false)
  const [serviceRestartReloading, setServiceRestartReloading] = useState(false)
  const [restartingServiceKey, setRestartingServiceKey] = useState('')
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    try {
      return localStorage.getItem('theme') === 'dark'
    } catch {
      return false
    }
  })
  const [isOnline, setIsOnline] = useState(() => {
    try {
      return typeof navigator !== 'undefined' ? Boolean(navigator.onLine) : true
    } catch {
      return true
    }
  })
  const [autoChatInput, setAutoChatInput] = useState('')
  const [autoChatUsernames, setAutoChatUsernames] = useState([])
  const [autoChatSelected, setAutoChatSelected] = useState([])
  const [autoChatErr, setAutoChatErr] = useState('')
  const [autoChatLoading, setAutoChatLoading] = useState(false)
  const [autoChatAiInstruction, setAutoChatAiInstruction] = useState('')
  const [autoChatGreetingExamples, setAutoChatGreetingExamples] = useState('')
  const [autoChatDelayEnabled, setAutoChatDelayEnabled] = useState(false)
  const [autoChatDelayMinSec, setAutoChatDelayMinSec] = useState('0')
  const [autoChatDelayMaxSec, setAutoChatDelayMaxSec] = useState('0')
  const [autoChatTypingEnabled, setAutoChatTypingEnabled] = useState(false)
  const [autoChatReadEnabled, setAutoChatReadEnabled] = useState(false)
  const [autoChatSettingsErr, setAutoChatSettingsErr] = useState('')
  const [autoChatSettingsLoading, setAutoChatSettingsLoading] = useState(false)
  const [homeAutoChatUsernames, setHomeAutoChatUsernames] = useState([])
  const [homeAutoChatErr, setHomeAutoChatErr] = useState('')
  const [homeAutoChatLoading, setHomeAutoChatLoading] = useState(false)
  const [homeAutoChatActive, setHomeAutoChatActive] = useState(null)
  const [homeAutoChatDialogs, setHomeAutoChatDialogs] = useState([])
  const [homeAutoChatDialogsMeta, setHomeAutoChatDialogsMeta] = useState({
    account_id: null,
    limit: 10,
    active_count: 0,
  })
  const [homeAutoChatDialogsErr, setHomeAutoChatDialogsErr] = useState('')
  const [homeAutoChatDialogsLoading, setHomeAutoChatDialogsLoading] = useState(false)
  const [homeAutoChatSelected, setHomeAutoChatSelected] = useState([])
  const [homeAutoChatMessages, setHomeAutoChatMessages] = useState([])
  const [homeAutoChatMessagesErr, setHomeAutoChatMessagesErr] = useState('')
  const [homeAutoChatMessagesLoading, setHomeAutoChatMessagesLoading] = useState(false)
  const homeAutoChatLastMessageIdRef = useRef(null)
  const [homeAutoChatHistoryActive, setHomeAutoChatHistoryActive] = useState(null)
  const [homeAutoChatHistoryMessages, setHomeAutoChatHistoryMessages] = useState([])
  const [homeAutoChatHistoryMessagesErr, setHomeAutoChatHistoryMessagesErr] = useState('')
  const [homeAutoChatHistoryMessagesLoading, setHomeAutoChatHistoryMessagesLoading] = useState(false)
  const homeAutoChatHistoryLastMessageIdRef = useRef(null)
  const adminAutoChatHistoryLastMessageIdRef = useRef(null)

  const [homeRequisites, setHomeRequisites] = useState([])
  const [homeRequisitesErr, setHomeRequisitesErr] = useState('')
  const [homeRequisitesLoading, setHomeRequisitesLoading] = useState(false)
  const [supportNoticeOpen, setSupportNoticeOpen] = useState(false)
  const [supportNoticeTitle, setSupportNoticeTitle] = useState('Новая линия поддержки')
  const [supportNoticeText, setSupportNoticeText] = useState('')
  const [systemRestartActive, setSystemRestartActive] = useState(false)
  const [systemRestartReason, setSystemRestartReason] = useState('')
  const [systemRestartUntil, setSystemRestartUntil] = useState('')

  const listeningGroups = useMemo(
    () => groups.filter(item => item.is_listening),
    [groups]
  )

  const systemRestartUntilDate = useMemo(() => toAlmatyDate(systemRestartUntil), [systemRestartUntil])
  const restartGraceActive = Boolean(systemRestartUntilDate && systemRestartUntilDate.getTime() > Date.now())
  const aiUnavailable = loggedIn && isOnline && (aiStatus?.ok === false || aiStatus?.deepseek_ok === false)
  const systemRestarting = loggedIn && (systemRestartActive || restartGraceActive)
  const systemBlockOpen = systemRestarting || !isOnline || aiUnavailable
  const systemBlockTitle = systemRestarting
    ? 'Сервер перезагружается'
    : (!isOnline ? 'Нет интернет-соединения' : 'ИИ недоступен')
  const systemBlockDetail = systemRestarting
    ? 'Идёт технический перезапуск серверных процессов. Окно закроется автоматически после завершения.'
    : (!isOnline
      ? 'Проверьте подключение к интернету. Окно закроется автоматически, когда соединение восстановится.'
      : (aiStatus?.deepseek_error || aiStatus?.error || 'Сервис временно недоступен. Попробуйте позже.'))

  const sortedGroups = useMemo(() => {
    return [...groups].sort((a, b) => {
      const aListen = a.is_listening ? 1 : 0
      const bListen = b.is_listening ? 1 : 0
      if (aListen !== bListen) return bListen - aListen
      const aTitle = (a.title || '').toLowerCase()
      const bTitle = (b.title || '').toLowerCase()
      if (aTitle < bTitle) return -1
      if (aTitle > bTitle) return 1
      return 0
    })
  }, [groups])

  const jobStatusMeta = status => {
    switch (status) {
      case 'RUNNING':
        return { label: 'Работает', cls: 'success' }
      case 'PENDING':
        return { label: 'В очереди', cls: 'warn' }
      case 'DONE':
        return { label: 'Готово', cls: 'success' }
      case 'FAILED':
        return { label: 'Ошибка', cls: 'danger' }
      case 'CANCELLED':
        return { label: 'Отменено', cls: 'muted' }
      default:
        return { label: status || '—', cls: 'muted' }
    }
  }

  const ERROR_MAP = {
    BAD_CREDENTIALS: 'Неверный логин или пароль',
    UNAUTHORIZED: 'Требуется вход',
    ADMIN_ONLY: 'Доступ только для администратора',
    SERVICE_DISABLED: 'Вам отключили возможности сервиса',
    FEATURE_DISABLED: 'Функция недоступна',
    NO_ACTIVE_ACCOUNT: 'Нет активного Telegram-аккаунта',
    SETTINGS_NOT_FOUND: 'Настройки не найдены',
    ACCOUNT_NOT_FOUND: 'Аккаунт не найден',
    SESSION_NOT_FOUND: 'Сессия не найдена',
    CONFIRM_REQUIRED: 'Требуется подтверждение',
    CREATE_FAILED: 'Ошибка создания',
    LOGIN_EXISTS: 'Логин уже существует',
    PHONE_EXISTS: 'Номер уже добавлен',
    PASSWORD_FAILED: 'Неверный пароль 2FA',
    CODE_INVALID: 'Неверный код',
    PHONE_CODE_INVALID: 'Неверный код',
    PHONE_NUMBER_INVALID: 'Неверный номер телефона',
    TG_SESSION_EXPIRED: 'Сессия Telegram истекла. Переавторизуйтесь',
    LOGIN_RATE_LIMITED: 'Слишком много попыток входа. Попробуйте позже',
  }

  const formatError = err => {
    if (!err) return ''
    let msg = typeof err === 'string' ? err : (err.message || String(err))
    msg = msg || ''
    let detail = ''
    const trimmed = msg.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed)
        detail = parsed.detail || parsed.message || parsed.error || ''
      } catch {
        detail = ''
      }
    }
    const raw = detail || msg
    const code = (raw.split(':')[0] || '').trim()
    if (ERROR_MAP[code]) {
      const tail = raw.includes(':') ? raw.split(':').slice(1).join(':').trim() : ''
      return tail ? `${ERROR_MAP[code]}: ${tail}` : ERROR_MAP[code]
    }
    return raw
  }

  const normalizePhoneDigits = raw => {
    const s = String(raw || '').trim()
    const digits = s.replace(/\D+/g, '')
    if (!digits) throw new Error('PHONE_NUMBER_INVALID')
    if (digits.length < 10 || digits.length > 15) throw new Error('PHONE_NUMBER_INVALID')
    return digits
  }

  const aiStatusText = () => {
    if (aiStatus?.ok !== true) return 'Ошибка'
    if (aiStatus?.deepseek_ok === false) return 'Ошибка'
    if (aiStatus?.deepseek_ok === true) return 'OK'
    return 'Проверка'
  }

  const removeToast = id => {
    setToasts(prev => prev.filter(t => t.id !== id))
    const tm = toastTimersRef.current.get(id)
    if (tm) clearTimeout(tm)
    toastTimersRef.current.delete(id)
  }

  const pushToast = (type, title, message, ttlMs = 3500) => {
    const id = toastIdRef.current++
    const item = {
      id,
      type: type || 'info',
      title: title || '',
      message: message || '',
    }
    setToasts(prev => {
      const next = [...prev, item]
      return next.length > 5 ? next.slice(next.length - 5) : next
    })
    const tm = setTimeout(() => removeToast(id), ttlMs)
    toastTimersRef.current.set(id, tm)
  }

  useEffect(() => {
    return () => {
      for (const tm of toastTimersRef.current.values()) {
        try {
          clearTimeout(tm)
        } catch {
        }
      }
      toastTimersRef.current.clear()
    }
  }, [])

  const isSameData = (a, b) => {
    try {
      return JSON.stringify(a) === JSON.stringify(b)
    } catch {
      return false
    }
  }

  const jobTypeLabel = type => {
    switch ((type || '').toUpperCase()) {
      case 'GROUP_LISTENER':
        return 'Мониторинг чатов'
      case 'CONNECT_CHECK':
        return 'Проверка подключения'
      case 'SUBSCRIBE_EVENTS':
        return 'Подписка на события'
      case 'READ_LAST_MESSAGES':
        return 'Чтение сообщений'
      case 'ANALYZE_MESSAGES':
        return 'Анализ сообщений'
      default:
        return type || '—'
    }
  }

  async function loadMe() {
    try {
      const r = await mainGet('/local/me')
      const admin = r.is_admin === 1 || r.is_admin === true || r.is_admin === '1'
      const superAdmin =
        r.is_super_admin === 1 ||
        r.is_super_admin === true ||
        r.is_super_admin === '1' ||
        (typeof r.role === 'string' && r.role.toLowerCase() === 'superadmin')
      setIsAdmin(Boolean(admin || superAdmin))
      setIsSuperAdmin(Boolean(superAdmin))
      setMeLogin(String(r.login || ''))
      setMeRole(typeof r.role === 'string' ? r.role.toLowerCase() : (superAdmin ? 'superadmin' : admin ? 'admin' : 'user'))
      setServiceEnabled(r.service_enabled === true || r.service_enabled === 1 || r.service_enabled === '1')
      setFeatureGroupReadingEnabled(
        r.feature_group_reading_enabled === true || r.feature_group_reading_enabled === 1 || r.feature_group_reading_enabled === '1'
      )
      setFeatureAutoDialogsEnabled(
        r.feature_auto_dialogs_enabled === true || r.feature_auto_dialogs_enabled === 1 || r.feature_auto_dialogs_enabled === '1'
      )
      setDisabledComment(String(r.disabled_comment || ''))
      return r
    } catch {
      setIsAdmin(false)
      setIsSuperAdmin(false)
      setMeLogin('')
      setMeRole('user')
      setServiceEnabled(true)
      setFeatureGroupReadingEnabled(true)
      setFeatureAutoDialogsEnabled(true)
      setDisabledComment('')
      return null
    } finally {
      setIsAdminChecked(true)
      setServiceEnabledChecked(true)
    }
  }

  async function loadAdminUsers() {
    const r = await mainGet('/admin/users')
    setAdminUsers(r.items || [])
  }

  async function loadAdminAccounts() {
    const r = await mainGet('/admin/accounts')
    setAdminAccounts(r.items || [])
  }

  async function loadAdminUserLoginHistory(userId, limit = 10, offset = 0) {
    const r = await mainGet(`/admin/users/${userId}/login_history?limit=${limit}&offset=${offset}`)
    return {
      items: r.items || [],
      total: Number(r.total || 0),
      limit: Number(r.limit || limit),
      offset: Number(r.offset || offset),
    }
  }

  async function loadAdminWorkers() {
    const r = await mainGet('/admin/group_workers')
    setAdminWorkers(r.items || [])
  }

  async function loadServiceRestarts({ silent = false } = {}) {
    if (!silent) {
      setServiceRestartErr('')
      setServiceRestartLoading(true)
    } else {
      setServiceRestartReloading(true)
    }
    try {
      const r = await mainGet('/admin/system/restarts')
      setServiceRestartItems(r.items || [])
      setServiceRestartErr('')
    } catch (e) {
      setServiceRestartErr(formatError(e))
      if (!silent) setServiceRestartItems([])
    } finally {
      if (!silent) setServiceRestartLoading(false)
      else setServiceRestartReloading(false)
    }
  }

  async function requestServiceRestart(serviceKey) {
    if (!serviceKey) return
    setRestartingServiceKey(serviceKey)
    try {
      const r = await mainPost(`/admin/system/restarts/${encodeURIComponent(serviceKey)}`, {})
      const label = r?.item?.label || serviceKey
      await loadServiceRestarts({ silent: true })
      pushToast('success', 'Поставлено в очередь', `Запрос на перезапуск "${label}" создан`)
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
      await loadServiceRestarts({ silent: true }).catch(() => {})
    } finally {
      setRestartingServiceKey('')
    }
  }

  async function loadAdminErrors(offset = adminErrorsOffset, limit = adminErrorsLimit) {
    setAdminErrorsErr('')
    setAdminErrorsLoading(true)
    try {
      const r = await mainGet(`/admin/errors?limit=${limit}&offset=${offset}`)
      setAdminErrors(r.items || [])
      setAdminErrorsTotal(Number(r.total || 0))
    } catch (e) {
      setAdminErrorsErr(formatError(e))
      setAdminErrors([])
      setAdminErrorsTotal(0)
    } finally {
      setAdminErrorsLoading(false)
    }
  }

  async function resolveAdminIncident(row) {
    const source = String(row?.source || '').trim()
    const sourceId = String(row?.source_id ?? '').trim()
    if (!source || !sourceId) return
    const key = `${source}:${sourceId}`
    setResolvingIncidentKey(key)
    try {
      await mainPost(`/admin/errors/${encodeURIComponent(source)}/${encodeURIComponent(sourceId)}/resolve`, {})
      await loadAdminErrors(adminErrorsOffset, adminErrorsLimit)
      if (source === 'support_tickets') {
        // keep support widget/status in sync if open in the same session
        await loadSupportNotice().catch(() => {})
      }
      pushToast('success', 'Сохранено', 'Инцидент помечен как решенный')
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    } finally {
      setResolvingIncidentKey('')
    }
  }

  async function resolveAllAdminIncidents() {
    setResolvingAllIncidents(true)
    try {
      const r = await mainPost('/admin/errors/resolve_all', {})
      await loadAdminErrors(adminErrorsOffset, adminErrorsLimit)
      await loadSupportNotice().catch(() => {})
      pushToast('success', 'Сохранено', `Отмечено как решенные: ${Number(r?.resolved || 0)}`)
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    } finally {
      setResolvingAllIncidents(false)
    }
  }

  async function loadAdminMatches(offset = adminMatchesOffset, limit = adminMatchesLimit) {
    const r = await mainGet(`/admin/group_matches?limit=${limit}&offset=${offset}`)
    setAdminMatches(r.items || [])
  }

  async function loadMonitoringListeningMatches(
    offset = monitoringListeningMatchesOffset,
    limit = monitoringListeningMatchesLimit
  ) {
    const r = await mainGet(`/group_matches?limit=${limit}&offset=${offset}`)
    setMonitoringListeningMatches(r.items || [])
  }

  async function loadAdminAutoChatDialogs() {
    setAdminAutoChatDialogsErr('')
    setAdminAutoChatDialogsLoading(true)
    try {
      const r = await mainGet('/admin/auto_chat/dialogs')
      setAdminAutoChatDialogs(r.items || [])
      setAdminAutoChatDialogsMeta({
        account_id: r.account_id ?? null,
        limit: r.limit ?? 10,
        active_count: r.active_count ?? 0,
      })
    } catch (e) {
      setAdminAutoChatDialogsErr(formatError(e))
      setAdminAutoChatDialogs([])
      setAdminAutoChatDialogsMeta({ account_id: null, limit: 10, active_count: 0 })
    } finally {
      setAdminAutoChatDialogsLoading(false)
    }
  }

  async function loadAdminAutoChatHistoryMessages(dialogId, limit = 2000) {
    if (!dialogId) return
    setAdminAutoChatHistoryMessagesErr('')
    setAdminAutoChatHistoryMessagesLoading(true)
    try {
      const r = await mainGet(`/admin/auto_chat/dialogs/${dialogId}/messages?limit=${limit}`)
      const items = r.items || []
      adminAutoChatHistoryLastMessageIdRef.current = items.length ? items[items.length - 1].id : null
      setAdminAutoChatHistoryMessages(items)
    } catch (e) {
      setAdminAutoChatHistoryMessagesErr(formatError(e))
      adminAutoChatHistoryLastMessageIdRef.current = null
      setAdminAutoChatHistoryMessages([])
    } finally {
      setAdminAutoChatHistoryMessagesLoading(false)
    }
  }

  async function loadAdminRequisites() {
    setAdminRequisitesErr('')
    setAdminRequisitesLoading(true)
    try {
      const r = await mainGet('/admin/requisites')
      setAdminRequisites(r.items || [])
    } catch (e) {
      setAdminRequisitesErr(formatError(e))
      setAdminRequisites([])
    } finally {
      setAdminRequisitesLoading(false)
    }
  }

  async function deleteMonitoringGroupMatch(matchId) {
    if (!isSuperAdmin || !matchId) return
    const ok = confirm('Удалить запись из истории чтения групп?')
    if (!ok) return
    try {
      await mainDelete(`/admin/group_matches/${matchId}`)
      await Promise.allSettled([
        loadAdminMatches(adminMatchesOffset, adminMatchesLimit),
        loadMonitoringListeningMatches(monitoringListeningMatchesOffset, monitoringListeningMatchesLimit),
      ])
      pushToast('success', 'Удалено', 'Запись удалена')
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function deleteMonitoringAutoDialog(dialogId) {
    if (!isSuperAdmin || !dialogId) return
    const ok = confirm('Удалить диалог из истории авто-общения?')
    if (!ok) return
    try {
      await mainDelete(`/admin/auto_chat/dialogs/${dialogId}`)
      await Promise.allSettled([loadAdminAutoChatDialogs(), loadHomeAutoChatDialogs()])
      if (adminAutoChatHistoryActive?.dialog_id === dialogId) {
        setAdminAutoChatHistoryActive(null)
        setAdminAutoChatHistoryMessages([])
      }
      if (homeAutoChatHistoryActive?.dialog_id === dialogId) {
        setHomeAutoChatHistoryActive(null)
        setHomeAutoChatHistoryMessages([])
      }
      pushToast('success', 'Удалено', 'Диалог удален')
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function deleteMonitoringRequisite(requisiteId) {
    if (!isSuperAdmin || !requisiteId) return
    const ok = confirm('Удалить реквизит из истории?')
    if (!ok) return
    try {
      await mainDelete(`/admin/requisites/${requisiteId}`)
      await Promise.allSettled([loadAdminRequisites(), loadHomeRequisites()])
      pushToast('success', 'Удалено', 'Реквизит удален')
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function createAdminUser() {
    setAdminErr('')
    try {
      let service_enabled = true
      let feature_group_reading_enabled = true
      let feature_auto_dialogs_enabled = true
      if (adminAccessMode === 'no_groups') {
        feature_group_reading_enabled = false
        feature_auto_dialogs_enabled = true
      } else if (adminAccessMode === 'no_auto') {
        feature_group_reading_enabled = true
        feature_auto_dialogs_enabled = false
      } else if (adminAccessMode === 'disabled') {
        service_enabled = false
        feature_group_reading_enabled = false
        feature_auto_dialogs_enabled = false
      }
      const r = await mainPost('/admin/users', {
        login: adminLogin,
        password: adminPassword,
        role: adminIsAdmin ? 'admin' : 'user',
        is_active: adminIsActive,
        service_enabled,
        feature_group_reading_enabled,
        feature_auto_dialogs_enabled,
      })
      if (r?.id) {
        setAdminLogin('')
        setAdminPassword('')
        setAdminIsAdmin(false)
        setAdminIsActive(true)
        setAdminAccessMode('both')
        pushToast('success', 'Создано', `Локальный аккаунт создан (ID: ${r.id})`)
      } else {
        pushToast('success', 'Создано', 'Локальный аккаунт создан')
      }
      await loadAdminUsers()
    } catch (e) {
      const msg = formatError(e)
      setAdminErr(msg)
      pushToast('error', 'Ошибка', msg, 6000)
    }
  }

  async function updateAdminUser(userId, patch) {
    setAdminErr('')
    try {
      await mainPatch(`/admin/users/${userId}`, patch || {})
      await loadAdminUsers()
      pushToast('success', 'Сохранено', `Пользователь обновлён (ID: ${userId})`)
    } catch (e) {
      const msg = formatError(e)
      setAdminErr(msg)
      pushToast('error', 'Ошибка', msg, 6000)
    }
  }

  async function deleteAdminUser(userId) {
    const ok = confirm('Удалить локального пользователя? Это удалит все его аккаунты и данные.')
    if (!ok) return
    try {
      await mainDelete(`/admin/users/${userId}?confirm=true`)
      await loadAdminUsers()
      await loadAdminAccounts()
      await loadAdminWorkers()
      await loadAdminMatches()
      pushToast('success', 'Удалено', `Локальный аккаунт удален (ID: ${userId})`)
    } catch (e) {
      const msg = formatError(e)
      setAdminErr(msg)
      pushToast('error', 'Ошибка', msg, 6000)
    }
  }

  async function deleteAdminAccount(accountId) {
    const ok = confirm('Удалить Telegram-аккаунт? Будут удалены сессии и данные.')
    if (!ok) return
    try {
      await mainDelete(`/admin/accounts/${accountId}?confirm=true`)
      await loadAdminAccounts()
      await loadAdminWorkers()
      await loadAdminMatches()
      pushToast('success', 'Удалено', `Telegram-аккаунт удален (ID: ${accountId})`)
    } catch (e) {
      const msg = formatError(e)
      setAdminErr(msg)
      pushToast('error', 'Ошибка', msg, 6000)
    }
  }

  const selectedAccount = useMemo(
    () => accounts.find(acc => acc.id === selectedId),
    [accounts, selectedId]
  )

  async function startQr() {
    setQrErr('')
    try {
      const r = await authPost('/auth/qr/start', {})
      setQrAuthId(r.auth_id)
      setQrStatus(r.status)
      setQrDataUrl(r.qr_data_url || '')
      setQrExpiresAt(r.expires_at || '')
      setQrRefreshAfter(r.refresh_after || '')
    } catch (e) {
      setQrErr(formatError(e))
    }
  }

  async function refreshQr() {
    if (!qrAuthId) return
    setQrErr('')
    try {
      const r = await authPost('/auth/qr/refresh', { auth_id: qrAuthId })
      setQrStatus(r.status)
      setQrDataUrl(r.qr_data_url || '')
      setQrExpiresAt(r.expires_at || '')
      setQrRefreshAfter(r.refresh_after || '')
    } catch (e) {
      setQrErr(formatError(e))
    }
  }

  async function continueQr() {
    if (!qrAuthId) return
    try {
      const r = await authPost('/auth/qr/continue', { auth_id: qrAuthId })
      setQrStatus(r.status)
      if (r.error_message) {
        setQrErr(r.error_message)
      }
    } catch (e) {
      setQrErr(formatError(e))
    }
  }

  function resetQrState() {
    setPassword('')
    setQrAuthId('')
    setQrStatus('')
    setQrDataUrl('')
    setQrExpiresAt('')
    setQrRefreshAfter('')
    setQrErr('')
    setQrSubmitting(false)
  }

  async function cancelQr() {
    setQrErr('')
    if (!qrAuthId) {
      resetQrState()
      return true
    }
    try {
      await authPost('/auth/cancel', { auth_id: qrAuthId })
      resetQrState()
      return true
    } catch (e) {
      setQrErr(formatError(e))
      return false
    }
  }

  async function closeAuthModal() {
    let cancelled = true
    if (qrAuthId && !qrStopped) {
      cancelled = await cancelQr()
    } else {
      resetQrState()
    }
    if (!cancelled) return
    resetQrState()
    setAuthModalOpen(false)
  }

  async function sendPassword() {
    setQrSubmitting(true)
    try {
      if (!qrAuthId) {
        throw new Error('AUTH_ID_REQUIRED')
      }
      const p = String(password || '')
      if (!p.trim()) {
        throw new Error('PASSWORD_REQUIRED')
      }
      const r = await authPost('/auth/password', { auth_id: qrAuthId, password: p })
      setQrStatus(r.status)
    } catch (e) {
      setQrErr(formatError(e))
    } finally {
      setQrSubmitting(false)
    }
  }

  async function loadAccounts() {
    const r = await mainGet('/accounts')
    setAccounts(r.items || [])
  }

  async function loadSessions(accountId) {
    if (!accountId) return setSessions([])
    const r = await mainGet(`/accounts/${accountId}/sessions`)
    setSessions(r.items || [])
  }

  async function loadJobs(accountId) {
    const path = accountId ? `/jobs?account_id=${accountId}` : '/jobs'
    const r = await mainGet(path)
    const next = r.items || []
    setJobs(prev => (isSameData(prev, next) ? prev : next))
  }

  async function loadStats() {
    const r = await mainGet('/stats')
    setStats(prev => (isSameData(prev, r) ? prev : r))
  }

  async function loadAiStatus() {
    try {
      const r = await mainGet('/ai/status?probe=true')
      setAiStatus({
        ok: Boolean(r?.ok),
        provider: String(r?.provider || ''),
        deepseek_ok: r?.deepseek_ok ?? null,
        deepseek_error: String(r?.deepseek_error || ''),
        error: r?.error ? String(r.error) : '',
      })
      setSystemRestartActive(Boolean(r?.system_restarting))
      setSystemRestartReason(String(r?.system_restart_reason || ''))
      setSystemRestartUntil(String(r?.system_restart_until || ''))
    } catch (e) {
      const keepRestartModal = Boolean(systemRestartUntilDate && systemRestartUntilDate.getTime() > Date.now())
      setSystemRestartActive(keepRestartModal)
      if (!keepRestartModal) {
        setSystemRestartReason('')
        setSystemRestartUntil('')
      }
      setAiStatus({ ok: false, provider: '', deepseek_ok: false, deepseek_error: '', error: formatError(e) })
    }
  }

  async function loadSupportNotice() {
    try {
      const r = await mainGet('/support/notice')
      const show = Boolean(r?.show)
      setSupportNoticeTitle(String(r?.title || 'Новая линия поддержки'))
      setSupportNoticeText(String(r?.text || ''))
      setSupportNoticeOpen(show)
    } catch {
      setSupportNoticeOpen(false)
    }
  }

  async function closeSupportNotice() {
    try {
      await mainPost('/support/notice/ack', {})
    } catch {
      // ignore
    } finally {
      setSupportNoticeOpen(false)
    }
  }

  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    try {
      window.addEventListener('online', onOnline)
      window.addEventListener('offline', onOffline)
    } catch {
      // ignore
    }
    return () => {
      try {
        window.removeEventListener('online', onOnline)
        window.removeEventListener('offline', onOffline)
      } catch {
        // ignore
      }
    }
  }, [])

  const aiPollingRef = useRef({ inFlight: false, t: null })
  useEffect(() => {
    if (!loggedIn) return
    if (!isOnline) return

    const tick = async () => {
      if (aiPollingRef.current.inFlight) return
      aiPollingRef.current.inFlight = true
      try {
        await loadAiStatus()
      } finally {
        aiPollingRef.current.inFlight = false
      }
    }

    tick().catch(() => {})
    const t = setInterval(() => tick().catch(() => {}), 15000)
    aiPollingRef.current.t = t
    return () => {
      try {
        clearInterval(t)
      } catch {
        // ignore
      }
      aiPollingRef.current.t = null
      aiPollingRef.current.inFlight = false
    }
  }, [loggedIn, isOnline, systemRestartUntilDate])

  async function loadSettings() {
    try {
      const r = await mainGet('/local/settings')
      setKeywords(r.keywords || '')
      setSettingsActive(r.is_active === 1 || r.is_active === true)
    } catch (e) {
      setSettingsErr(formatError(e))
    }
  }

  const normalizeKeywords = value => {
    const raw = String(value || '')
    // Keep it simple: comma-separated list, trim parts, drop empties, keep order, de-dupe case-insensitively.
    const parts = raw
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    const seen = new Set()
    const out = []
    for (const p of parts) {
      const k = p.toLowerCase()
      if (seen.has(k)) continue
      seen.add(k)
      out.push(p)
    }
    return out.join(', ')
  }

  async function saveSettings(nextKeywords, nextActive) {
    setSettingsErr('')
    try {
      await mainPatch('/local/settings', {
        keywords: normalizeKeywords(nextKeywords),
        is_active: nextActive,
      })
    } catch (e) {
      setSettingsErr(formatError(e))
    }
  }

  async function handleKeywordsChange(value) {
    await saveSettings(value, settingsActive)
  }

  async function handleActiveToggle(value) {
    await saveSettings(keywords, value)
  }

  async function saveListeningSettings(nextKeywords, nextActive) {
    setSettingsErr('')
    try {
      await mainPatch('/local/settings', {
        keywords: normalizeKeywords(nextKeywords),
        is_active: Boolean(nextActive),
      })
      // Ensure UI is always consistent with DB state (and also pulls normalized keywords).
      await loadSettings()
      // Keywords changes also resync Home match visibility server-side; refresh counts for Home view.
      await loadGroups().catch(() => {})
      if (showMatchesModal && matchesGroup?.id) {
        await reloadGroupMatches().catch(() => {})
      }
      pushToast('success', 'Сохранено', 'Настройки чтения групп обновлены')
    } catch (e) {
      const msg = formatError(e)
      setSettingsErr(msg)
      pushToast('error', 'Ошибка', msg, 6000)
    }
  }

  async function loadGroups() {
    setGroupsErr('')
    setGroupsLoading(true)
    try {
      const r = await mainGet('/groups')
      setGroups(r.items || [])
      setGroupWorkerId(r.worker_id || null)
      const wr = await mainGet('/group_workers')
      setGroupWorkers(wr.items || [])
      const counts = {}
      for (const item of r.items || []) {
        counts[item.id] = item.match_count || 0
      }
      setGroupMatchCounts(counts)
    } catch (e) {
      setGroupsErr(formatError(e))
      setGroups([])
      setGroupMatchCounts({})
      setGroupWorkerId(null)
      setGroupWorkers([])
    } finally {
      setGroupsLoading(false)
    }
  }

  async function reloadGroupMatches() {
    if (!matchesGroup?.id) return
    setMatchesErr('')
    setMatchesLoading(true)
    try {
      const r = await mainGet(`/groups/${matchesGroup.id}/matches`)
      setMatches(r.items || [])
    } catch (e) {
      setMatchesErr(formatError(e))
      setMatches([])
    } finally {
      setMatchesLoading(false)
    }
  }

  // Note: Home matches are auto-hidden on settings save (keywords change).

  async function loadGroupMatchCount(chatId) {
    try {
      const r = await mainGet(`/groups/${chatId}/matches/count`)
      setGroupMatchCounts(prev => ({ ...prev, [chatId]: r.count || 0 }))
    } catch (e) {
      setGroupMatchCounts(prev => ({ ...prev, [chatId]: 0 }))
    }
  }

  async function openMatchesModal(group) {
    if (!group) return
    setMatchesErr('')
    setMatchesLoading(true)
    setShowMatchesModal(true)
    setMatchesGroup(group)
    try {
      const r = await mainGet(`/groups/${group.id}/matches`)
      setMatches(r.items || [])
    } catch (e) {
      setMatchesErr(formatError(e))
      setMatches([])
    } finally {
      setMatchesLoading(false)
    }
  }

  async function setGroupListening(group, nextValue) {
    if (!group) return
    try {
      await mainPost(`/groups/${group.id}/listen`, {
        is_listening: nextValue,
        title: group.title || null,
      })
      setGroups(prev =>
        prev.map(item =>
          item.id === group.id ? { ...item, is_listening: nextValue } : item
        )
      )
      if (nextValue) {
        await loadGroupMatchCount(group.id)
      } else {
        setGroupMatchCounts(prev => ({ ...prev, [group.id]: 0 }))
      }
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  async function loadActiveSession() {
    const r = await mainGet('/sessions/active')
    const first = (r.items || [])[0]
    const nextId = first ? first.account_id : null
    setActiveAccountId(prev => (prev === nextId ? prev : nextId))
  }

  async function handleTelegramSessionExpired() {
    setTgSessionExpiredText('Сессия Telegram истекла или была отозвана. Пожалуйста, авторизуйтесь заново.')
    resetQrState()
    setTgSessionExpiredOpen(true)
    setAuthModalOpen(false)
    setAccounts([])
    setSessions([])
    setJobs([])
    setStats(null)
    setGroups([])
    setGroupMatchCounts({})
    setGroupWorkers([])
    setGroupWorkerId(null)
    setSelectedGroupId(null)
    setSelectedId(null)
    setActiveAccountId(null)
    await Promise.allSettled([
      loadAccounts(),
      loadActiveSession(),
      loadStats(),
      loadSessions(null),
    ])
  }

  function handleTelegramReauthClick() {
    setTgSessionExpiredOpen(false)
    setAuthModalOpen(true)
  }

  const parseUsernames = value =>
    (value || '')
      .split(/\r?\n/)
      .map(item => item.trim())
      .filter(Boolean)
      .map(item => item.replace(/^@+/, '').toLowerCase())
      .filter(Boolean)

  async function loadAutoChatUsernames() {
    setAutoChatErr('')
    setAutoChatLoading(true)
    try {
      const r = await mainGet('/local/auto_chat/usernames')
      const items = r.items || []
      setAutoChatUsernames(items)
      setAutoChatSelected([])
    } catch (e) {
      setAutoChatErr(formatError(e))
      setAutoChatUsernames([])
      setAutoChatSelected([])
    } finally {
      setAutoChatLoading(false)
    }
  }

  async function loadHomeAutoChatUsernames() {
    setHomeAutoChatErr('')
    setHomeAutoChatLoading(true)
    try {
      const r = await mainGet('/local/auto_chat/usernames')
      const items = (r.items || []).filter(item => item.status === 'OK')
      setHomeAutoChatUsernames(items)
    } catch (e) {
      setHomeAutoChatErr(formatError(e))
      setHomeAutoChatUsernames([])
    } finally {
      setHomeAutoChatLoading(false)
    }
  }

  async function loadHomeAutoChatDialogs() {
    setHomeAutoChatDialogsErr('')
    setHomeAutoChatDialogsLoading(true)
    try {
      const r = await mainGet('/auto_chat/dialogs')
      setHomeAutoChatDialogs(r.items || [])
      setHomeAutoChatDialogsMeta({
        account_id: r.account_id ?? null,
        limit: r.limit ?? 10,
        active_count: r.active_count ?? 0,
      })
    } catch (e) {
      setHomeAutoChatDialogsErr(formatError(e))
      setHomeAutoChatDialogs([])
      setHomeAutoChatDialogsMeta({ account_id: null, limit: 10, active_count: 0 })
    } finally {
      setHomeAutoChatDialogsLoading(false)
    }
  }

  async function startHomeAutoChat(tgUserIds) {
    setHomeAutoChatDialogsErr('')
    try {
      const r = await mainPost('/auto_chat/dialogs/start', { tg_user_ids: tgUserIds })
      setHomeAutoChatSelected([])
      await loadHomeAutoChatDialogs()
      const started = r?.started != null ? Number(r.started) : null
      pushToast('success', 'Запущено', started != null ? `Диалогов: ${started}` : 'Диалоги запущены')
    } catch (e) {
      setHomeAutoChatDialogsErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function stopHomeAutoChat(dialogId) {
    setHomeAutoChatDialogsErr('')
    try {
      await mainPost('/auto_chat/dialogs/stop', { dialog_id: dialogId })
      await loadHomeAutoChatDialogs()
      setHomeAutoChatMessages([])
      setHomeAutoChatMessagesErr('')
      setHomeAutoChatMessagesLoading(false)
      if (homeAutoChatActive?.dialog_id === dialogId) {
        setHomeAutoChatActive(null)
      }
      pushToast('success', 'Остановлено', 'Диалог остановлен')
    } catch (e) {
      setHomeAutoChatDialogsErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function loadHomeAutoChatMessages(dialogId, opts = {}) {
    if (!dialogId) return
    setHomeAutoChatMessagesErr('')
    const incremental = opts.after_id != null
    if (!incremental) setHomeAutoChatMessagesLoading(true)
    try {
      const limit = opts.limit ?? 200
      const params = new URLSearchParams()
      params.set('limit', String(limit))
      if (opts.since) params.set('since', opts.since)
      if (opts.after_id != null) params.set('after_id', String(opts.after_id))
      const r = await mainGet(`/auto_chat/dialogs/${dialogId}/messages?${params.toString()}`)
      if (opts.after_id != null) {
        const incoming = r.items || []
        if (incoming.length) {
          setHomeAutoChatMessages(prev => {
            const seen = new Set((prev || []).map(x => x.id))
            const merged = [...(prev || [])]
            for (const m of incoming) {
              if (!seen.has(m.id)) merged.push(m)
            }
            homeAutoChatLastMessageIdRef.current = merged.length ? merged[merged.length - 1].id : null
            return merged
          })
        }
      } else {
        const items = r.items || []
        homeAutoChatLastMessageIdRef.current = items.length ? items[items.length - 1].id : null
        setHomeAutoChatMessages(items)
      }
    } catch (e) {
      setHomeAutoChatMessagesErr(formatError(e))
      if (!incremental) {
        homeAutoChatLastMessageIdRef.current = null
        setHomeAutoChatMessages([])
      }
    } finally {
      if (!incremental) setHomeAutoChatMessagesLoading(false)
    }
  }

  async function loadHomeAutoChatHistoryMessages(dialogId, limit = 2000) {
    if (!dialogId) return
    setHomeAutoChatHistoryMessagesErr('')
    setHomeAutoChatHistoryMessagesLoading(true)
    try {
      const r = await mainGet(`/auto_chat/dialogs/${dialogId}/messages?limit=${limit}`)
      const items = r.items || []
      homeAutoChatHistoryLastMessageIdRef.current = items.length ? items[items.length - 1].id : null
      setHomeAutoChatHistoryMessages(items)
    } catch (e) {
      setHomeAutoChatHistoryMessagesErr(formatError(e))
      homeAutoChatHistoryLastMessageIdRef.current = null
      setHomeAutoChatHistoryMessages([])
    } finally {
      setHomeAutoChatHistoryMessagesLoading(false)
    }
  }

  async function loadHomeRequisites() {
    setHomeRequisitesErr('')
    setHomeRequisitesLoading(true)
    try {
      const r = await mainGet('/requisites')
      setHomeRequisites(r.items || [])
    } catch (e) {
      setHomeRequisitesErr(formatError(e))
      setHomeRequisites([])
    } finally {
      setHomeRequisitesLoading(false)
    }
  }

  async function pollHomeAutoChatIncremental(dialog) {
    if (!dialog?.id) return
    const lastId = homeAutoChatLastMessageIdRef.current
    if (!lastId) return
    await loadHomeAutoChatMessages(dialog.id, {
      since: dialog.started_at || homeAutoChatActive?.started_at || null,
      after_id: lastId,
      limit: 200,
    })
  }

  async function pollHomeAutoChatHistoryIncremental(dialogId) {
    if (!dialogId) return
    const lastId = homeAutoChatHistoryLastMessageIdRef.current
    if (!lastId) return
    setHomeAutoChatHistoryMessagesErr('')
    try {
      const r = await mainGet(`/auto_chat/dialogs/${dialogId}/messages?after_id=${lastId}&limit=500`)
      const incoming = r.items || []
      if (incoming.length) {
        setHomeAutoChatHistoryMessages(prev => {
          const seen = new Set((prev || []).map(x => x.id))
          const merged = [...(prev || [])]
          for (const m of incoming) {
            if (!seen.has(m.id)) merged.push(m)
          }
          homeAutoChatHistoryLastMessageIdRef.current = merged.length ? merged[merged.length - 1].id : null
          return merged
        })
      }
    } catch (e) {
      setHomeAutoChatHistoryMessagesErr(formatError(e))
    }
  }

  async function pollAdminAutoChatHistoryIncremental(dialogId) {
    if (!dialogId) return
    const lastId = adminAutoChatHistoryLastMessageIdRef.current
    if (!lastId) return
    setAdminAutoChatHistoryMessagesErr('')
    try {
      const r = await mainGet(`/admin/auto_chat/dialogs/${dialogId}/messages?after_id=${lastId}&limit=500`)
      const incoming = r.items || []
      if (incoming.length) {
        setAdminAutoChatHistoryMessages(prev => {
          const seen = new Set((prev || []).map(x => x.id))
          const merged = [...(prev || [])]
          for (const m of incoming) {
            if (!seen.has(m.id)) merged.push(m)
          }
          adminAutoChatHistoryLastMessageIdRef.current = merged.length ? merged[merged.length - 1].id : null
          return merged
        })
      }
    } catch (e) {
      setAdminAutoChatHistoryMessagesErr(formatError(e))
    }
  }

  async function saveAutoChatUsernames() {
    setAutoChatErr('')
    const list = parseUsernames(autoChatInput)
    if (!list.length) {
      setAutoChatErr('Введите хотя бы один юзернейм.')
      return
    }
    try {
      await mainPost('/local/auto_chat/usernames', { usernames: list })
      setAutoChatInput('')
      await loadAutoChatUsernames()
      pushToast('success', 'Сохранено', `Добавлено: ${list.length}`)
    } catch (e) {
      setAutoChatErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function loadAutoChatSettings() {
    setAutoChatSettingsErr('')
    setAutoChatSettingsLoading(true)
    try {
      const r = await mainGet('/local/auto_chat/settings')
      setAutoChatAiInstruction(r.ai_instruction || '')
      setAutoChatGreetingExamples(r.greeting_examples || '')
      setAutoChatDelayEnabled(Boolean(r.delay_enabled))
      setAutoChatDelayMinSec(String(((r.delay_min_ms || 0) / 1000)).replace(/\.0+$/, ''))
      setAutoChatDelayMaxSec(String(((r.delay_max_ms || 0) / 1000)).replace(/\.0+$/, ''))
      setAutoChatTypingEnabled(Boolean(r.typing_enabled))
      setAutoChatReadEnabled(Boolean(r.read_enabled))
    } catch (e) {
      setAutoChatSettingsErr(formatError(e))
      setAutoChatAiInstruction('')
      setAutoChatGreetingExamples('')
      setAutoChatDelayEnabled(false)
      setAutoChatDelayMinSec('0')
      setAutoChatDelayMaxSec('0')
      setAutoChatTypingEnabled(false)
      setAutoChatReadEnabled(false)
    } finally {
      setAutoChatSettingsLoading(false)
    }
  }

  async function saveAutoChatSettings() {
    setAutoChatSettingsErr('')
    try {
      const minMs = Math.max(0, Math.round(parseFloat(autoChatDelayMinSec || '0') * 1000))
      const maxMs = Math.max(0, Math.round(parseFloat(autoChatDelayMaxSec || '0') * 1000))
      await mainPatch('/local/auto_chat/settings', {
        ai_instruction: autoChatAiInstruction,
        greeting_examples: autoChatGreetingExamples,
        delay_enabled: autoChatDelayEnabled,
        delay_min_ms: minMs,
        delay_max_ms: maxMs,
        typing_enabled: autoChatTypingEnabled,
        read_enabled: autoChatReadEnabled,
      })
      pushToast('success', 'Сохранено', 'Настройки авто-общения обновлены')
    } catch (e) {
      setAutoChatSettingsErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function deleteAutoChatSelected() {
    setAutoChatErr('')
    if (!autoChatSelected.length) return
    try {
      await mainPost('/local/auto_chat/usernames/delete', { usernames: autoChatSelected })
      await loadAutoChatUsernames()
      pushToast('success', 'Удалено', `Юзернеймов: ${autoChatSelected.length}`)
    } catch (e) {
      setAutoChatErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function deleteAutoChatAll() {
    setAutoChatErr('')
    try {
      await mainPost('/local/auto_chat/usernames/clear', {})
      setAutoChatUsernames([])
      setAutoChatSelected([])
      pushToast('success', 'Удалено', 'Все юзернеймы удалены')
    } catch (e) {
      setAutoChatErr(formatError(e))
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  async function switchToSelectedAccount() {
    if (!selectedId) return
    if (activeAccountId === selectedId) return
    try {
      let sessionList = sessions
      if (!sessionList.length) {
        const r = await mainGet(`/accounts/${selectedId}/sessions`)
        sessionList = r.items || []
        setSessions(sessionList)
      }
      const active = sessionList.find(s => !s.revoked_at)
      const target = active || sessionList[0]
      if (!target) {
        setUiErr('Нет доступных сессий для этого аккаунта')
        return
      }
      await mainPost(`/accounts/${selectedId}/sessions/switch`, { session_id: target.id })
      await loadActiveSession()
      await loadAccounts()
      pushToast('success', 'Готово', 'Сессия переключена')
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  async function deleteAccount() {
    if (!selectedId) return
    const ok = confirm('Удалить аккаунт? Это удалит сессии, логи и задания.')
    if (!ok) return
    try {
      await mainDelete(`/accounts/${selectedId}?confirm=true`)
      if (selectedId === activeAccountId) {
        setActiveAccountId(null)
      }
      setSelectedId(null)
      await loadAccounts()
      await loadSessions(null)
      pushToast('success', 'Удалено', 'Аккаунт удален')
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  async function deleteAllAccounts() {
    if (!accounts.length) return
    const ok = confirm('Удалить все аккаунты? Это удалит сессии, логи и задания.')
    if (!ok) return
    try {
      for (const acc of accounts) {
        await mainDelete(`/accounts/${acc.id}?confirm=true`)
      }
      setSelectedId(null)
      setActiveAccountId(null)
      await loadAccounts()
      await loadSessions(null)
      pushToast('success', 'Удалено', 'Все аккаунты удалены')
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  // session-level controls removed from UI; switch is handled by account action

  async function cancelJob(jobId) {
    try {
      await mainPost(`/jobs/${jobId}/cancel`, {})
      await loadJobs(selectedId)
      pushToast('success', 'Отменено', 'Задача отменена')
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  useEffect(() => {
    if (!loggedIn) return
    ;(async () => {
      const me = await loadMe().catch(() => null)
      const svc = me?.service_enabled === true || me?.service_enabled === 1 || me?.service_enabled === '1'
      if (svc === false) return
      const canListening =
        me?.feature_group_reading_enabled === true ||
        me?.feature_group_reading_enabled === 1 ||
        me?.feature_group_reading_enabled === '1'
      loadAccounts().catch(e => setUiErr(formatError(e)))
      loadStats().catch(() => {})
      loadAiStatus().catch(() => {})
      loadSupportNotice().catch(() => {})
      loadActiveSession().catch(() => {})
      if (canListening) {
        loadSettings().catch(() => {})
      }
    })()
  }, [])

  useEffect(() => {
    if (!uiErr) return
    pushToast('error', 'Ошибка', uiErr, 6000)
    setUiErr('')
  }, [uiErr])

  useEffect(() => {
    if (!isSuperAdmin && adminIsAdmin) {
      setAdminIsAdmin(false)
    }
  }, [isSuperAdmin, adminIsAdmin])

  useEffect(() => {
    if (!selectedAccount) {
      return
    }
    loadSessions(selectedAccount.id).catch(() => {})
    loadJobs(selectedAccount.id).catch(() => {})
  }, [selectedAccount])

  const qrStopped = ['READY', 'ERROR', 'CANCELLED', 'EXPIRED'].includes(qrStatus)
  const [lastAuthRefreshAt, setLastAuthRefreshAt] = useState(0)
  const needsGroups =
    (activeTopTab === 'home' && homeSideTab === 'listening')
  const monitoringAdminView =
    isAdmin &&
    activeTopTab === 'monitoring' &&
    ['admin-accounts', 'admin-workers', 'admin-errors'].includes(monitorSideTab)

  useEffect(() => {
    if (!loggedIn) return
    if (!serviceEnabledChecked) return
    const canListening = Boolean(featureGroupReadingEnabled)
    const canAuto = Boolean(featureAutoDialogsEnabled)

    // Home
    if (homeSideTab === 'listening' && !canListening) {
      if (canAuto) setHomeSideTab('auto')
    }
    if (homeSideTab === 'auto' && !canAuto) {
      if (canListening) setHomeSideTab('listening')
    }

    // Monitoring
    if (monitorSideTab === 'listening_history' && !canListening) {
      if (canAuto) setMonitorSideTab('auto_history')
      else setMonitorSideTab('requisites_history')
    }
    if (monitorSideTab === 'auto_history' && !canAuto) {
      if (canListening) setMonitorSideTab('listening_history')
      else setMonitorSideTab('requisites_history')
    }

    // Settings
    if (settingsSideTab === 'listening' && !canListening) setSettingsSideTab('main')
    if (settingsSideTab === 'auto' && !canAuto) setSettingsSideTab('main')
    if (settingsSideTab === 'service-control' && !isAdmin) setSettingsSideTab('main')
  }, [
    loggedIn,
    serviceEnabledChecked,
    featureGroupReadingEnabled,
    featureAutoDialogsEnabled,
    isAdmin,
    homeSideTab,
    monitorSideTab,
    settingsSideTab,
  ])

  const [monitoringHistoryScope, setMonitoringHistoryScope] = useState(() => {
    try {
      const saved = localStorage.getItem('monitoringHistoryScope')
      return saved === 'common' ? 'common' : 'personal'
    } catch {
      return 'personal'
    }
  })

  const resetAutoChatHistorySelection = () => {
    setHomeAutoChatHistoryActive(null)
    setHomeAutoChatHistoryMessages([])
    setHomeAutoChatHistoryMessagesErr('')
    setHomeAutoChatHistoryMessagesLoading(false)
    homeAutoChatHistoryLastMessageIdRef.current = null

    setAdminAutoChatHistoryActive(null)
    setAdminAutoChatHistoryMessages([])
    setAdminAutoChatHistoryMessagesErr('')
    setAdminAutoChatHistoryMessagesLoading(false)
    adminAutoChatHistoryLastMessageIdRef.current = null
  }

  const resetMonitoringHistoryPaging = () => {
    setMonitoringListeningMatchesOffset(0)
    setAdminMatchesOffset(0)
  }

  const setMonitoringHistoryScopeSafe = next => {
    const v = next === 'common' ? 'common' : 'personal'
    setMonitoringHistoryScope(v)
    // Reset state to avoid mixing pages/dialogs between scopes.
    if (monitorSideTab === 'listening_history') {
      resetMonitoringHistoryPaging()
    } else if (monitorSideTab === 'auto_history') {
      resetAutoChatHistorySelection()
    } else if (monitorSideTab === 'requisites_history') {
      setHomeRequisitesErr('')
      setHomeRequisites([])
      setAdminRequisitesErr('')
      setAdminRequisites([])
    }
  }

  useEffect(() => {
    document.body.classList.toggle('theme-dark', isDarkTheme)
    try {
      localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light')
    } catch {
    }
  }, [isDarkTheme])

  useEffect(() => {
    const hasModal = authModalOpen || showMatchesModal || systemBlockOpen || tgSessionExpiredOpen || supportNoticeOpen
    document.body.classList.toggle('modal-open', hasModal)
  }, [authModalOpen, showMatchesModal, systemBlockOpen, tgSessionExpiredOpen, supportNoticeOpen])

  useEffect(() => {
    if (!systemBlockOpen) return
    const onKeyDownCapture = e => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
      }
    }
    try {
      window.addEventListener('keydown', onKeyDownCapture, true)
    } catch {
      // ignore
    }
    return () => {
      try {
        window.removeEventListener('keydown', onKeyDownCapture, true)
      } catch {
        // ignore
      }
    }
  }, [systemBlockOpen])

  const qrPollingRef = useRef({ inFlight: false, t: null })
  useEffect(() => {
    // Auto-check QR auth status only while the auth modal is open and QR flow is active.
    if (!authModalOpen) return
    if (!qrAuthId) return
    if (qrStopped) return
    if (qrStatus === 'WAIT_PASSWORD') return

    const tick = async () => {
      if (qrPollingRef.current.inFlight) return
      qrPollingRef.current.inFlight = true
      try {
        await continueQr()
      } catch {
        // continueQr already sets qrErr
      } finally {
        qrPollingRef.current.inFlight = false
      }
    }

    // Kick once quickly, then poll.
    tick()
    const t = setInterval(tick, 1500)
    qrPollingRef.current.t = t
    return () => {
      try {
        clearInterval(t)
      } catch {
      }
      qrPollingRef.current.t = null
      qrPollingRef.current.inFlight = false
    }
  }, [authModalOpen, qrAuthId, qrStopped, qrStatus])

  useEffect(() => {
    if (!isAdminChecked) return
    if (isAdmin) return
    if (!['admin-accounts', 'admin-workers', 'admin-errors'].includes(monitorSideTab)) return
    setMonitorSideTab('listening_history')
  }, [isAdminChecked, isAdmin, monitorSideTab])

  useEffect(() => {
    if (!isAdminChecked) return
    if (isSuperAdmin) return
    if (monitorSideTab !== 'admin-errors') return
    setMonitorSideTab('listening_history')
  }, [isAdminChecked, isSuperAdmin, monitorSideTab])

  useEffect(() => {
    if (!isAdminChecked) return
    if (isAdmin) return
    if (monitoringHistoryScope === 'personal') return
    setMonitoringHistoryScopeSafe('personal')
  }, [isAdminChecked, isAdmin, monitoringHistoryScope])

  useEffect(() => {
    try {
      localStorage.setItem('monitoringHistoryScope', monitoringHistoryScope)
    } catch {
    }
  }, [monitoringHistoryScope])

  useEffect(() => {
    const allowedHome = new Set(['listening', 'auto'])
    if (!allowedHome.has(homeSideTab)) {
      setHomeSideTab('listening')
    }
  }, [homeSideTab])

  useEffect(() => {
    const allowed = new Set(['listening_history', 'auto_history', 'requisites_history', 'admin-accounts', 'admin-workers', 'admin-errors'])
    if (!allowed.has(monitorSideTab)) {
      setMonitorSideTab('listening_history')
    }
  }, [monitorSideTab])

  useEffect(() => {
    // Reset offsets/selection when switching tabs, to keep UX predictable.
    if (monitorSideTab === 'listening_history') {
      resetMonitoringHistoryPaging()
    } else if (monitorSideTab === 'auto_history') {
      resetAutoChatHistorySelection()
    } else if (monitorSideTab === 'admin-errors') {
      setAdminErrorsOffset(0)
    }
  }, [monitorSideTab])

  useEffect(() => {
    if (!loggedIn) return
    const ready = qrStatus === 'READY'
    if (!ready) return
    const now = Date.now()
    if (now - lastAuthRefreshAt < 2000) return
    setLastAuthRefreshAt(now)
    loadAccounts().catch(() => {})
    loadActiveSession().catch(() => {})
    loadStats().catch(() => {})
    if (needsGroups) {
      loadGroups().catch(() => {})
    }
  }, [qrStatus, loggedIn, needsGroups, lastAuthRefreshAt])

  useEffect(() => {
    if (!loggedIn) return
    if (!needsGroups) return
    loadGroups().catch(() => {})
  }, [loggedIn, activeAccountId, needsGroups])

  useEffect(() => {
    if (!loggedIn || !monitoringAdminView) return
    loadAdminUsers().catch(() => {})
    loadAdminAccounts().catch(() => {})
    loadAdminWorkers().catch(() => {})
  }, [loggedIn, monitoringAdminView])

  useEffect(() => {
    if (!loggedIn) return
    if (!activeAccountId) return
    if (!needsGroups) return
    loadGroups().catch(() => {})
  }, [activeAccountId, loggedIn, needsGroups])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'settings') return
    if (settingsSideTab !== 'auto') return
    loadAutoChatUsernames().catch(() => {})
    loadAutoChatSettings().catch(() => {})
  }, [loggedIn, activeTopTab, settingsSideTab])

  useEffect(() => {
    if (!loggedIn) return
    if (!isAdmin) return
    if (activeTopTab !== 'settings') return
    if (settingsSideTab !== 'service-control') return
    loadServiceRestarts().catch(() => {})
  }, [loggedIn, isAdmin, activeTopTab, settingsSideTab])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab === 'auto') {
      loadHomeAutoChatUsernames().catch(() => {})
      loadHomeAutoChatDialogs().catch(() => {})
    } else {
      setHomeAutoChatHistoryActive(null)
      setHomeAutoChatHistoryMessages([])
      setHomeAutoChatHistoryMessagesErr('')
      setHomeAutoChatHistoryMessagesLoading(false)
    }
  }, [
    loggedIn,
    activeTopTab,
    homeSideTab,
    activeAccountId,
  ])

  // Auto refresh only for "Авто. диалоги": keep the dialogs list up-to-date.
  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab !== 'auto') return
    const id = setInterval(() => {
      loadHomeAutoChatDialogs().catch(() => {})
    }, 4000)
    return () => clearInterval(id)
  }, [loggedIn, activeTopTab, homeSideTab, activeAccountId])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'monitoring') return

    const scope = isAdmin ? monitoringHistoryScope : 'personal'

    if (monitorSideTab === 'listening_history') {
      if (scope === 'common') {
        loadAdminMatches(adminMatchesOffset, adminMatchesLimit).catch(() => {})
      } else {
        loadMonitoringListeningMatches(monitoringListeningMatchesOffset, monitoringListeningMatchesLimit).catch(() => {})
      }
      return
    }

    if (monitorSideTab === 'auto_history') {
      if (scope === 'common') {
        loadAdminAutoChatDialogs().catch(() => {})
      } else {
        loadHomeAutoChatUsernames().catch(() => {})
        loadHomeAutoChatDialogs().catch(() => {})
      }
      return
    }

    if (monitorSideTab === 'requisites_history') {
      if (scope === 'common') {
        loadAdminRequisites().catch(() => {})
      } else {
        loadHomeRequisites().catch(() => {})
      }
      return
    }

    if (monitorSideTab === 'admin-errors') {
      if (!isSuperAdmin) return
      loadAdminErrors(adminErrorsOffset, adminErrorsLimit).catch(() => {})
    }
  }, [
    loggedIn,
    activeTopTab,
    monitorSideTab,
    isAdmin,
    monitoringHistoryScope,
    activeAccountId,
    monitoringListeningMatchesOffset,
    monitoringListeningMatchesLimit,
    adminMatchesOffset,
    adminMatchesLimit,
    adminErrorsOffset,
    adminErrorsLimit,
    isSuperAdmin,
  ])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab !== 'auto') return
    if (!homeAutoChatActive?.tg_user_id && !homeAutoChatActive?.dialog_id) return

    const dialog =
      (homeAutoChatActive?.dialog_id
        ? (homeAutoChatDialogs || []).find(d => d.id === homeAutoChatActive.dialog_id)
        : null) ||
      (homeAutoChatActive?.tg_user_id
        ? (homeAutoChatDialogs || []).find(d => d.peer_tg_user_id === homeAutoChatActive.tg_user_id)
        : null)

    if (!dialog?.id) return
    if (dialog.status === 'STOPPED') return

    loadHomeAutoChatMessages(dialog.id, {
      since: dialog.started_at || homeAutoChatActive?.started_at || null,
      limit: 200,
    }).catch(() => {})
  }, [
    loggedIn,
    activeTopTab,
    homeSideTab,
    homeAutoChatActive?.dialog_id,
    homeAutoChatActive?.tg_user_id,
    homeAutoChatActive?.started_at,
    homeAutoChatDialogs,
  ])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab !== 'auto') return

    const dialog =
      (homeAutoChatActive?.dialog_id
        ? (homeAutoChatDialogs || []).find(d => d.id === homeAutoChatActive.dialog_id)
        : null) ||
      (homeAutoChatActive?.tg_user_id
        ? (homeAutoChatDialogs || []).find(d => d.peer_tg_user_id === homeAutoChatActive.tg_user_id)
        : null)

    if (!dialog?.id) return
    if (dialog.status === 'STOPPED') return

    const id = setInterval(() => {
      pollHomeAutoChatIncremental(dialog).catch(() => {})
    }, 1500)
    return () => clearInterval(id)
  }, [
    loggedIn,
    activeTopTab,
    homeSideTab,
    homeAutoChatActive?.dialog_id,
    homeAutoChatActive?.tg_user_id,
    homeAutoChatDialogs,
  ])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'monitoring') return
    if (monitorSideTab !== 'auto_history') return
    const scope = isAdmin ? monitoringHistoryScope : 'personal'

    if (scope === 'common') {
      if (!adminAutoChatHistoryActive?.dialog_id) return
      loadAdminAutoChatHistoryMessages(adminAutoChatHistoryActive.dialog_id, 2000).catch(() => {})
      return
    }

    if (!homeAutoChatHistoryActive?.dialog_id) return
    loadHomeAutoChatHistoryMessages(homeAutoChatHistoryActive.dialog_id, 2000).catch(() => {})
  }, [
    loggedIn,
    activeTopTab,
    monitorSideTab,
    isAdmin,
    monitoringHistoryScope,
    homeAutoChatHistoryActive?.dialog_id,
    adminAutoChatHistoryActive?.dialog_id,
  ])

  // No periodic refresh for matches modal; use manual refresh button.

  useEffect(() => {
    const handler = () => resetAuthState()
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  useEffect(() => {
    const handler = () => {
      handleTelegramSessionExpired().catch(() => {})
    }
    window.addEventListener('tg:session-expired', handler)
    return () => window.removeEventListener('tg:session-expired', handler)
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('activeTopTab', activeTopTab)
    } catch {
    }
  }, [activeTopTab])

  useEffect(() => {
    try {
      localStorage.setItem('homeSideTab', homeSideTab)
    } catch {
    }
  }, [homeSideTab])

  useEffect(() => {
    try {
      localStorage.setItem('monitorSideTab', monitorSideTab)
    } catch {
    }
  }, [monitorSideTab])

  useEffect(() => {
    try {
      localStorage.setItem('settingsSideTab', settingsSideTab)
    } catch {
    }
  }, [settingsSideTab])

  async function handleLogin() {
    setLoginErr('')
    try {
      const r = await mainPost('/local/login', { login, password: loginPassword }, false)
      setAuthToken(r.token)
      setLoggedIn(true)
      setIsAdmin(r.is_admin === true)
      const me = await loadMe()
      const svc = me?.service_enabled === true || me?.service_enabled === 1 || me?.service_enabled === '1'
      const canListening =
        me?.feature_group_reading_enabled === true ||
        me?.feature_group_reading_enabled === 1 ||
        me?.feature_group_reading_enabled === '1'
      // If user is fully disabled, show the disabled screen only (no extra API calls).
      if (svc === false) return
      await loadAccounts()
      await loadActiveSession()
      await loadStats()
      if (canListening) {
        await loadSettings()
      }
      await loadSupportNotice()
    } catch (e) {
      setLoginErr(formatError(e))
    }
  }

  const handleHomeSideTabChange = next => {
    setHomeSideTab(next)
    if (next !== 'listening') {
      setSelectedGroupId(null)
    } else {
      loadGroups().catch(() => {})
    }
    if (next !== 'auto') {
      setHomeAutoChatActive(null)
      setHomeAutoChatSelected([])
      setHomeAutoChatMessages([])
      setHomeAutoChatMessagesErr('')
      homeAutoChatLastMessageIdRef.current = null
    }
  }

  const handleMonitorSideTabChange = next => {
    setMonitorSideTab(next)
  }

  const handleSettingsSideTabChange = next => {
    setSettingsSideTab(next)
  }

  function resetAuthState() {
    setAuthToken('')
    setLoggedIn(false)
    setIsAdmin(false)
    setIsSuperAdmin(false)
    setMeLogin('')
    setMeRole('user')
    setServiceEnabledChecked(false)
    setServiceEnabled(true)
    setFeatureGroupReadingEnabled(true)
    setFeatureAutoDialogsEnabled(true)
    setDisabledComment('')
    setAccounts([])
    setSessions([])
    setJobs([])
    setStats(null)
    setSelectedId(null)
    setActiveAccountId(null)
    setKeywords('')
    setSettingsActive(true)
    setSettingsErr('')
    setActiveTopTab('home')
    setHomeSideTab('listening')
    setMonitorSideTab('listening_history')
    setSettingsSideTab('main')
    resetQrState()
    setAuthModalOpen(false)
    setTgSessionExpiredOpen(false)
    setTgSessionExpiredText('')
    setAutoChatInput('')
    setAutoChatUsernames([])
    setAutoChatSelected([])
    setAutoChatErr('')
    setAutoChatLoading(false)
    setAutoChatAiInstruction('')
    setAutoChatGreetingExamples('')
    setAutoChatSettingsErr('')
    setAutoChatSettingsLoading(false)
    setHomeAutoChatUsernames([])
    setHomeAutoChatErr('')
    setHomeAutoChatLoading(false)
    setHomeAutoChatActive(null)
    setHomeAutoChatDialogs([])
    setHomeAutoChatDialogsMeta({ account_id: null, limit: 10, active_count: 0 })
    setHomeAutoChatDialogsErr('')
    setHomeAutoChatDialogsLoading(false)
    setHomeAutoChatSelected([])
    setHomeAutoChatMessages([])
    setHomeAutoChatMessagesErr('')
    setHomeAutoChatMessagesLoading(false)
    setSupportNoticeOpen(false)
    setSupportNoticeText('')
    setSystemRestartActive(false)
    setSystemRestartReason('')
    setSystemRestartUntil('')
    setServiceRestartItems([])
    setServiceRestartErr('')
    setServiceRestartLoading(false)
    setServiceRestartReloading(false)
    setRestartingServiceKey('')
  }

  async function handleLogout() {
    try {
      await mainPost('/local/logout', {}, true)
    } catch {
    } finally {
      resetAuthState()
    }
  }

  const homeListeningProps = {
    activeAccountId,
    groupsLoading,
    groupsErr,
    sortedGroups,
    selectedGroupId,
    setSelectedGroupId,
    groupMatchCounts,
    setGroupListening,
    openMatchesModal,
    reloadGroups: () => loadGroups().catch(() => {}),
  }

  const effectiveMonitoringScope = isAdmin ? monitoringHistoryScope : 'personal'
  const showMonitoringScopeToggle = Boolean(isAdmin)

  const monitoringListeningHistoryProps = {
    showScopeToggle: showMonitoringScopeToggle,
    scope: effectiveMonitoringScope,
    setScope: setMonitoringHistoryScopeSafe,
    keywords,
    matches: effectiveMonitoringScope === 'common' ? adminMatches : monitoringListeningMatches,
    offset: effectiveMonitoringScope === 'common' ? adminMatchesOffset : monitoringListeningMatchesOffset,
    limit: effectiveMonitoringScope === 'common' ? adminMatchesLimit : monitoringListeningMatchesLimit,
    setOffset: effectiveMonitoringScope === 'common' ? setAdminMatchesOffset : setMonitoringListeningMatchesOffset,
    reload: () => {
      if (effectiveMonitoringScope === 'common') {
        return loadAdminMatches(adminMatchesOffset, adminMatchesLimit).catch(() => {})
      }
      return loadMonitoringListeningMatches(monitoringListeningMatchesOffset, monitoringListeningMatchesLimit).catch(() => {})
    },
    isSuperAdmin,
    deleteMonitoringGroupMatch,
  }

  const adminAccountsProps = {
    isSuperAdmin,
    adminLogin,
    setAdminLogin,
    adminPassword,
    setAdminPassword,
    adminIsAdmin,
    setAdminIsAdmin,
    adminIsActive,
    setAdminIsActive,
    adminAccessMode,
    setAdminAccessMode,
    createAdminUser,
    updateAdminUser,
    adminErr,
    adminUsers,
    deleteAdminUser,
    adminAccounts,
    deleteAdminAccount,
    loadAdminUserLoginHistory,
  }

  const adminWorkersProps = {
    adminWorkers,
    jobStatusMeta,
  }

  const adminErrorsProps = {
    adminErrors,
    adminErrorsOffset,
    adminErrorsLimit,
    adminErrorsTotal,
    adminErrorsLoading,
    adminErrorsErr,
    setAdminErrorsOffset,
    reloadAdminErrors: () => loadAdminErrors(adminErrorsOffset, adminErrorsLimit).catch(() => {}),
    resolveAdminIncident,
    resolveAllAdminIncidents,
    resolvingIncidentKey,
    resolvingAllIncidents,
  }

  const settingsAccountsProps = {
    accounts,
    selectedId,
    setSelectedId,
    activeAccountId,
    switchToSelectedAccount,
    deleteAccount,
    deleteAllAccounts,
    openAuthModal: () => setAuthModalOpen(true),
  }

  const settingsListeningProps = {
    keywords,
    settingsActive,
    handleKeywordsChange,
    handleActiveToggle,
    saveListeningSettings,
    settingsErr,
  }

  const homeAutoChatProps = {
    homeAutoChatUsernames,
    homeAutoChatErr,
    homeAutoChatLoading,
    homeAutoChatActive,
    setHomeAutoChatActive,
    homeAutoChatDialogs,
    homeAutoChatDialogsMeta,
    homeAutoChatDialogsErr,
    homeAutoChatDialogsLoading,
    homeAutoChatSelected,
    setHomeAutoChatSelected,
    homeAutoChatMessages,
    homeAutoChatMessagesErr,
    homeAutoChatMessagesLoading,
    reload: async () => {
      await loadHomeAutoChatUsernames()
      await loadHomeAutoChatDialogs()
    },
    startHomeAutoChat,
    stopHomeAutoChat,
    loadHomeAutoChatMessages,
  }

  const monitoringAutoChatHistoryProps = {
    showScopeToggle: showMonitoringScopeToggle,
    scope: effectiveMonitoringScope,
    setScope: setMonitoringHistoryScopeSafe,
    homeAutoChatDialogs: effectiveMonitoringScope === 'common' ? adminAutoChatDialogs : homeAutoChatDialogs,
    homeAutoChatDialogsMeta: effectiveMonitoringScope === 'common' ? adminAutoChatDialogsMeta : homeAutoChatDialogsMeta,
    homeAutoChatDialogsErr: effectiveMonitoringScope === 'common' ? adminAutoChatDialogsErr : homeAutoChatDialogsErr,
    homeAutoChatDialogsLoading: effectiveMonitoringScope === 'common' ? adminAutoChatDialogsLoading : homeAutoChatDialogsLoading,
    homeAutoChatHistoryActive: effectiveMonitoringScope === 'common' ? adminAutoChatHistoryActive : homeAutoChatHistoryActive,
    setHomeAutoChatHistoryActive: effectiveMonitoringScope === 'common' ? setAdminAutoChatHistoryActive : setHomeAutoChatHistoryActive,
    homeAutoChatHistoryMessages: effectiveMonitoringScope === 'common' ? adminAutoChatHistoryMessages : homeAutoChatHistoryMessages,
    homeAutoChatHistoryMessagesErr: effectiveMonitoringScope === 'common' ? adminAutoChatHistoryMessagesErr : homeAutoChatHistoryMessagesErr,
    homeAutoChatHistoryMessagesLoading: effectiveMonitoringScope === 'common' ? adminAutoChatHistoryMessagesLoading : homeAutoChatHistoryMessagesLoading,
    loadHomeAutoChatHistoryMessages: effectiveMonitoringScope === 'common' ? loadAdminAutoChatHistoryMessages : loadHomeAutoChatHistoryMessages,
    reload: async () => {
      if (effectiveMonitoringScope === 'common') {
        await loadAdminAutoChatDialogs()
      } else {
        await loadHomeAutoChatDialogs()
      }
    },
    isSuperAdmin,
    deleteMonitoringAutoDialog,
  }

  const monitoringRequisitesHistoryProps = {
    showScopeToggle: showMonitoringScopeToggle,
    scope: effectiveMonitoringScope,
    setScope: setMonitoringHistoryScopeSafe,
    homeRequisites: effectiveMonitoringScope === 'common' ? adminRequisites : homeRequisites,
    homeRequisitesErr: effectiveMonitoringScope === 'common' ? adminRequisitesErr : homeRequisitesErr,
    homeRequisitesLoading: effectiveMonitoringScope === 'common' ? adminRequisitesLoading : homeRequisitesLoading,
    reload: async () => {
      if (effectiveMonitoringScope === 'common') {
        await loadAdminRequisites()
      } else {
        await loadHomeRequisites()
      }
    },
    isSuperAdmin,
    deleteMonitoringRequisite,
  }

  const settingsAutoChatProps = {
    autoChatInput,
    setAutoChatInput,
    autoChatUsernames,
    autoChatSelected,
    setAutoChatSelected,
    autoChatErr,
    autoChatLoading,
    saveAutoChatUsernames,
    deleteAutoChatSelected,
    deleteAutoChatAll,
    autoChatAiInstruction,
    setAutoChatAiInstruction,
    autoChatGreetingExamples,
    setAutoChatGreetingExamples,
    autoChatDelayEnabled,
    setAutoChatDelayEnabled,
    autoChatDelayMinSec,
    setAutoChatDelayMinSec,
    autoChatDelayMaxSec,
    setAutoChatDelayMaxSec,
    autoChatTypingEnabled,
    setAutoChatTypingEnabled,
    autoChatReadEnabled,
    setAutoChatReadEnabled,
    autoChatSettingsErr,
    autoChatSettingsLoading,
    saveAutoChatSettings,
  }

  const settingsServiceControlProps = {
    items: serviceRestartItems,
    loading: serviceRestartLoading,
    err: serviceRestartErr,
    reloading: serviceRestartReloading,
    restartingKey: restartingServiceKey,
    reload: () => loadServiceRestarts({ silent: true }).catch(() => {}),
    requestRestart: requestServiceRestart,
  }

  const themeProps = {
    isDarkTheme,
    onToggleTheme: setIsDarkTheme,
  }

  if (!loggedIn) {
    return (
      <div className="page login-page">
        <header className="hero">
          <div>
            <div className="eyebrow">TG Web Auth</div>
            <h1>{'Вход в систему'}</h1>
            <p>{'Доступ к функциям возможен только после авторизации.'}</p>
          </div>
          <div className="hero-card">
            <div className="stat">
              <span>{'Безопасность'}</span>
              <strong>{'Локально'}</strong>
            </div>
            <div className="stat">
              <span>{'Сессии'}</span>
              <strong>{'Защищены'}</strong>
            </div>
          </div>
        </header>

        <main className="grid auth-grid">
          <section className="panel auth auth-panel">
            <div className="panel-head">
              <h2>{'Локальный вход'}</h2>
            </div>
            <div className="field">
              <label>{'Логин'}</label>
              <input value={login} onChange={e => setLogin(e.target.value)} placeholder="admin1" />
            </div>
            <div className="field">
              <label>{'Пароль'}</label>
              <input type="password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} placeholder="??????" />
            </div>
            <div className="actions">
              <button className="primary" onClick={handleLogin}>{'Войти'}</button>
            </div>
            {loginErr && <div className="status error">{loginErr}</div>}
          </section>
          <section className="panel auth-hint">
            <h3>{'Что дальше'}</h3>
            <p className="muted">{'После входа вы сможете добавить Telegram-аккаунты и управлять мониторингом.'}</p>
            <div className="pill">{'Поддержка QR и 2FA'}</div>
          </section>
        </main>
      </div>
    )
  }

  const hasAnyFeature = Boolean(featureGroupReadingEnabled) || Boolean(featureAutoDialogsEnabled)
  if (serviceEnabledChecked && (!serviceEnabled || !hasAnyFeature)) {
    return (
      <div className="page">
        <header className="hero">
          <div>
            <div className="eyebrow">TG Web Auth</div>
            <h1>Панель управления</h1>
          </div>
          <div className="hero-card">
            <div className="me-card">
              <div className="me-name">{meLogin || '—'}</div>
            </div>
          </div>
        </header>
        <div className="tabs tabs-row">
          <div className="tabs-left" />
          <button className="tab active tab-logout" onClick={handleLogout}>Выйти</button>
        </div>
        <main style={{ padding: 16 }}>
          <section className="panel service-disabled">
            <div className="service-disabled-icon" aria-hidden="true">
              <ShieldX size={88} strokeWidth={1.8} />
            </div>
            <h2 className="service-disabled-title">Вам отключили возможности сервиса</h2>
            <p className="muted service-disabled-subtitle">
              Свяжитесь, пожалуйста, с администратором.
            </p>
            {(disabledComment || '').trim() ? (
              <div className="status warn service-disabled-reason">
                <strong>Причина:</strong> {disabledComment}
              </div>
            ) : null}
          </section>
        </main>
      </div>
    )
  }


  return (
    <div className="page">
      <header className="hero">
        <div>
          <div className="eyebrow">TG Web Auth</div>
          <h1>Панель управления</h1>
        </div>
        <div className="hero-card">
          <div className="me-card">
            <div className="me-name">{meLogin || '—'}</div>
          </div>
          <div className="stat">
            <span>Аккаунты</span>
            <strong>{stats ? stats.accounts_total : '—'}</strong>
          </div>
          <div className="stat">
            <span>Статус ИИ</span>
            <strong>{aiStatusText()}</strong>
          </div>
        </div>
      </header>

      <div className="tabs tabs-row">
        <div className="tabs-left tabs-left-desktop">
          <button
            className={`tab ${activeTopTab === 'home' ? 'active' : ''}`}
            onClick={() => setActiveTopTab('home')}
          >
            Главная
          </button>
          <button
            className={`tab ${activeTopTab === 'monitoring' ? 'active' : ''}`}
            onClick={() => setActiveTopTab('monitoring')}
          >
            Мониторинг
          </button>
          <button
            className={`tab ${activeTopTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTopTab('settings')}
          >
            Настройки
          </button>
        </div>
        <div className="tabs-mobile-select-wrap">
          <select
            className="tabs-mobile-select"
            value={activeTopTab}
            onChange={e => setActiveTopTab(e.target.value)}
          >
            <option value="home">Главная</option>
            <option value="monitoring">Мониторинг</option>
            <option value="settings">Настройки</option>
          </select>
        </div>
        <button className="tab active tab-logout" onClick={handleLogout}>Выйти</button>
      </div>

      {activeTopTab === 'home' && (
        <HomeTab
          activeSideTab={homeSideTab}
          setActiveSideTab={handleHomeSideTabChange}
          listeningProps={homeListeningProps}
          autoChatProps={homeAutoChatProps}
          canGroupReading={featureGroupReadingEnabled}
          canAutoDialogs={featureAutoDialogsEnabled}
        />
      )}

      {activeTopTab === 'monitoring' && (
        <MonitoringTab
          isAdmin={isAdmin}
          isSuperAdmin={isSuperAdmin}
          activeSideTab={monitorSideTab}
          setActiveSideTab={handleMonitorSideTabChange}
          listeningHistoryProps={monitoringListeningHistoryProps}
          autoChatHistoryProps={monitoringAutoChatHistoryProps}
          requisitesHistoryProps={monitoringRequisitesHistoryProps}
          adminAccountsProps={adminAccountsProps}
          adminWorkersProps={adminWorkersProps}
          adminErrorsProps={adminErrorsProps}
          canGroupReading={featureGroupReadingEnabled}
          canAutoDialogs={featureAutoDialogsEnabled}
        />
      )}

      {activeTopTab === 'settings' && (
        <SettingsTab
          activeSideTab={settingsSideTab}
          setActiveSideTab={handleSettingsSideTabChange}
          accountsProps={settingsAccountsProps}
          listeningProps={settingsListeningProps}
          autoChatProps={settingsAutoChatProps}
          serviceControlProps={settingsServiceControlProps}
          themeProps={themeProps}
          canGroupReading={featureGroupReadingEnabled}
          canAutoDialogs={featureAutoDialogsEnabled}
          canServiceControl={isAdmin}
        />
      )}

      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {(toasts || []).map(t => (
          <div key={t.id} className={`toast-item ${t.type || 'info'}`}>
            <div className="toast-title">
              {t.title || (t.type === 'error' ? 'Ошибка' : 'Готово')}
            </div>
            <button className="toast-close" onClick={() => removeToast(t.id)} aria-label="Закрыть">
              <span className="toast-close-icon">x</span>
            </button>
            {t.message ? <div className="toast-msg">{t.message}</div> : null}
          </div>
        ))}
      </div>

      {systemBlockOpen && (
        <div className="modal-backdrop sys-block-backdrop">
          <div className="modal sys-block-modal" onClick={e => e.stopPropagation()}>
            <div className={`sys-block-icon${systemRestarting ? ' spin' : ''}`} aria-hidden="true">
              {systemRestarting ? (
                <RefreshCw size={68} strokeWidth={1.8} />
              ) : (
                <ShieldX size={68} strokeWidth={1.8} />
              )}
            </div>
            <h2 className="sys-block-title">{systemBlockTitle}</h2>
            <p className="muted sys-block-text">{systemBlockDetail}</p>
            {systemRestarting && systemRestartUntil ? (
              <p className="muted sys-block-subtext">
                Повторная проверка до: {formatDateTime(systemRestartUntil)}
              </p>
            ) : null}
            {systemRestarting && systemRestartReason ? (
              <p className="muted sys-block-subtext">
                Причина: {systemRestartReason}
              </p>
            ) : null}
          </div>
        </div>
      )}

      {tgSessionExpiredOpen && (
        <div className="modal-backdrop">
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Требуется переавторизация Telegram</h2>
            </div>
            <p className="muted">{tgSessionExpiredText}</p>
            <div className="actions">
              <button className="primary" onClick={handleTelegramReauthClick}>Переавторизоваться</button>
            </div>
          </div>
        </div>
      )}

      {authModalOpen && (
        <div className="modal-backdrop" onClick={closeAuthModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Добавить аккаунт Telegram</h2>
              <button className="ghost" onClick={closeAuthModal}>Закрыть</button>
            </div>

            <div className="panel-head">
              <h3>QR вход</h3>
            </div>
            <div className="actions">
              <button className="primary" onClick={startQr}>Войти по QR</button>
              <button className="danger" onClick={cancelQr} disabled={!qrAuthId || qrStopped}>Отменить</button>
              <button className="ghost" onClick={continueQr} disabled={!qrAuthId || qrStopped || qrSubmitting}>Проверить</button>
            </div>

            {qrAuthId && !qrStopped && (
              <div className="kv">
                <div>
                  <span>auth_id</span>
                  <strong>{qrAuthId}</strong>
                </div>
                <div>
                  <span>Действителен до</span>
                  <strong>{qrExpiresAt || '—'}</strong>
                </div>
              </div>
            )}

            {qrDataUrl && !qrStopped && (
              <div className="qr-box">
                <img src={qrDataUrl} alt="QR" />
                <div className="muted">Обновить после: {qrRefreshAfter || '—'}</div>
              </div>
            )}

            {qrStatus === 'WAIT_PASSWORD' && (
              <div className="subcard">
                <label>Пароль 2FA</label>
                <input value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
                <div className="actions">
                  <button className="primary" onClick={sendPassword} disabled={qrSubmitting}>Подтвердить пароль</button>
                </div>
              </div>
            )}

            {qrStatus === 'READY' && (
              <div className="status success">
                Готово. QR авторизация завершена.
              </div>
            )}

            {qrStopped && (
              <button className="ghost" onClick={startQr}>Начать новый QR</button>
            )}

            {qrErr && <div className="status error">{qrErr}</div>}
          </div>
        </div>
      )}

      {showMatchesModal && (
        <div className="modal-backdrop" onClick={() => setShowMatchesModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Найденные сообщения</h2>
              <div className="row-actions">
                <button className="ghost" onClick={() => reloadGroupMatches().catch(() => {})} disabled={matchesLoading}>
                  Обновить
                </button>
                <button className="ghost" onClick={() => setShowMatchesModal(false)}>Закрыть</button>
              </div>
            </div>
            {matchesLoading && <p className="muted">Загрузка...</p>}
            {!matchesLoading && matchesErr && <div className="status error">{matchesErr}</div>}
            {!matchesLoading && !matchesErr && (
              <div className="log-list lg">
                {matches.map(item => (
                  <div className="log-item" key={item.id}>
                    <span>{formatDateTime(item.created_at)}</span>
                    <div>
                      <KeywordHighlight text={item.message_text || '—'} keywords={item.matched_keywords || keywords} />
                    </div>
                    <div className="muted">
                      {item.sender_phone ? `+${item.sender_phone}` : 'Номер скрыт'}
                    </div>
                  </div>
                ))}
                {!matches.length && <div className="muted">Пока ничего не найдено.</div>}
              </div>
            )}
          </div>
        </div>
      )}

      {supportNoticeOpen && (
        <div className="modal-backdrop" onClick={closeSupportNotice}>
          <div className="modal support-notice-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>{supportNoticeTitle}</h2>
              <button className="ghost" onClick={closeSupportNotice}>Закрыть</button>
            </div>
            <p className="muted">{supportNoticeText}</p>
            <p className="muted">Если возникнет проблема, можно сразу создать обращение в поддержку.</p>
            <div className="support-onboard-arrow" aria-hidden="true" />
          </div>
        </div>
      )}

      <SupportWidget
        loggedIn={loggedIn}
        pushToast={pushToast}
        formatError={formatError}
      />
    </div>
  )
}
