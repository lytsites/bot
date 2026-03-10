import React from 'react'
import { Trash2 } from 'lucide-react'
import KeywordHighlight from '../components/KeywordHighlight'
import { formatDateTime } from '../time'

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
  isSuperAdmin,
  deleteMonitoringGroupMatch,
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
            <div className="log-item-top">
              <span>{formatDateTime(m.created_at)}</span>
              {isSuperAdmin && (
                <button
                  className="ghost icon-only"
                  type="button"
                  aria-label="Удалить из истории"
                  onClick={() => deleteMonitoringGroupMatch?.(m.id)}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
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
