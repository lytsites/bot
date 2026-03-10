import React, { useMemo, useState } from 'react'
import { LifeBuoy, MessageCirclePlus, Send, List } from 'lucide-react'
import { mainGet, mainPost } from '../api'
import { formatDateTime } from '../time'

function fmtDate(value) {
  if (!value) return '—'
  try {
    return formatDateTime(value)
  } catch {
    return String(value)
  }
}

function statusMeta(status) {
  const s = String(status || '').toUpperCase()
  if (s === 'RESOLVED') return { label: 'Решено', cls: 'success' }
  if (s === 'ESCALATED') return { label: 'Передано', cls: 'warn' }
  return { label: 'Открыто', cls: 'info' }
}

function renderMiniChatText(text) {
  const src = String(text || '')
  const parts = []
  const re = /\*\*(.+?)\*\*/gs
  let last = 0
  let m
  let key = 0
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) {
      parts.push(<span key={`t-${key++}`}>{src.slice(last, m.index)}</span>)
    }
    parts.push(
      <strong key={`bi-${key++}`}>
        <em>{m[1]}</em>
      </strong>
    )
    last = re.lastIndex
  }
  if (last < src.length) {
    parts.push(<span key={`t-${key++}`}>{src.slice(last)}</span>)
  }
  return parts
}

