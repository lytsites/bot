import React from 'react'

export default function HomeListening({
  activeAccountId,
  groupsLoading,
  groupsErr,
  sortedGroups,
  selectedGroupId,
  setSelectedGroupId,
  groupMatchCounts,
  setGroupListening,
  openMatchesModal,
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Прослушивание</h2>
        <span className="muted">
          {activeAccountId ? `Аккаунт #${activeAccountId}` : 'Нет активного аккаунта'}
        </span>
      </div>

      {groupsLoading && <p className="muted">Загрузка...</p>}
      {!groupsLoading && groupsErr && <div className="status error">{groupsErr}</div>}
      {!groupsLoading && !groupsErr && selectedGroupId === null && (
        <div className="list">
          {sortedGroups.map(item => (
            <button
              key={`group-${item.id}`}
              className={`row ${item.is_listening ? 'listening' : ''}`}
              onClick={() => setSelectedGroupId(item.id)}
            >
              <div>
                <strong>{item.title || 'Без названия'}</strong>
                <span>#{item.id}</span>
              </div>
              <span className={`badge ${item.is_listening ? 'ok' : 'muted'}`}>
                {item.is_listening ? 'LISTENING' : 'OFF'}
              </span>
            </button>
          ))}
          {!sortedGroups.length && <div className="muted">Список пуст.</div>}
        </div>
      )}

      {!groupsLoading && !groupsErr && selectedGroupId !== null && (
        <div className="split split-compact">
          <div className="list">
            {sortedGroups.map(item => (
              <button
                key={`group-${item.id}`}
                className={`row ${selectedGroupId === item.id ? 'active' : ''} ${item.is_listening ? 'listening' : ''}`}
                onClick={() => {
                  if (selectedGroupId === item.id) {
                    setSelectedGroupId(null)
                  } else {
                    setSelectedGroupId(item.id)
                  }
                }}
              >
                <div>
                  <strong>{item.title || 'Без названия'}</strong>
                  <span>#{item.id}</span>
                </div>
                <span className={`badge ${item.is_listening ? 'ok' : 'muted'}`}>
                  {item.is_listening ? 'LISTENING' : 'OFF'}
                </span>
              </button>
            ))}
          </div>

          <div className="details">
            <div className="subcard">
              <h3>Группа</h3>
              <p className="muted">
                {(sortedGroups.find(g => g.id === selectedGroupId)?.title) || 'Без названия'}
              </p>
              <div className="actions">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={!!sortedGroups.find(g => g.id === selectedGroupId)?.is_listening}
                    onChange={e => {
                      const group = sortedGroups.find(g => g.id === selectedGroupId)
                      setGroupListening(group, e.target.checked)
                    }}
                  />
                  <span>Слушать</span>
                </label>
              </div>
              {(() => {
                const group = sortedGroups.find(g => g.id === selectedGroupId)
                if (!group || !group.is_listening) return null
                const count = groupMatchCounts[selectedGroupId] || 0
                return (
                  <div className="match-row">
                    <span>Найдено: {count} сообщений</span>
                    <button
                      className="ghost"
                      disabled={!count}
                      onClick={() => openMatchesModal(group)}
                    >
                      Показать
                    </button>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
