import React from 'react'

export default function MonitoringAdminErrors({
  adminErrors,
  adminErrorsOffset,
  adminErrorsLimit,
  adminErrorsTotal,
  adminErrorsLoading,
  adminErrorsErr,
  setAdminErrorsOffset,
  reloadAdminErrors,
}) {
  const page = Math.floor((adminErrorsOffset || 0) / (adminErrorsLimit || 1)) + 1
  const pages = Math.max(1, Math.ceil((adminErrorsTotal || 0) / (adminErrorsLimit || 1)))

  const levelCls = level => {
    const v = String(level || '').toUpperCase()
    if (v === 'ERROR') return 'danger'
    if (v === 'WARN' || v === 'WARNING') return 'warn'
    return 'muted'
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Ошибки</h2>
      </div>

      <div className="actions">
        <button
          className="ghost"
          disabled={adminErrorsLoading || adminErrorsOffset <= 0}
          onClick={() => setAdminErrorsOffset(prev => Math.max(0, prev - adminErrorsLimit))}
        >
          Назад
        </button>
        <button
          className="ghost"
          disabled={adminErrorsLoading || adminErrorsOffset + adminErrorsLimit >= adminErrorsTotal}
          onClick={() => setAdminErrorsOffset(prev => prev + adminErrorsLimit)}
        >
          Вперед
        </button>
        <button className="ghost" disabled={adminErrorsLoading} onClick={reloadAdminErrors}>
          Обновить
        </button>
        <div className="pill">Стр: {page} / {pages}</div>
        <div className="pill">Всего: {adminErrorsTotal || 0}</div>
      </div>

      {adminErrorsErr && <div className="status error">{adminErrorsErr}</div>}
      {adminErrorsLoading && <div className="muted">Загрузка...</div>}

      {!adminErrorsLoading && !adminErrorsErr && (
        <div className="table">
          <div className="table-head">
            <span>Когда</span>
            <span>Уровень</span>
            <span>Источник</span>
            <span>Локальный</span>
            <span>Аккаунт</span>
            <span>Ошибка</span>
          </div>
          {(adminErrors || []).map(row => (
            <div className="table-row" key={`${row.source}-${row.source_id}`}>
              <span>{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</span>
              <span><span className={`tag ${levelCls(row.level)}`}>{row.level || '—'}</span></span>
              <span title={row.context || ''}>{row.source || '—'}</span>
              <span>{row.local_login || (row.local_user_id ? `#${row.local_user_id}` : '—')}</span>
              <span>{row.account_id ? `#${row.account_id}` : '—'}</span>
              <span title={row.message || ''}>{row.message || '—'}</span>
            </div>
          ))}
          {!(adminErrors || []).length && <div className="muted">Пока ничего нет.</div>}
        </div>
      )}
    </section>
  )
}

