import React from 'react'

export default function SettingsAccounts({
  accounts,
  selectedId,
  setSelectedId,
  activeAccountId,
  switchToSelectedAccount,
  deleteAccount,
  deleteAllAccounts,
  openAuthModal,
}) {
  return (
    <div className="grid">
      <section className="panel auth">
        <div className="panel-head">
          <h2>Telegram</h2>
        </div>
        <p className="muted">Добавляйте аккаунты Telegram через отдельное окно авторизации.</p>
        <div className="actions">
          <button className="primary" onClick={openAuthModal}>Добавить аккаунт TG</button>
        </div>
      </section>

      <section className="panel accounts">
        <div className="panel-head">
          <h2>Аккаунты</h2>
        </div>

        <div className="split">
          <div className="list">
            {accounts.map(acc => (
              <button
                key={acc.id}
                className={`row ${selectedId === acc.id ? 'active' : ''}`}
                onClick={() => setSelectedId(acc.id)}
              >
                <div>
                  <strong>{acc.display_name || 'Без имени'}</strong>
                  <span>{acc.phone || '—'}</span>
                </div>
                <span className={`badge ${acc.id === activeAccountId ? 'ok' : 'muted'}`}>
                  {acc.id === activeAccountId ? 'ACTIVE' : 'INACTIVE'}
                </span>
              </button>
            ))}
          </div>

          <div className="details">
            <div className="subcard">
              <h3>Действия</h3>
              <p className="muted">Активный аккаунт — только один. Сессии не удаляются при переключении.</p>
              <div className="actions">
                <button
                  className="primary"
                  onClick={switchToSelectedAccount}
                  disabled={!selectedId || selectedId === activeAccountId}
                >
                  Переключиться
                </button>
                <button className="danger" onClick={deleteAccount} disabled={!selectedId}>
                  Удалить аккаунт
                </button>
                <button className="danger" onClick={deleteAllAccounts} disabled={!accounts.length}>
                  Удалить все
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
