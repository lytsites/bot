import React, { useEffect, useState } from 'react'

export default function SettingsListening({
  keywords,
  settingsActive,
  handleKeywordsChange,
  handleActiveToggle,
  saveListeningSettings,
  settingsErr,
}) {
  const [draftKeywords, setDraftKeywords] = useState(keywords || '')
  const [draftActive, setDraftActive] = useState(Boolean(settingsActive))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraftKeywords(keywords || '')
  }, [keywords])

  useEffect(() => {
    setDraftActive(Boolean(settingsActive))
  }, [settingsActive])

  const save = async () => {
    setSaving(true)
    try {
      if (typeof saveListeningSettings === 'function') {
        await saveListeningSettings(draftKeywords, Boolean(draftActive))
        return
      }
      if (draftKeywords !== (keywords || '')) {
        await handleKeywordsChange(draftKeywords)
      }
      if (Boolean(draftActive) !== Boolean(settingsActive)) {
        await handleActiveToggle(Boolean(draftActive))
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="panel settings">
      <div className="panel-head">
        <h2>Чтение групп</h2>
      </div>
      <div className="field">
        <label>Ключевые слова (через запятую)</label>
        <input
          value={draftKeywords}
          onChange={e => setDraftKeywords(e.target.value)}
          placeholder="пример: bitcoin, scam, airdrop"
        />
      </div>
      <div className="actions">
        <label className="toggle">
          <input
            type="checkbox"
            checked={draftActive}
            onChange={e => setDraftActive(e.target.checked)}
          />
          <span>Активно</span>
        </label>
        <button
          className="primary"
          type="button"
          onClick={() => save().catch(() => {})}
          disabled={saving}
        >
          Сохранить
        </button>
      </div>
      {settingsErr && <div className="status error">{settingsErr}</div>}
    </section>
  )
}
