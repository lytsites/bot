import React from 'react'
import { formatDateTime } from '../time'

export default function SettingsServiceControl({
  items,
  loading,
  err,
  reloading,
  restartingKey,
  clearingAuths,
  reload,
  requestRestart,
  clearAllAuths,
}) {
  const rows = Array.isArray(items) ? items : []

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Перезапуск сервисов</h2>
        <div className="row-actions">
          <button className="danger" onClick={clearAllAuths} disabled={loading || reloading || clearingAuths}>
            Очистить все авторизации
          </button>
          <button className="ghost" onClick={reload} disabled={loading || reloading || clearingAuths}>
            Обновить
          </button>
        </div>
      </div>

      <p className="muted">
        Каждый сервис можно перезапускать не чаще одного раза в 24 часа. Запрос ставится в очередь и выполняется
        root-helper на сервере.
      </p>
      <p className="muted">
        Очистка авторизаций принудительно завершает все текущие входы Telegram, включая активные QR-сессии.
      </p>

      {err && <div className="status error">{err}</div>}
      {loading && <div className="muted">Загрузка...</div>}

      {!loading && (
        <div className="list">
          {rows.map(item => {
            const last = item?.last_request || null
            const pending = last?.status === 'PENDING' || last?.status === 'PROCESSING'
            const disabled = pending || !item?.can_request || restartingKey === item?.service_key || clearingAuths
            return (
              <div className="row" key={item.service_key}>
                <div>
                  <div className="row-header">
                    <strong>{item.label}</strong>
                    <div className="badges">
                      <span className={`badge ${pending ? 'warning' : last?.status === 'FAILED' ? 'danger' : 'active'}`}>
                        {pending ? 'В очереди' : last?.status === 'FAILED' ? 'Ошибка' : 'Готов'}
                      </span>
                    </div>
                  </div>
                  <div className="row-details">
                    <span><strong>Unit:</strong> {item.system_unit}</span>
                    <span><strong>Последний запрос:</strong> {formatDateTime(last?.requested_at)}</span>
                    <span><strong>Кем:</strong> {last?.requested_by_login || '—'}</span>
                    <span><strong>Обработан:</strong> {formatDateTime(last?.processed_at)}</span>
                    <span><strong>Доступно снова:</strong> {formatDateTime(item?.cooldown_until)}</span>
                    {last?.error_message && <span><strong>Ошибка:</strong> {last.error_message}</span>}
                  </div>
                </div>
                <button
                  className="primary"
                  type="button"
                  disabled={disabled}
                  onClick={() => requestRestart?.(item.service_key)}
                >
                  Перезапустить
                </button>
              </div>
            )
          })}
          {!rows.length && <div className="muted">Сервисы не найдены.</div>}
        </div>
      )}
    </section>
  )
}
