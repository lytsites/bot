import React from 'react'

export default function MonitoringListening({
  listeningGroups,
  activeAccountId,
  groupWorkerId,
  jobs,
  jobTypeLabel,
  jobStatusMeta,
  cancelJob,
}) {
  return (
    <section className="panel jobs">
      <div className="panel-head">
        <h2>Воркеры</h2>
        <span className="muted">Polling 3s</span>
      </div>
      <div className="table">
        <div className="table-head">
          <span>ID</span>
          <span>Тип</span>
          <span>Статус</span>
          <span>Таргеты</span>
          <span>Действия</span>
        </div>
        {listeningGroups.length > 0 && (
          <div className="table-row">
            <span>
              {activeAccountId && groupWorkerId
                ? `${activeAccountId}_${groupWorkerId}_GROUPS`
                : '—'}
            </span>
            <span>
              <span className="tag info">{jobTypeLabel('GROUP_LISTENER')}</span>
            </span>
            <span>
              <span className="tag success">Работает</span>
            </span>
            <span>
              {listeningGroups.map(item => item.title || `#${item.id}`).join(', ')}
            </span>
            <span className="row-actions">—</span>
          </div>
        )}
        {jobs.map(job => (
          <div className="table-row" key={job.id}>
            <span>#{job.id}</span>
            <span>
              <span className="tag info">{jobTypeLabel(job.type)}</span>
            </span>
            <span>
              <span className={`tag ${jobStatusMeta(job.status).cls}`}>
                {jobStatusMeta(job.status).label}
              </span>
            </span>
            <span>
              {job.progress !== null && job.progress !== undefined
                ? `${job.progress || 0}%`
                : '—'}
            </span>
            <span className="row-actions">
              <button
                className="danger"
                onClick={() => cancelJob(job.id)}
                disabled={job.status !== 'RUNNING' && job.status !== 'PENDING'}
              >
                Отменить
              </button>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
