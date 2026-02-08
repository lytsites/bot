import React from 'react'

export default function SettingsListening({
  keywords,
  settingsActive,
  handleKeywordsChange,
  handleActiveToggle,
  settingsErr,
}) {
  return (
    <section className="panel settings">
      <div className="panel-head">
        <h2>Прослушивание</h2>
      </div>
      <div className="field">
        <label>Ключевые слова (через запятую)</label>
        <input
          value={keywords}
          onChange={e => handleKeywordsChange(e.target.value)}
          placeholder="пример: bitcoin, scam, airdrop"
        />
      </div>
      <div className="actions">
        <label className="toggle">
          <input
            type="checkbox"
            checked={settingsActive}
            onChange={e => handleActiveToggle(e.target.checked)}
          />
          <span>Активно</span>
        </label>
      </div>
      {settingsErr && <div className="status error">{settingsErr}</div>}
    </section>
  )
}
