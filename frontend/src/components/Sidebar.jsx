import React from 'react'

export default function Sidebar({ title, items, activeId, onChange }) {
  return (
    <aside className="sidebar">
      {title && <div className="sidebar-title">{title}</div>}
      <div className="sidebar-mobile-select-wrap">
        <select
          className="sidebar-mobile-select"
          value={activeId || ''}
          onChange={e => onChange(e.target.value)}
        >
          {items.map(item => (
            <option key={`m-${item.id}`} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div className="sidebar-tabs">
        {items.map(item => (
          <button
            key={item.id}
            className={`sidebar-tab ${activeId === item.id ? 'active' : ''}`}
            onClick={() => onChange(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>
    </aside>
  )
}