export default function SupportWidget({ loggedIn, pushToast, formatError }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('list') // list | new | chat
  const [tickets, setTickets] = useState([])
  const [ticketsLoading, setTicketsLoading] = useState(false)
  const [ticketsErr, setTicketsErr] = useState('')
  const [subject, setSubject] = useState('')
  const [text, setText] = useState('')
  const [newSubmitting, setNewSubmitting] = useState(false)
  const [activeTicket, setActiveTicket] = useState(null)
  const [messages, setMessages] = useState([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatSubmitting, setChatSubmitting] = useState(false)

  const canChat = useMemo(() => {
    if (!activeTicket) return false
    return String(activeTicket.route || '') === 'SELF_SERVICE' && String(activeTicket.status || '') !== 'RESOLVED'
  }, [activeTicket])

  async function loadTickets() {
    setTicketsErr('')
    setTicketsLoading(true)
    try {
      const r = await mainGet('/support/tickets?limit=100&offset=0')
      setTickets(r.items || [])
    } catch (e) {
      setTicketsErr(formatError(e))
    } finally {
      setTicketsLoading(false)
    }
  }

  async function openPanel() {
    setOpen(true)
    setMode('list')
    await loadTickets()
  }

  async function openChat(ticket) {
    if (!ticket?.id) return
    setActiveTicket(ticket)
    setMode('chat')
    setMessagesLoading(true)
    try {
      const r = await mainGet(`/support/tickets/${ticket.id}/messages?limit=500`)
      setMessages(r.items || [])
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 5000)
      setMessages([])
    } finally {
      setMessagesLoading(false)
    }
  }

  async function createTicket() {
    const s = String(subject || '').trim()
    const m = String(text || '').trim()
    if (s.length < 3 || m.length < 3) {
      pushToast('error', 'Ошибка', 'Заполните тему и текст обращения', 4000)
      return
    }
    setNewSubmitting(true)
    try {
      const r = await mainPost('/support/tickets', { subject: s, message: m })
      setSubject('')
      setText('')
      await loadTickets()
      if (r?.action === 'self_answer' && r?.ticket?.id) {
        await openChat(r.ticket)
      } else {
        setMode('list')
        pushToast('success', 'Отправлено', 'Обращение передано в поддержку')
      }
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    } finally {
      setNewSubmitting(false)
    }
  }

  async function sendChat() {
    if (!activeTicket?.id || !canChat) return
    const m = String(chatInput || '').trim()
    if (!m) return
    setChatSubmitting(true)
    try {
      const r = await mainPost(`/support/tickets/${activeTicket.id}/chat`, { message: m })
      setChatInput('')
      if (r?.ticket) setActiveTicket(r.ticket)
      const rr = await mainGet(`/support/tickets/${activeTicket.id}/messages?limit=500`)
      setMessages(rr.items || [])
      await loadTickets()
      if (r?.action === 'escalated') {
        pushToast('success', 'Передано', 'Диалог передан в поддержку')
      }
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    } finally {
      setChatSubmitting(false)
    }
  }

  async function resolveTicket() {
    if (!activeTicket?.id) return
    try {
      const r = await mainPost(`/support/tickets/${activeTicket.id}/resolve`, {})
      if (r?.ticket) setActiveTicket(r.ticket)
      const rr = await mainGet(`/support/tickets/${activeTicket.id}/messages?limit=500`)
      setMessages(rr.items || [])
      await loadTickets()
      pushToast('success', 'Готово', 'Обращение помечено как решенное')
    } catch (e) {
      pushToast('error', 'Ошибка', formatError(e), 6000)
    }
  }

  if (!loggedIn) return null

  return (
    <>
      <button className="support-fab" onClick={() => (open ? setOpen(false) : openPanel())} aria-label="Поддержка">
        <LifeBuoy size={18} />
        <span>Поддержка</span>
      </button>

      {open && (
        <div className="support-panel">
          <div className="support-head">
            <h3>Техподдержка</h3>
            <div className="row-actions">
              {mode === 'chat' && (
                <button className="ghost" onClick={() => setMode('list')}>К списку</button>
              )}
              <button className="ghost icon-only" onClick={() => setOpen(false)} aria-label="Закрыть">×</button>
            </div>
          </div>

          {mode === 'list' && (
            <>
              <div className="actions support-list-actions">
                <button className="primary" onClick={() => setMode('new')}>
                  <MessageCirclePlus size={16} /> Новое обращение
                </button>
                <button className="ghost" onClick={loadTickets}>
                  <List size={16} /> Обновить
                </button>
              </div>
              {ticketsErr && <div className="status error">{ticketsErr}</div>}
              {ticketsLoading ? (
                <p className="muted">Загрузка...</p>
              ) : (
                <div className="support-tickets">
                  {(tickets || []).map(t => {
                    const st = statusMeta(t.status)
                    return (
                      <button className="support-ticket" key={t.id} onClick={() => openChat(t)}>
                        <div className="support-ticket-top">
                          <strong>{t.subject || 'Без темы'}</strong>
                          <span className={`tag ${st.cls}`}>{st.label}</span>
                        </div>
                        <div className="support-ticket-meta">
                          {formatDateTime(t.updated_at || t.created_at)}
                        </div>
                      </button>
                    )
                  })}
                  {!(tickets || []).length && <div className="muted">Обращений пока нет.</div>}
                </div>
              )}
            </>
          )}

          {mode === 'new' && (
            <div className="support-form">
              <div className="field">
                <label>Тема</label>
                <input
                  value={subject}
                  onChange={e => setSubject(e.target.value)}
                  placeholder="Коротко опишите проблему"
                />
              </div>
              <div className="field">
                <label>Сообщение</label>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  rows={6}
                  placeholder="Что произошло, как повторить, что ожидали увидеть"
                />
              </div>
              <div className="actions">
                <button className="primary" onClick={createTicket} disabled={newSubmitting}>
                  <Send size={16} /> Отправить
                </button>
                <button className="ghost" onClick={() => setMode('list')}>Назад</button>
              </div>
            </div>
          )}

          {mode === 'chat' && (
            <div className="support-chat-wrap">
              <div className="support-chat-subject">{activeTicket?.subject || 'Диалог'}</div>
              <div className="support-chat">
                {messagesLoading ? (
                  <p className="muted">Загрузка...</p>
                ) : (
                  (messages || []).map(m => (
                    <div className={`support-msg ${String(m.sender_type || '').toLowerCase()}`} key={m.id}>
                      <div className="support-msg-role">
                        {m.sender_type === 'USER' ? 'Вы' : (m.sender_type === 'ASSISTANT' ? 'Бот' : 'Система')}
                      </div>
                      <div>{renderMiniChatText(m.message)}</div>
                      <div className="support-msg-time">{formatDateTime(m.created_at)}</div>
                    </div>
                  ))
                )}
              </div>
              {canChat ? (
                <div className="support-chat-input">
                  <textarea
                    rows={3}
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    placeholder="Напишите сообщение..."
                  />
                  <button className="primary" onClick={sendChat} disabled={chatSubmitting}>
                    <Send size={16} /> Отправить
                  </button>
                  {String(activeTicket?.status || '').toUpperCase() !== 'RESOLVED' && (
                    <button className="ghost" onClick={resolveTicket}>Решено</button>
                  )}
                </div>
              ) : (
                <div className="muted">Этот диалог закрыт для чата. Обращение передано в поддержку.</div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  )
}
