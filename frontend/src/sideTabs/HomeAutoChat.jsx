import React, { useEffect, useMemo, useState } from 'react'
import ChatThread from '../components/ChatThread'

export default function HomeAutoChat({
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
  reload,
  startHomeAutoChat,
  stopHomeAutoChat,
  loadHomeAutoChatMessages,
}) {
  const dialogByPeer = useMemo(
    () => new Map((homeAutoChatDialogs || []).map(d => [d.peer_tg_user_id, d])),
    [homeAutoChatDialogs]
  )

  const limit = homeAutoChatDialogsMeta?.limit ?? 10
  const activeCount = homeAutoChatDialogsMeta?.active_count ?? 0
  const available = Math.max(0, limit - activeCount)

  const isActiveStatus = status =>
    status === 'STARTING' || status === 'WAIT_REPLY' || status === 'ACTIVE'

  const isValidPeerId = tgUserId => Number.isFinite(Number(tgUserId)) && Number(tgUserId) > 0

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
    if (isActiveStatus(status)) return 'active'
    return 'neutral'
  }

  const selectedInactiveCount = useMemo(() => {
    return (homeAutoChatSelected || []).filter(id => {
      const d = dialogByPeer.get(id)
      return !isActiveStatus(d?.status || null)
    }).length
  }, [homeAutoChatSelected, dialogByPeer])

  const toggleSelected = tgUserId => {
    setHomeAutoChatSelected(prev => {
      if (prev.includes(tgUserId)) return prev.filter(x => x !== tgUserId)

      const d = dialogByPeer.get(tgUserId)
      const active = isActiveStatus(d?.status || null)
      if (!active) {
        const inactiveCount = prev.filter(id => {
          const dd = dialogByPeer.get(id)
          return !isActiveStatus(dd?.status || null)
        }).length
        if (inactiveCount >= available) return prev
      }
      return [...prev, tgUserId]
    })
  }

  const activeDialog = useMemo(() => {
    if (!homeAutoChatActive) return null
    if (homeAutoChatActive.dialog_id) {
      return (
        (homeAutoChatDialogs || []).find(d => d.id === homeAutoChatActive.dialog_id) ||
        dialogByPeer.get(homeAutoChatActive.tg_user_id) ||
        null
      )
    }
    return dialogByPeer.get(homeAutoChatActive.tg_user_id) || null
  }, [homeAutoChatActive, homeAutoChatDialogs, dialogByPeer])

  const activeStatus = activeDialog?.status || homeAutoChatActive?.status || null
  const canStop = isActiveStatus(activeStatus)
  const canStart = !isActiveStatus(activeStatus) && available > 0

  const [showHistory, setShowHistory] = useState(true)

  useEffect(() => {
    setShowHistory(activeStatus !== 'STOPPED')
  }, [homeAutoChatActive?.dialog_id, activeStatus])

  const selectedToStart = useMemo(() => {
    return (homeAutoChatSelected || []).filter(id => {
      const d = dialogByPeer.get(id)
      return isValidPeerId(id) && !isActiveStatus(d?.status || null)
    })
  }, [homeAutoChatSelected, dialogByPeer])

  if (homeAutoChatActive) {
    return (
      <section className="panel">
        <div className="panel-head">
          <button className="ghost" onClick={() => setHomeAutoChatActive(null)} type="button">
            ← Назад
          </button>
          <h2>{homeAutoChatActive.display_name || homeAutoChatActive.username}</h2>
          <div className="row-actions">
            {activeStatus && (
              <span className={`tag ${activeStatus === 'ERROR' ? 'danger' : 'info'}`}>
                {statusLabel(activeStatus)}
              </span>
            )}
            {activeDialog?.id && (
              <button
                className="danger"
                disabled={!canStop}
                onClick={() => stopHomeAutoChat(activeDialog.id)}
                type="button"
              >
                Остановить
              </button>
            )}
            {homeAutoChatActive.tg_user_id && (
              <button
                className="primary"
                disabled={!canStart}
                onClick={() => startHomeAutoChat([homeAutoChatActive.tg_user_id])}
                type="button"
              >
                Запустить
              </button>
            )}
          </div>
        </div>

        {activeDialog?.pending_incoming && <div className="status success">Генерирую ответ...</div>}
        {activeDialog?.last_error && <div className="status error">{activeDialog.last_error}</div>}

        {activeStatus === 'STOPPED' && !showHistory && (
          <div className="subcard">
            <p className="muted">Диалог остановлен. История скрыта.</p>
            <div className="actions">
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  setShowHistory(true)
                  if (activeDialog?.id) {
                    loadHomeAutoChatMessages(activeDialog.id, {
                      since: activeDialog?.started_at || homeAutoChatActive?.started_at || null,
                      limit: 200,
                    }).catch(() => {})
                  }
                }}
              >
                Показать историю
              </button>
            </div>
          </div>
        )}

        {(activeStatus !== 'STOPPED' || showHistory) && (
          <>
            {homeAutoChatMessagesLoading && <p className="muted">Загрузка...</p>}
            {!homeAutoChatMessagesLoading && homeAutoChatMessagesErr && (
              <div className="status error">{homeAutoChatMessagesErr}</div>
            )}
            {!homeAutoChatMessagesLoading && !homeAutoChatMessagesErr && (
              <>
                <ChatThread messages={homeAutoChatMessages} />
                {!homeAutoChatMessages.length && (
                  <div className="muted" style={{ marginTop: 10 }}>
                    История пуста. После запуска появятся сообщения.
                  </div>
                )}
              </>
            )}
          </>
        )}
      </section>
    )
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Авто. общение</h2>
        <div className="row-actions">
          <div className="pill">Активно: {activeCount}/{limit}</div>
          <button
            className="primary"
            onClick={() => startHomeAutoChat(selectedToStart)}
            disabled={!selectedToStart.length || available <= 0}
            type="button"
          >
            Запустить ({selectedToStart.length})
          </button>
          <button className="ghost" onClick={() => reload().catch(() => {})} type="button">
            Обновить
          </button>
        </div>
      </div>

      {(homeAutoChatDialogsLoading || homeAutoChatLoading) && <p className="muted">Загрузка...</p>}
      {!homeAutoChatLoading && (homeAutoChatErr || homeAutoChatDialogsErr) && (
        <div className="status error">{homeAutoChatErr || homeAutoChatDialogsErr}</div>
      )}
      {!homeAutoChatLoading && !homeAutoChatErr && !homeAutoChatUsernames.length && (
        <p className="muted">Список пуст.</p>
      )}

      {!homeAutoChatLoading && !homeAutoChatErr && homeAutoChatUsernames.length > 0 && (
        <div className="list">
          {homeAutoChatUsernames.map(item => {
            const peerId = item.tg_user_id
            const dialog = dialogByPeer.get(peerId)
            const status = dialog?.status || null
            const active = isActiveStatus(status)
            const pending = Boolean(dialog?.pending_incoming)
            const checked = homeAutoChatSelected.includes(peerId)

            const canSelect = (() => {
              if (!isValidPeerId(peerId)) return false
              if (checked) return true
              if (active) return true
              return selectedInactiveCount < available
            })()

            return (
              <div
                key={item.id || item.username}
                className={`row ${checked ? 'active' : ''}`}
              >
                <div
                  className="row-main"
                  role="button"
                  tabIndex={0}
                  onClick={() =>
                    setHomeAutoChatActive({
                      username: item.username,
                      display_name: item.display_name,
                      tg_user_id: peerId,
                      dialog_id: dialog?.id || null,
                      started_at: dialog?.started_at || null,
                      status: status,
                    })
                  }
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setHomeAutoChatActive({
                        username: item.username,
                        display_name: item.display_name,
                        tg_user_id: peerId,
                        dialog_id: dialog?.id || null,
                        started_at: dialog?.started_at || null,
                        status: status,
                      })
                    }
                  }}
                >
                  <strong>{item.username}</strong>
                  <span>{item.display_name || '—'}</span>
                  <span>User ID: {peerId || '—'}</span>
                  {pending && <span className="badge active">Генерирую...</span>}
                  {!pending && status && (
                    <span className={`badge ${statusBadgeClass(status)}`}>{statusLabel(status)}</span>
                  )}
                  {status === 'ERROR' && dialog?.last_error && <span>Ошибка: {dialog.last_error}</span>}
                </div>

                <label className="checkbox" onClick={e => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!canSelect}
                    onClick={e => e.stopPropagation()}
                    onChange={e => {
                      e.stopPropagation()
                      toggleSelected(peerId)
                    }}
                  />
                </label>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

