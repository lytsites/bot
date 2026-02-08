import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  authGet,
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
import './styles.css'

export default function App() {
  const [phone, setPhone] = useState('')
  const [authId, setAuthId] = useState('')
  const [status, setStatus] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [authErr, setAuthErr] = useState('')
  const [authSubmitting, setAuthSubmitting] = useState(false)
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

  const [adminUsers, setAdminUsers] = useState([])
  const [adminAccounts, setAdminAccounts] = useState([])
  const [adminWorkers, setAdminWorkers] = useState([])
  const [adminMatches, setAdminMatches] = useState([])
  const [adminMatchesOffset, setAdminMatchesOffset] = useState(0)
  const [adminMatchesLimit, setAdminMatchesLimit] = useState(10)
  const [adminLogin, setAdminLogin] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [adminIsAdmin, setAdminIsAdmin] = useState(false)
  const [adminIsActive, setAdminIsActive] = useState(true)
  const [adminErr, setAdminErr] = useState('')
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    try {
      return localStorage.getItem('theme') === 'dark'
    } catch {
      return false
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

  const [homeRequisites, setHomeRequisites] = useState([])
  const [homeRequisitesErr, setHomeRequisitesErr] = useState('')
  const [homeRequisitesLoading, setHomeRequisitesLoading] = useState(false)

  const listeningGroups = useMemo(
    () => groups.filter(item => item.is_listening),
    [groups]
  )

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
    NO_ACTIVE_ACCOUNT: 'Нет активного Telegram-аккаунта',
    SETTINGS_NOT_FOUND: 'Настройки не найдены',
    ACCOUNT_NOT_FOUND: 'Аккаунт не найден',
    SESSION_NOT_FOUND: 'Сессия не найдена',
    CONFIRM_REQUIRED: 'Требуется подтверждение',
    CREATE_FAILED: 'Ошибка создания',
    PASSWORD_FAILED: 'Неверный пароль 2FA',
    CODE_INVALID: 'Неверный код',
    PHONE_CODE_INVALID: 'Неверный код',
    PHONE_NUMBER_INVALID: 'Неверный номер телефона',
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
    } catch {
      setIsAdmin(false)
      setIsSuperAdmin(false)
      setMeLogin('')
      setMeRole('user')
    } finally {
      setIsAdminChecked(true)
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

  async function loadAdminWorkers() {
    const r = await mainGet('/admin/group_workers')
    setAdminWorkers(r.items || [])
  }

  async function loadAdminMatches(offset = adminMatchesOffset, limit = adminMatchesLimit) {
    const r = await mainGet(`/admin/group_matches?limit=${limit}&offset=${offset}`)
    setAdminMatches(r.items || [])
  }

  async function createAdminUser() {
    setAdminErr('')
    try {
      const r = await mainPost('/admin/users', {
        login: adminLogin,
        password: adminPassword,
        role: adminIsAdmin ? 'admin' : 'user',
        is_active: adminIsActive,
      })
      if (r?.id) {
        setAdminLogin('')
        setAdminPassword('')
        setAdminIsAdmin(false)
        setAdminIsActive(true)
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

  async function startAuth() {
    setAuthErr('')
    try {
      const r = await authPost('/auth/start', { phone })
      setAuthId(r.auth_id)
      setStatus(r.status)
    } catch (e) {
      setAuthErr(formatError(e))
    }
  }

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

  async function cancelQr() {
    if (!qrAuthId) return
    setQrErr('')
    try {
      const r = await authPost('/auth/cancel', { auth_id: qrAuthId })
      setQrStatus(r.status)
    } catch (e) {
      setQrErr(formatError(e))
    }
  }

  async function sendCode() {
    setAuthErr('')
    try {
      const r = await authPost('/auth/code', { auth_id: authId, code })
      setStatus(r.status)
    } catch (e) {
      setAuthErr(formatError(e))
    }
  }

  async function sendPassword() {
    setAuthErr('')
    setAuthSubmitting(true)
    setQrSubmitting(true)
    try {
      const targetId = qrStatus === 'WAIT_PASSWORD' && qrAuthId ? qrAuthId : authId
      const r = await authPost('/auth/password', { auth_id: targetId, password })
      if (targetId === qrAuthId) {
        setQrStatus(r.status)
      } else {
        setStatus(r.status)
      }
    } catch (e) {
      if (qrStatus === 'WAIT_PASSWORD' && qrAuthId) {
        setQrErr(formatError(e))
      } else {
        setAuthErr(formatError(e))
      }
    } finally {
      setAuthSubmitting(false)
      setQrSubmitting(false)
    }
  }

  async function cancelAuth() {
    setAuthErr('')
    try {
      const r = await authPost('/auth/cancel/' + authId, {})
      setStatus(r.status)
    } catch (e) {
      setAuthErr(formatError(e))
    }
  }

  async function refreshAuth() {
    if (!authId) return
    try {
      const r = await authGet('/auth/status/' + authId)
      setStatus(r.status)
    } catch (e) {
      setAuthErr(formatError(e))
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
    } catch (e) {
      setAiStatus({ ok: false, provider: '', deepseek_ok: false, deepseek_error: '', error: formatError(e) })
    }
  }

  async function loadSettings() {
    try {
      const r = await mainGet('/local/settings')
      setKeywords(r.keywords || '')
      setSettingsActive(r.is_active === 1 || r.is_active === true)
    } catch (e) {
      setSettingsErr(formatError(e))
    }
  }

  async function saveSettings(nextKeywords, nextActive) {
    setSettingsErr('')
    try {
      await mainPatch('/local/settings', {
        keywords: nextKeywords,
        is_active: nextActive,
      })
    } catch (e) {
      setSettingsErr(formatError(e))
    }
  }

  async function handleKeywordsChange(value) {
    setKeywords(value)
    await saveSettings(value, settingsActive)
  }

  async function handleActiveToggle(value) {
    setSettingsActive(value)
    await saveSettings(keywords, value)
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
    loadAccounts().catch(e => setUiErr(formatError(e)))
    loadStats().catch(() => {})
    loadAiStatus().catch(() => {})
    loadActiveSession().catch(() => {})
    loadSettings().catch(() => {})
    loadMe().catch(() => {})
  }, [])

  useEffect(() => {
    if (!loggedIn) return
    const id = setInterval(() => {
      loadAiStatus().catch(() => {})
    }, 15000)
    return () => clearInterval(id)
  }, [loggedIn])

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

  useEffect(() => {
    if (!authId) return
    const id = setInterval(() => {
      refreshAuth().catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [authId])

  const qrStopped = ['READY', 'ERROR', 'CANCELLED', 'EXPIRED'].includes(qrStatus)
  const [lastAuthRefreshAt, setLastAuthRefreshAt] = useState(0)
  const needsGroups =
    (activeTopTab === 'home' && homeSideTab === 'listening') ||
    (activeTopTab === 'monitoring' && monitorSideTab === 'listening')
  const monitoringAdminView =
    isAdmin &&
    activeTopTab === 'monitoring' &&
    ['admin-accounts', 'admin-workers', 'admin-listening'].includes(monitorSideTab)

  useEffect(() => {
    if (!qrAuthId || qrSubmitting || qrStopped) return
    const id = setInterval(() => {
      continueQr().catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [qrAuthId, qrSubmitting, qrStopped])

  useEffect(() => {
    document.body.classList.toggle('theme-dark', isDarkTheme)
    try {
      localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light')
    } catch {
    }
  }, [isDarkTheme])

  useEffect(() => {
    const hasModal = authModalOpen || showMatchesModal
    document.body.classList.toggle('modal-open', hasModal)
  }, [authModalOpen, showMatchesModal])

  useEffect(() => {
    if (!isAdminChecked) return
    if (isAdmin) return
    if (!['admin-accounts', 'admin-workers', 'admin-listening'].includes(monitorSideTab)) return
    setMonitorSideTab('listening')
  }, [isAdminChecked, isAdmin, monitorSideTab])

  useEffect(() => {
    if (!loggedIn) return
    const ready = status === 'READY' || qrStatus === 'READY'
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
  }, [status, qrStatus, loggedIn, needsGroups, lastAuthRefreshAt])

  useEffect(() => {
    const id = setInterval(() => {
      if (!loggedIn) return
      loadStats().catch(() => {})
      loadJobs(selectedId).catch(() => {})
      loadActiveSession().catch(() => {})
    }, 3000)
    return () => clearInterval(id)
  }, [selectedId, loggedIn])

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
    loadAdminMatches(adminMatchesOffset, adminMatchesLimit).catch(() => {})
  }, [loggedIn, monitoringAdminView, adminMatchesOffset, adminMatchesLimit])

  useEffect(() => {
    if (!loggedIn) return
    if (!activeAccountId) return
    if (!needsGroups) return
    loadGroups().catch(() => {})
  }, [activeAccountId, loggedIn, needsGroups])

  useEffect(() => {
    if (!loggedIn) return
    if (!needsGroups) return
    const id = setInterval(() => {
      loadGroups().catch(() => {})
    }, 10000)
    return () => clearInterval(id)
  }, [loggedIn, needsGroups])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'settings') return
    if (settingsSideTab !== 'auto') return
    loadAutoChatUsernames().catch(() => {})
    loadAutoChatSettings().catch(() => {})
  }, [loggedIn, activeTopTab, settingsSideTab])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab === 'auto' || homeSideTab === 'auto_history') {
      loadHomeAutoChatUsernames().catch(() => {})
      loadHomeAutoChatDialogs().catch(() => {})
    } else if (homeSideTab === 'requisites_history') {
      loadHomeRequisites().catch(() => {})
    } else {
      setHomeAutoChatHistoryActive(null)
      setHomeAutoChatHistoryMessages([])
      setHomeAutoChatHistoryMessagesErr('')
      setHomeAutoChatHistoryMessagesLoading(false)
    }
  }, [loggedIn, activeTopTab, homeSideTab])

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
    if (activeTopTab !== 'home') return
    if (homeSideTab !== 'auto_history') return
    if (!homeAutoChatHistoryActive?.dialog_id) return

    const id = setInterval(() => {
      pollHomeAutoChatHistoryIncremental(homeAutoChatHistoryActive.dialog_id).catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [loggedIn, activeTopTab, homeSideTab, homeAutoChatHistoryActive?.dialog_id])

  useEffect(() => {
    if (!loggedIn) return
    if (activeTopTab !== 'home') return
    if (homeSideTab !== 'auto_history') return
    if (!homeAutoChatHistoryActive?.dialog_id) return
    loadHomeAutoChatHistoryMessages(homeAutoChatHistoryActive.dialog_id, 2000).catch(() => {})
  }, [loggedIn, activeTopTab, homeSideTab, homeAutoChatHistoryActive?.dialog_id])

  useEffect(() => {
    if (!showMatchesModal || !matchesGroup) return
    const id = setInterval(() => {
      mainGet(`/groups/${matchesGroup.id}/matches`)
        .then(r => setMatches(r.items || []))
        .catch(() => {})
    }, 3000)
    return () => clearInterval(id)
  }, [showMatchesModal, matchesGroup])

  useEffect(() => {
    const handler = () => resetAuthState()
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
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
      await loadAccounts()
      await loadStats()
      await loadSettings()
      await loadMe()
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
    if (next !== 'auto_history') {
      setHomeAutoChatHistoryActive(null)
      setHomeAutoChatHistoryMessages([])
      setHomeAutoChatHistoryMessagesErr('')
      setHomeAutoChatHistoryMessagesLoading(false)
      homeAutoChatHistoryLastMessageIdRef.current = null
    }
    if (next !== 'requisites_history') {
      setHomeRequisites([])
      setHomeRequisitesErr('')
      setHomeRequisitesLoading(false)
    }
  }

  const handleMonitorSideTabChange = next => {
    setMonitorSideTab(next)
    if (next !== 'listening') {
      setSelectedGroupId(null)
    } else {
      loadGroups().catch(() => {})
    }
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
    setMonitorSideTab('listening')
    setSettingsSideTab('main')
    setAuthModalOpen(false)
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
  }

  const monitoringListeningProps = {
    listeningGroups,
    activeAccountId,
    groupWorkerId,
    jobs,
    jobTypeLabel,
    jobStatusMeta,
    cancelJob,
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
    createAdminUser,
    adminErr,
    adminUsers,
    deleteAdminUser,
    adminAccounts,
    deleteAdminAccount,
  }

  const adminWorkersProps = {
    adminWorkers,
    jobStatusMeta,
  }

  const adminListeningProps = {
    adminMatches,
    adminMatchesOffset,
    adminMatchesLimit,
    setAdminMatchesOffset,
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

  const homeAutoChatHistoryProps = {
    homeAutoChatDialogs,
    homeAutoChatDialogsMeta,
    homeAutoChatDialogsErr,
    homeAutoChatDialogsLoading,
    homeAutoChatHistoryActive,
    setHomeAutoChatHistoryActive,
    homeAutoChatHistoryMessages,
    homeAutoChatHistoryMessagesErr,
    homeAutoChatHistoryMessagesLoading,
    loadHomeAutoChatHistoryMessages,
    reload: async () => {
      await loadHomeAutoChatDialogs()
    },
  }

  const homeRequisitesHistoryProps = {
    homeRequisites,
    homeRequisitesErr,
    homeRequisitesLoading,
    reload: async () => {
      await loadHomeRequisites()
    },
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
        <div className="tabs-left">
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
        <button className="tab active tab-logout" onClick={handleLogout}>Выйти</button>
      </div>

      {activeTopTab === 'home' && (
        <HomeTab
          activeSideTab={homeSideTab}
          setActiveSideTab={handleHomeSideTabChange}
          listeningProps={homeListeningProps}
          autoChatProps={homeAutoChatProps}
          autoChatHistoryProps={homeAutoChatHistoryProps}
          requisitesHistoryProps={homeRequisitesHistoryProps}
        />
      )}

      {activeTopTab === 'monitoring' && (
        <MonitoringTab
          isAdmin={isAdmin}
          isSuperAdmin={isSuperAdmin}
          activeSideTab={monitorSideTab}
          setActiveSideTab={handleMonitorSideTabChange}
          listeningProps={monitoringListeningProps}
          adminAccountsProps={adminAccountsProps}
          adminWorkersProps={adminWorkersProps}
          adminListeningProps={adminListeningProps}
        />
      )}

      {activeTopTab === 'settings' && (
        <SettingsTab
          activeSideTab={settingsSideTab}
          setActiveSideTab={handleSettingsSideTabChange}
          accountsProps={settingsAccountsProps}
          listeningProps={settingsListeningProps}
          autoChatProps={settingsAutoChatProps}
          themeProps={themeProps}
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

      {authModalOpen && (
        <div className="modal-backdrop" onClick={() => setAuthModalOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Добавить аккаунт Telegram</h2>
              <button className="ghost" onClick={() => setAuthModalOpen(false)}>Закрыть</button>
            </div>

            <div className="field">
              <label>Телефон</label>
              <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+7..." />
            </div>
            <div className="actions">
              <button className="primary" onClick={startAuth}>Отправить код</button>
              <button className="danger" onClick={cancelAuth} disabled={!authId}>Отменить</button>
            </div>

            {authId && (
              <div className="kv">
                <div>
                  <span>auth_id</span>
                  <strong>{authId}</strong>
                </div>
                <div>
                  <span>Статус</span>
                  <strong>{status || '—'}</strong>
                </div>
              </div>
            )}

            {status === 'CODE_SENT' && (
              <div className="subcard">
                <label>Код из Telegram</label>
                <input value={code} onChange={e => setCode(e.target.value)} placeholder="12345" />
                <button className="primary" onClick={sendCode}>Подтвердить код</button>
              </div>
            )}

            {status === 'WAIT_PASSWORD' && (
              <div className="subcard">
                <label>Пароль 2FA</label>
                <input value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
                <button className="primary" onClick={sendPassword} disabled={authSubmitting}>Подтвердить пароль</button>
              </div>
            )}

            {status === 'READY' && (
              <div className="status success">
                Готово. Сессия сохранена в базе.
              </div>
            )}

            {authErr && <div className="status error">{authErr}</div>}

            <div className="divider" />

            <div className="panel-head">
              <h3>QR вход</h3>
            </div>
            <div className="actions">
              <button className="primary" onClick={startQr}>Войти по QR</button>
              <button className="danger" onClick={cancelQr} disabled={!qrAuthId || qrStopped}>Отменить</button>
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
                <button className="primary" onClick={sendPassword} disabled={qrSubmitting}>Подтвердить пароль</button>
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
              <button className="ghost" onClick={() => setShowMatchesModal(false)}>Закрыть</button>
            </div>
            {matchesLoading && <p className="muted">Загрузка...</p>}
            {!matchesLoading && matchesErr && <div className="status error">{matchesErr}</div>}
            {!matchesLoading && !matchesErr && (
              <div className="log-list">
                {matches.map(item => (
                  <div className="log-item" key={item.id}>
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                    <div>{item.message_text || '—'}</div>
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
    </div>
  )
}
