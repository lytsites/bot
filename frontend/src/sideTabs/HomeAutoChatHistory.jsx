import React, { useMemo } from 'react'
import ChatThread from '../components/ChatThread'

export default function HomeAutoChatHistory({
  showScopeToggle,
  scope,
  setScope,
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
  reload,
}) {
  const items = useMemo(() => homeAutoChatDialogs || [], [homeAutoChatDialogs])

  const statusLabel = status => {
    switch (status) {
      case 'STARTING':
        return 'Запуск'
      case 'WAIT_REPLY':
        return 'Ждет ответ'
      case 'ACTIVE':
        return 'Активен'
      case 'STOPPED':
        return 'Остановлен'
      case 'ERROR':
        return 'Ошибка'
      default:
        return status || '—'
    }
  }

  const statusBadgeClass = status => {
    if (!status) return 'neutral'
    if (status === 'ERROR') return 'danger'
    if (status === 'STARTING' || status === 'WAIT_REPLY' || status === 'ACTIVE') return 'active'
    return 'neutral'
  }

  if (homeAutoChatHistoryActive) {
    const title =
      homeAutoChatHistoryActive.peer_display_name ||
      homeAutoChatHistoryActive.peer_username ||
      String(homeAutoChatHistoryActive.peer_tg_user_id || 'Диалог')

    return (
      <section className="panel">
        <div className="panel-head">
          <button className="ghost" onClick={() => setHomeAutoChatHistoryActive(null)} type="button">
            ← Назад
          </button>
          <h2>{title}</h2>
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
            <span className={`badge ${statusBadgeClass(homeAutoChatHistoryActive.status)}`}>
              {statusLabel(homeAutoChatHistoryActive.status)}
            </span>
            <button
              className="ghost"
              type="button"
              onClick={() => loadHomeAutoChatHistoryMessages(homeAutoChatHistoryActive.dialog_id, 2000)}
            >
              Обновить
            </button>
          </div>
        </div>

        {homeAutoChatHistoryMessagesLoading && <p className="muted">Загрузка...</p>}
        {!homeAutoChatHistoryMessagesLoading && homeAutoChatHistoryMessagesErr && (
          <div className="status error">{homeAutoChatHistoryMessagesErr}</div>
        )}
        {!homeAutoChatHistoryMessagesLoading && !homeAutoChatHistoryMessagesErr && (
          <>
            <ChatThread messages={homeAutoChatHistoryMessages} />
            {!homeAutoChatHistoryMessages.length && (
              <div className="muted" style={{ marginTop: 10 }}>
                История пуста.
              </div>
            )}
          </>
        )}
      </section>
    )
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>История авто. диалогов</h2>
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
          <button className="ghost" onClick={() => reload().catch(() => {})} type="button">
            Обновить
          </button>
        </div>
      </div>

      {homeAutoChatDialogsLoading && <p className="muted">Загрузка...</p>}
      {!homeAutoChatDialogsLoading && homeAutoChatDialogsErr && (
        <div className="status error">{homeAutoChatDialogsErr}</div>
      )}
      {!homeAutoChatDialogsLoading && !homeAutoChatDialogsErr && !items.length && (
        <p className="muted">Диалогов пока нет.</p>
      )}

      {!homeAutoChatDialogsLoading && !homeAutoChatDialogsErr && items.length > 0 && (
        <div className="list">
          {items.map(d => (
            <button
              key={d.id}
              className="row"
              type="button"
              onClick={() => {
                setHomeAutoChatHistoryActive({
                  dialog_id: d.id,
                  peer_tg_user_id: d.peer_tg_user_id,
                  peer_username: d.peer_username,
                  peer_display_name: d.peer_display_name,
                  status: d.status,
                })
              }}
            >
              <div>
                <strong>{d.peer_username || d.peer_display_name || d.peer_tg_user_id}</strong>
                {d.peer_display_name && <span>Имя: {d.peer_display_name}</span>}
                <span>User ID: {d.peer_tg_user_id}</span>
                <span className={`badge ${statusBadgeClass(d.status)}`}>{statusLabel(d.status)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
