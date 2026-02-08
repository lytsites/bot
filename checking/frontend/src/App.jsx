import React, { useEffect, useMemo, useState } from 'react'
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

  const [uiErr, setUiErr] = useState('')
  const [loggedIn, setLoggedIn] = useState(!!getAuthToken())
  const [login, setLogin] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginErr, setLoginErr] = useState('')
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isAdmin, setIsAdmin] = useState(false)
  const [keywords, setKeywords] = useState('')
  const [settingsActive, setSettingsActive] = useState(true)
  const [settingsErr, setSettingsErr] = useState('')
  const [groups, setGroups] = useState([])
  const [groupsErr, setGroupsErr] = useState('')
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [selectedGroupId, setSelectedGroupId] = useState(null)
  const [messagesTab, setMessagesTab] = useState('groups')
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
      setIsAdmin(r.is_admin === 1 || r.is_admin === true)
    } catch {
      setIsAdmin(false)
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
        is_admin: adminIsAdmin,
        is_active: adminIsActive,
      })
      if (r?.id) {
        setAdminLogin('')
        setAdminPassword('')
        setAdminIsAdmin(false)
        setAdminIsActive(true)
      }
      await loadAdminUsers()
    } catch (e) {
      setAdminErr(formatError(e))
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
    } catch (e) {
      setAdminErr(formatError(e))
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
    } catch (e) {
      setAdminErr(formatError(e))
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
    setJobs(r.items || [])
  }

  async function loadStats() {
    const r = await mainGet('/stats')
    setStats(r)
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
    setActiveAccountId(first ? first.account_id : null)
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
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  // session-level controls removed from UI; switch is handled by account action

  async function cancelJob(jobId) {
    try {
      await mainPost(`/jobs/${jobId}/cancel`, {})
      await loadJobs(selectedId)
    } catch (e) {
      setUiErr(formatError(e))
    }
  }

  useEffect(() => {
    if (!loggedIn) return
    loadAccounts().catch(e => setUiErr(formatError(e)))
    loadStats().catch(() => {})
    loadActiveSession().catch(() => {})
    loadSettings().catch(() => {})
    loadMe().catch(() => {})
  }, [])

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

  useEffect(() => {
    if (!qrAuthId || qrSubmitting || qrStopped) return
    const id = setInterval(() => {
      continueQr().catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [qrAuthId, qrSubmitting, qrStopped])

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
    if (activeTab === 'messages' && messagesTab === 'groups') {
      loadGroups().catch(() => {})
    }
  }, [status, qrStatus, loggedIn, activeTab, messagesTab, lastAuthRefreshAt])

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
    if (activeTab !== 'messages') return
    if (messagesTab === 'groups') {
      loadGroups().catch(() => {})
    }
  }, [activeTab, activeAccountId, messagesTab])

  useEffect(() => {
    if (!loggedIn || !isAdmin || activeTab !== 'admin') return
    loadAdminUsers().catch(() => {})
    loadAdminAccounts().catch(() => {})
    loadAdminWorkers().catch(() => {})
    loadAdminMatches(adminMatchesOffset, adminMatchesLimit).catch(() => {})
  }, [loggedIn, isAdmin, activeTab, adminMatchesOffset, adminMatchesLimit])

  useEffect(() => {
    if (!loggedIn) return
    if (!activeAccountId) return
    loadGroups().catch(() => {})
  }, [activeAccountId, loggedIn])

  useEffect(() => {
    if (!loggedIn) return
    const id = setInterval(() => {
      loadGroups().catch(() => {})
    }, 10000)
    return () => clearInterval(id)
  }, [loggedIn])

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

  function resetAuthState() {
    setAuthToken('')
    setLoggedIn(false)
    setIsAdmin(false)
    setAccounts([])
    setSessions([])
    setJobs([])
    setStats(null)
    setSelectedId(null)
    setActiveAccountId(null)
    setKeywords('')
    setSettingsActive(true)
    setSettingsErr('')
    setActiveTab('dashboard')
    setAuthModalOpen(false)
  }

  async function handleLogout() {
    try {
      await mainPost('/local/logout', {}, true)
    } catch {
    } finally {
      resetAuthState()
    }
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
          <div className="stat">
            <span>Аккаунты</span>
            <strong>{stats ? stats.accounts_total : '—'}</strong>
          </div>
          <div className="stat">
            <span>Активные воркеры</span>
            <strong>{stats ? stats.workers_active : '—'}</strong>
          </div>
          <div className="stat">
            <span>Очередь</span>
            <strong>{stats ? stats.queue_total : '—'}</strong>
          </div>
        </div>
      </header>

      <div className="tabs tabs-row">
        <div className="tabs-left">
          <button
            className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Управление
          </button>
          <button
            className={`tab ${activeTab === 'messages' ? 'active' : ''}`}
            onClick={() => setActiveTab('messages')}
          >
            Сообщения
          </button>
          {isAdmin && (
            <button
              className={`tab ${activeTab === 'admin' ? 'active' : ''}`}
              onClick={() => setActiveTab('admin')}
            >
              Админ
            </button>
          )}
        </div>
        <button className="tab active tab-logout" onClick={handleLogout}>Выйти</button>
      </div>

      {activeTab === 'messages' && (
        <main className="grid">
          <section className="panel">
            <div className="panel-head">
              <h2>Сообщения</h2>
              <span className="muted">
                {activeAccountId ? `Аккаунт #${activeAccountId}` : 'Нет активного аккаунта'}
              </span>
            </div>
            <div className="subtabs">
              <button
                className={`subtab ${messagesTab === 'groups' ? 'active' : ''}`}
                onClick={() => {
                  setMessagesTab('groups')
                  setSelectedGroupId(null)
                  loadGroups().catch(() => {})
                }}
              >
                Группы
              </button>
              <button
                className={`subtab ${messagesTab === 'private' ? 'active' : ''}`}
                onClick={() => {
                  setMessagesTab('private')
                  setSelectedGroupId(null)
                }}
              >
                Личные
              </button>
            </div>

            {messagesTab === 'private' && (
              <p className="muted">Личные переписки пока не подключены.</p>
            )}

            {messagesTab === 'groups' && (
              <>
                {groupsLoading && <p className="muted">Загрузка...</p>}
                {!groupsLoading && groupsErr && <div className="status error">{groupsErr}</div>}
                {!groupsLoading && !groupsErr && selectedGroupId === null && (
                  <div className="list">
                    {sortedGroups.map(item => (
                      <button
                        key={`group-${item.id}`}
                        className={`row ${item.is_listening ? 'listening' : ''}`}
                        onClick={() => setSelectedGroupId(item.id)}
                      >
                        <div>
                          <strong>{item.title || 'Без названия'}</strong>
                          <span>#{item.id}</span>
                        </div>
                        <span className={`badge ${item.is_listening ? 'ok' : 'muted'}`}>
                          {item.is_listening ? 'LISTENING' : 'OFF'}
                        </span>
                      </button>
                    ))}
                    {!groups.length && <div className="muted">Список пуст.</div>}
                  </div>
                )}

                {!groupsLoading && !groupsErr && selectedGroupId !== null && (
                  <div className="split split-compact">
                    <div className="list">
                      {sortedGroups.map(item => (
                        <button
                          key={`group-${item.id}`}
                          className={`row ${selectedGroupId === item.id ? 'active' : ''} ${item.is_listening ? 'listening' : ''}`}
                          onClick={() => {
                            if (selectedGroupId === item.id) {
                              setSelectedGroupId(null)
                            } else {
                              setSelectedGroupId(item.id)
                            }
                          }}
                        >
                          <div>
                            <strong>{item.title || 'Без названия'}</strong>
                            <span>#{item.id}</span>
                          </div>
                          <span className={`badge ${item.is_listening ? 'ok' : 'muted'}`}>
                            {item.is_listening ? 'LISTENING' : 'OFF'}
                          </span>
                        </button>
                      ))}
                    </div>

                    <div className="details">
                      <div className="subcard">
                        <h3>Группа</h3>
                        <p className="muted">
                          {(sortedGroups.find(g => g.id === selectedGroupId)?.title) || 'Без названия'}
                        </p>
                        <div className="actions">
                          <label className="toggle">
                            <input
                              type="checkbox"
                              checked={!!sortedGroups.find(g => g.id === selectedGroupId)?.is_listening}
                              onChange={e => {
                                const group = sortedGroups.find(g => g.id === selectedGroupId)
                                setGroupListening(group, e.target.checked)
                              }}
                            />
                            <span>Слушать</span>
                          </label>
                        </div>
                        {(() => {
                          const group = sortedGroups.find(g => g.id === selectedGroupId)
                          if (!group || !group.is_listening) return null
                          const count = groupMatchCounts[selectedGroupId] || 0
                          return (
                            <div className="match-row">
                              <span>Найдено: {count} сообщений</span>
                              <button
                                className="ghost"
                                disabled={!count}
                                onClick={() => openMatchesModal(group)}
                              >
                                Показать
                              </button>
                            </div>
                          )
                        })()}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        </main>
      )}

      {activeTab === 'dashboard' && (
      <main className="grid">
        <section className="panel auth">
          <div className="panel-head">
            <h2>Telegram</h2>
          </div>
          <p className="muted">Добавляйте аккаунты Telegram через отдельное окно авторизации.</p>
          <div className="actions">
            <button className="primary" onClick={() => setAuthModalOpen(true)}>Добавить аккаунт TG</button>
          </div>
        </section>

        <section className="panel accounts">
          <div className="panel-head">
            <h2>Аккаунты</h2>
          </div>

          <div className="split">
            <div className="list">
              {accounts.map(acc => (
                <button
                  key={acc.id}
                  className={`row ${selectedId === acc.id ? 'active' : ''}`}
                  onClick={() => setSelectedId(acc.id)}
                >
                  <div>
                    <strong>{acc.display_name || 'Без имени'}</strong>
                    <span>{acc.phone || '—'}</span>
                  </div>
                  <span className={`badge ${acc.id === activeAccountId ? 'ok' : 'muted'}`}>
                    {acc.id === activeAccountId ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                </button>
              ))}
            </div>

            <div className="details">
              <div className="subcard">
                <h3>Действия</h3>
                <p className="muted">Активный аккаунт — только один. Сессии не удаляются при переключении.</p>
                <div className="actions">
                  <button
                    className="primary"
                    onClick={switchToSelectedAccount}
                    disabled={!selectedId || selectedId === activeAccountId}
                  >
                    Переключиться
                  </button>
                  <button className="danger" onClick={deleteAccount} disabled={!selectedId}>
                    Удалить аккаунт
                  </button>
                  <button className="danger" onClick={deleteAllAccounts} disabled={!accounts.length}>
                    Удалить все
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="panel jobs">
          <div className="panel-head">
            <h2>Jobs / Worker</h2>
            <span className="muted">Polling 3s</span>
          </div>
          <div className="table">
            <div className="table-head">
              <span>ID</span>
              <span>Тип</span>
              <span>Статус</span>
              <span>Таргеты</span>
              <span>Действия</span>
            </div>
            {listeningGroups.length > 0 && (
              <div className="table-row">
                <span>
                  {activeAccountId && groupWorkerId
                    ? `${activeAccountId}_${groupWorkerId}_GROUPS`
                    : '—'}
                </span>
                <span>
                  <span className="tag info">{jobTypeLabel('GROUP_LISTENER')}</span>
                </span>
                <span>
                  <span className="tag success">Работает</span>
                </span>
                <span>
                  {listeningGroups.map(item => item.title || `#${item.id}`).join(', ')}
                </span>
                <span className="row-actions">—</span>
              </div>
            )}
            {jobs.map(job => (
              <div className="table-row" key={job.id}>
                <span>#{job.id}</span>
                <span>
                  <span className="tag info">{jobTypeLabel(job.type)}</span>
                </span>
                <span>
                  <span className={`tag ${jobStatusMeta(job.status).cls}`}>
                    {jobStatusMeta(job.status).label}
                  </span>
                </span>
                <span>
                  {job.progress !== null && job.progress !== undefined
                    ? `${job.progress || 0}%`
                    : '—'}
                </span>
                <span className="row-actions">
                  <button className="danger" onClick={() => cancelJob(job.id)} disabled={job.status !== 'RUNNING' && job.status !== 'PENDING'}>
                    Отменить
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel settings">
          <div className="panel-head">
            <h2>Ключевые слова</h2>
          </div>
          <div className="field">
            <label>Ключевые слова (через запятую)</label>
            <input
              value={keywords}
              onChange={e => handleKeywordsChange(e.target.value)}
              placeholder="пример: bitcoin, scam, airdrop"
            />
          </div>
          <div className="actions">
            <label className="toggle">
              <input
                type="checkbox"
                checked={settingsActive}
                onChange={e => handleActiveToggle(e.target.checked)}
              />
              <span>Активно</span>
            </label>
          </div>
          {settingsErr && <div className="status error">{settingsErr}</div>}
        </section>

      </main>
      )}

      {activeTab === 'admin' && (
        <main className="grid">
          <section className="panel">
            <div className="panel-head">
              <h2>Пользователи</h2>
            </div>
            <div className="field">
              <label>Логин (email)</label>
              <input value={adminLogin} onChange={e => setAdminLogin(e.target.value)} placeholder="user@example.com" />
            </div>
            <div className="field">
              <label>Пароль</label>
              <input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <div className="actions">
              <label className="toggle">
                <input type="checkbox" checked={adminIsAdmin} onChange={e => setAdminIsAdmin(e.target.checked)} />
                <span>Админ</span>
              </label>
              <label className="toggle">
                <input type="checkbox" checked={adminIsActive} onChange={e => setAdminIsActive(e.target.checked)} />
                <span>Активен</span>
              </label>
              <button className="primary" onClick={createAdminUser}>Создать</button>
            </div>
            {adminErr && <div className="status error">{adminErr}</div>}
            <div className="table">
              <div className="table-head">
                <span>ID</span>
                <span>Логин</span>
                <span>Роль</span>
                <span>Статус</span>
                <span>Действия</span>
              </div>
              {adminUsers.map(u => (
                <div className="table-row" key={`u-${u.id}`}>
                  <span>#{u.id}</span>
                  <span>{u.login}</span>
                  <span><span className={`tag ${u.is_admin ? 'info' : 'muted'}`}>{u.is_admin ? 'Админ' : 'Пользователь'}</span></span>
                  <span><span className={`tag ${u.is_active ? 'success' : 'muted'}`}>{u.is_active ? 'Активен' : 'Отключён'}</span></span>
                  <span className="row-actions">
                    <button className="danger" onClick={() => deleteAdminUser(u.id)}>Удалить</button>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Telegram аккаунты</h2>
            </div>
            <div className="table">
              <div className="table-head">
                <span>ID</span>
                <span>Имя</span>
                <span>Владелец</span>
                <span>Статус</span>
                <span>Действия</span>
              </div>
              {adminAccounts.map(a => (
                <div className="table-row" key={`a-${a.id}`}>
                  <span>#{a.id}</span>
                  <span>{a.display_name || 'Без имени'}</span>
                  <span>{a.local_login || `#${a.local_user_id}`}</span>
                  <span><span className={`tag ${a.is_active ? 'success' : 'muted'}`}>{a.is_active ? 'Активен' : 'Отключён'}</span></span>
                  <span className="row-actions">
                    <button className="danger" onClick={() => deleteAdminAccount(a.id)}>Удалить</button>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>История воркеров</h2>
            </div>
            <div className="table">
              <div className="table-head">
                <span>ID</span>
                <span>Аккаунт</span>
                <span>Статус</span>
                <span>Период</span>
                <span>Ошибка</span>
              </div>
              {adminWorkers.map(w => (
                <div className="table-row" key={`w-${w.id}`}>
                  <span>#{w.id}</span>
                  <span>{w.account_id}</span>
                  <span><span className={`tag ${jobStatusMeta(w.status).cls}`}>{jobStatusMeta(w.status).label}</span></span>
                  <span>{w.started_at}{w.stopped_at ? ` → ${w.stopped_at}` : ''}</span>
                  <span className="muted">{w.last_error || '—'}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Прослушивания</h2>
            </div>
            <div className="actions">
              <button
                className="ghost"
                disabled={adminMatchesOffset === 0}
                onClick={() => setAdminMatchesOffset(prev => Math.max(0, prev - adminMatchesLimit))}
              >
                Назад
              </button>
              <button
                className="ghost"
                onClick={() => setAdminMatchesOffset(prev => prev + adminMatchesLimit)}
              >
                Дальше
              </button>
              <div className="pill">Сдвиг: {adminMatchesOffset}</div>
              <div className="pill">Лимит: {adminMatchesLimit}</div>
            </div>
            <div className="log-list">
              {adminMatches.map(m => (
                <div className="log-item" key={`m-${m.id}`}>
                  <span>{new Date(m.created_at).toLocaleString()}</span>
                  <div>{m.message_text || '—'}</div>
                  <div className="muted">Акк: {m.account_id} • Чат: {m.chat_id} • Msg: {m.message_id}</div>
                </div>
              ))}
              {!adminMatches.length && <div className="muted">Пока ничего нет.</div>}
            </div>
          </section>
        </main>
      )}

      {uiErr && <div className="toast">{uiErr}</div>}

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
