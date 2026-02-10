import React, { useMemo } from 'react'

export default function HomeRequisitesHistory({
  showScopeToggle,
  scope,
  setScope,
  homeRequisites,
  homeRequisitesErr,
  homeRequisitesLoading,
  reload,
}) {
  const items = useMemo(() => homeRequisites || [], [homeRequisites])

  const requisiteTypeLabel = type => {
    switch (type) {
      case 'phone':
        return 'Телефон'
      case 'card':
        return 'Банковская карта'
      case 'iban':
        return 'IBAN'
      case 'unknown':
        return 'Неопознанный'
      default:
        return type || '—'
    }
  }

  const countryLabel = country => {
    switch (country) {
      case 'Казахстан':
        return 'Казахстан'
      case 'СНГ':
        return 'СНГ'
      case 'Зарубеж':
        return 'Зарубеж'
      default:
        return country || '—'
    }
  }

  const countryBadgeClass = country => {
    if (!country) return 'neutral'
    if (country === 'Казахстан') return 'active'
    if (country === 'СНГ') return 'warning'
    if (country === 'Зарубеж') return 'danger'
    return 'neutral'
  }

  const requisiteTypeBadgeClass = type => {
    if (!type) return 'neutral'
    if (type === 'phone') return 'info'
    if (type === 'card') return 'danger'
    if (type === 'iban') return 'success'
    return 'neutral'
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>История реквизитов</h2>
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

      {homeRequisitesLoading && <p className="muted">Загрузка...</p>}
      {!homeRequisitesLoading && homeRequisitesErr && (
        <div className="status error">{homeRequisitesErr}</div>
      )}
      {!homeRequisitesLoading && !homeRequisitesErr && !items.length && (
        <p className="muted">Реквизитов пока нет.</p>
      )}

      {!homeRequisitesLoading && !homeRequisitesErr && items.length > 0 && (
        <div className="list">
          {items.map(r => (
            <div key={r.id} className="row">
              <div>
                <div className="row-header">
                  <strong>{r.value}</strong>
                  <div className="badges">
                    <span className={`badge ${requisiteTypeBadgeClass(r.requisite_type)}`}>
                      {requisiteTypeLabel(r.requisite_type)}
                    </span>
                    <span className={`badge ${countryBadgeClass(r.country)}`}>
                      {countryLabel(r.country)}
                    </span>
                  </div>
                </div>
                <div className="row-details">
                  {r.sender_username && (
                    <span>
                      <strong>Юзернейм:</strong> {r.sender_username}
                    </span>
                  )}
                  {r.sender_phone && (
                    <span>
                      <strong>Телефон:</strong> {r.sender_phone}
                    </span>
                  )}
                  {r.chat_id && (
                    <span>
                      <strong>Группа:</strong> {r.chat_id}
                    </span>
                  )}
                  {r.dialog_id && (
                    <span>
                      <strong>Диалог авто-общения:</strong> {r.dialog_id}
                    </span>
                  )}
                  <span>
                    <strong>Найдено:</strong> {new Date(r.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
