import React from 'react'
import KeywordHighlight from '../components/KeywordHighlight'
import { formatDateTime } from '../time'

export default function HomeListeningHistory({
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
          <div className="log-item" key={`hm-${m.id}`}>
            <span>{formatDateTime(m.created_at)}</span>
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
