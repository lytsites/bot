import React from 'react'

export default function SettingsMain({ isDarkTheme, onToggleTheme }) {
  return (
    <section className="panel empty-state">
      <div className="panel-head">
        <h2>Основные</h2>
      </div>
      <div className="actions">
        <label className="toggle">
          <input
            type="checkbox"
            checked={isDarkTheme}
            onChange={e => onToggleTheme(e.target.checked)}
          />
          <span>Темная тема</span>
        </label>
      </div>
      <p className="muted">Смена темы применяется сразу.</p>
    </section>
  )
}
