import React from 'react'
import Sidebar from '../components/Sidebar'
import MonitoringListening from '../sideTabs/MonitoringListening'
import MonitoringAutoChat from '../sideTabs/MonitoringAutoChat'
import MonitoringAdminAccounts from '../sideTabs/MonitoringAdminAccounts'
import MonitoringAdminWorkers from '../sideTabs/MonitoringAdminWorkers'
import MonitoringAdminListeningHistory from '../sideTabs/MonitoringAdminListeningHistory'

export default function MonitoringTab({
  isAdmin,
  isSuperAdmin,
  activeSideTab,
  setActiveSideTab,
  listeningProps,
  adminAccountsProps,
  adminWorkersProps,
  adminListeningProps,
}) {
  const items = [
    { id: 'listening', label: 'Прослушивание' },
    { id: 'auto', label: 'Авто. общение' },
  ]

  if (isAdmin) {
    items.push(
      { id: 'admin-accounts', label: 'Аккаунты' },
      { id: 'admin-workers', label: 'История воркеров' },
      { id: 'admin-listening', label: 'История прослушивания' }
    )
  }

  return (
    <div className="workspace">
      <Sidebar title="Мониторинг" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'listening' && <MonitoringListening {...listeningProps} />}
        {activeSideTab === 'auto' && <MonitoringAutoChat />}
        {activeSideTab === 'admin-accounts' && isAdmin && (
          <MonitoringAdminAccounts {...adminAccountsProps} />
        )}
        {activeSideTab === 'admin-workers' && isAdmin && (
          <MonitoringAdminWorkers {...adminWorkersProps} />
        )}
        {activeSideTab === 'admin-listening' && isAdmin && (
          <MonitoringAdminListeningHistory {...adminListeningProps} />
        )}
      </div>
    </div>
  )
}
