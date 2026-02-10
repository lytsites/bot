import React from 'react'
import KeywordHighlight from '../components/KeywordHighlight'

export default function MonitoringListeningHistory({
  showScopeToggle,
  scope,
  setScope,
  reload,
  matches,
  keywords,
  offset,
  limit,
  setOffset,
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>История чтения групп</h2>
        <div className="row-actions">
          {showScopeToggle && (
            <div className="seg" role="tablist" aria-label="Режим истории">
              <button
                type="button"
                className={`seg-btn ${scope === 'personal' ? 'active' : ''}`}
                onClick={() => setScope('personal')}
              >
                Личные
              </button>
              <button
                type="button"
                className={`seg-btn ${scope === 'common' ? 'active' : ''}`}
                onClick={() => setScope('common')}
              >
                Общие
              </button>
            </div>
          )}
          <button className="ghost" onClick={() => reload?.()} type="button">
            Обновить
          </button>
        </div>
      </div>

      <div className="actions">
        <button
          className="ghost"
          disabled={offset === 0}
          onClick={() => setOffset(prev => Math.max(0, prev - limit))}
        >
          Назад
        </button>
        <button className="ghost" onClick={() => setOffset(prev => prev + limit)}>
          Дальше
        </button>
        <div className="pill">Сдвиг: {offset}</div>
        <div className="pill">Лимит: {limit}</div>
      </div>

      <div className="log-list lg">
        {(matches || []).map(m => (
          <div className="log-item" key={`mm-${m.id}`}>
            <span>{m.created_at ? new Date(m.created_at).toLocaleString() : '—'}</span>
            <div>
              <KeywordHighlight text={m.message_text || '—'} keywords={m.matched_keywords || keywords} />
            </div>
            <div className="muted">
              {m.chat_title ? `${m.chat_title} • ` : ''}
              Чат: {m.chat_id}
              {m.message_id ? ` • Msg: ${m.message_id}` : ''}
            </div>
          </div>
        ))}
        {(!matches || matches.length === 0) && <div className="muted">Пока ничего нет.</div>}
      </div>
    </section>
  )
}
