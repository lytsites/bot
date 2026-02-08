import React, { useMemo, useState } from 'react'

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
  createAdminUser,
  adminErr,
  adminUsers,
  deleteAdminUser,
  adminAccounts,
  deleteAdminAccount,
}) {
  const [roleFilter, setRoleFilter] = useState('all') // all|user|admin|superadmin

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
            <span>Действия</span>
          </div>
          {filteredUsers.map(u => (
            <div className="table-row" key={`u-${u.id}`}>
              <span>#{u.id}</span>
              <span>{u.login}</span>
              <span><span className={`tag ${roleMeta(u).cls}`}>{roleMeta(u).label}</span></span>
              <span><span className={`tag ${u.is_active ? 'success' : 'muted'}`}>{u.is_active ? 'Активен' : 'Отключён'}</span></span>
              <span className="row-actions">
                <button className="danger" onClick={() => deleteAdminUser(u.id)} disabled={!canDeleteUser(u)}>
                  Удалить
                </button>
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
    </div>
  )
}
