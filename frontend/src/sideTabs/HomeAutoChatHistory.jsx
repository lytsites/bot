import React, { useMemo, useRef, useState } from 'react'
import { Trash2 } from 'lucide-react'
import ChatThread from '../components/ChatThread'
import { exportChatThreadAsZip } from '../utils/exportChatScreenshots'

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
  isSuperAdmin,
  deleteMonitoringAutoDialog,
}) {
  const items = useMemo(() => homeAutoChatDialogs || [], [homeAutoChatDialogs])
  const threadRef = useRef(null)
  const [exportingDialog, setExportingDialog] = useState(false)
  const [exportStatus, setExportStatus] = useState('')
  const [exportErr, setExportErr] = useState('')

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

  const handleExportDialog = async () => {
    if (!homeAutoChatHistoryActive?.dialog_id || !threadRef.current) return
    setExportingDialog(true)
    setExportErr('')
    setExportStatus('Подготавливаю архив скринов...')
    try {
      const title =
        homeAutoChatHistoryActive.peer_display_name ||
        homeAutoChatHistoryActive.peer_username ||
        String(homeAutoChatHistoryActive.peer_tg_user_id || 'dialog')
      const result = await exportChatThreadAsZip({
        threadEl: threadRef.current,
        title,
        dialogId: homeAutoChatHistoryActive.dialog_id,
      })
      setExportStatus(`Архив готов: ${result.pageCount} экранов`)
    } catch (e) {
      setExportErr(String(e?.message || e || 'EXPORT_FAILED'))
      setExportStatus('')
    } finally {
      setExportingDialog(false)
    }
  }

  if (homeAutoChatHistoryActive) {
    const title =
      homeAutoChatHistoryActive.peer_display_name ||
      homeAutoChatHistoryActive.peer_username ||
      String(homeAutoChatHistoryActive.peer_tg_user_id || 'Диалог')

    return (
      <section className="panel">
        <div className="panel-head">
          <button
            className="ghost"
            onClick={() => {
              setExportStatus('')
              setExportErr('')
              setHomeAutoChatHistoryActive(null)
            }}
            type="button"
          >
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
            <button
              className="ghost"
              type="button"
              disabled={exportingDialog || homeAutoChatHistoryMessagesLoading || !homeAutoChatHistoryMessages.length}
              onClick={handleExportDialog}
            >
              {exportingDialog ? 'Подготовка...' : 'Скачать скринами'}
            </button>
          </div>
        </div>

        {exportStatus && <div className="status success">{exportStatus}</div>}
        {exportErr && <div className="status error">{exportErr}</div>}

        {homeAutoChatHistoryMessagesLoading && <p className="muted">Загрузка...</p>}
        {!homeAutoChatHistoryMessagesLoading && homeAutoChatHistoryMessagesErr && (
          <div className="status error">{homeAutoChatHistoryMessagesErr}</div>
        )}
        {!homeAutoChatHistoryMessagesLoading && !homeAutoChatHistoryMessagesErr && (
          <>
            <ChatThread messages={homeAutoChatHistoryMessages} threadRef={threadRef} />
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
            <div key={d.id} className="row">
              <button
                className="row-main"
                type="button"
                onClick={() => {
                  setExportStatus('')
                  setExportErr('')
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
              {isSuperAdmin && (
                <button
                  className="ghost icon-only"
                  type="button"
                  aria-label="Удалить диалог из истории"
                  onClick={() => deleteMonitoringAutoDialog?.(d.id)}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
