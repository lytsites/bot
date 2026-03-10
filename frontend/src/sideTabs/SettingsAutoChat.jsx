import React from 'react'
import { formatDateTime } from '../time'

export default function SettingsAutoChat({
  autoChatInput,
  setAutoChatInput,
  autoChatUsernames,
  autoChatSelected,
  setAutoChatSelected,
  autoChatErr,
  autoChatLoading,
  saveAutoChatUsernames,
  deleteAutoChatSelected,
  deleteAutoChatAll,
  autoChatAiInstruction,
  setAutoChatAiInstruction,
  autoChatGreetingExamples,
  setAutoChatGreetingExamples,
  autoChatDelayEnabled,
  setAutoChatDelayEnabled,
  autoChatDelayMinSec,
  setAutoChatDelayMinSec,
  autoChatDelayMaxSec,
  setAutoChatDelayMaxSec,
  autoChatTypingEnabled,
  setAutoChatTypingEnabled,
  autoChatReadEnabled,
  setAutoChatReadEnabled,
  autoChatSettingsErr,
  autoChatSettingsLoading,
  saveAutoChatSettings,
}) {
  const selectedSet = new Set(autoChatSelected)
  const toggleSelected = username => {
    setAutoChatSelected(prev => {
      if (prev.includes(username)) {
        return prev.filter(item => item !== username)
      }
      return [...prev, username]
    })
  }

  const formatDate = value => {
    if (!value) return '—'
    return formatDateTime(value)
  }

  const statusLabel = item => {
    if (item.status === 'NOT_FOUND') return 'Не найден/недоступен'
    if (item.status === 'NOT_USER') return 'Не пользователь'
    return 'OK'
  }

  return (
    <section className="panel empty-state">
      <div className="panel-head">
        <h2>Авто. диалоги</h2>
      </div>
      <div className="field">
        <label>Юзернеймы Telegram (по одному на строку, без @)</label>
        <textarea
          rows={4}
          value={autoChatInput}
          onChange={e => setAutoChatInput(e.target.value)}
          placeholder="username1&#10;username2"
        />
      </div>
      <div className="actions">
        <button className="primary" onClick={saveAutoChatUsernames}>Сохранить</button>
        <button className="danger" onClick={deleteAutoChatSelected} disabled={!autoChatSelected.length}>
          Удалить выбранные
        </button>
        <button className="danger" onClick={deleteAutoChatAll} disabled={!autoChatUsernames.length}>
          Удалить все
        </button>
      </div>
      {autoChatErr && <div className="status error">{autoChatErr}</div>}

      <div className="divider" />
      {autoChatLoading && <p className="muted">Загрузка...</p>}
      {!autoChatLoading && !autoChatUsernames.length && (
        <p className="muted">Список пуст.</p>
      )}
      {!autoChatLoading && autoChatUsernames.length > 0 && (
        <div className="list">
          {autoChatUsernames.map(item => (
            <button
              key={item.id || item.username}
              className={`row ${selectedSet.has(item.username) ? 'active' : ''}`}
              onClick={() => toggleSelected(item.username)}
            >
              <div>
                <strong>{item.username}</strong>
                <span>Добавлен: {formatDate(item.created_at)}</span>
                <span>Имя: {item.display_name || '—'}</span>
                <span>User ID: {item.tg_user_id || '—'}</span>
                <span>Статус: {statusLabel(item)}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="divider" />
      <div className="panel-head">
        <h3>Роль и примеры для ИИ</h3>
        <button className="primary" onClick={saveAutoChatSettings} disabled={autoChatSettingsLoading}>
          Сохранить
        </button>
      </div>

      <div className="subcard">
        <h3>Имитации</h3>

        <div className="sim-options">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!autoChatDelayEnabled}
              onChange={e => setAutoChatDelayEnabled(e.target.checked)}
            />
            <span>Задержка перед ответом (случайно в диапазоне)</span>
          </label>

          {autoChatDelayEnabled && (
            <div className="sim-delay">
              <div className="field">
                <label>От (сек)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={autoChatDelayMinSec}
                  onChange={e => setAutoChatDelayMinSec(e.target.value)}
                />
              </div>
              <div className="field">
                <label>До (сек)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={autoChatDelayMaxSec}
                  onChange={e => setAutoChatDelayMaxSec(e.target.value)}
                />
              </div>
            </div>
          )}

          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!autoChatTypingEnabled}
              onChange={e => setAutoChatTypingEnabled(e.target.checked)}
            />
            <span>Имитация печатания (во время генерации и ожидания)</span>
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!autoChatReadEnabled}
              onChange={e => setAutoChatReadEnabled(e.target.checked)}
            />
            <span>Имитация прочтения (помечать входящее как прочитанное)</span>
          </label>
        </div>
      </div>

      <div className="field">
        <label>Инструкция для ИИ (роль, стиль, ограничения)</label>
        <textarea
          rows={6}
          value={autoChatAiInstruction}
          onChange={e => setAutoChatAiInstruction(e.target.value)}
          placeholder="Опиши роль: кто ты, как общаешься, чего не делаешь, как отвечаешь на вопросы."
        />
      </div>

      <div className="field">
        <label>Примеры приветствий и первых сообщений (каждый пример с новой строки)</label>
        <textarea
          rows={6}
          value={autoChatGreetingExamples}
          onChange={e => setAutoChatGreetingExamples(e.target.value)}
          placeholder="Пример 1: Привет! Увидел(а) твой пост...&#10;Пример 2: Добрый день! Хотел уточнить..."
        />
      </div>

      {autoChatSettingsErr && <div className="status error">{autoChatSettingsErr}</div>}
    </section>
  )
}
