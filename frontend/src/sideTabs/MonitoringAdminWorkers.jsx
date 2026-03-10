import React from 'react'
import { formatDateTimeRange } from '../time'

export default function MonitoringAdminWorkers({ adminWorkers, jobStatusMeta }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>История воркеров</h2>
      </div>
      <div className="table">
        <div className="table-head">
          <span>ID</span>
          <span>Аккаунт</span>
          <span>Статус</span>
          <span>Период</span>
          <span>Ошибка</span>
        </div>
        {adminWorkers.map(w => (
          <div className="table-row" key={`w-${w.id}`}>
            <span>#{w.id}</span>
            <span>{w.account_id}</span>
            <span><span className={`tag ${jobStatusMeta(w.status).cls}`}>{jobStatusMeta(w.status).label}</span></span>
            <span>{formatDateTimeRange(w.started_at, w.stopped_at)}</span>
            <span className="muted">{w.last_error || '—'}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
