import React from 'react'

export default function MonitoringAdminListeningHistory({
  adminMatches,
  adminMatchesOffset,
  adminMatchesLimit,
  setAdminMatchesOffset,
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>История чтения групп</h2>
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
      <div className="log-list lg">
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
  )
}
