import React, { useEffect, useMemo, useState } from 'react'
import { formatDateTime } from '../time'

export default function MonitoringAdminAccounts({
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
}) {
  const [roleFilter, setRoleFilter] = useState('all') // all|user|admin|superadmin
  const [edits, setEdits] = useState({}) // userId -> { mode, is_active }
  const [userModalOpen, setUserModalOpen] = useState(false)
  const [userModalUser, setUserModalUser] = useState(null)
  const [commentModalOpen, setCommentModalOpen] = useState(false)
  const [commentModalUser, setCommentModalUser] = useState(null)
  const [commentDraft, setCommentDraft] = useState('')
  const [loginHistory, setLoginHistory] = useState([])
  const [loginHistoryLoading, setLoginHistoryLoading] = useState(false)
  const [loginHistoryErr, setLoginHistoryErr] = useState('')
  const [loginHistoryTotal, setLoginHistoryTotal] = useState(0)
  const [loginHistoryPage, setLoginHistoryPage] = useState(0)
  const LOGIN_HISTORY_PAGE_SIZE = 10

  const roleMeta = u => {
    const role = String(u?.role || '').toLowerCase()
    if (role === 'superadmin' || u?.is_super_admin) return { label: 'Супер-админ', cls: 'warn', key: 'superadmin' }
    if (role === 'admin' || u?.is_admin) return { label: 'Админ', cls: 'info', key: 'admin' }
    return { label: 'Пользователь', cls: 'muted', key: 'user' }
  }

  const canDeleteUser = u => {
    const key = roleMeta(u).key
    if (key === 'superadmin') return false
    if (key === 'admin') return Boolean(isSuperAdmin)
    return true
  }

  const canEditUser = u => {
    // Same permissions model as delete: admin can manage users; superadmin can manage admins too.
    return canDeleteUser(u)
  }

  const modeFromUser = u => {
    // Be defensive: if backend doesn't return these columns (older DB / migrations not applied),
    // treat missing values as enabled to avoid showing everything as "disabled".
    const svcRaw = u?.service_enabled
    const gRaw = u?.feature_group_reading_enabled
    const aRaw = u?.feature_auto_dialogs_enabled
    const svc = svcRaw == null ? true : (svcRaw === true || svcRaw === 1 || svcRaw === '1')
    const g = gRaw == null ? true : (gRaw === true || gRaw === 1 || gRaw === '1')
    const a = aRaw == null ? true : (aRaw === true || aRaw === 1 || aRaw === '1')
    if (!svc) return 'disabled'
    if (g && a) return 'both'
    if (!g && a) return 'no_groups'
    if (g && !a) return 'no_auto'
    return 'disabled'
  }

  const flagsFromMode = mode => {
    if (mode === 'no_groups') return { service_enabled: true, feature_group_reading_enabled: false, feature_auto_dialogs_enabled: true }
    if (mode === 'no_auto') return { service_enabled: true, feature_group_reading_enabled: true, feature_auto_dialogs_enabled: false }
    if (mode === 'disabled') return { service_enabled: false, feature_group_reading_enabled: false, feature_auto_dialogs_enabled: false }
    return { service_enabled: true, feature_group_reading_enabled: true, feature_auto_dialogs_enabled: true }
  }

  const accessTypeMeta = mode => {
    if (mode === 'no_groups') return { label: 'Тип 1', cls: 'muted' }
    if (mode === 'no_auto') return { label: 'Тип 2', cls: 'muted' }
    if (mode === 'disabled') return { label: 'Отключён', cls: 'warn' }
    return { label: 'Оба', cls: 'success' }
  }

  const getEdit = u => {
    const id = String(u?.id || '')
    const cur = edits[id]
    const base = {
      mode: modeFromUser(u),
      is_active: Boolean(u?.is_active),
    }
    if (cur) return { ...base, ...cur }
    return base
  }

  const setEdit = (userId, next) => {
    setEdits(prev => ({ ...prev, [String(userId)]: { ...(prev[String(userId)] || {}), ...next } }))
  }

  const discardEdits = userId => {
    if (userId == null) return
    setEdits(prev => {
      const next = { ...prev }
      delete next[String(userId)]
      return next
    })
  }

  const openUserModal = u => {
    if (!u) return
    setUserModalUser(u)
    setLoginHistoryPage(0)
    setUserModalOpen(true)
  }

  const closeUserModal = () => {
    if (userModalUser?.id != null) discardEdits(userModalUser.id)
    setUserModalOpen(false)
    setUserModalUser(null)
    setLoginHistory([])
    setLoginHistoryLoading(false)
    setLoginHistoryErr('')
    setLoginHistoryTotal(0)
    setLoginHistoryPage(0)
  }

  const loginAttemptMeta = row => {
    if (row?.success === 1 || row?.success === true) return { label: 'Успешно', cls: 'success' }
    if ((row?.reason || '') === 'LOGIN_RATE_LIMITED') return { label: 'Лимит', cls: 'warn' }
    return { label: 'Ошибка', cls: 'danger' }
  }

  const loginAttemptReason = row => {
    const reason = String(row?.reason || '')
    if (reason === 'OK') return 'Вход выполнен'
    if (reason === 'LOGIN_RATE_LIMITED') return 'Слишком много попыток'
    if (reason === 'BAD_CREDENTIALS') return 'Неверный логин или пароль'
    return reason || '—'
  }

  useEffect(() => {
    if (!userModalOpen || !userModalUser?.id) return
    let cancelled = false
    setLoginHistory([])
    setLoginHistoryErr('')
    setLoginHistoryLoading(true)
    const offset = loginHistoryPage * LOGIN_HISTORY_PAGE_SIZE
    loadAdminUserLoginHistory(userModalUser.id, LOGIN_HISTORY_PAGE_SIZE, offset)
      .then(payload => {
        if (cancelled) return
        setLoginHistory(payload?.items || [])
        setLoginHistoryTotal(Number(payload?.total || 0))
      })
      .catch(e => {
        if (cancelled) return
        setLoginHistoryErr(String(e?.message || e || 'ERROR'))
      })
      .finally(() => {
        if (cancelled) return
        setLoginHistoryLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userModalOpen, userModalUser?.id, loginHistoryPage])

  const openSaveModal = u => {
    if (!u) return
    setCommentModalUser(u)
    setCommentDraft('') // всегда пустой, как ты просил
    setCommentModalOpen(true)
  }

  const closeSaveModal = () => {
    setCommentModalOpen(false)
    setCommentModalUser(null)
    setCommentDraft('')
  }

  const cancelSave = () => {
    // отмена отменяет локальные изменения (роль/флаги не отправляются на сервер)
    if (commentModalUser?.id != null) {
      discardEdits(commentModalUser.id)
    }
    closeSaveModal()
  }

  const confirmSave = async () => {
    const u = commentModalUser
    if (!u) return
    const e = getEdit(u)
    const flags = flagsFromMode(e.mode)
    const patch = {
      is_active: Boolean(e.is_active),
      service_enabled: flags.service_enabled,
      feature_group_reading_enabled: flags.feature_group_reading_enabled,
      feature_auto_dialogs_enabled: flags.feature_auto_dialogs_enabled,
    }
    // Always send disabled_comment, even if empty: empty clears the previous comment.
    patch.disabled_comment = String(commentDraft || '')
    await updateAdminUser(u.id, patch)
    setEdits(prev => {
      const next = { ...prev }
      delete next[String(u.id)]
      return next
    })
    closeSaveModal()
    // Close the user edit modal only after a successful save.
    closeUserModal()
  }

  const filteredUsers = useMemo(() => {
    if (roleFilter === 'all') return adminUsers || []
    return (adminUsers || []).filter(u => roleMeta(u).key === roleFilter)
  }, [adminUsers, roleFilter])

  return (
    <div className="grid">
      <section className="panel">
        <div className="panel-head">
          <h2>Пользователи</h2>
          <div className="seg">
            <button className={`seg-btn ${roleFilter === 'all' ? 'active' : ''}`} onClick={() => setRoleFilter('all')}>
              Все
            </button>
            <button className={`seg-btn ${roleFilter === 'user' ? 'active' : ''}`} onClick={() => setRoleFilter('user')}>
              Пользователи
            </button>
            <button className={`seg-btn ${roleFilter === 'admin' ? 'active' : ''}`} onClick={() => setRoleFilter('admin')}>
              Админы
            </button>
            <button className={`seg-btn ${roleFilter === 'superadmin' ? 'active' : ''}`} onClick={() => setRoleFilter('superadmin')}>
              Супер-админы
            </button>
          </div>
        </div>
        <div className="field">
          <label>Логин (email)</label>
          <input value={adminLogin} onChange={e => setAdminLogin(e.target.value)} placeholder="user@example.com" />
        </div>
        <div className="field">
          <label>Пароль</label>
          <input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <div className="field">
          <label>Доступ</label>
          <select value={adminAccessMode} onChange={e => setAdminAccessMode(e.target.value)}>
            <option value="both">Оба: Чтение групп + Авто. диалоги</option>
            <option value="no_groups">Тип 1: без Чтения групп</option>
            <option value="no_auto">Тип 2: без Авто. диалогов</option>
            <option value="disabled">Отключить возможности</option>
          </select>
        </div>
        <div className="actions">
          {isSuperAdmin && (
            <label className="toggle">
              <input type="checkbox" checked={adminIsAdmin} onChange={e => setAdminIsAdmin(e.target.checked)} />
              <span>Админ</span>
            </label>
          )}
          <label className="toggle">
            <input type="checkbox" checked={adminIsActive} onChange={e => setAdminIsActive(e.target.checked)} />
            <span>Активен</span>
          </label>
          <button className="primary" onClick={createAdminUser}>Создать</button>
        </div>
        {adminErr && <div className="status error">{adminErr}</div>}
        <div className="panel-spacer" />
        <div className="table">
          <div className="table-head">
            <span>ID</span>
            <span>Логин</span>
            <span>Роль</span>
            <span>Статус</span>
            <span>Последний онлайн</span>
            <span>Действия</span>
          </div>
          {filteredUsers.map(u => (
            <div
              className="table-row"
              key={`u-${u.id}`}
              role="button"
              tabIndex={0}
              onClick={() => openUserModal(u)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') openUserModal(u)
              }}
              style={{ cursor: 'pointer' }}
            >
              {(() => {
                const e = getEdit(u)
                return (
                  <>
              <span>#{u.id}</span>
              <span>{u.login}</span>
              <span>
                <span className="tag-stack">
                  <span className={`tag ${roleMeta(u).cls}`}>{roleMeta(u).label}</span>
                  <span className={`tag ${accessTypeMeta(e.mode).cls}`}>{accessTypeMeta(e.mode).label}</span>
                </span>
              </span>
              <span><span className={`tag ${e.is_active ? 'success' : 'muted'}`}>{e.is_active ? 'Активен' : 'Отключён'}</span></span>
              <span>{formatDateTime(u.last_online_at)}</span>
              <span className="row-actions" onClick={ev => ev.stopPropagation()}>
                <button className="ghost" onClick={() => openUserModal(u)}>Открыть</button>
                <button className="danger" onClick={() => deleteAdminUser(u.id)} disabled={!canDeleteUser(u)}>Удалить</button>
              </span>
                  </>
                )
              })()}
            </div>
          ))}
        </div>
      </section>

      {userModalOpen && userModalUser && (
        <div className="modal-backdrop" onClick={closeUserModal} style={{ zIndex: 1000 }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Пользователь #{userModalUser.id}</h2>
              <button className="ghost" onClick={closeUserModal}>Закрыть</button>
            </div>

            {(() => {
              const e = getEdit(userModalUser)
              const editable = canEditUser(userModalUser)
              const currentComment = String(userModalUser?.disabled_comment || '').trim()
              return (
                <>
                  <div className="kv">
                    <div>
                      <span>Логин</span>
                      <strong>{userModalUser.login}</strong>
                    </div>
                    <div>
                      <span>Роль</span>
                      <strong>{roleMeta(userModalUser).label}</strong>
                    </div>
                  </div>

                  <div className="field">
                    <label>Активен</label>
                    <label className="toggle" style={{ gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={Boolean(e.is_active)}
                        onChange={ev => setEdit(userModalUser.id, { is_active: ev.target.checked })}
                        disabled={!editable}
                      />
                      <span className={`tag ${e.is_active ? 'success' : 'muted'}`}>{e.is_active ? 'Активен' : 'Отключён'}</span>
                    </label>
                  </div>

                  <div className="field">
                    <label>Доступ</label>
                    <select
                      value={e.mode}
                      onChange={ev => setEdit(userModalUser.id, { mode: ev.target.value })}
                      disabled={!editable}
                    >
                      <option value="both">Оба</option>
                      <option value="no_groups">Тип 1 (без Чтения групп)</option>
                      <option value="no_auto">Тип 2 (без Авто. диалогов)</option>
                      <option value="disabled">Отключён</option>
                    </select>
                  </div>

                  <div className="field">
                    <label>Комментарий (последний сохранённый)</label>
                    <div className="status muted">{currentComment || '—'}</div>
                  </div>

                  <div className="panel-spacer" />
                  <div className="field">
                    <label>История входов</label>
                    {loginHistoryLoading && <div className="muted">Загрузка...</div>}
                    {!loginHistoryLoading && loginHistoryErr && <div className="status error">{loginHistoryErr}</div>}
                    {!loginHistoryLoading && !loginHistoryErr && (
                      <>
                        <div className="login-history-scroll">
                          <div className="table">
                            <div className="table-head">
                              <span>Время</span>
                              <span>Статус</span>
                              <span>IP</span>
                              <span>Причина</span>
                              <span>User-Agent</span>
                            </div>
                            {loginHistory.map(row => {
                              const meta = loginAttemptMeta(row)
                              return (
                                <div className="table-row" key={`lh-${row.id}`}>
                                  <span>{formatDateTime(row.created_at)}</span>
                                  <span><span className={`tag ${meta.cls}`}>{meta.label}</span></span>
                                  <span>{row.ip || '—'}</span>
                                  <span>{loginAttemptReason(row)}</span>
                                  <span title={row.user_agent || ''}>{row.user_agent || '—'}</span>
                                </div>
                              )
                            })}
                            {!loginHistory.length && <div className="muted">Записей пока нет.</div>}
                          </div>
                        </div>
                        <div className="actions login-history-pager">
                          <span className="muted">
                            Стр. {loginHistoryPage + 1} из {Math.max(1, Math.ceil(loginHistoryTotal / LOGIN_HISTORY_PAGE_SIZE))}
                          </span>
                          <button
                            className="ghost"
                            onClick={() => setLoginHistoryPage(p => Math.max(0, p - 1))}
                            disabled={loginHistoryPage <= 0 || loginHistoryLoading}
                          >
                            Назад
                          </button>
                          <button
                            className="ghost"
                            onClick={() => setLoginHistoryPage(p => p + 1)}
                            disabled={(loginHistoryPage + 1) * LOGIN_HISTORY_PAGE_SIZE >= loginHistoryTotal || loginHistoryLoading}
                          >
                            Вперед
                          </button>
                        </div>
                      </>
                    )}
                    {!loginHistoryLoading && !loginHistoryErr && loginHistoryTotal > 0 && (
                      <div className="muted">
                        Показано {loginHistory.length} из {loginHistoryTotal}
                      </div>
                    )}
                  </div>

                  <div className="actions">
                    <button className="primary" onClick={() => openSaveModal(userModalUser)} disabled={!editable}>
                      Сохранить
                    </button>
                    <button
                      className="danger"
                      onClick={async () => {
                        await deleteAdminUser(userModalUser.id)
                        closeUserModal()
                      }}
                      disabled={!canDeleteUser(userModalUser)}
                    >
                      Удалить
                    </button>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {commentModalOpen && (
        <div className="modal-backdrop" onClick={cancelSave} style={{ zIndex: 2000 }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Комментарий</h2>
              <button className="ghost" onClick={cancelSave}>Закрыть</button>
            </div>
            <div className="field">
              <label>Комментарий (необязательно)</label>
              <input
                value={commentDraft}
                onChange={e => setCommentDraft(e.target.value)}
                placeholder="Причина изменения / отключения"
              />
            </div>
            <div className="actions">
              <button className="primary" onClick={confirmSave}>
                {String(commentDraft || '').trim() ? 'Сохранить' : 'Сохранить без комментария'}
              </button>
              <button className="danger" onClick={cancelSave}>Отмена</button>
            </div>
          </div>
        </div>
      )}

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
    </div>
  )
}
